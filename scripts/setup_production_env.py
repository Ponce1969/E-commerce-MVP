#!/usr/bin/env python3
"""
setup_production_env.py
Generador automático de entorno seguro para producción en Orange Pi (Ubuntu Linux).
Crea y blinda el archivo backend/.env con claves criptográficas aleatorias (Cero dependencias externas).
"""

import argparse
import contextlib
import datetime
import io
import os
import secrets
import sys
from pathlib import Path

# Asegurar codificación UTF-8 si la terminal lo admite
if hasattr(sys.stdout, "reconfigure"):
    with contextlib.suppress(AttributeError, io.UnsupportedOperation):
        sys.stdout.reconfigure(encoding="utf-8")


def print_banner() -> None:
    print("\n==================================================================")
    print("  2 Rodríguez Distribuidora — Generador de Entorno Seguro (.env)")
    print("  Optimizado para Orange Pi / Servidores Ubuntu Linux")
    print("==================================================================\n")


def generate_secure_token(nbytes: int = 48) -> str:
    """Genera una clave criptográficamente segura usando el generador de entropía del SO."""
    return secrets.token_urlsafe(nbytes)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera el archivo .env de producción para 2 Rodríguez con claves de alta entropía."
    )
    parser.add_argument(
        "--domain",
        type=str,
        default=None,
        help="URL o dominio del frontend (ej: https://2rodriguez.uy o http://192.168.1.50:4321)",
    )
    parser.add_argument(
        "--port",
        type=str,
        default="5436",
        help="Puerto PostgreSQL para el contenedor de la base de datos (por defecto: 5436)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Sobrescribe el .env existente sin preguntar (haciendo backup automático)",
    )

    args = parser.parse_args()
    print_banner()

    # Detectar directorio raíz del proyecto
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    backend_dir = project_root / "backend"

    if not backend_dir.exists():
        print(f"[!] Error: No se encontró la carpeta 'backend' en {project_root}")
        sys.exit(1)

    target_env = backend_dir / ".env"

    # Si ya existe un .env, hacer copia de respaldo
    if target_env.exists():
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backend_dir / f".env.backup_{timestamp}"
        target_env.rename(backup_path)
        print(f"[*] Se encontró un .env previo. Respaldado en: {backup_path.name}")

    # Generación de claves seguras con secrets (alta entropía)
    jwt_secret_key = generate_secure_token(48)  # ~64 caracteres
    db_password = generate_secure_token(24)  # ~32 caracteres
    db_user = "web2r_prod_user"
    db_name = "web_2r_prod"
    db_port = args.port

    frontend_url = args.domain
    if not frontend_url:
        default_domain = "http://localhost:4321"
        try:
            print("Configuración de Dominio / Red:")
            user_input = input(
                f"  Ingresá la URL del frontend [{default_domain}]: "
            ).strip()
            frontend_url = user_input if user_input else default_domain
        except (EOFError, KeyboardInterrupt):
            print("\n[!] Modo no interactivo detectado. Usando valor por defecto.")
            frontend_url = default_domain

    env_content = f"""# ==============================================================================
# 2 Rodríguez Distribuidora — Variables de Entorno de Producción (Orange Pi)
# Generado automáticamente: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
# ==============================================================================

# Entorno de Ejecución
PROJECT_NAME="2 Rodríguez Distribuidora API"
ENVIRONMENT="production"
DEBUG=false
API_V1_STR="/api/v1"

# Orígenes Permitidos (CORS estricto)
CORS_ORIGINS=["{frontend_url}", "http://localhost:4321", "http://127.0.0.1:4321"]

# Base de Datos PostgreSQL
POSTGRES_USER={db_user}
POSTGRES_PASSWORD={db_password}
POSTGRES_SERVER=localhost
POSTGRES_PORT={db_port}
POSTGRES_DB={db_name}

# Seguridad Criptográfica (JWT / RBAC)
SECRET_KEY={jwt_secret_key}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480

# Correo Transaccional (Resend API)
# NOTA: Pegá tu clave real de Resend aquí abajo (comienza con 're_')
RESEND_API_KEY=
RESEND_FROM_EMAIL="2 Rodríguez Distribuidora <onboarding@resend.dev>"
COMPANY_EMAIL="dosrodriguezdistribuidora@gmail.com"
FRONTEND_URL="{frontend_url}"
"""

    # Guardar archivo .env
    target_env.write_text(env_content, encoding="utf-8")

    # Si es Linux / Unix, blindar permisos del archivo a chmod 600
    if os.name == "posix":
        try:
            os.chmod(target_env, 0o600)
            print(
                "[+] Permisos del archivo blindados a chmod 600 (solo lectura del usuario)."
            )
        except OSError as e:
            print(f"[!] No se pudo aplicar chmod 600: {e}")

    print(f"\n[+] Archivo .env generado exitosamente en: {target_env}")
    print("\nCredenciales de Producción Generadas:")
    print(
        f"  * Base de Datos: Usuario '{db_user}' | Base '{db_name}' | Puerto {db_port}"
    )
    print(f"  * Clave de BD:   {db_password}")
    print(f"  * JWT Secret:    {jwt_secret_key[:12]}... (64 bytes de alta entropía)")
    print("\nPASO SIGUIENTE OBLIGATORIO:")
    print(f"  Abrí {target_env} y colocá tu clave de Resend en la línea:")
    print("  RESEND_API_KEY=re_tu_clave_aqui\n")


if __name__ == "__main__":
    main()
