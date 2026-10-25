from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dtos.auth_dto import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from src.application.use_cases.auth.authenticate_user import AuthenticateUserUseCase
from src.application.use_cases.auth.password_recovery import PasswordRecoveryUseCase
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


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    summary="Solicitar recuperación de contraseña vía Resend",
)
async def forgot_password(
    data: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ForgotPasswordResponse:
    use_case = PasswordRecoveryUseCase(session)
    return await use_case.request_reset(data.email)


@router.post(
    "/reset-password",
    summary="Restablecer contraseña con token temporal",
)
async def reset_password(
    data: ResetPasswordRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    use_case = PasswordRecoveryUseCase(session)
    try:
        return await use_case.reset_password(data.token, data.new_password)
    except BusinessRuleViolationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
