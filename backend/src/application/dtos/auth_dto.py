from pydantic import BaseModel, EmailStr

from src.infrastructure.security.jwt import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    email: str
    commercial_list_id: int | None = None
    user_id: int


class CustomerRegisterRequest(BaseModel):
    document_type: str
    document_number: str
    business_name: str
    contact_name: str
    phone_whatsapp: str
    email: EmailStr
    password: str
    commercial_list_id: int
    reception_notes: str | None = None
    authorized_persons: str | None = None
