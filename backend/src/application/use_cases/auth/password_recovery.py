import logging
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dtos.auth_dto import ForgotPasswordResponse
from src.config import settings
from src.domain.exceptions import BusinessRuleViolationException
from src.infrastructure.db.models import AdminUserORM, CustomerORM
from src.infrastructure.security.jwt import (
    UserRole,
    create_password_reset_token,
    decode_password_reset_token,
)
from src.infrastructure.security.password import hash_password

logger = logging.getLogger(__name__)


class PasswordRecoveryUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def request_reset(self, email: str) -> ForgotPasswordResponse:
        """Finds user, creates reset token and sends email via Resend."""
        target_user: Any = None
        user_role: UserRole | None = None

        # Check in Admin users
        stmt_admin = select(AdminUserORM).where(
            AdminUserORM.email == email,
            AdminUserORM.is_active == True,  # noqa: E712
        )
        res_admin = await self.session.execute(stmt_admin)
        admin = res_admin.scalar_one_or_none()

        if admin:
            target_user = admin
            user_role = UserRole.ADMIN
        else:
            # Check in Customers
            stmt_cust = select(CustomerORM).where(
                CustomerORM.email == email,
                CustomerORM.is_active == True,  # noqa: E712
            )
            res_cust = await self.session.execute(stmt_cust)
            customer = res_cust.scalar_one_or_none()
            if customer:
                target_user = customer
                user_role = UserRole.CUSTOMER

        if not target_user or not user_role:
            # Return uniform message to prevent user enumeration
            return ForgotPasswordResponse(
                message="Si el correo ingresado se encuentra registrado, recibirás un enlace para restablecer tu contraseña.",
                email_sent=True,
            )

        token = create_password_reset_token(
            user_id=target_user.id,
            email=target_user.email,
            role=user_role,
            expires_minutes=60,
        )

        reset_url = f"{settings.FRONTEND_URL}/portal?reset_token={token}"
        email_sent = await self._send_email_via_resend(target_user.email, reset_url)

        return ForgotPasswordResponse(
            message="Si el correo ingresado se encuentra registrado, recibirás un enlace para restablecer tu contraseña.",
            email_sent=email_sent,
        )

    async def reset_password(self, token: str, new_password: str) -> dict[str, str]:
        """Validates token and updates user password."""
        token_data = decode_password_reset_token(token)
        if not token_data:
            raise BusinessRuleViolationException(
                "El enlace de recuperación es inválido o ha expirado. Por favor solicitá uno nuevo."
            )

        if len(new_password) < 6:
            raise BusinessRuleViolationException(
                "La nueva contraseña debe tener al menos 6 caracteres."
            )

        new_hash = hash_password(new_password)

        if token_data.role == UserRole.ADMIN:
            stmt = select(AdminUserORM).where(AdminUserORM.id == token_data.user_id)
            res = await self.session.execute(stmt)
            user = res.scalar_one_or_none()
            if not user:
                raise BusinessRuleViolationException("Usuario no encontrado.")
            user.password_hash = new_hash
        else:
            stmt_cust = select(CustomerORM).where(CustomerORM.id == token_data.user_id)
            res_c = await self.session.execute(stmt_cust)
            cust = res_c.scalar_one_or_none()
            if not cust:
                raise BusinessRuleViolationException("Cliente no encontrado.")
            cust.password_hash = new_hash

        await self.session.commit()
        return {
            "message": "Tu contraseña ha sido actualizada con éxito. Ya podés iniciar sesión con tus nuevas credenciales."
        }

    async def _send_email_via_resend(self, to_email: str, reset_url: str) -> bool:
        if not settings.RESEND_API_KEY:
            logger.warning(
                "RESEND_API_KEY no configurada. Link de reseteo generado para %s: %s",
                to_email,
                reset_url,
            )
            return True

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #f4f6f8; margin: 0; padding: 24px;">
          <div style="max-width: 540px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; padding: 32px; border: 1px solid #e2e8f0;">
            <div style="text-align: center; margin-bottom: 24px;">
              <h2 style="color: #0b4ca0; margin: 0;">2 Rodríguez Distribuidora</h2>
              <p style="color: #64748b; font-size: 13px; margin: 4px 0 0 0;">Plataforma de Clientes & Backoffice</p>
            </div>

            <p style="font-size: 14px; color: #1e293b; line-height: 1.5;">
              Hola,<br><br>
              Recibimos una solicitud para restablecer la contraseña de tu cuenta asociada a <strong>{to_email}</strong>.
            </p>

            <div style="text-align: center; margin: 30px 0;">
              <a href="{reset_url}" style="background-color: #0b4ca0; color: #ffffff; text-decoration: none; padding: 12px 24px; font-size: 14px; font-weight: bold; border-radius: 8px; display: inline-block;">
                Restablecer Contraseña
              </a>
            </div>

            <p style="font-size: 12px; color: #64748b; line-height: 1.5;">
              Este enlace es válido por <strong>60 minutos</strong>. Si no solicitaste este cambio, podés ignorar este correo de forma segura.
            </p>

            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;" />

            <p style="font-size: 11px; color: #94a3b8; text-align: center; margin: 0;">
              Punto de Retiro: Ángel Salvo 56 (Paso Molino, Montevideo)<br>
              Consultas: {settings.COMPANY_EMAIL} | WhatsApp: +598 95 250 673
            </p>
          </div>
        </body>
        </html>
        """

        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": settings.RESEND_FROM_EMAIL,
                        "to": [to_email],
                        "subject": "Restablecer contraseña — 2 Rodríguez Distribuidora",
                        "html": html_content,
                    },
                    timeout=10.0,
                )
                if not res.is_success:
                    logger.error("Error al enviar email con Resend: %s", res.text)
                    return False
                return True
        except Exception as ex:
            logger.error("Excepción al conectar con la API de Resend: %s", ex)
            return False
