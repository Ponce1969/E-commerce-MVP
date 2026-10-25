from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.application.dtos.catalog_dto import ProductPortalItemDTO
from src.application.dtos.order_dto import (
    OrderCreateDTO,
    OrderItemResponseDTO,
    OrderResponseDTO,
)
from src.domain.exceptions import (
    BusinessRuleViolationException,
    EntityNotFoundException,
)
from src.domain.models import DeliveryType, OrderStatus
from src.domain.services.pricing_service import PricingService
from src.infrastructure.db.models import OrderItemORM, OrderORM, ProductORM, ProductPriceORM


class PortalCatalogUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_catalog(
        self,
        commercial_list_id: int,
        category: str | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ProductPortalItemDTO]:
        """
        UC-CLI-02: Consulta de productos publicados con precios filtrados
        exclusivamente por la lista comercial asociada al cliente.
        """
        query = (
            select(ProductORM, ProductPriceORM)
            .join(ProductPriceORM, ProductORM.id == ProductPriceORM.product_id)
            .where(
                ProductORM.is_published == True,  # noqa: E712
                ProductORM.is_active == True,  # noqa: E712
                ProductPriceORM.commercial_list_id == commercial_list_id,
                ProductPriceORM.price_iva_inc.isnot(None),
            )
        )

        if category:
            query = query.where(ProductORM.category == category)
        if search:
            query = query.where(ProductORM.name.ilike(f"%{search}%"))

        query = query.order_by(ProductORM.name.asc()).limit(limit).offset(offset)
        result = await self.session.execute(query)
        rows = result.all()

        return [
            ProductPortalItemDTO(
                id=prod.id,
                name=prod.name,
                presentation=prod.presentation,
                category=prod.category,
                price_iva_inc=price.price_iva_inc,  # type: ignore[arg-type]
                iva_rate=prod.iva_rate,
                image_url=prod.image_url,
                tech_sheet_url=prod.tech_sheet_url,
            )
            for prod, price in rows
        ]

    async def create_order(
        self,
        customer_id: int,
        commercial_list_id: int,
        data: OrderCreateDTO,
    ) -> OrderResponseDTO:
        """
        UC-CLI-03: Registro de orden de compra con selector de método de entrega.
        """
        # Determine delivery freight cost
        if data.delivery_type == DeliveryType.PICKUP_PASO_MOLINO:
            delivery_cost = Decimal("0.00")
        elif data.delivery_type == DeliveryType.CADETERIA_MARCO_POSTAL:
            delivery_cost = Decimal("250.00")
            if not data.delivery_address or not data.delivery_address.strip():
                raise BusinessRuleViolationException(
                    "Debe indicar una dirección de entrega para envíos por cadetería."
                )
        else:
            delivery_cost = Decimal("0.00")

        # Resolve items and verify pricing
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
        prod_res = await self.session.execute(prod_stmt)
        products_map = {p.id: p for p in prod_res.scalars().all()}

        order_items_orm: list[OrderItemORM] = []
        items_response: list[OrderItemResponseDTO] = []
        subtotal_sum = Decimal("0.00")

        for item_in in data.items:
            product = products_map.get(item_in.product_id)
            if not product:
                raise EntityNotFoundException(
                    f"Producto con ID {item_in.product_id} no disponible en catálogo autorizado."
                )

            if product.current_stock < item_in.quantity and not product.allow_backorder:
                raise BusinessRuleViolationException(
                    f"Stock insuficiente para '{product.name}'. Disponible: {product.current_stock}, solicitado: {item_in.quantity}."
                )
            product.current_stock -= item_in.quantity

            price_row = next(
                (pr for pr in product.prices if pr.commercial_list_id == commercial_list_id),
                None,
            )

            if not price_row or price_row.price_iva_inc is None:
                raise BusinessRuleViolationException(
                    f"El producto '{product.name}' no tiene precio asignado para tu lista comercial."
                )

            unit_price = price_row.price_iva_inc
            line_subtotal = PricingService.calculate_item_subtotal(
                unit_price=unit_price,
                quantity=item_in.quantity,
                discount_percentage=Decimal("0.0000"),
            )
            subtotal_sum += line_subtotal

            item_orm = OrderItemORM(
                product_id=product.id,
                quantity=item_in.quantity,
                unit_price=unit_price,
                discount_percent=Decimal("0.0000"),
                subtotal=line_subtotal,
            )
            order_items_orm.append(item_orm)

        grand_total = subtotal_sum + delivery_cost

        order_orm = OrderORM(
            customer_id=customer_id,
            order_status=OrderStatus.PENDIENTE.value,
            delivery_type=data.delivery_type.value,
            delivery_cost=delivery_cost,
            delivery_address=data.delivery_address,
            delivery_notes=data.delivery_notes,
            total_amount=grand_total,
            items=order_items_orm,
        )
        self.session.add(order_orm)
        await self.session.commit()

        for it in order_items_orm:
            prod_obj = products_map[it.product_id]
            items_response.append(
                OrderItemResponseDTO(
                    id=it.id or 0,
                    product_id=it.product_id,
                    product_name=prod_obj.name,
                    quantity=it.quantity,
                    unit_price=it.unit_price,
                    discount_percent=it.discount_percent,
                    subtotal=it.subtotal,
                )
            )

        return OrderResponseDTO(
            id=order_orm.id,
            customer_id=order_orm.customer_id,
            order_status=OrderStatus(order_orm.order_status),
            delivery_type=DeliveryType(order_orm.delivery_type),
            delivery_cost=order_orm.delivery_cost,
            total_amount=order_orm.total_amount,
            delivery_address=order_orm.delivery_address,
            delivery_notes=order_orm.delivery_notes,
            created_at=order_orm.created_at,
            items=items_response,
        )
