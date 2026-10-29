from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from src.domain.models import DeliveryType, OrderStatus, PaymentMethod, PaymentStatus


class ShippingAddressDTO(BaseModel):
    recipient_name: str = Field(..., description="Nombre y apellido del destinatario")
    document_number: str = Field(..., description="CI o RUT")
    street: str = Field(..., description="Nombre de la calle")
    street_number: str = Field(..., description="Número de puerta / altura")
    apartment: str | None = Field(None, description="Piso / depto / número de casa")
    city: str = Field(..., description="Localidad / Barrio")
    state: str = Field(..., description="Departamento")
    postal_code: str = Field(..., description="Código postal")
    phone: str = Field(..., description="Celular de contacto")
    notes: str | None = Field(None, description="Aclaraciones u observaciones para el fletero")


class OrderItemCreateDTO(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0)


class OrderCreateDTO(BaseModel):
    delivery_type: DeliveryType
    delivery_address: str | None = None
    delivery_notes: str | None = None
    items: list[OrderItemCreateDTO] = Field(..., min_length=1)


class OrderCheckoutCreateDTO(BaseModel):
    payment_method: PaymentMethod
    delivery_type: DeliveryType
    shipping_address: ShippingAddressDTO | None = None
    delivery_notes: str | None = None
    items: list[OrderItemCreateDTO] = Field(..., min_length=1)


class BankTransferInfoDTO(BaseModel):
    banco: str
    tipo_cuenta: str
    titular: str
    numero_cuenta: str
    descuento_percent: float
    monto_total: Decimal
    referencia: str


class CheckoutResponseDTO(BaseModel):
    order_id: int
    payment_method: PaymentMethod
    payment_status: PaymentStatus
    total_amount: Decimal
    init_point: str | None = None
    preference_id: str | None = None
    bank_transfer_info: BankTransferInfoDTO | None = None
    message: str


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
    payment_method: PaymentMethod | None = None
    payment_status: PaymentStatus | None = None
    payment_id: str | None = None
    preference_id: str | None = None
    remito_postal: str | None = None
    tracking_url: str | None = None
    delivery_address: str | None = None
    delivery_notes: str | None = None
    created_at: datetime
    items: list[OrderItemResponseDTO]
