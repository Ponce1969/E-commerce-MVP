#!/usr/bin/env python3
"""
set_admin_password.py
Permite actualizar o crear la contraseña del usuario Administrador (Mariana)
tomando las credenciales desde backend/.env o mediante argumentos CLI.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Agregar backend al PYTHONPATH para importar módulos de la app
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)


async def update_or_create_admin(
    email: str, password: str, full_name: str = "Mariana 2 Rodríguez"
) -> None:
    from sqlalchemy import select
    from src.infrastructure.db.models import AdminUserORM
    from src.infrastructure.db.session import async_session_factory, engine
    from src.infrastructure.security.password import hash_password

    async with async_session_factory() as session:
        stmt = select(AdminUserORM).where(AdminUserORM.email == email)
        result = await session.execute(stmt)
        admin = result.scalar_one_or_none()

        new_hash = hash_password(password)

        if admin:
            admin.password_hash = new_hash
            admin.is_active = True
            print(f"[+] Contraseña de '{email}' actualizada exitosamente en la base de datos.")
        else:
            admin = AdminUserORM(
                email=email,
                password_hash=new_hash,
                full_name=full_name,
                is_active=True,
            )
            session.add(admin)
            print(f"[+] Usuario Administrador '{email}' creado exitosamente en la base de datos.")

        await session.commit()
    await engine.dispose()


def main() -> None:
    from src.config import settings

    parser = argparse.ArgumentParser(
        description="Actualiza la contraseña del Administrador en la base de datos."
    )
    parser.add_argument(
        "--email",
        type=str,
        default=settings.INITIAL_ADMIN_EMAIL,
        help="Email del administrador (por defecto toma INITIAL_ADMIN_EMAIL de .env)",
    )
    parser.add_argument(
        "--password",
        type=str,
        default=settings.INITIAL_ADMIN_PASSWORD,
        help="Nueva contraseña (por defecto toma INITIAL_ADMIN_PASSWORD de .env)",
    )
    parser.add_argument(
        "--name",
        type=str,
        default="Mariana 2 Rodríguez",
        help="Nombre completo del administrador",
    )

    args = parser.parse_args()

    if not args.email or not args.password:
        print("[!] Error: Email y contraseña no pueden estar vacíos.")
        sys.exit(1)

    print(f"[*] Actualizando credenciales para: {args.email}")
    asyncio.run(update_or_create_admin(args.email, args.password, args.name))


if __name__ == "__main__":
    main()
