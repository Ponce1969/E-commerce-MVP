import calendar
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.application.dtos.finance_dto import (
    ExpenseCreateDTO,
    ExpenseResponseDTO,
    FinancialSummaryDTO,
    MonthlyTrendItemDTO,
)
from src.domain.exceptions import EntityNotFoundException
from src.domain.services.financial_service import FinancialService
from src.infrastructure.db.models import (
    ExpenseORM,
    OrderItemORM,
    OrderORM,
    ProductORM,
)

SPANISH_MONTHS = [
    "",
    "Ene",
    "Feb",
    "Mar",
    "Abr",
    "May",
    "Jun",
    "Jul",
    "Ago",
    "Set",
    "Oct",
    "Nov",
    "Dic",
]


class FinancialUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_expense(self, data: ExpenseCreateDTO) -> ExpenseResponseDTO:
        expense = ExpenseORM(
            category=data.category.strip(),
            description=data.description.strip(),
            expense_date=data.expense_date,
            amount=data.amount,
        )
        self.session.add(expense)
        await self.session.commit()
        await self.session.refresh(expense)

        return ExpenseResponseDTO(
            id=expense.id,
            category=expense.category,
            description=expense.description,
            expense_date=expense.expense_date,
            amount=expense.amount,
            created_at=expense.created_at,
        )

    async def list_expenses(
        self,
        year: int | None = None,
        month: int | None = None,
        category: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ExpenseResponseDTO]:
        query = select(ExpenseORM)

        if year and month:
            start_date = date(year, month, 1)
            _, last_day = calendar.monthrange(year, month)
            end_date = date(year, month, last_day)
            query = query.where(
                ExpenseORM.expense_date >= start_date, ExpenseORM.expense_date <= end_date
            )
        elif year:
            start_date = date(year, 1, 1)
            end_date = date(year, 12, 31)
            query = query.where(
                ExpenseORM.expense_date >= start_date, ExpenseORM.expense_date <= end_date
            )

        if category:
            query = query.where(ExpenseORM.category == category)

        query = query.order_by(ExpenseORM.expense_date.desc(), ExpenseORM.id.desc())
        query = query.limit(limit).offset(offset)

        result = await self.session.execute(query)
        expenses = result.scalars().all()

        return [
            ExpenseResponseDTO(
                id=e.id,
                category=e.category,
                description=e.description,
                expense_date=e.expense_date,
                amount=e.amount,
                created_at=e.created_at,
            )
            for e in expenses
        ]

    async def delete_expense(self, expense_id: int) -> bool:
        stmt = select(ExpenseORM).where(ExpenseORM.id == expense_id)
        res = await self.session.execute(stmt)
        expense = res.scalar_one_or_none()
        if not expense:
            raise EntityNotFoundException(f"Gasto con ID {expense_id} no encontrado.")

        del_stmt = delete(ExpenseORM).where(ExpenseORM.id == expense_id)
        await self.session.execute(del_stmt)
        await self.session.commit()
        return True

    async def get_financial_summary(
        self, year: int | None = None, month: int | None = None
    ) -> FinancialSummaryDTO:
        now = datetime.now(UTC)
        target_year = year or now.year
        target_month = month or now.month

        # Compute summary for the specific month
        summary = await self._compute_month_kpis(target_year, target_month)

        # Compute historical 6-month trend ending at target month
        monthly_trend: list[MonthlyTrendItemDTO] = []
        cur_y = target_year
        cur_m = target_month

        months_back = []
        for _ in range(6):
            months_back.append((cur_y, cur_m))
            cur_m -= 1
            if cur_m == 0:
                cur_m = 12
                cur_y -= 1

        months_back.reverse()

        for y, m in months_back:
            kpis = await self._compute_month_kpis(y, m)
            month_label = f"{SPANISH_MONTHS[m]} {y}"
            month_key = f"{y}-{m:02d}"
            monthly_trend.append(
                MonthlyTrendItemDTO(
                    month_key=month_key,
                    month_label=month_label,
                    gross_revenue=kpis["gross_revenue"],
                    cogs=kpis["cogs"],
                    gross_margin=kpis["gross_margin"],
                    expenses=kpis["expenses"],
                    net_profit=kpis["net_profit"],
                )
            )

        period_label = f"{SPANISH_MONTHS[target_month]} {target_year}"
        margin_pct = FinancialService.calculate_margin_percentage(
            summary["gross_margin"], summary["gross_revenue"]
        )

        return FinancialSummaryDTO(
            period_label=period_label,
            year=target_year,
            month=target_month,
            gross_revenue=summary["gross_revenue"],
            cogs=summary["cogs"],
            gross_margin=summary["gross_margin"],
            margin_percentage=margin_pct,
            total_expenses=summary["expenses"],
            net_profit=summary["net_profit"],
            orders_count=summary["orders_count"],
            monthly_trend=monthly_trend,
        )

    async def _compute_month_kpis(self, year: int, month: int) -> dict[str, Any]:
        _, last_day = calendar.monthrange(year, month)
        start_dt = datetime(year, month, 1, 0, 0, 0, tzinfo=UTC)
        end_dt = datetime(year, month, last_day, 23, 59, 59, 999999, tzinfo=UTC)
        start_d = date(year, month, 1)
        end_d = date(year, month, last_day)

        # 1. Fetch Orders for the period
        orders_stmt = (
            select(OrderORM)
            .options(
                selectinload(OrderORM.customer),
                selectinload(OrderORM.items)
                .selectinload(OrderItemORM.product)
                .selectinload(ProductORM.prices),
            )
            .where(
                OrderORM.created_at >= start_dt,
                OrderORM.created_at <= end_dt,
                OrderORM.order_status != "CANCELADO",
            )
        )
        orders_res = await self.session.execute(orders_stmt)
        orders = orders_res.scalars().all()

        gross_revenue = Decimal("0.00")
        total_cogs = Decimal("0.00")

        for order in orders:
            gross_revenue += order.total_amount
            cust_list_id = order.customer.commercial_list_id if order.customer else None

            for it in order.items:
                product = it.product
                price_match = None
                if product and product.prices:
                    if cust_list_id:
                        price_match = next(
                            (pr for pr in product.prices if pr.commercial_list_id == cust_list_id),
                            None,
                        )
                    if not price_match:
                        price_match = product.prices[0]

                unit_cost = price_match.cost_iva_inc if price_match else None
                markup = price_match.markup_percentage if price_match else None

                item_cogs = FinancialService.calculate_cogs(
                    unit_cost=unit_cost,
                    unit_price=it.unit_price,
                    markup_percentage=markup,
                    quantity=it.quantity,
                )
                total_cogs += item_cogs

        # 2. Fetch Expenses for the period
        exp_stmt = select(func.coalesce(func.sum(ExpenseORM.amount), Decimal("0.00"))).where(
            ExpenseORM.expense_date >= start_d, ExpenseORM.expense_date <= end_d
        )
        exp_res = await self.session.execute(exp_stmt)
        total_expenses = exp_res.scalar() or Decimal("0.00")

        gross_margin = FinancialService.calculate_gross_margin(gross_revenue, total_cogs)
        net_profit = FinancialService.calculate_net_profit(gross_margin, total_expenses)

        return {
            "gross_revenue": gross_revenue,
            "cogs": total_cogs,
            "gross_margin": gross_margin,
            "expenses": total_expenses,
            "net_profit": net_profit,
            "orders_count": len(orders),
        }
