from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.application.dtos.catalog_dto import (
    CategoryCreateDTO,
    CategoryUpdateDTO,
    ProductCreateDTO,
    ProductUpdateDTO,
)
from src.application.use_cases.catalog.admin_catalog import AdminCatalogUseCase
from src.domain.exceptions import (
    BusinessRuleViolationException,
)
from src.infrastructure.db.models import (
    CategoryORM,
    PriceListORM,
    ProductORM,
)


@pytest.mark.asyncio
async def test_get_categories_returns_alphabetical_with_counts() -> None:
    session = AsyncMock()
    cat1 = CategoryORM(id=1, name="Cocina", is_active=True)
    cat2 = CategoryORM(id=2, name="Lavandería", is_active=True)

    exec_result = MagicMock()
    exec_result.all.return_value = [(cat1, 10), (cat2, 5)]
    session.execute.return_value = exec_result

    use_case = AdminCatalogUseCase(session)
    categories = await use_case.get_categories()

    assert len(categories) == 2
    assert categories[0].name == "Cocina"
    assert categories[0].product_count == 10
    assert categories[1].name == "Lavandería"
    assert categories[1].product_count == 5


@pytest.mark.asyncio
async def test_create_category_sanitizes_and_enforces_unique_name() -> None:
    session = AsyncMock()
    session.add = MagicMock()

    # 1. Unique name -> success
    exec_empty = MagicMock()
    exec_empty.scalar_one_or_none.return_value = None

    exec_max_id = MagicMock()
    exec_max_id.scalar.return_value = 29

    session.execute.side_effect = [exec_empty, exec_max_id]

    use_case = AdminCatalogUseCase(session)
    dto = CategoryCreateDTO(name="   Lavado Principal   ", description="Detergentes y aditivos")
    created = await use_case.create_category(dto)

    assert created.id == 30
    assert created.name == "Lavado Principal"
    assert created.description == "Detergentes y aditivos"
    session.add.assert_called_once()
    session.commit.assert_awaited()

    # 2. Duplicate name (case-insensitive) -> raises BusinessRuleViolationException
    session.reset_mock()
    existing_cat = CategoryORM(id=1, name="Lavado Principal", is_active=True)
    exec_existing = MagicMock()
    exec_existing.scalar_one_or_none.return_value = existing_cat
    session.execute.side_effect = None
    session.execute.return_value = exec_existing

    with pytest.raises(BusinessRuleViolationException, match="Ya existe una categoría"):
        await use_case.create_category(CategoryCreateDTO(name="lavado principal", description=None))


@pytest.mark.asyncio
async def test_update_category_renames_and_syncs_products() -> None:
    session = AsyncMock()
    cat = CategoryORM(id=3, name="Limpieza Pisos", is_active=True)

    # 1st call: find category
    res_find = MagicMock()
    res_find.scalar_one_or_none.return_value = cat

    # 2nd call: check duplicate name
    res_dup = MagicMock()
    res_dup.scalar_one_or_none.return_value = None

    # 3rd call: update products.category (exec)
    res_upd = MagicMock()

    # 4th call: count products
    res_count = MagicMock()
    res_count.scalar.return_value = 12

    session.execute.side_effect = [res_find, res_dup, res_upd, res_count]

    use_case = AdminCatalogUseCase(session)
    dto = CategoryUpdateDTO(name="Pisos y Superficies", description=None, is_active=True)
    updated = await use_case.update_category(3, dto)

    assert updated.name == "Pisos y Superficies"
    assert updated.product_count == 12
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_update_product_atomic_nm_sync_and_primary_category() -> None:
    session = AsyncMock()
    product = ProductORM(
        id=10,
        name="Bio 100 ED",
        category="General",
        categories=[],
        prices=[],
        price_list_items=[],
    )

    cat1 = CategoryORM(id=101, name="Prelavado", is_active=True)
    cat2 = CategoryORM(id=102, name="Lavado Principal", is_active=True)

    # 1. Product lookup
    res_prod = MagicMock()
    res_prod.scalar_one_or_none.return_value = product

    # 2. Categories lookup by IDs
    res_cats = MagicMock()
    res_cats.scalars.return_value.all.return_value = [cat1, cat2]

    session.execute.side_effect = [res_prod, res_cats]

    use_case = AdminCatalogUseCase(session)
    dto = ProductUpdateDTO(
        name="Bio 100 ED Super",
        category=None,
        category_ids=[102, 101],  # Lavado Principal first, then Prelavado
        code=None,
        presentation=None,
        provider=None,
        iva_rate=Decimal("0.22"),
    )
    result = await use_case.update_product_info(10, dto)

    # Atomically attached both categories
    assert len(product.categories) == 2
    assert product.categories[0].id == 102
    assert product.categories[1].id == 101
    # Primary category synced to first element in category_ids
    assert product.category == "Lavado Principal"
    assert result.category == "Lavado Principal"
    assert result.category_ids == [102, 101]  # 'Lavado Principal' comes before 'Prelavado'
    assert len(result.categories) == 2
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_create_product_with_category_ids() -> None:
    session = AsyncMock()
    session.add = MagicMock()

    # max id
    res_max = MagicMock()
    res_max.scalar.return_value = 50

    # category lookup
    cat_cocina = CategoryORM(id=5, name="Cocina", is_active=True)
    res_cats = MagicMock()
    res_cats.scalars.return_value.all.return_value = [cat_cocina]

    # price lists lookup
    pl = PriceListORM(id=1, code="RESIDENCIALES", name="Residenciales", is_active=True)
    res_pls = MagicMock()
    res_pls.scalars.return_value.all.return_value = [pl]

    # commercial lists lookup (for legacy prices)
    comm_list = MagicMock()
    comm_list.id = 1
    res_comm = MagicMock()
    res_comm.scalars.return_value.all.return_value = [comm_list]

    # reload product query
    reloaded_prod = ProductORM(
        id=51,
        name="Detergente Vajilla Pro",
        category="Cocina",
        categories=[cat_cocina],
        prices=[],
        price_list_items=[],
        is_published=False,
        is_active=True,
    )
    res_reload = MagicMock()
    res_reload.scalar_one.return_value = reloaded_prod

    session.execute.side_effect = [res_max, res_cats, res_pls, res_comm, res_reload]

    use_case = AdminCatalogUseCase(session)
    dto = ProductCreateDTO(
        name="Detergente Vajilla Pro",
        category="IgnoredWhenCategoryIdsProvided",
        category_ids=[5],
        cost_iva_inc=Decimal("100"),
        markup_percentage=Decimal("50"),
        current_stock=0,
    )
    result = await use_case.create_product(dto)

    assert result.category == "Cocina"
    assert result.category_ids == [5]
    assert len(result.categories) == 1
    assert result.categories[0].name == "Cocina"
