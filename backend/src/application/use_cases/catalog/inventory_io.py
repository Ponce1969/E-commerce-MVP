import contextlib
import csv
import io
import math
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.infrastructure.db.models import CommercialListORM, ProductORM, ProductPriceORM


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

    def get_catalog_template_csv(self) -> bytes:
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(
            [
                "Codigo",
                "Nombre",
                "Presentacion",
                "Proveedor",
                "Categoria",
                "Costo_IVA_Inc",
                "Precio_Venta_IVA_Inc",
                "Stock",
                "Alerta_Minima",
                "Publicar",
            ]
        )
        writer.writerow(
            [
                "GAB-001",
                "Silicona Perfumada Auto",
                "500 cc",
                "Química Gabriel",
                "Automotriz",
                "150.00",
                "225.00",
                "20",
                "5",
                "NO",
            ]
        )
        writer.writerow(
            [
                "GAB-002",
                "Cera Líquida Rápida",
                "5 L",
                "Química Gabriel",
                "Automotriz",
                "480.00",
                "720.00",
                "10",
                "3",
                "NO",
            ]
        )
        return output.getvalue().encode("utf-8-sig")

    async def import_catalog_csv(self, content_bytes: bytes) -> dict[str, Any]:
        # Guardrail 1: Max file size 5MB
        if len(content_bytes) > 5 * 1024 * 1024:
            return {
                "created_count": 0,
                "updated_count": 0,
                "total_processed": 0,
                "errors": ["El archivo supera el tamaño máximo permitido de 5 MB."],
            }

        text = ""
        for encoding in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
            try:
                text = content_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        if not text:
            return {
                "created_count": 0,
                "updated_count": 0,
                "total_processed": 0,
                "errors": [
                    "No se pudo decodificar el archivo. Asegúrese de que sea texto CSV válido."
                ],
            }

        # Strip Markdown code fences (e.g. ```csv ... ```) if pasted directly from ChatGPT
        cleaned_lines = [
            line for line in text.strip().splitlines() if not line.strip().startswith("```")
        ]
        text = "\n".join(cleaned_lines)

        first_line = cleaned_lines[0] if cleaned_lines else ""
        delimiter = ";" if ";" in first_line else ("," if "," in first_line else "\t")

        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        if not reader.fieldnames:
            return {
                "created_count": 0,
                "updated_count": 0,
                "total_processed": 0,
                "errors": ["El archivo CSV no contiene encabezados de columnas."],
            }

        field_map = {fn.strip().lower(): fn for fn in reader.fieldnames if fn}

        def find_col(candidates: list[str]) -> str | None:
            for c in candidates:
                if c in field_map:
                    return field_map[c]
            return None

        name_col = find_col(
            ["nombre", "name", "articulo", "artículo", "producto", "descripcion", "descripción"]
        )
        if not name_col:
            return {
                "created_count": 0,
                "updated_count": 0,
                "total_processed": 0,
                "errors": [
                    f"Columna obligatoria 'Nombre' no encontrada. Columnas detectadas: {list(reader.fieldnames)}. Descargue la plantilla oficial."
                ],
            }

        code_col = find_col(["codigo", "código", "code", "sku", "id_articulo"])
        pres_col = find_col(["presentacion", "presentación", "presentation", "medida", "envase"])
        prov_col = find_col(["proveedor", "provider", "marca"])
        cat_col = find_col(["categoria", "categoría", "category", "rubro"])
        cost_col = find_col(["costo_iva_inc", "costo", "cost", "costo con iva", "costo_iva"])
        price_col = find_col(
            ["precio_venta_iva_inc", "precio", "precio_venta", "price", "precio con iva"]
        )
        stock_col = find_col(["stock", "stock actual", "existencia", "cantidad"])
        min_col = find_col(
            ["alerta_minima", "alerta mínima", "alerta", "min_stock_alert", "stock minimo"]
        )
        pub_col = find_col(["publicar", "publicado", "is_published", "publicar en web"])
        img_col = find_col(["foto_url", "imagen_url", "image_url", "foto", "imagen"])
        pdf_col = find_col(["ficha_pdf_url", "tech_sheet_url", "ficha_pdf", "pdf_url", "ficha"])

        # Fetch active commercial lists
        lists_stmt = select(CommercialListORM).where(CommercialListORM.is_active == True)  # noqa: E712
        lists_res = await self.session.execute(lists_stmt)
        active_lists = lists_res.scalars().all()

        # Fetch existing products with prices loaded
        prod_stmt = select(ProductORM).options(selectinload(ProductORM.prices))
        prod_res = await self.session.execute(prod_stmt)
        existing_products = prod_res.scalars().all()

        by_code: dict[str, ProductORM] = {}
        by_name_pres: dict[tuple[str, str], ProductORM] = {}
        for p in existing_products:
            if p.code:
                by_code[p.code.strip().lower()] = p
            norm_key = (p.name.strip().lower(), (p.presentation or "").strip().lower())
            by_name_pres[norm_key] = p

        max_id_stmt = select(func.max(ProductORM.id))
        max_id_res = await self.session.execute(max_id_stmt)
        next_id = (max_id_res.scalar() or 0) + 1

        def parse_dec(val: Any) -> Decimal | None:
            if val is None:
                return None
            s = str(val).strip().replace("$", "").replace(" ", "")
            if not s or s.upper() in {"N/A", "NONE", "NULL", "-", ""}:
                return None
            if "." in s and "," in s:
                s = s.replace(".", "").replace(",", ".")
            elif "," in s:
                s = s.replace(",", ".")
            try:
                return Decimal(s)
            except InvalidOperation:
                return None

        created_count = 0
        updated_count = 0
        errors: list[str] = []

        for row_idx, row in enumerate(reader, start=2):
            raw_name = (row.get(name_col) or "").strip()
            if not raw_name:
                continue

            raw_code = (row.get(code_col) or "").strip() if code_col else ""
            raw_pres = (row.get(pres_col) or "").strip() if pres_col else ""
            raw_prov = (row.get(prov_col) or "").strip() if prov_col else ""
            raw_cat = (row.get(cat_col) or "").strip() if cat_col else ""
            raw_cost_str = (row.get(cost_col) or "").strip() if cost_col else ""
            raw_price_str = (row.get(price_col) or "").strip() if price_col else ""
            raw_stock_str = (row.get(stock_col) or "").strip() if stock_col else ""
            raw_min_str = (row.get(min_col) or "").strip() if min_col else ""
            raw_pub_str = (row.get(pub_col) or "").strip() if pub_col else ""
            raw_img_url = (row.get(img_col) or "").strip() if img_col else ""
            raw_pdf_url = (row.get(pdf_col) or "").strip() if pdf_col else ""

            if len(raw_name) < 2:
                errors.append(
                    f"Fila {row_idx}: El nombre '{raw_name}' es demasiado corto (mínimo 2 caracteres)."
                )
                continue

            cost_val = parse_dec(raw_cost_str) if raw_cost_str else None
            price_val = parse_dec(raw_price_str) if raw_price_str else None

            if raw_cost_str and cost_val is None:
                errors.append(
                    f"Fila {row_idx} ({raw_name}): Costo '{raw_cost_str}' no es un número válido."
                )
                continue
            if raw_price_str and price_val is None:
                errors.append(
                    f"Fila {row_idx} ({raw_name}): Precio '{raw_price_str}' no es un número válido."
                )
                continue

            if cost_val is not None and cost_val < 0:
                errors.append(f"Fila {row_idx} ({raw_name}): El costo no puede ser negativo.")
                continue
            if price_val is not None and price_val < 0:
                errors.append(f"Fila {row_idx} ({raw_name}): El precio no puede ser negativo.")
                continue

            # Gabriel's Rule: If cost given but price not, apply 50% markup rounded up to next integer
            if cost_val is not None and price_val is None:
                price_val = Decimal(str(math.ceil(float(cost_val) * 1.50)))

            markup_pct = None
            if cost_val is not None and price_val is not None:
                if cost_val > 0:
                    markup_pct = round((price_val - cost_val) / cost_val, 4)
                else:
                    markup_pct = Decimal("0.0000")

            stock_val = 0
            if raw_stock_str:
                try:
                    stock_val = max(0, int(raw_stock_str))
                except ValueError:
                    errors.append(
                        f"Fila {row_idx} ({raw_name}): Stock '{raw_stock_str}' no es un entero válido."
                    )
                    continue

            min_alert_val = 5
            if raw_min_str:
                with contextlib.suppress(ValueError):
                    min_alert_val = max(0, int(raw_min_str))

            is_pub = raw_pub_str.upper() in {"SI", "S", "TRUE", "1", "YES", "PUBLICAR"}

            match_prod = None
            if raw_code and raw_code.lower() in by_code:
                match_prod = by_code[raw_code.lower()]
            else:
                key = (raw_name.lower(), raw_pres.lower())
                if key in by_name_pres:
                    match_prod = by_name_pres[key]

            if match_prod:
                match_prod.name = raw_name
                if raw_code:
                    match_prod.code = raw_code
                if raw_pres:
                    match_prod.presentation = raw_pres
                if raw_prov:
                    match_prod.provider = raw_prov
                if raw_cat:
                    match_prod.category = raw_cat
                if raw_stock_str:
                    match_prod.current_stock = stock_val
                if raw_min_str:
                    match_prod.min_stock_alert = min_alert_val
                if raw_pub_str:
                    match_prod.is_published = is_pub
                if raw_img_url:
                    match_prod.image_url = raw_img_url
                if raw_pdf_url:
                    match_prod.tech_sheet_url = raw_pdf_url

                if cost_val is not None or price_val is not None:
                    existing_prices_by_list = {p.commercial_list_id: p for p in match_prod.prices}
                    for cl in active_lists:
                        if cl.id in existing_prices_by_list:
                            p_row = existing_prices_by_list[cl.id]
                            if cost_val is not None:
                                p_row.cost_iva_inc = cost_val
                            if price_val is not None:
                                p_row.price_iva_inc = price_val
                            if markup_pct is not None:
                                p_row.markup_percentage = markup_pct
                        else:
                            p_row = ProductPriceORM(
                                product_id=match_prod.id,
                                commercial_list_id=cl.id,
                                cost_iva_inc=cost_val,
                                price_iva_inc=price_val,
                                markup_percentage=markup_pct,
                                has_conflict=False,
                            )
                            self.session.add(p_row)
                            match_prod.prices.append(p_row)

                updated_count += 1
            else:
                new_prod = ProductORM(
                    id=next_id,
                    name=raw_name,
                    code=raw_code or None,
                    presentation=raw_pres or None,
                    provider=raw_prov or "Química Gabriel",
                    category=raw_cat or "General",
                    iva_rate=Decimal("0.22"),
                    is_published=is_pub,
                    is_active=True,
                    current_stock=stock_val,
                    min_stock_alert=min_alert_val,
                    allow_backorder=False,
                    image_url=raw_img_url or None,
                    tech_sheet_url=raw_pdf_url or None,
                )
                self.session.add(new_prod)
                await self.session.flush()

                new_prod.prices = []
                for cl in active_lists:
                    p_row = ProductPriceORM(
                        product_id=new_prod.id,
                        commercial_list_id=cl.id,
                        cost_iva_inc=cost_val,
                        price_iva_inc=price_val,
                        markup_percentage=markup_pct,
                        has_conflict=False,
                    )
                    self.session.add(p_row)
                    new_prod.prices.append(p_row)

                if raw_code:
                    by_code[raw_code.lower()] = new_prod
                by_name_pres[(raw_name.lower(), raw_pres.lower())] = new_prod

                next_id += 1
                created_count += 1

        if created_count > 0 or updated_count > 0:
            await self.session.commit()

        return {
            "created_count": created_count,
            "updated_count": updated_count,
            "total_processed": created_count + updated_count,
            "errors": errors[:50],
        }
