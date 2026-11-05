#!/usr/bin/env python3
"""
deduplicate_products.py
Identifica y fusiona productos duplicados en el catálogo (ej. IDs 82, 153, 223),
consolidándolos en una entidad canónica única con inventario centralizado
y vinculando sus listas de precios a la tabla N:M product_price_list_items.

Uso:
    python scripts/deduplicate_products.py --dry-run
    python scripts/deduplicate_products.py --apply
"""

import argparse
import asyncio
import os
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

# Agregar backend al PYTHONPATH de forma agnóstica (local o dentro del contenedor)
SCRIPT_DIR = Path(__file__).resolve().parent
if (Path("/app/src")).exists():
    BACKEND_DIR = Path("/app")
elif (SCRIPT_DIR.parent / "backend" / "src").exists():
    BACKEND_DIR = SCRIPT_DIR.parent / "backend"
else:
    BACKEND_DIR = SCRIPT_DIR

sys.path.insert(0, str(BACKEND_DIR))
if BACKEND_DIR.exists():
    os.chdir(BACKEND_DIR)


def normalize_text(text: str | None) -> str:
    """Normaliza texto removiendo acentos, espacios extra y pasando a minúsculas."""
    if not text:
        return ""
    # Quitar acentos
    normalized = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in normalized if not unicodedata.combining(c))
    # Unificar caracteres y minúsculas
    cleaned = re.sub(r"\s+", " ", stripped).strip().lower()
    return cleaned


def build_dedup_key(name: str, presentation: str | None) -> str:
    """Genera clave canónica para agrupar duplicados."""
    norm_name = normalize_text(name)
    norm_pres = normalize_text(presentation)
    # Estandarizar presentaciones comunes (ej. 5l, 5 l, 5 litros)
    norm_pres = re.sub(r"(\d+)\s*(l|lt|lts|litros|litro)\b", r"\1l", norm_pres)
    norm_pres = re.sub(r"(\d+)\s*(ml|cc)\b", r"\1ml", norm_pres)
    return f"{norm_name}___{norm_pres}"


async def find_and_merge_duplicates(dry_run: bool = True) -> dict[str, Any]:
    from sqlalchemy import select, update
    from sqlalchemy.orm import selectinload
    from src.infrastructure.db.models import (
        OrderItemORM,
        ProductORM,
        ProductPriceListItemORM,
        ProductPriceORM,
    )
    from src.infrastructure.db.session import async_session_factory

    stats = {
        "total_products": 0,
        "duplicate_groups": 0,
        "clones_merged": 0,
        "orders_reassigned": 0,
        "price_items_linked": 0,
    }

    async with async_session_factory() as session:
        # 1. Cargar todos los productos activos
        stmt = (
            select(ProductORM)
            .options(
                selectinload(ProductORM.prices),
                selectinload(ProductORM.price_list_items),
            )
            .order_by(ProductORM.id.asc())
        )
        result = await session.execute(stmt)
        products = list(result.scalars().all())
        stats["total_products"] = len(products)

        # 2. Agrupar por clave canónica
        grouped: dict[str, list[ProductORM]] = defaultdict(list)
        for p in products:
            key = build_dedup_key(p.name, p.presentation)
            grouped[key].append(p)

        duplicate_groups = {k: v for k, v in grouped.items() if len(v) > 1}
        stats["duplicate_groups"] = len(duplicate_groups)

        print(f"\n[INFO] Total productos analizados: {stats['total_products']}")
        print(f"[INFO] Grupos de duplicados encontrados: {stats['duplicate_groups']}\n")

        if not duplicate_groups:
            print("[✓] No se detectaron productos duplicados en el catálogo.")
            return stats

        for _key, prods in duplicate_groups.items():
            # Seleccionar maestro: el que tenga ID más antiguo o datos más completos
            # Puntuamos por completitud de campos
            def score_product(prod: ProductORM) -> tuple[int, int]:
                completeness = sum(
                    [
                        1 if prod.image_url else 0,
                        1 if prod.tech_sheet_url else 0,
                        1 if prod.code else 0,
                        1 if prod.provider else 0,
                        1 if prod.current_stock > 0 else 0,
                    ]
                )
                # Queremos mayor completitud y menor ID (más antiguo)
                return (completeness, -prod.id)

            sorted_prods = sorted(prods, key=score_product, reverse=True)
            master = sorted_prods[0]
            clones = sorted_prods[1:]

            print(
                "--------------------------------------------------------------------------------"
            )
            print(
                f"Grupo: '{master.name}' (Presentación: '{master.presentation or 'N/A'}') -> {len(prods)} registros"
            )
            print(
                f"  -> REGISTRO MAESTRO: ID #{master.id} | Categoría: '{master.category}' | Stock: {master.current_stock}"
            )
            for c in clones:
                print(
                    f"     Clon a fusionar: ID #{c.id} | Categoría: '{c.category}' | Stock: {c.current_stock}"
                )

            if dry_run:
                stats["clones_merged"] += len(clones)
                continue

            # --- APLICACIÓN DE FUSIÓN DENTRO DE TRANSACCIÓN ---
            # A. Consolidar inventario y campos faltantes en el maestro
            total_stock = master.current_stock
            for c in clones:
                total_stock += c.current_stock
                if not master.image_url and c.image_url:
                    master.image_url = c.image_url
                if not master.tech_sheet_url and c.tech_sheet_url:
                    master.tech_sheet_url = c.tech_sheet_url
                if not master.code and c.code:
                    master.code = c.code
                if not master.provider and c.provider:
                    master.provider = c.provider

            master.current_stock = total_stock

            # B. Migrar listas de precios hacia el maestro en product_price_list_items
            existing_pl_ids = {item.price_list_id for item in master.price_list_items}
            for c in clones:
                for c_item in c.price_list_items:
                    if c_item.price_list_id not in existing_pl_ids:
                        new_item = ProductPriceListItemORM(
                            product_id=master.id,
                            price_list_id=c_item.price_list_id,
                            sale_price=c_item.sale_price,
                            is_active=c_item.is_active,
                        )
                        session.add(new_item)
                        existing_pl_ids.add(c_item.price_list_id)
                        stats["price_items_linked"] += 1

            # Migrar precios legados de product_prices hacia el maestro
            existing_legacy_ids = {p.commercial_list_id for p in master.prices}
            for c in clones:
                for c_price in c.prices:
                    if c_price.commercial_list_id not in existing_legacy_ids:
                        new_legacy = ProductPriceORM(
                            product_id=master.id,
                            commercial_list_id=c_price.commercial_list_id,
                            cost_iva_inc=c_price.cost_iva_inc,
                            markup_percentage=c_price.markup_percentage,
                            price_iva_inc=c_price.price_iva_inc,
                            has_conflict=c_price.has_conflict,
                            conflict_detail=c_price.conflict_detail,
                        )
                        session.add(new_legacy)
                        existing_legacy_ids.add(c_price.commercial_list_id)

            # C. Reasignar pedidos históricos hacia el maestro
            for c in clones:
                order_update_stmt = (
                    update(OrderItemORM)
                    .where(OrderItemORM.product_id == c.id)
                    .values(product_id=master.id)
                )
                order_res = await session.execute(order_update_stmt)
                rc = getattr(order_res, "rowcount", 0)
                if rc and rc > 0:
                    stats["orders_reassigned"] += rc

                # D. Desactivar y marcar el clon como fusionado
                c.is_active = False
                c.is_published = False
                c.name = f"[FUSIONADO #{master.id}] {c.name}"
                stats["clones_merged"] += 1

        if not dry_run:
            await session.commit()
            print("\n[✓] Transacción confirmada exitosamente en la base de datos.")
        else:
            print("\n[DRY-RUN] Simulación completa. Ningún dato fue modificado.")

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Saneamiento de catálogo y consolidación de clones canónicos."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica los cambios en la base de datos (por defecto es --dry-run)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Simula la deduplicación sin modificar registros",
    )
    args = parser.parse_args()

    is_apply = args.apply
    dry_run = not is_apply

    print("============================================================")
    print(" SANEAMIENTO CANÓNICO DE PRODUCTOS - DOS RODRÍGUEZ")
    print(f" Modo: {'APLICAR CAMBIOS (--apply)' if is_apply else 'SIMULACIÓN (--dry-run)'}")
    print("============================================================")

    asyncio.run(find_and_merge_duplicates(dry_run=dry_run))


if __name__ == "__main__":
    main()
