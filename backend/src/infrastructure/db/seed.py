import asyncio
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.services.pricing_service import PricingService
from src.infrastructure.db.models import (
    CommercialListORM,
    ProductORM,
    ProductPriceORM,
)
from src.infrastructure.db.session import Base, async_session_factory, engine

CANONICAL_LISTS = [
    {"name": "Empresas / Limpieza", "description": "Canal corporativo y empresas de limpieza"},
    {"name": "Residenciales", "description": "Residenciales de ancianos y casas de salud"},
    {"name": "Lavandería profesional", "description": "Lavanderías industriales y comerciales"},
    {"name": "Lavandería domiciliaria", "description": "Servicios de lavandería doméstica"},
    {"name": "Automotriz", "description": "Talleres y lavaderos automotrices"},
]

LIST_NAME_NORMALIZATION = {
    "Lavandera profesional": "Lavandería profesional",
    "Lavandera domiciliaria": "Lavandería domiciliaria",
    "Lavanderia profesional": "Lavandería profesional",
    "Lavanderia domiciliaria": "Lavandería domiciliaria",
    "limpieza": "Empresas / Limpieza",
}


def normalize_list_name(raw_name: str) -> str:
    cleaned = raw_name.strip()
    return LIST_NAME_NORMALIZATION.get(cleaned, cleaned)


def parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


async def seed_database(json_path: Path) -> dict[str, int]:
    """Imports 311 catalog products and commercial conditions into PostgreSQL."""
    if not json_path.exists():
        raise FileNotFoundError(f"Source JSON file not found at: {json_path}")

    with open(json_path, encoding="utf-8") as f:
        data: list[dict[str, Any]] = json.load(f)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        list_records = await _seed_commercial_lists(session)
        stats = await _seed_products(session, data, list_records)
        await session.commit()

    return stats


async def _seed_commercial_lists(
    session: AsyncSession,
) -> dict[str, CommercialListORM]:
    list_map: dict[str, CommercialListORM] = {}

    for item in CANONICAL_LISTS:
        stmt = select(CommercialListORM).where(CommercialListORM.name == item["name"])
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            record = CommercialListORM(
                name=item["name"],
                description=item["description"],
                is_active=True,
            )
            session.add(record)
            await session.flush()

        list_map[item["name"]] = record

    return list_map


async def _seed_products(
    session: AsyncSession,
    raw_products: list[dict[str, Any]],
    list_map: dict[str, CommercialListORM],
) -> dict[str, int]:
    total_products = 0
    total_prices = 0
    total_conflicts = 0
    incomplete_drafts = 0

    for item in raw_products:
        prod_id = int(item["id"])
        name = str(item["nombre"]).strip()
        provider = str(item["proveedor"]).strip() if item.get("proveedor") else None
        presentation = str(item["presentacion"]).strip() if item.get("presentacion") else None
        category = str(item.get("categoria") or "General").strip()
        is_inactive = bool(item.get("inactivo", False))

        raw_cost = parse_decimal(item.get("costo"))
        raw_recargo = parse_decimal(item.get("recargo"))
        conflict_list: list[str] = item.get("conflictos") or []
        has_any_conflict = len(conflict_list) > 0

        if not provider or not presentation or raw_cost is None or raw_recargo is None:
            incomplete_drafts += 1

        product = ProductORM(
            id=prod_id,
            name=name,
            provider=provider,
            presentation=presentation,
            category=category,
            iva_rate=Decimal("0.22"),
            is_published=False,  # Unapproved / safe default for MVP
            is_active=not is_inactive,
        )
        session.add(product)
        await session.flush()
        total_products += 1

        raw_lists = item.get("listas") or []
        precios_originales = item.get("preciosOriginales") or {}

        # If item has no explicit lists, attach to all canonical lists
        effective_lists = raw_lists if raw_lists else list_map.keys()

        for raw_list_name in effective_lists:
            norm_name = normalize_list_name(raw_list_name)
            comm_list = list_map.get(norm_name)
            if not comm_list:
                continue

            # Original price if present
            orig_price_val = None
            for p_key, p_val in precios_originales.items():
                if normalize_list_name(p_key) == norm_name:
                    orig_price_val = parse_decimal(p_val)
                    break

            # Calculate price if not explicitly in preciosOriginales
            price_val = orig_price_val
            if price_val is None and raw_cost is not None and raw_recargo is not None:
                price_val = PricingService.calculate_price_iva_inc(raw_cost, raw_recargo)

            # Detect if this list is specifically affected by conflict
            list_conflicts = [
                c for c in conflict_list if norm_name in c or normalize_list_name(c) in norm_name
            ]
            has_list_conflict = len(list_conflicts) > 0 or (
                has_any_conflict and len(conflict_list) == 1
            )
            detail = (
                "; ".join(list_conflicts)
                if list_conflicts
                else ("; ".join(conflict_list) if has_any_conflict else None)
            )

            if has_list_conflict:
                total_conflicts += 1

            price_record = ProductPriceORM(
                product_id=product.id,
                commercial_list_id=comm_list.id,
                cost_iva_inc=raw_cost,
                markup_percentage=raw_recargo,
                price_iva_inc=price_val,
                has_conflict=has_list_conflict,
                conflict_detail=detail,
            )
            session.add(price_record)
            total_prices += 1

    return {
        "total_products": total_products,
        "total_prices": total_prices,
        "total_conflicts": total_conflicts,
        "incomplete_drafts": incomplete_drafts,
    }


if __name__ == "__main__":
    file_path = Path("data/2R_respaldo_original_intacto.json")
    print(f"Starting seed from: {file_path}")
    result = asyncio.run(seed_database(file_path))
    print(f"Seed completed successfully: {result}")
