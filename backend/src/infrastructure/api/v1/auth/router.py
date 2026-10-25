from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dtos.auth_dto import LoginRequest, TokenResponse
from src.application.use_cases.auth.authenticate_user import AuthenticateUserUseCase
from src.domain.exceptions import BusinessRuleViolationException
from src.infrastructure.db.session import get_db_session

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Iniciar sesión (Admin o Cliente B2B)",
)
async def login(
    data: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    use_case = AuthenticateUserUseCase(session)
    try:
        return await use_case.execute(data)
    except BusinessRuleViolationException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e
