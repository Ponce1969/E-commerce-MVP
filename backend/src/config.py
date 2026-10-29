from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "2 Rodríguez Distribuidora API"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # CORS Configuration
    CORS_ORIGINS: list[str] = [
        "http://localhost:4321",
        "http://127.0.0.1:4321",
        "http://localhost:3000",
    ]

    # PostgreSQL Database
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "web_2r"

    # Security
    SECRET_KEY: str = "dev_secret_key_change_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Email / Resend API
    RESEND_API_KEY: str | None = None
    RESEND_FROM_EMAIL: str = "2 Rodríguez Distribuidora <onboarding@resend.dev>"
    COMPANY_EMAIL: str = "dosrodriguezdistribuidora@gmail.com"
    FRONTEND_URL: str = "http://localhost:4321"

    # Mercado Pago Uruguay (Checkout Pro)
    MP_PUBLIC_KEY: str = "PEGAR_AQUI_PUBLIC_KEY"
    MP_ACCESS_TOKEN: str = "PEGAR_AQUI_ACCESS_TOKEN"
    MP_WEBHOOK_SECRET: str | None = None
    MP_BACK_URL_SUCCESS: str = "https://2rodriguez.com.uy/checkout/success"
    MP_BACK_URL_PENDING: str = "https://2rodriguez.com.uy/checkout/pending"
    MP_BACK_URL_FAILURE: str = "https://2rodriguez.com.uy/checkout/failure"

    # Marco Postal / ePresis API v2
    MARCO_POSTAL_API_URL: str = "https://marcopostal.epresis.com/api/v2"
    MARCO_POSTAL_TOKEN: str = "LRJ4DwsDY21qwf3PSqsbTBMzAkAlWRCVVtcY2CYw28XGpyApGxNrEE4tU1NQ"
    MARCO_POSTAL_SUCURSAL: str = "10090"
    MARCO_POSTAL_SERVICIO: str = "004"

    # Datos fijos de Remitente (Mariana / Dos Rodríguez)
    SENDER_EMPRESA: str = "Dos Rodríguez Distribuidora - Mariana Moreira Rodríguez"
    SENDER_REMITENTE: str = "Mariana Moreira Rodríguez"
    SENDER_RUT: str = "220848220010"
    SENDER_CALLE: str = "Gregorio Camino"
    SENDER_ALTURA: str = "243"
    SENDER_LOCALIDAD: str = "BELVEDERE"
    SENDER_PROVINCIA: str = "MONTEVIDEO"
    SENDER_CP: str = "11700"
    SENDER_CELULAR: str = "094151177"
    SENDER_EMAIL: str = "dosrodriguezdistribuidora@gmail.com"

    # Datos de Cobro Transferencia BROU
    BROU_BANCO: str = "Banco República (BROU)"
    BROU_TIPO_CUENTA: str = "Caja de Ahorro en Pesos Uruguayos"
    BROU_TITULAR: str = "Mariana Moreira Rodríguez"
    BROU_NUMERO_CUENTA: str = "COMPLETAR_CUENTA_BROU"
    BROU_DESCUENTO_PERCENT: float = 0.0

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.ENVIRONMENT.lower() == "production":
            if self.SECRET_KEY == "dev_secret_key_change_in_production":
                raise ValueError(
                    "CRITICAL SECURITY ERROR: SECRET_KEY must be configured in production via .env and cannot use default dev key."
                )
            if len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "CRITICAL SECURITY ERROR: Production SECRET_KEY must be at least 32 characters long."
                )
        return self

    @property
    def async_database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
