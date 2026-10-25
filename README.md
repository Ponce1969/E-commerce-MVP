<div align="center">

<img src="frontend/public/logo.png" alt="2 Rodríguez Distribuidora" width="220" />

# 2 Rodríguez Distribuidora
### Plataforma de Gestión Comercial, Portal B2B/B2C & Inteligencia Financiera

*Solución integral desarrollada a medida para centralizar el catálogo maestro, blindar márgenes comerciales, automatizar pedidos mayoristas y erradicar las planillas manuales de Excel.*

---

<!-- Badges Banner de Tecnologías -->
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Astro 5](https://img.shields.io/badge/Astro-5.0-BC52EE?style=for-the-badge&logo=astro&logoColor=white)](https://astro.build/)
[![Tailwind CSS v4](https://img.shields.io/badge/Tailwind_CSS-v4.0-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0%2B-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![uv](https://img.shields.io/badge/uv-Package_Manager-DE5FE9?style=for-the-badge&logo=astral&logoColor=white)](https://astral.sh/uv)
[![pnpm](https://img.shields.io/badge/pnpm-9.x-F69220?style=for-the-badge&logo=pnpm&logoColor=white)](https://pnpm.io/)
[![Argon2id](https://img.shields.io/badge/Security-Argon2id%20%2B%20JWT-critical?style=for-the-badge&logo=auth0&logoColor=white)](https://github.com/P-H-C/phc-winner-argon2)

<p align="center">
  <b>Paso Molino, Montevideo, Uruguay</b> • <b>WhatsApp Comercial: +598 95 250 673</b>
</p>

</div>

---

## 🎯 Visión y Propósito del Sistema

El negocio operaba históricamente sobre un archivo Excel de 311 productos, con múltiples listas de precios y 19 conflictos matemáticos de margen. Esta plataforma moderna sustituye la complejidad manual por un ecosistema web seguro, accesible desde computadoras, tablets y celulares:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Ecosistema 2 Rodríguez                                │
├─────────────────────────┬─────────────────────────┬─────────────────────────┤
│    Catálogo Público     │     Portal Clientes     │    Backoffice Mariana   │
│   (/ y /catalogo)       │       (/portal)         │        (/admin)         │
├─────────────────────────┼─────────────────────────┼─────────────────────────┤
│ • Precios protegidos    │ • Acceso B2B mayorista  │ • Control 311 artículos │
│ • Pedidos WhatsApp      │ • Precios según lista   │ • Alertas stock crítico │
│ • Retiro en Paso Molino │ • Checkout c/flete      │ • Rentabilidad mensual  │
│ • Blindaje proveedores  │ • Descuento de stock    │ • Export/Import Excel   │
└─────────────────────────┴─────────────────────────┴─────────────────────────┘
```

---

## ✨ Características y Módulos Destacados

### 1. 📦 Control de Inventario & Alertas Tempranas (Pilar 1)
- **Descuento Atómico**: En cada orden confirmada, el stock se decrementa bajo transacciones ACID con bloqueo pesimista (`SELECT ... FOR UPDATE`), evitando sobreventas.
- **Semáforo Visual**: Indicadores en tiempo real (Rojo = Agotado, Amarillo = Stock Crítico $\le$ umbral, Verde = Disponible).
- **Ajuste Express**: Modal instantáneo para modificar existencias físicas sin recargar la página.

### 2. 🛡️ Blindaje de Proveedores & Exportación Excel (Pilar 2)
- **Secreto Comercial Garantizado**: La información de costos y proveedores (`Moizo`, etc.) está estrictamente restringida al rol `ADMIN`. Los contratos de cliente y público omiten estos campos a nivel de serializador.
- **Exportación de Catálogo Excel/CSV**: Descarga con formato `UTF-8-BOM` y separador `;`, garantizando apertura limpia en Microsoft Excel sin deformar tildes ni caracteres uruguayos.
- **Carga Masiva Drag & Drop**: Zona para arrastrar planillas CSV y actualizar cientos de productos en segundos.
- **Archivos Multimedia**: Carga directa de fotos de artículos y fichas técnicas en PDF por arrastre.

### 3. 📊 Mini-Contabilidad & Gráfica de Rentabilidad (Pilar 3)
- **Aritmética Financiera Estricta**: Cálculos basados en `Decimal` (cero flotantes con pérdida de precisión).
- **Métricas Consolidadas**:
  $$\text{Margen Bruto} = \text{Facturación Bruta} - \text{Costo de Mercadería Vendida (COGS)}$$
  $$\text{Ganancia Neta} = \text{Margen Bruto} - \text{Gastos Operativos}$$
- **Gráfica de Rentabilidad Nativa SVG**: Visualización responsiva y ultra-liviana de la evolución de los últimos 6 meses comparando ingresos, egresos y beneficio neto.
- **Gestor de Gastos Operativos**: Registro ágil clasificado por rubro (Alquiler Paso Molino, Fletes, Packaging, BPS/DGI, Sueldos).

### 4. 🧾 Presupuestos Corporativos Formales en PDF
- Emisión inmediata de presupuestos PDF vía **ReportLab** con logo corporativo, membrete oficial, desglose de ítems con IVA y exclusión absoluta de costos internos.

---

## 🏛️ Arquitectura Hexagonal del Backend

```
backend/
├── src/
│   ├── domain/               # Entidades de negocio, enums y servicios puros
│   │   ├── models/           # Product, Order, Expense, CommercialList
│   │   └── services/         # PricingService, FinancialService (Decimal)
│   ├── application/          # Casos de uso y DTOs de Pydantic v2
│   │   ├── dtos/             # Schemas tipados sin Any
│   │   └── use_cases/        # Catalog, Orders, Finances, Quotes, Attachments
│   ├── infrastructure/       # Adaptadores de entrada y salida
│   │   ├── api/v1/           # Controladores FastAPI (Auth, Admin, Portal, Finances)
│   │   ├── db/               # PostgreSQL, SQLAlchemy ORM y migraciones Alembic
│   │   └── security/         # Hasheo Argon2id y tokens JWT
│   └── main.py               # Ensamblador de la aplicación y middlewares CORS
```

---

## ⚡ Guía de Inicio Rápido (Local)

### 1. Clonar el repositorio
```bash
git clone https://github.com/Ponce1969/E-commerce-MVP.git
cd E-commerce-MVP
```

### 2. Base de Datos (Docker)
```bash
cd backend
docker compose up -d
```
> La base de datos queda expuesta de manera aislada en el puerto `5436` para evitar colisiones con otros servicios PostgreSQL locales.

### 3. Servidor Backend (FastAPI + uv)
```bash
cd backend
uv run alembic upgrade head
uv run uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload
```
- **Documentación Interactiva Swagger**: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)

### 4. Servidor Frontend (Astro 5 + Tailwind)
```bash
cd frontend
pnpm install
pnpm run dev --host 127.0.0.1 --port 4321
```
- **Catálogo Web**: [http://localhost:4321](http://localhost:4321)
- **Portal B2B**: [http://localhost:4321/portal](http://localhost:4321/portal)
- **Backoffice Mariana**: [http://localhost:4321/admin](http://localhost:4321/admin)

---

## 🧪 Pruebas Automatizadas y Calidad

El proyecto cuenta con un pipeline estricto de calidad de código:

```bash
# Backend (Pruebas unitarias e integración)
cd backend
uv run pytest -v

# Linter y formateador (Ruff)
uv run ruff check .

# Tipado estático estricto (Mypy)
uv run mypy src tests

# Frontend (Compilación estática Astro)
cd frontend
pnpm run build
```

---

## 💳 Formas de Pago Integradas

- **Transferencia BROU / Redes de Cobranza**:
  - Titular: Mariana Moreira
  - Caja de Ahorro en Pesos: `110975226-00001`
  - Redes (Abitab / Redpagos): `601-0551790`
- **Mercado Pago**: Hasta 12 cuotas.

---

<div align="center">

Desarrollado con dedicación técnica y arquitectura sólida para **2 Rodríguez Distribuidora**.  
© 2026 Todos los derechos reservados.

</div>
