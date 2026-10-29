from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum


class DeliveryType(StrEnum):
    PICKUP_PASO_MOLINO = "PICKUP_PASO_MOLINO"
    CADETERIA_MARCO_POSTAL = "CADETERIA_MARCO_POSTAL"


class OrderStatus(StrEnum):
    PENDIENTE = "PENDIENTE"
    CONFIRMADO = "CONFIRMADO"
    EN_PREPARACION = "EN_PREPARACION"
    DESPACHADO = "DESPACHADO"
    ENTREGADO = "ENTREGADO"
    CANCELADO = "CANCELADO"


class PaymentMethod(StrEnum):
    BROU_TRANSFER = "BROU_TRANSFER"
    MERCADO_PAGO = "MERCADO_PAGO"


class PaymentStatus(StrEnum):
    PENDING = "PENDING"
    PAID = "PAID"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class DocumentType(StrEnum):
    RUT = "RUT"
    CI = "CI"


class CRMStatus(StrEnum):
    PROSPECTO = "PROSPECTO"
    ACTIVO = "ACTIVO"
    INACTIVO = "INACTIVO"


@dataclass
class CommercialList:
    id: int
    name: str
    description: str | None = None
    is_active: bool = True


@dataclass
class ProductPrice:
    id: int | None
    product_id: int
    commercial_list_id: int
    cost_iva_inc: Decimal | None
    markup_percentage: Decimal | None
    price_iva_inc: Decimal | None
    has_conflict: bool = False
    conflict_detail: str | None = None


@dataclass
class Product:
    id: int
    name: str
    code: str | None = None
    presentation: str | None = None
    provider: str | None = None
    category: str = "General"
    iva_rate: Decimal = Decimal("0.22")
    is_published: bool = False
    tech_sheet_url: str | None = None
    image_url: str | None = None
    is_active: bool = True
    current_stock: int = 0
    min_stock_alert: int = 5
    allow_backorder: bool = False
    prices: list[ProductPrice] = field(default_factory=list)

    @property
    def is_low_stock(self) -> bool:
        return self.current_stock <= self.min_stock_alert

    @property
    def is_out_of_stock(self) -> bool:
        return self.current_stock <= 0

    @property
    def is_pending_draft(self) -> bool:
        """Determines if the product is incomplete (missing cost, markup, presentation or provider)."""
        if not (self.presentation and self.presentation.strip()):
            return True
        if not (self.provider and self.provider.strip()):
            return True
        # Check if default/base price or any price has missing cost/markup
        if not self.prices:
            return True
        return any(p.cost_iva_inc is None or p.markup_percentage is None for p in self.prices)


@dataclass
class Customer:
    id: int | None
    document_type: DocumentType
    document_number: str
    business_name: str
    contact_name: str
    phone_whatsapp: str
    email: str
    password_hash: str
    commercial_list_id: int
    reception_notes: str | None = None
    authorized_persons: str | None = None
    crm_status: CRMStatus = CRMStatus.ACTIVO
    is_active: bool = True


@dataclass
class OrderItem:
    id: int | None
    order_id: int | None
    product_id: int
    quantity: int
    unit_price: Decimal
    discount_percent: Decimal = Decimal("0.0000")
    subtotal: Decimal = Decimal("0.00")


@dataclass
class Order:
    id: int | None
    customer_id: int
    order_status: OrderStatus
    delivery_type: DeliveryType
    delivery_cost: Decimal
    total_amount: Decimal
    delivery_address: str | None = None
    delivery_notes: str | None = None
    payment_method: PaymentMethod | None = None
    payment_status: PaymentStatus = PaymentStatus.PENDING
    payment_id: str | None = None
    preference_id: str | None = None
    remito_postal: str | None = None
    tracking_url: str | None = None
    # Datos de envío estructurados (compatibles con Marco Postal / ePresis)
    recipient_name: str | None = None
    document_number: str | None = None
    street: str | None = None
    street_number: str | None = None
    apartment: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    phone: str | None = None
    notes: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    items: list[OrderItem] = field(default_factory=list)


@dataclass
class Expense:
    id: int | None
    category: str
    description: str
    expense_date: date
    amount: Decimal
    created_at: datetime = field(default_factory=datetime.utcnow)
