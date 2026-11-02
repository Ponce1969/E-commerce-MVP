from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dtos.finance_dto import (
    ExpenseCreateDTO,
    ExpenseResponseDTO,
    FinancialSummaryDTO,
)
from src.application.use_cases.finances.financial_use_case import FinancialUseCase
from src.domain.exceptions import EntityNotFoundException
from src.infrastructure.db.session import get_db_session
from src.infrastructure.security.audit import audit_log
from src.infrastructure.security.dependencies import require_admin
from src.infrastructure.security.jwt import TokenData

router = APIRouter(
    prefix="/admin/finances",
    tags=["Contabilidad y Finanzas (Admin)"],
    dependencies=[Depends(require_admin)],
)


@router.get("/summary", response_model=FinancialSummaryDTO)
async def get_financial_summary(
    year: int | None = Query(None, description="Año fiscal (ej: 2026)"),
    month: int | None = Query(None, ge=1, le=12, description="Mes fiscal (1-12)"),
    session: AsyncSession = Depends(get_db_session),
) -> FinancialSummaryDTO:
    use_case = FinancialUseCase(session)
    return await use_case.get_financial_summary(year=year, month=month)


@router.get("/expenses", response_model=list[ExpenseResponseDTO])
async def list_expenses(
    year: int | None = Query(None, description="Filtrar por año"),
    month: int | None = Query(None, ge=1, le=12, description="Filtrar por mes"),
    category: str | None = Query(None, description="Filtrar por categoría de gasto"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> list[ExpenseResponseDTO]:
    use_case = FinancialUseCase(session)
    return await use_case.list_expenses(
        year=year, month=month, category=category, limit=limit, offset=offset
    )


@router.post(
    "/expenses",
    response_model=ExpenseResponseDTO,
    status_code=status.HTTP_201_CREATED,
)
async def create_expense(
    data: ExpenseCreateDTO,
    admin_user: TokenData = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> ExpenseResponseDTO:
    use_case = FinancialUseCase(session)
    expense = await use_case.create_expense(data)
    audit_log(
        action="CREATE_FINANCIAL_EXPENSE",
        target_entity="expense",
        target_id=expense.id,
        actor=admin_user,
        details={"category": expense.category, "amount": float(expense.amount)},
    )
    return expense


@router.delete("/expenses/{expense_id}")
async def delete_expense(
    expense_id: int,
    admin_user: TokenData = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, bool]:
    use_case = FinancialUseCase(session)
    try:
        await use_case.delete_expense(expense_id)
        audit_log(
            action="DELETE_FINANCIAL_EXPENSE",
            target_entity="expense",
            target_id=expense_id,
            actor=admin_user,
        )
        return {"success": True}
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
