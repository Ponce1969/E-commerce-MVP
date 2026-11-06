from decimal import Decimal

from pydantic import BaseModel, Field


class PriceListDTO(BaseModel):
    id: int
    code: str
    name: str
    description: str | None = None
    is_active: bool = True


class PriceListCreateDTO(BaseModel):
    code: str = Field(
        ..., min_length=2, max_length=50, description="Código único, ej. VETERINARIAS"
    )
    name: str = Field(
        ..., min_length=2, max_length=100, description="Nombre descriptivo de la lista"
    )
    description: str | None = Field(None, description="Descripción opcional del segmento")
    is_active: bool = Field(True, description="Estado activo de la lista")


class PriceListUpdateDTO(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    description: str | None = None
    is_active: bool | None = None


class CategoryDTO(BaseModel):
    id: int
    name: str
    description: str | None = None
    is_active: bool = True
    product_count: int = 0


class CategoryCreateDTO(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Nombre de la categoría")
    description: str | None = Field(None, description="Descripción opcional")


class CategoryUpdateDTO(BaseModel):
    name: str | None = Field(
        None, min_length=1, max_length=100, description="Nombre de la categoría"
    )
    description: str | None = Field(None, description="Descripción opcional")
    is_active: bool | None = Field(None, description="Estado activo")


class ProductPriceDetailDTO(BaseModel):
    commercial_list_id: int
    commercial_list_name: str
    cost_iva_inc: Decimal | None = None
    markup_percentage: Decimal | None = None
    price_iva_inc: Decimal | None = None
    has_conflict: bool = False
    conflict_detail: str | None = None


class ProductPriceListItemDetailDTO(BaseModel):
    price_list_id: int
    price_list_code: str
    price_list_name: str
    sale_price: Decimal
    is_active: bool = True


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
    price_list_items: list[ProductPriceListItemDetailDTO] = []
    active_price_list_ids: list[int] = []
    category_ids: list[int] = []
    categories: list[CategoryDTO] = []


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
    category_ids: list[int] = Field(
        default_factory=list, description="IDs de categorías asociadas (N:M)"
    )
    iva_rate: Decimal = Decimal("0.22")
    cost_iva_inc: Decimal | None = Field(None, ge=0)
    markup_percentage: Decimal | None = Field(None, ge=0)
    current_stock: int = Field(0, ge=0)
    is_published: bool = False
    price_list_ids: list[int] = Field(
        default_factory=list, description="IDs de listas de precios asignadas al crear"
    )


class ProductUpdateDTO(BaseModel):
    name: str = Field(..., min_length=2, description="Nombre del artículo")
    category: str | None = Field(None, description="Categoría comercial principal (legacy)")
    category_ids: list[int] | None = Field(None, description="IDs de categorías asociadas (N:M)")
    code: str | None = Field(None, description="Código de barras o referencia")
    presentation: str | None = Field(None, description="Presentación comercial (ej. 5L, Bidón)")
    provider: str | None = Field(None, description="Proveedor o fabricante")
    iva_rate: Decimal = Field(Decimal("0.22"), description="Tasa de IVA")


class ProductPriceUpdateItemDTO(BaseModel):
    commercial_list_id: int
    cost_iva_inc: Decimal
    markup_percentage: Decimal | None = None
    price_iva_inc: Decimal | None = None


class ProductUpdatePricesDTO(BaseModel):
    prices: list[ProductPriceUpdateItemDTO] = []
    price_list_ids: list[int] | None = Field(
        None, description="IDs de listas asignadas para sincronización N:M"
    )
    cost_iva_inc: Decimal | None = Field(None, ge=0)
    markup_percentage: Decimal | None = Field(None, ge=0)
    price_iva_inc: Decimal | None = Field(None, ge=0)


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
