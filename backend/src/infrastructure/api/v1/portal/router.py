from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.application.dtos.catalog_dto import ProductPortalItemDTO
from src.application.dtos.order_dto import (
    OrderCreateDTO,
    OrderItemResponseDTO,
    OrderResponseDTO,
)
from src.application.use_cases.portal.portal_catalog import PortalCatalogUseCase
from src.domain.exceptions import (
    BusinessRuleViolationException,
    EntityNotFoundException,
)
from src.domain.models import DeliveryType, OrderStatus
from src.infrastructure.db.models import OrderItemORM, OrderORM
from src.infrastructure.db.session import get_db_session
from src.infrastructure.security.dependencies import require_customer
from src.infrastructure.security.jwt import TokenData

router = APIRouter(
    prefix="/portal",
    tags=["Portal B2B Clientes"],
    dependencies=[Depends(require_customer)],
)


@router.get("/catalog", response_model=list[ProductPortalItemDTO])
async def get_authorized_catalog(
    category: str | None = Query(None, description="Filtrar por categoría"),
    search: str | None = Query(None, description="Buscador por nombre"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    customer: TokenData = Depends(require_customer),
    session: AsyncSession = Depends(get_db_session),
) -> list[ProductPortalItemDTO]:
    assert customer.commercial_list_id is not None
    use_case = PortalCatalogUseCase(session)
    return await use_case.list_catalog(
        commercial_list_id=customer.commercial_list_id,
        category=category,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/orders",
    response_model=OrderResponseDTO,
    status_code=status.HTTP_201_CREATED,
)
async def create_order(
    data: OrderCreateDTO,
    customer: TokenData = Depends(require_customer),
    session: AsyncSession = Depends(get_db_session),
) -> OrderResponseDTO:
    assert customer.commercial_list_id is not None
    use_case = PortalCatalogUseCase(session)
    try:
        return await use_case.create_order(
            customer_id=customer.user_id,
            commercial_list_id=customer.commercial_list_id,
            data=data,
        )
    except (EntityNotFoundException, BusinessRuleViolationException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("/orders", response_model=list[OrderResponseDTO])
async def list_orders(
    customer: TokenData = Depends(require_customer),
    session: AsyncSession = Depends(get_db_session),
) -> list[OrderResponseDTO]:
    stmt = (
        select(OrderORM)
        .options(selectinload(OrderORM.items).selectinload(OrderItemORM.product))
        .where(OrderORM.customer_id == customer.user_id)
        .order_by(OrderORM.created_at.desc())
    )
    result = await session.execute(stmt)
    orders = result.scalars().all()

    return [
        OrderResponseDTO(
            id=o.id,
            customer_id=o.customer_id,
            order_status=OrderStatus(o.order_status),
            delivery_type=DeliveryType(o.delivery_type),
            delivery_cost=o.delivery_cost,
            total_amount=o.total_amount,
            delivery_address=o.delivery_address,
            delivery_notes=o.delivery_notes,
            created_at=o.created_at,
            items=[
                OrderItemResponseDTO(
                    id=it.id,
                    product_id=it.product_id,
                    product_name=it.product.name if it.product else "",
                    quantity=it.quantity,
                    unit_price=it.unit_price,
                    discount_percent=it.discount_percent,
                    subtotal=it.subtotal,
                )
                for it in o.items
            ],
        )
        for o in orders
    ]
