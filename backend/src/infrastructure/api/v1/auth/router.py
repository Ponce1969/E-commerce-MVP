from fastapi import APIRouter, Depends, HTTPException, Request, status
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
from src.infrastructure.security.audit import audit_log
from src.infrastructure.security.rate_limiter import (
    login_rate_limiter,
    password_reset_rate_limiter,
    rate_limit,
)

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Iniciar sesión (Admin o Cliente B2B)",
    dependencies=[Depends(rate_limit(login_rate_limiter))],
)
async def login(
    data: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if not client_ip and request.client:
        client_ip = request.client.host

    use_case = AuthenticateUserUseCase(session)
    try:
        token = await use_case.execute(data)
        audit_log(
            action="LOGIN_SUCCESS",
            target_entity="user",
            target_id=token.email,
            ip_address=client_ip,
            details={"role": token.role.value},
        )
        return token
    except BusinessRuleViolationException as e:
        audit_log(
            action="LOGIN_FAILURE",
            target_entity="user",
            target_id=data.email,
            ip_address=client_ip,
            details={"error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    summary="Solicitar recuperación de contraseña vía Resend",
    dependencies=[Depends(rate_limit(password_reset_rate_limiter))],
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
    dependencies=[Depends(rate_limit(password_reset_rate_limiter))],
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
