# 2 Rodríguez Distribuidora — Plataforma Comercial & E-commerce B2B/B2C

Plataforma integral de gestión comercial, catálogo digital B2B/B2C y control contable para **2 Rodríguez Distribuidora** (Paso Molino, Montevideo, Uruguay).

---

## 🏗️ Arquitectura & Stack Tecnológico

El proyecto está diseñado bajo una arquitectura limpia y desacoplada monorepo:

- **Backend (`/backend`)**:
  - **Framework**: Python 3.12+ con **FastAPI**.
  - **Arquitectura**: Hexagonal / Puertos y Adaptadores (`domain/`, `application/`, `infrastructure/`).
  - **Aritmética Financiera**: Precisión monetaria estricta con `Decimal` (prohibido uso de `float` para precios y márgenes).
  - **Persistencia**: PostgreSQL 16 con **SQLAlchemy 2.0 Async** y migraciones automáticas con **Alembic**.
  - **Seguridad**: Autenticación JWT con hasheo de contraseñas con **Argon2id** y control de acceso basado en roles (`ADMIN` y `CUSTOMER`).
  - **Gestor de Paquetes**: **`uv`** (Astral).
  - **Generación de Reportes**: **ReportLab** para presupuestos corporativos formales en PDF.

- **Frontend (`/frontend`)**:
  - **Framework**: **Astro 5** en modo estático de alto rendimiento.
  - **Estilos**: **Tailwind CSS v4** con diseño atómico, tokens semánticos y soporte para modo oscuro.
  - **Visualización**: Gráfica de rentabilidad nativa con **SVG responsivo**, sin dependencias externas pesadas.
  - **Gestor de Paquetes**: **`pnpm`**.

---

## 🚀 Módulos Principales

### 1. Catálogo Público (`/` y `/catalogo`)
- Buscador en tiempo real por nombre y categoría.
- Precios confidenciales con botón directo de consulta a **WhatsApp Oficial (+598 95 250 673)**.
- Información de entrega y retiro gratuito en depósito Paso Molino.

### 2. Portal Clientes B2B (`/portal`)
- Autenticación segura de clientes mayoristas / corporativos.
- Visualización de precios finales autorizados según su **lista comercial asignada**.
- Checkout con selector logístico:
  - Retiro gratuito en Paso Molino ($0).
  - Cadetería Marco Postal ($250).
- Descuento atómico de inventario con bloqueo pesimista de fila (`with_for_update`).

### 3. Backoffice Administrativo Mariana (`/admin`)
- **Gestión de Catálogo**: 311 artículos maestros con los 19 conflictos históricos de márgenes preservados intactos.
- **Control de Inventario**:
  - Alerta de stock crítico (rojo/amarillo/verde).
  - Modal rápido de ajuste físico de existencias y umbral de aviso.
  - Exportación de catálogo completo a **Excel / CSV** con codificación `UTF-8-BOM` y separador `;`.
  - Importación masiva de stock arrastrando planillas CSV (*Drag & Drop*).
- **Archivos Multimedia**:
  - Carga *Drag & Drop* de fotos de artículos (`.jpg`, `.png`, `.webp`) con previsualización en vivo.
  - Carga *Drag & Drop* de fichas técnicas en formato `.pdf` vinculadas al producto.
- **Blindaje Comercial**:
  - Proveedores y costos de compra 100% ocultos al público y clientes B2B.
  - Filtro dinámico por proveedor en el panel de administración.
- **Mini-Contabilidad & Rentabilidad**:
  - Métricas mensuales: Facturación Bruta, Costo Mercadería (COGS), Gastos Operativos y Ganancia Neta.
  - Gráfica a golpe de ojo con SVG nativo responsivo comparando los últimos 6 meses.
  - Registro ágil de gastos operativos (alquiler, fletes, packaging, sueldos, tributos).
- **Emisión de Presupuestos PDF**:
  - Generador de cotizaciones formales con logo corporativo, membrete y exclusión absoluta de costos internos.

---

## 🛠️ Puesta en Marcha Local

### Prerrequisitos
- Docker & Docker Compose
- Python 3.12+ y `uv`
- Node.js 20+ y `pnpm`

### 1. Base de Datos (PostgreSQL 16)
Levantar el contenedor aislado en el puerto `5436`:
```bash
cd backend
docker compose up -d
```

### 2. Backend API
Instalar dependencias, aplicar migraciones y levantar el servidor FastAPI:
```bash
cd backend
uv run alembic upgrade head
uv run uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload
```
- API Docs: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)

### 3. Frontend Astro
Instalar dependencias y levantar el servidor de desarrollo:
```bash
cd frontend
pnpm install
pnpm run dev --port 4321
```
- Web: [http://localhost:4321](http://localhost:4321)
- Panel Admin: [http://localhost:4321/admin](http://localhost:4321/admin)

---

## 🧪 Pruebas y Calidad de Código

### Backend
```bash
cd backend
uv run pytest
uv run ruff check .
uv run mypy src tests
```

### Frontend
```bash
cd frontend
pnpm run build
```
