import contextlib
import csv
import io
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import ProductORM


class InventoryIOUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def export_inventory_csv(self) -> bytes:
        stmt = select(ProductORM).order_by(ProductORM.id.asc())
        result = await self.session.execute(stmt)
        products = result.scalars().all()

        output = io.StringIO()
        # Semicolon is standard for Excel in Spanish (Uruguay/Argentina)
        writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(
            [
                "ID",
                "Codigo",
                "Nombre",
                "Presentacion",
                "Proveedor",
                "Categoria",
                "Stock Actual",
                "Alerta Minima",
                "Permitir Backorder",
            ]
        )

        for p in products:
            writer.writerow(
                [
                    p.id,
                    p.code or "",
                    p.name,
                    p.presentation or "",
                    p.provider or "",
                    p.category,
                    p.current_stock,
                    p.min_stock_alert,
                    "SI" if p.allow_backorder else "NO",
                ]
            )

        # Prepend UTF-8 BOM so Excel opens with correct Spanish accents
        return output.getvalue().encode("utf-8-sig")

    async def import_inventory_csv(self, content_bytes: bytes) -> dict[str, Any]:
        text = ""
        for encoding in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
            try:
                text = content_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        if not text:
            return {"updated_count": 0, "errors": ["No se pudo decodificar el archivo"]}

        # Detect delimiter: semicolon or comma
        first_line = text.splitlines()[0] if text.splitlines() else ""
        delimiter = ";" if ";" in first_line else ","

        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        if not reader.fieldnames:
            return {"updated_count": 0, "errors": ["El archivo CSV no contiene encabezados."]}

        # Normalize field names
        field_map = {fn.strip().lower(): fn for fn in reader.fieldnames}

        id_col = None
        for candidate in ["id", "código", "codigo"]:
            if candidate in field_map:
                id_col = field_map[candidate]
                break

        stock_col = None
        for candidate in ["stock actual", "stock", "current_stock", "existencia", "cantidad"]:
            if candidate in field_map:
                stock_col = field_map[candidate]
                break

        min_col = None
        for candidate in [
            "alerta minima",
            "alerta mínima",
            "alerta",
            "min_stock_alert",
            "stock minimo",
            "stock mínimo",
        ]:
            if candidate in field_map:
                min_col = field_map[candidate]
                break

        backorder_col = None
        for candidate in ["permitir backorder", "backorder", "allow_backorder"]:
            if candidate in field_map:
                backorder_col = field_map[candidate]
                break

        if not id_col or not stock_col:
            return {
                "updated_count": 0,
                "errors": [
                    f"Faltan columnas obligatorias. Columnas detectadas: {list(reader.fieldnames)}. Se requiere al menos 'ID' y 'Stock Actual'."
                ],
            }

        stmt = select(ProductORM)
        res = await self.session.execute(stmt)
        products_map = {p.id: p for p in res.scalars().all()}

        updated_count = 0
        errors: list[str] = []

        for row_idx, row in enumerate(reader, start=2):
            raw_id = (row.get(id_col) or "").strip()
            raw_stock = (row.get(stock_col) or "").strip()

            if not raw_id:
                continue

            try:
                prod_id = int(raw_id)
            except ValueError:
                errors.append(f"Fila {row_idx}: ID '{raw_id}' no es un entero válido.")
                continue

            product = products_map.get(prod_id)
            if not product:
                errors.append(f"Fila {row_idx}: Producto con ID {prod_id} no existe en catálogo.")
                continue

            try:
                stock_val = int(raw_stock)
                if stock_val < 0:
                    errors.append(f"Fila {row_idx}: Stock '{stock_val}' no puede ser negativo.")
                    continue
                product.current_stock = stock_val
            except ValueError:
                errors.append(f"Fila {row_idx}: Stock '{raw_stock}' no es un entero válido.")
                continue

            if min_col and row.get(min_col):
                raw_min = row[min_col].strip()
                with contextlib.suppress(ValueError):
                    product.min_stock_alert = max(0, int(raw_min))

            if backorder_col and row.get(backorder_col):
                raw_bo = row[backorder_col].strip().upper()
                product.allow_backorder = raw_bo in {"SI", "S", "TRUE", "1", "YES"}

            updated_count += 1

        if updated_count > 0:
            await self.session.commit()

        return {
            "updated_count": updated_count,
            "errors": errors[:50],
        }
