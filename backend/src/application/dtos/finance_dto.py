from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ExpenseCreateDTO(BaseModel):
    category: str = Field(..., min_length=2, max_length=100)
    description: str = Field(..., min_length=2, max_length=255)
    expense_date: date
    amount: Decimal = Field(..., gt=Decimal("0.00"), description="Monto en pesos uruguayos")


class ExpenseResponseDTO(BaseModel):
    id: int
    category: str
    description: str
    expense_date: date
    amount: Decimal
    created_at: datetime


class MonthlyTrendItemDTO(BaseModel):
    month_key: str
    month_label: str
    gross_revenue: Decimal
    cogs: Decimal
    gross_margin: Decimal
    expenses: Decimal
    net_profit: Decimal


class FinancialSummaryDTO(BaseModel):
    period_label: str
    year: int
    month: int
    gross_revenue: Decimal
    cogs: Decimal
    gross_margin: Decimal
    margin_percentage: Decimal
    total_expenses: Decimal
    net_profit: Decimal
    orders_count: int
    monthly_trend: list[MonthlyTrendItemDTO] = []
