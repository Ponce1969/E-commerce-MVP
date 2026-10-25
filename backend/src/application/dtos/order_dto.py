from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from src.domain.models import DeliveryType, OrderStatus


class OrderItemCreateDTO(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0)


class OrderCreateDTO(BaseModel):
    delivery_type: DeliveryType
    delivery_address: str | None = None
    delivery_notes: str | None = None
    items: list[OrderItemCreateDTO] = Field(..., min_length=1)


class OrderItemResponseDTO(BaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int
    unit_price: Decimal
    discount_percent: Decimal
    subtotal: Decimal


class OrderResponseDTO(BaseModel):
    id: int
    customer_id: int
    order_status: OrderStatus
    delivery_type: DeliveryType
    delivery_cost: Decimal
    total_amount: Decimal
    delivery_address: str | None = None
    delivery_notes: str | None = None
    created_at: datetime
    items: list[OrderItemResponseDTO]
