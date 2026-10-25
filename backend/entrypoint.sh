#!/bin/bash
set -e

echo "==> Esperando conexión con PostgreSQL..."
python3 - << 'EOF'
import os
import sys
import time
import socket

host = os.getenv("POSTGRES_SERVER", "postgres")
port = int(os.getenv("POSTGRES_PORT", 5432))

max_retries = 30
for i in range(max_retries):
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"==> Base de datos lista en {host}:{port}")
            sys.exit(0)
    except (socket.timeout, ConnectionRefusedError, OSError):
        print(f"==> Intentando conectar a la base de datos ({i+1}/{max_retries})...")
        time.sleep(1)

print("==> Error: No se pudo conectar a PostgreSQL.", file=sys.stderr)
sys.exit(1)
EOF

echo "==> Ejecutando migraciones de base de datos con Alembic..."
uv run alembic upgrade head

echo "==> Iniciando servidor Uvicorn en producción..."
exec uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 2
