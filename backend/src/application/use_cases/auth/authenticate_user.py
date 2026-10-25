from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dtos.auth_dto import LoginRequest, TokenResponse
from src.domain.exceptions import BusinessRuleViolationException
from src.infrastructure.db.models import AdminUserORM, CustomerORM
from src.infrastructure.security.jwt import UserRole, create_access_token
from src.infrastructure.security.password import verify_password


class AuthenticateUserUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute(self, request: LoginRequest) -> TokenResponse:
        # 1. First check if user is an Administrator
        stmt_admin = select(AdminUserORM).where(
            AdminUserORM.email == request.email,
            AdminUserORM.is_active == True,  # noqa: E712
        )
        res_admin = await self.session.execute(stmt_admin)
        admin = res_admin.scalar_one_or_none()

        if admin and verify_password(request.password, admin.password_hash):
            token = create_access_token(
                user_id=admin.id,
                email=admin.email,
                role=UserRole.ADMIN,
                commercial_list_id=None,
            )
            return TokenResponse(
                access_token=token,
                role=UserRole.ADMIN,
                email=admin.email,
                commercial_list_id=None,
                user_id=admin.id,
            )

        # 2. Check if user is a B2B Customer
        stmt_cust = select(CustomerORM).where(
            CustomerORM.email == request.email,
            CustomerORM.is_active == True,  # noqa: E712
        )
        res_cust = await self.session.execute(stmt_cust)
        customer = res_cust.scalar_one_or_none()

        if customer and verify_password(request.password, customer.password_hash):
            token = create_access_token(
                user_id=customer.id,
                email=customer.email,
                role=UserRole.CUSTOMER,
                commercial_list_id=customer.commercial_list_id,
            )
            return TokenResponse(
                access_token=token,
                role=UserRole.CUSTOMER,
                email=customer.email,
                commercial_list_id=customer.commercial_list_id,
                user_id=customer.id,
            )

        raise BusinessRuleViolationException("Credenciales inválidas o usuario inactivo.")
