# SPEC-004: Listas de Precios Dinámicas (N:M), Redondeo Comercial y Autonomía de Catálogo

- **Estado:** APPROVED / READY FOR IMPLEMENTATION
- **Fecha:** Noviembre 2026
- **Ámbito:** Backend (FastAPI, SQLAlchemy 2.0, Alembic), Admin UI (FastAPI Templates / Jinja2 / Astro)
- **Prioridad:** Alta (Requerimiento operativo de Mariana Moreira)
- **Objetivo:** Brindar autonomía total a la administración para crear segmentos de clientes (listas de precios), permitir asignación granular y arbitraria de artículos por lista (evitando mezclar rubros no afines), aplicar redondeo comercial automático a pesos uruguayos enteros y propagar precios de forma consistente sin conflictos de sincronización.

---

## 1. Contexto y Diagnóstico de Negocio

Mariana Moreira (Dos Rodríguez Distribuidora) atiende diversos segmentos B2B/B2C en Uruguay:
- Residenciales y Hogares de Ancianos (foco en incontinencia, cuidado e higiene).
- Hoteles Boutique / Gastronomía (rollos de cocina, servilletas, desengrasantes).
- Empresas de Limpieza (química pesada a granel, hipoclorito concentrado).
- Futuros segmentos en rápida expansión: Veterinarias, Odontología/Ortopedia, Lavaderos.

### Problemas Actuales Detectados en la Operación:
1. **Inflexibilidad en Asignación de Listas:** El panel actual fuerza una disyuntiva binaria ("mantener la lista actual" o "aplicar a todas las 5 listas"). No permite asociar un artículo a un subconjunto arbitrario (ej. disponible solo en Residenciales y Hoteles, pero excluido de Empresas de Limpieza).
2. **Conflictos Históricos por Desincronización de Precios:** Al modificar el costo o margen de un artículo en una lista, el cambio no se refleja en las demás donde el artículo participa, generando registros discordantes.
3. **Cálculo Manual de Centavos:** Mariana debe redondear precios con calculadora externa. Se requiere redondeo comercial uruguayo automático a números enteros.
4. **Dependencia Técnica:** En 6 meses sumó 4 listas. Si la creación de listas depende de migraciones o Enums en código, el desarrollador se transforma en un cuello de botella constante.

---

## 2. Requerimientos Funcionales y Reglas de Negocio

### RF-01: Redondeo Comercial a Pesos Uruguayos Enteros (UYU)
Todo cálculo automático de precio de venta final debe cuantizarse a números enteros mediante la regla estándar uruguaya (`ROUND_HALF_UP` a 0 decimales):

$$\text{Centavos } \in [0.01, 0.49] \implies \text{redondea hacia abajo}$$
$$\text{Centavos } \in [0.50, 0.99] \implies \text{redondea hacia arriba}$$

**Contabilidad estricta:** Todos los valores se manipulan y persisten como `Decimal` (`Numeric(10, 2)` en PostgreSQL). El precio de venta exhibido y persistido no debe contener fracciones de peso (ej. `$154.00`, nunca `$154.38`).

### RF-02: Asignación Arbitraria a Listas de Precios (Relación N:M)
- Un producto puede pertenecer a $0, 1, 2, \dots, N$ listas de precios simultáneamente.
- La interfaz de administración debe reemplazar el selector excluyente por un grupo de selectores independientes (checkboxes dinámicos).
- Al guardar el producto, el backend debe sincronizar la relación de pertenencia: vincular las listas seleccionadas y desvincular las omitidas sin borrar registros históricos de compras.

### RF-03: Propagación Coherente de Precios
- Al actualizar costo, margen o precio base de un producto, el valor debe actualizarse de manera automática y transaccional en todas las listas donde dicho producto se encuentre activo.
- No deben quedar precios huérfanos o desactualizados entre diferentes listas activas.

### RF-04: Autonomía Administrativa (ABM de Listas)
- Mariana debe poder crear, renombrar o pausar listas de precios directamente desde el panel de administración sin intervención del equipo técnico ni despliegues de código.
- Los checkboxes del formulario de producto deben renderizarse de forma dinámica consultando las listas activas de la base de datos.

### 2.5 Consolidación Canónica de Catálogo y Saneamiento de Duplicados

#### Diagnóstico del Defecto en Producción
Se detectó que el catálogo actual fragmentó entidades idénticas en múltiples filas de la tabla `products` para simular la asignación a listas de precios (ejemplo: *Vinagre 5L* clonado bajo `ID 82` en *Varios*, `ID 153` en *Limpieza Profesional* e `ID 223` en *Suavizado Y Perfumado*). Esto ocasiona:
1. **Corrupción taxonómica:** Un mismo artículo físico queda asociado a categorías contradictorias.
2. **Desincronización de inventario:** El stock se divide o queda en 0 en clones no atendidos.
3. **Conflictos históricos de precios:** Actualizar un clon no propaga el cambio a las demás listas.

#### Requerimientos de Corrección Arquitectural
1. **Entidad Canónica Única (`Product`):**
   - Cada artículo físico en el galpón debe existir exactamente una vez en `products`.
   - Posee una única categoría/rubro real (`category_id` / `department`).
   - El inventario físico (`stock_quantity`) es centralizado y único.
2. **Desacoplamiento Relacional (`product_price_list_items`):**
   - La presencia en listas se modela estrictamente a través de la tabla de unión N:M `(product_id, price_list_id, price, is_active)`.
3. **Script de Migración y Fusión (`scripts/deduplicate_products.py`):**
   - Identificar grupos de duplicados mediante normalización de texto (`LOWER(TRIM(name))` + presentación/litros).
   - Conservar como registro maestro el ID más antiguo o con datos más completos.
   - Migrar las listas de precios de los clones hacia la tabla intermedia asociada al ID maestro.
   - Reasignar referencias foráneas existentes (órdenes históricas, logs) hacia el ID maestro y eliminar de forma segura (`soft delete` o borrado físico controlado) los registros clonados redundantes.

### 2.6 Acción de Eliminación Segura con Modal de Doble Confirmación

#### Requerimiento de UX (Prevención de Errores)
1. **Nuevo Botón en Columna de Acciones:**
   - Incorporar el botón `Eliminar` (estilo destructivo/rojo suave) en la fila de cada producto junto a `Editar`, `Archivos`, `Stock` y `Precios`.
2. **Flujo de Confirmación en Dos Pasos (Pop-up Modal):**
   - **Paso 1 (Trigger):** Al hacer clic en `Eliminar`, no se ejecuta ninguna acción inmediata en la base de datos.
   - **Paso 2 (Modal Preventivo):** Se abre un diálogo modal emergente con foco bloqueante:
     - Título: *"¿Estás segura de eliminar este artículo?"*
     - Mensaje: *"Estás a punto de eliminar **[Nombre del Producto]**. Esta acción no se puede deshacer."*
     - Acciones:
       - Botón secundario: *"Cancelar"* (cierra el diálogo sin modificar el registro).
       - Botón principal destructivo: *"Sí, eliminar artículo"* (dispara la mutación hacia el backend).

#### Lógica de Negocio y Persistencia (Backend)
- **Endpoint:** `DELETE /api/v1/admin/products/{id}`.
- **Validación de Integridad:**
  - Si el producto **no posee historial de pedidos ni ventas**: se realiza la eliminación física (`hard delete`) de la fila y de sus vínculos en `product_price_list_items`.
  - Si el producto **posee pedidos históricos asociados**: para preservar la integridad contable y transaccional, se aplica un borrado lógico (*soft delete*: `is_deleted = True` o `archived_at = now()`), retirándolo de la vista del catálogo y de la grilla de administración activa sin romper claves foráneas históricas.

---

## 3. Arquitectura y Modelo de Datos

### 3.1. Esquema Relacional en PostgreSQL

```sql
-- Tabla dinámica de listas de precios (elimina Enums rígidos)
CREATE TABLE IF NOT EXISTS price_lists (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,       -- ej: 'RESIDENCIALES', 'HOTELES', 'VETERINARIAS'
    name VARCHAR(100) NOT NULL,             -- ej: 'Residenciales y Casas de Salud'
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tabla intermedia de asociación Producto <-> Lista de Precios
CREATE TABLE IF NOT EXISTS product_price_list_items (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    price_list_id INTEGER NOT NULL REFERENCES price_lists(id) ON DELETE RESTRICT,
    sale_price NUMERIC(10, 2) NOT NULL,     -- Guardado con .00 (redondeado a entero)
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT uq_product_price_list UNIQUE (product_id, price_list_id)
);
```

### 3.2. Dominio y Utilidad de Redondeo (Python 3.12+ / Decimal)

```python
from decimal import Decimal, ROUND_HALF_UP


def round_commercial_uyu(amount: Decimal) -> Decimal:
    """
    Aplica redondeo comercial a pesos uruguayos enteros:
    - 0.01 a 0.49 redondea hacia abajo.
    - 0.50 a 0.99 redondea hacia arriba.
    Mantiene tipo Decimal con precisión de centavos .00.
    """
    return amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP).quantize(Decimal("0.01"))
```

---

## 4. Plan de Implementación por Fases (Work Breakdown Structure)

### Fase 1: Motor Contable y Migración Dinámica (Inmediato)
- **Migración Alembic:**
  - Crear tabla `price_lists` y migrar las 5 listas actuales como registros semilla (seeds).
  - Crear tabla `product_price_list_items` asegurando constraints únicas e índices en `(product_id, price_list_id)`.
- **Capa de Dominio y Servicios:**
  - Implementar función utilitaria de redondeo `round_commercial_uyu` con tests unitarios exhaustivos.
  - Actualizar el servicio de catálogo para sincronizar la lista de identificadores `price_list_ids: list[int]` recibida en la actualización de producto.
  - Propagar el nuevo precio a todos los registros asociados en `product_price_list_items`.

### Fase 2: Ajustes en UI del Admin (Carga de Artículos)
- Sustituir en la vista de edición de productos el selector de listas por un listado dinámico de checkboxes generados desde `GET /api/v1/admin/price-lists`.
- Ajustar la reactividad en el navegador para que el cálculo bidireccional (costo $\leftrightarrow$ margen $\leftrightarrow$ precio) refleje inmediatamente el número entero redondeado.

### Fase 3: Módulo de Gestión de Listas para Mariana (Autonomía)
- Endpoint `POST /api/v1/admin/price-lists` para creación de nuevas listas.
- Vista sencilla en el panel con tabla de listas existentes y botón modal `+ Crear Nueva Lista`.

---

## 5. Criterios de Aceptación (Definition of Done)

- [ ] Las 5 listas existentes se preservan y cargan dinámicamente desde base de datos.
- [ ] Mariana puede tildar 1, 2 o más listas al editar un artículo sin verse obligada a marcar todas.
- [ ] Modificar el precio de un artículo actualiza el registro en todas las listas donde esté vinculado.
- [ ] Todo precio calculado finaliza en `.00` siguiendo estrictamente la regla de redondeo especificada.
- [ ] El suite de pruebas automáticas (`pytest`) valida los casos borde de redondeo (ej. `$150.49 -> $150.00`, `$150.50 -> $151.00`).
- [ ] Cobertura de tipos estricta (`mypy`) y formato sin observaciones (`ruff`).
