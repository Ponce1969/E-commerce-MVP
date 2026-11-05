from collections.abc import Coroutine
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from src.application.dtos.catalog_dto import (
    PriceListCreateDTO,
    PriceListUpdateDTO,
    ProductPriceUpdateItemDTO,
)
from src.application.use_cases.catalog.admin_catalog import AdminCatalogUseCase
from src.domain.exceptions import (
    BusinessRuleViolationException,
)
from src.domain.services.pricing_service import round_commercial_uyu
from src.infrastructure.db.models import (
    PriceListORM,
    ProductORM,
    ProductPriceListItemORM,
    ProductPriceORM,
)


def run_coro(coro: Coroutine[Any, Any, Any]) -> Any:
    """Executes a coroutine deterministically without relying on Windows loopback sockets."""
    try:
        return coro.send(None)
    except StopIteration as e:
        return e.value


def test_create_price_list_success() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    exec_result_empty = MagicMock()
    exec_result_empty.scalar_one_or_none.return_value = None

    exec_result_max_id = MagicMock()
    exec_result_max_id.scalar.return_value = 5

    session.execute.side_effect = [exec_result_empty, exec_result_max_id]

    use_case = AdminCatalogUseCase(session)
    dto = PriceListCreateDTO(
        code="veterinarias",
        name="Clínicas Veterinarias",
        description="Sector veterinario",
        is_active=True,
    )
    result = run_coro(use_case.create_price_list(dto))

    assert result.code == "VETERINARIAS"
    assert result.name == "Clínicas Veterinarias"
    assert result.id == 6
    assert session.add.call_count == 2
    session.commit.assert_awaited_once()


def test_create_price_list_duplicate_code_raises_exception() -> None:
    session = AsyncMock()
    existing_list = PriceListORM(id=1, code="RESIDENCIALES", name="Residenciales")
    exec_res = MagicMock()
    exec_res.scalar_one_or_none.return_value = existing_list
    session.execute.return_value = exec_res

    use_case = AdminCatalogUseCase(session)
    dto = PriceListCreateDTO(
        code="residenciales",
        name="Otro Nombre",
        description=None,
        is_active=True,
    )

    try:
        run_coro(use_case.create_price_list(dto))
        raise AssertionError("Se esperaba BusinessRuleViolationException")
    except BusinessRuleViolationException as exc:
        assert "Ya existe una lista de precios con el código 'RESIDENCIALES'" in str(exc)


def test_update_price_list_success() -> None:
    session = AsyncMock()
    pl = PriceListORM(id=2, code="HOTELES", name="Hoteles", is_active=True)
    exec_pl = MagicMock()
    exec_pl.scalar_one_or_none.return_value = pl

    exec_comm = MagicMock()
    exec_comm.scalar_one_or_none.return_value = None

    session.execute.side_effect = [exec_pl, exec_comm]

    use_case = AdminCatalogUseCase(session)
    dto = PriceListUpdateDTO(name="Hoteles y Gastronomía", is_active=False)
    updated = run_coro(use_case.update_price_list(2, dto))

    assert updated.name == "Hoteles y Gastronomía"
    assert updated.is_active is False
    session.commit.assert_awaited_once()


def test_delete_product_soft_delete_when_has_orders() -> None:
    session = AsyncMock()
    prod = ProductORM(id=82, name="Vinagre 5L", is_active=True, is_published=True)

    exec_prod = MagicMock()
    exec_prod.scalar_one_or_none.return_value = prod

    exec_orders = MagicMock()
    exec_orders.scalar.return_value = 3

    session.execute.side_effect = [exec_prod, exec_orders]

    use_case = AdminCatalogUseCase(session)
    result = run_coro(use_case.delete_product(82))

    assert result["action"] == "soft_delete"
    assert prod.is_active is False
    assert prod.is_published is False
    session.delete.assert_not_called()
    session.commit.assert_awaited_once()


def test_delete_product_hard_delete_when_no_orders() -> None:
    session = AsyncMock()
    prod = ProductORM(id=999, name="Producto Huérfano", is_active=True, is_published=True)

    exec_prod = MagicMock()
    exec_prod.scalar_one_or_none.return_value = prod

    exec_orders = MagicMock()
    exec_orders.scalar.return_value = 0

    session.execute.side_effect = [exec_prod, exec_orders]

    use_case = AdminCatalogUseCase(session)
    result = run_coro(use_case.delete_product(999))

    assert result["action"] == "hard_delete"
    session.delete.assert_awaited_once_with(prod)
    session.commit.assert_awaited_once()


def test_update_prices_with_commercial_rounding_and_nm_sync() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    prod = ProductORM(id=10, name="Detergente Enzimático")
    item1 = ProductPriceListItemORM(
        id=1, product_id=10, price_list_id=1, sale_price=Decimal("100.00"), is_active=True
    )
    item2 = ProductPriceListItemORM(
        id=2, product_id=10, price_list_id=2, sale_price=Decimal("100.00"), is_active=True
    )
    prod.price_list_items = [item1, item2]

    legacy1 = ProductPriceORM(
        id=1,
        product_id=10,
        commercial_list_id=1,
        cost_iva_inc=Decimal("80.00"),
        markup_percentage=Decimal("25.00"),
        price_iva_inc=Decimal("100.00"),
        has_conflict=False,
    )
    legacy2 = ProductPriceORM(
        id=2,
        product_id=10,
        commercial_list_id=2,
        cost_iva_inc=Decimal("80.00"),
        markup_percentage=Decimal("25.00"),
        price_iva_inc=Decimal("100.00"),
        has_conflict=False,
    )
    prod.prices = [legacy1, legacy2]

    exec_prod = MagicMock()
    exec_prod.scalar_one_or_none.return_value = prod

    exec_refresh = MagicMock()
    exec_refresh.scalars.return_value.all.return_value = prod.prices

    session.execute.side_effect = [exec_prod, exec_refresh]

    use_case = AdminCatalogUseCase(session)
    price_update = ProductPriceUpdateItemDTO(
        commercial_list_id=2,
        cost_iva_inc=Decimal("100.00"),
        markup_percentage=Decimal("50.49"),
        price_iva_inc=Decimal("150.49"),
    )
    run_coro(
        use_case.update_prices(
            product_id=10,
            price_updates=[price_update],
            price_list_ids=[2, 3],
            cost_iva_inc=Decimal("100.00"),
            price_iva_inc=Decimal("150.49"),
        )
    )

    session.delete.assert_awaited_once_with(item1)
    assert item2.sale_price == Decimal("150.00")
    added_pli = [
        args[0]
        for args, _ in session.add.call_args_list
        if isinstance(args[0], ProductPriceListItemORM)
    ]
    assert any(pli.price_list_id == 3 and pli.sale_price == Decimal("150.00") for pli in added_pli)
    session.commit.assert_awaited_once()


def test_round_commercial_uyu_always_ends_in_two_zeros() -> None:
    amounts = [
        Decimal("10.01"),
        Decimal("10.49"),
        Decimal("10.50"),
        Decimal("10.99"),
        Decimal("299.4999"),
        Decimal("299.5000"),
    ]
    for a in amounts:
        res = round_commercial_uyu(a)
        assert res == res.quantize(Decimal("1"))
        assert str(res).endswith(".00")
