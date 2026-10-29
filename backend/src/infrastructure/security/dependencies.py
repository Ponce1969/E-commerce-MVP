from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.infrastructure.security.jwt import TokenData, UserRole, decode_access_token

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> TokenData:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el token de autorización en la solicitud.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = decode_access_token(credentials.credentials)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token_data


async def require_admin(
    current_user: TokenData = Depends(get_current_user),
) -> TokenData:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso restringido: requiere permisos de Administrador.",
        )
    return current_user


async def require_customer(
    current_user: TokenData = Depends(get_current_user),
) -> TokenData:
    if current_user.role != UserRole.CUSTOMER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso restringido: requiere cuenta de Cliente B2B.",
        )
    if current_user.commercial_list_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cliente no tiene lista comercial asignada.",
        )
    return current_user


async def get_optional_customer(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> TokenData | None:
    if not credentials:
        return None
    token_data = decode_access_token(credentials.credentials)
    if token_data and token_data.role == UserRole.CUSTOMER:
        return token_data
    return None
