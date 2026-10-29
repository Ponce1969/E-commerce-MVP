import logging
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.application.dtos.order_dto import (
    BankTransferInfoDTO,
    CheckoutResponseDTO,
    OrderCheckoutCreateDTO,
)
from src.config import settings
from src.domain.models import DeliveryType, OrderStatus, PaymentMethod, PaymentStatus
from src.domain.services.pricing_service import PricingService
from src.infrastructure.db.models import (
    CommercialListORM,
    CustomerORM,
    OrderItemORM,
    OrderORM,
    ProductORM,
)
from src.infrastructure.db.session import get_db_session
from src.infrastructure.logistics.marco_postal_client import MarcoPostalClient
from src.infrastructure.payments.mercadopago_client import MercadoPagoClient
from src.infrastructure.security.dependencies import get_optional_customer
from src.infrastructure.security.jwt import TokenData

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Checkout y Pagos"])


@router.post(
    "/checkout/create-order",
    response_model=CheckoutResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar orden de compra y procesar pago (Checkout Pro o BROU)",
)
async def create_checkout_order(
    data: OrderCheckoutCreateDTO,
    opt_customer: TokenData | None = Depends(get_optional_customer),
    session: AsyncSession = Depends(get_db_session),
) -> CheckoutResponseDTO:
    """Registra la orden transaccional en PostgreSQL con payment_status = 'PENDING'.

    - Si payment_method es BROU_TRANSFER: retorna los datos bancarios para depósito.
    - Si payment_method es MERCADO_PAGO: invoca crear_preferencia y devuelve el init_point.
    """
    # 1. Resolver cliente y lista comercial asociada
    customer_id: int | None = opt_customer.user_id if opt_customer else None
    commercial_list_id: int | None = opt_customer.commercial_list_id if opt_customer else None

    if not customer_id or not commercial_list_id:
        # Si no viene autenticado por token, buscar por documento en shipping_address
        if data.shipping_address and data.shipping_address.document_number:
            cust_stmt = select(CustomerORM).where(
                CustomerORM.document_number == data.shipping_address.document_number
            )
            cust_res = await session.execute(cust_stmt)
            existing_cust = cust_res.scalar_one_or_none()
            if existing_cust:
                customer_id = existing_cust.id
                commercial_list_id = existing_cust.commercial_list_id

        # Fallback si aún no está resuelto: tomar cliente activo o crear uno
        if not customer_id or not commercial_list_id:
            first_cust_stmt = select(CustomerORM).limit(1)
            first_res = await session.execute(first_cust_stmt)
            fallback_cust = first_res.scalar_one_or_none()
            if fallback_cust:
                customer_id = fallback_cust.id
                commercial_list_id = fallback_cust.commercial_list_id
            else:
                # Obtener lista comercial activa
                cl_stmt = (
                    select(CommercialListORM).where(CommercialListORM.is_active.is_(True)).limit(1)
                )
                cl_res = await session.execute(cl_stmt)
                cl = cl_res.scalar_one_or_none()
                if not cl:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="No existe ninguna lista comercial activa en el sistema.",
                    )
                # Crear cliente genérico para checkout
                new_cust = CustomerORM(
                    document_type="CI",
                    document_number=(
                        data.shipping_address.document_number
                        if data.shipping_address
                        else "00000000"
                    ),
                    business_name=(
                        data.shipping_address.recipient_name
                        if data.shipping_address
                        else "Consumidor Final"
                    ),
                    contact_name=(
                        data.shipping_address.recipient_name
                        if data.shipping_address
                        else "Consumidor Final"
                    ),
                    phone_whatsapp=(
                        data.shipping_address.phone if data.shipping_address else "099000000"
                    ),
                    email=(
                        f"checkout_{data.shipping_address.phone if data.shipping_address else 'guest'}@2rodriguez.uy"
                    ),
                    password_hash="checkout_guest",
                    commercial_list_id=cl.id,
                    crm_status="ACTIVO",
                    is_active=True,
                )
                session.add(new_cust)
                await session.flush()
                customer_id = new_cust.id
                commercial_list_id = cl.id

    # 2. Calcular costo de flete y validar dirección si es cadetería Marco Postal
    if data.delivery_type == DeliveryType.PICKUP_PASO_MOLINO:
        delivery_cost = Decimal("0.00")
    elif data.delivery_type == DeliveryType.CADETERIA_MARCO_POSTAL:
        delivery_cost = Decimal("250.00")
        if not data.shipping_address:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debe incluir la información de envío (shipping_address) para despachos con Marco Postal.",
            )
        if not data.shipping_address.street or not data.shipping_address.street_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La calle y el número de puerta son obligatorios para el envío postal.",
            )
    else:
        delivery_cost = Decimal("0.00")

    # 3. Resolver productos, validar stock y calcular totales
    product_ids = [item.product_id for item in data.items]
    prod_stmt = (
        select(ProductORM)
        .options(selectinload(ProductORM.prices))
        .where(
            ProductORM.id.in_(product_ids),
            ProductORM.is_published == True,  # noqa: E712
            ProductORM.is_active == True,  # noqa: E712
        )
        .with_for_update()
    )
    prod_res = await session.execute(prod_stmt)
    products_map = {p.id: p for p in prod_res.scalars().all()}

    order_items_orm: list[OrderItemORM] = []
    subtotal_sum = Decimal("0.00")

    for item_in in data.items:
        product = products_map.get(item_in.product_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Producto #{item_in.product_id} no encontrado o inactivo en el catálogo.",
            )

        if product.current_stock < item_in.quantity and not product.allow_backorder:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stock insuficiente para '{product.name}'. Disponible: {product.current_stock}, solicitado: {item_in.quantity}.",
            )
        product.current_stock -= item_in.quantity

        price_row = next(
            (pr for pr in product.prices if pr.commercial_list_id == commercial_list_id),
            None,
        )
        if not price_row or price_row.price_iva_inc is None:
            # Fallback al primer precio disponible del producto si no tiene el de la lista
            price_row = next((pr for pr in product.prices if pr.price_iva_inc is not None), None)

        if not price_row or price_row.price_iva_inc is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El producto '{product.name}' no tiene precio asignado.",
            )

        unit_price = price_row.price_iva_inc
        line_subtotal = PricingService.calculate_item_subtotal(
            unit_price=unit_price,
            quantity=item_in.quantity,
            discount_percentage=Decimal("0.0000"),
        )
        subtotal_sum += line_subtotal

        order_items_orm.append(
            OrderItemORM(
                product_id=product.id,
                quantity=item_in.quantity,
                unit_price=unit_price,
                discount_percent=Decimal("0.0000"),
                subtotal=line_subtotal,
            )
        )

    grand_total = subtotal_sum + delivery_cost

    # 4. Instanciar la Orden en PostgreSQL
    order_orm = OrderORM(
        customer_id=customer_id,
        order_status=OrderStatus.PENDIENTE.value,
        delivery_type=data.delivery_type.value,
        delivery_cost=delivery_cost,
        delivery_notes=data.delivery_notes,
        total_amount=grand_total,
        payment_method=data.payment_method.value,
        payment_status=PaymentStatus.PENDING.value,
        # Campos estructurados de envío para Marco Postal
        shipping_recipient_name=(
            data.shipping_address.recipient_name if data.shipping_address else None
        ),
        shipping_document_number=(
            data.shipping_address.document_number if data.shipping_address else None
        ),
        shipping_street=data.shipping_address.street if data.shipping_address else None,
        shipping_street_number=(
            data.shipping_address.street_number if data.shipping_address else None
        ),
        shipping_apartment=(data.shipping_address.apartment if data.shipping_address else None),
        shipping_city=data.shipping_address.city if data.shipping_address else None,
        shipping_state=data.shipping_address.state if data.shipping_address else None,
        shipping_postal_code=(data.shipping_address.postal_code if data.shipping_address else None),
        shipping_phone=data.shipping_address.phone if data.shipping_address else None,
        shipping_notes=data.shipping_address.notes if data.shipping_address else None,
        items=order_items_orm,
    )

    session.add(order_orm)
    await session.flush()

    # 5. Bifurcación por método de pago
    if data.payment_method == PaymentMethod.BROU_TRANSFER:
        await session.commit()
        bank_info = BankTransferInfoDTO(
            banco=settings.BROU_BANCO,
            tipo_cuenta=settings.BROU_TIPO_CUENTA,
            titular=settings.BROU_TITULAR,
            numero_cuenta=settings.BROU_NUMERO_CUENTA,
            descuento_percent=settings.BROU_DESCUENTO_PERCENT,
            monto_total=order_orm.total_amount,
            referencia=f"2R-{order_orm.id}",
        )
        return CheckoutResponseDTO(
            order_id=order_orm.id,
            payment_method=PaymentMethod.BROU_TRANSFER,
            payment_status=PaymentStatus.PENDING,
            total_amount=order_orm.total_amount,
            bank_transfer_info=bank_info,
            message="Orden creada con éxito. Por favor efectúa el depósito en BROU con la referencia indicada.",
        )

    if data.payment_method == PaymentMethod.MERCADO_PAGO:
        mp_client = MercadoPagoClient()
        try:
            init_point = await mp_client.crear_preferencia(order=order_orm, items=order_orm.items)
        except Exception as err:
            logger.error("Error al crear preferencia en Mercado Pago: %s", err)
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Error al conectar con la pasarela de pagos de Mercado Pago.",
            ) from err

        await session.commit()
        return CheckoutResponseDTO(
            order_id=order_orm.id,
            payment_method=PaymentMethod.MERCADO_PAGO,
            payment_status=PaymentStatus.PENDING,
            total_amount=order_orm.total_amount,
            init_point=init_point,
            preference_id=order_orm.preference_id,
            message="Preferencia de Mercado Pago creada con éxito. Redirigir al init_point.",
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Método de pago '{data.payment_method}' no soportado.",
    )


@router.post(
    "/payments/webhook",
    status_code=status.HTTP_200_OK,
    summary="Webhook idempotente para notificaciones de Mercado Pago",
)
async def mercadopago_webhook(
    request: Request,
    topic: str | None = Query(None, description="Tema de IPN (ej: payment)"),
    id: str | None = Query(None, description="ID de recurso para IPN"),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Recibe la notificación de Mercado Pago de forma idempotente (200 OK).

    - Consulta el estado del pago con la API de MP (GET /v1/payments/{id}).
    - Si el estado es 'approved':
        - Actualiza payment_status = 'PAID' en la orden vinculada mediante external_reference.
        - Dispara automáticamente la creación de la guía en Marco Postal llamando a crear_guia.
    """
    payment_id: str | None = id
    body: dict[str, Any] = {}

    try:
        body = await request.json()
    except Exception:
        body = {}

    # Extraer ID de pago desde webhook JSON moderno o IPN clásico
    if not payment_id and isinstance(body, dict):
        data_block = body.get("data")
        if isinstance(data_block, dict) and data_block.get("id"):
            payment_id = str(data_block.get("id"))
        elif body.get("id"):
            payment_id = str(body.get("id"))

    if not payment_id:
        logger.info(
            "Webhook Mercado Pago recibido sin payment_id (topic=%s, ping o evento no-pago).",
            topic,
        )
        return {"status": "ok", "message": "Ignored: no payment id found"}

    logger.info("Procesando notificación de pago MP: topic=%s, payment_id=%s", topic, payment_id)

    # Consultar estado del pago en la API oficial de Mercado Pago
    mp_client = MercadoPagoClient()
    try:
        payment_data = await mp_client.obtener_pago(payment_id)
    except Exception as exc:
        logger.error("No se pudo obtener el pago %s de Mercado Pago: %s", payment_id, exc)
        return {"status": "ok", "message": "Error contacting MP API, handled idempotently"}

    mp_status = payment_data.get("status")
    external_ref = payment_data.get("external_reference")

    logger.info(
        "Detalle de pago MP %s: status=%s, external_reference=%s",
        payment_id,
        mp_status,
        external_ref,
    )

    if not external_ref:
        return {"status": "ok", "message": "Ignored: no external_reference associated"}

    try:
        order_id = int(str(external_ref).replace("2R-", ""))
    except ValueError:
        logger.warning("external_reference '%s' no es un ID numérico válido", external_ref)
        return {"status": "ok", "message": "Invalid order_id format in external_reference"}

    # Bloqueo transaccional de la orden
    stmt = (
        select(OrderORM)
        .options(
            selectinload(OrderORM.customer),
            selectinload(OrderORM.items).selectinload(OrderItemORM.product),
        )
        .where(OrderORM.id == order_id)
        .with_for_update()
    )
    result = await session.execute(stmt)
    order = result.scalar_one_or_none()

    if not order:
        logger.warning("Orden ID %s referenciada en pago MP no existe", order_id)
        return {"status": "ok", "message": f"Order {order_id} not found"}

    # Idempotencia: si ya está pagada, no repetir acciones colaterales
    if order.payment_status == PaymentStatus.PAID.value:
        logger.info("Orden ID %s ya registrada previamente como PAID.", order.id)
        return {"status": "ok", "message": "Order already marked as PAID"}

    if mp_status == "approved":
        order.payment_status = PaymentStatus.PAID.value
        order.payment_id = str(payment_id)
        order.order_status = OrderStatus.CONFIRMADO.value
        logger.info("Orden ID %s actualizada exitosamente a PAID y CONFIRMADO.", order.id)

        # Disparar automáticamente creación de guía en Marco Postal si aplica cadetería o datos de entrega
        if (
            order.delivery_type == DeliveryType.CADETERIA_MARCO_POSTAL.value
            or order.shipping_street
        ):
            try:
                marco_postal = MarcoPostalClient()
                await marco_postal.crear_guia(order=order, customer=order.customer)
                logger.info(
                    "Guía Marco Postal generada para orden %s: remito=%s, tracking=%s",
                    order.id,
                    order.remito_postal,
                    order.tracking_url,
                )
            except Exception as err:
                logger.error(
                    "Fallo al emitir guía automática en Marco Postal para orden %s: %s",
                    order.id,
                    err,
                )

        await session.commit()
        return {
            "status": "ok",
            "order_id": order.id,
            "payment_status": order.payment_status,
            "remito_postal": order.remito_postal,
        }

    if mp_status in ("rejected", "cancelled"):
        order.payment_status = PaymentStatus.REJECTED.value
        await session.commit()
        return {"status": "ok", "order_id": order.id, "payment_status": "REJECTED"}

    return {"status": "ok", "order_id": order.id, "payment_status": order.payment_status}
