from decimal import Decimal

from pydantic import BaseModel, Field


class ProductPriceDetailDTO(BaseModel):
    commercial_list_id: int
    commercial_list_name: str
    cost_iva_inc: Decimal | None = None
    markup_percentage: Decimal | None = None
    price_iva_inc: Decimal | None = None
    has_conflict: bool = False
    conflict_detail: str | None = None


class ProductAdminDetailDTO(BaseModel):
    id: int
    code: str | None = None
    name: str
    presentation: str | None = None
    provider: str | None = None
    category: str
    iva_rate: Decimal
    is_published: bool
    is_pending_draft: bool
    tech_sheet_url: str | None = None
    image_url: str | None = None
    is_active: bool
    current_stock: int = 0
    min_stock_alert: int = 5
    allow_backorder: bool = False
    is_low_stock: bool = False
    is_out_of_stock: bool = False
    prices: list[ProductPriceDetailDTO] = []


class ProductStockUpdateDTO(BaseModel):
    current_stock: int = Field(..., ge=0, description="Stock físico actual en depósito")
    min_stock_alert: int = Field(5, ge=0, description="Umbral de alerta para stock crítico")
    allow_backorder: bool = Field(False, description="Permitir venta sin stock disponible")


class ProductCreateDTO(BaseModel):
    name: str = Field(..., min_length=2)
    code: str | None = None
    presentation: str | None = None
    provider: str | None = None
    category: str = "General"
    iva_rate: Decimal = Decimal("0.22")


class ProductPriceUpdateItemDTO(BaseModel):
    commercial_list_id: int
    cost_iva_inc: Decimal
    markup_percentage: Decimal


class ProductUpdatePricesDTO(BaseModel):
    prices: list[ProductPriceUpdateItemDTO]


class ProductTogglePublishDTO(BaseModel):
    is_published: bool


class ProductPortalItemDTO(BaseModel):
    id: int
    name: str
    presentation: str | None = None
    category: str
    price_iva_inc: Decimal
    iva_rate: Decimal
    image_url: str | None = None
    tech_sheet_url: str | None = None


class UploadAttachmentResponseDTO(BaseModel):
    url: str
    filename: str
    file_type: str
