from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class QuoteItemCreateDTO(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0)
    discount_percentage: Decimal = Field(
        default=Decimal("0.0000"), ge=Decimal("0.0000"), le=Decimal("100.0000")
    )


class QuoteCreateDTO(BaseModel):
    commercial_list_id: int
    customer_id: int | None = None
    client_name: str
    client_phone: str | None = None
    client_email: str | None = None
    valid_until: date | None = None
    items: list[QuoteItemCreateDTO] = Field(..., min_length=1)
