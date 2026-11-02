import csv
import io
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.application.use_cases.catalog.inventory_io import InventoryIOUseCase
from src.infrastructure.db.models import CommercialListORM, ProductORM, ProductPriceORM


def test_get_catalog_template_csv() -> None:
    use_case = InventoryIOUseCase(None)  # type: ignore
    csv_bytes = use_case.get_catalog_template_csv()
    assert csv_bytes.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM
    text = csv_bytes.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    assert len(rows) >= 3
    headers = rows[0]
    assert "Nombre" in headers
    assert "Codigo" in headers
    assert "Costo_IVA_Inc" in headers
    assert "Precio_Venta_IVA_Inc" in headers


@pytest.mark.asyncio
async def test_import_catalog_csv_size_guardrail() -> None:
    use_case = InventoryIOUseCase(None)  # type: ignore
    huge_bytes = b"x" * (5 * 1024 * 1024 + 10)
    result = await use_case.import_catalog_csv(huge_bytes)
    assert result["created_count"] == 0
    assert "supera el tamaño máximo" in result["errors"][0]


@pytest.mark.asyncio
async def test_import_catalog_csv_missing_name_guardrail() -> None:
    use_case = InventoryIOUseCase(None)  # type: ignore
    bad_csv = b"Codigo;Stock\nABC;10\n"
    result = await use_case.import_catalog_csv(bad_csv)
    assert result["created_count"] == 0
    assert any("Nombre" in err for err in result["errors"])


@pytest.mark.asyncio
async def test_import_catalog_csv_valid_with_gabriel_pricing_rule() -> None:
    mock_session = AsyncMock()

    comm_list = CommercialListORM(id=1, name="General", is_active=True)
    existing_product = ProductORM(
        id=10,
        code="EXIST-01",
        name="Limpiavidrios Original",
        presentation="1 L",
        provider="Moizo",
        category="Limpieza",
        iva_rate=Decimal("0.22"),
        is_published=False,
        is_active=True,
        current_stock=5,
        min_stock_alert=5,
    )
    existing_product.prices = [
        ProductPriceORM(
            id=1,
            product_id=10,
            commercial_list_id=1,
            cost_iva_inc=Decimal("100"),
            price_iva_inc=Decimal("150"),
            markup_percentage=Decimal("0.50"),
        )
    ]

    # Mock DB executions
    # 1. active commercial lists
    mock_lists_result = MagicMock()
    mock_lists_result.scalars.return_value.all.return_value = [comm_list]

    # 2. existing products
    mock_prod_result = MagicMock()
    mock_prod_result.scalars.return_value.all.return_value = [existing_product]

    # 3. max id
    mock_max_result = MagicMock()
    mock_max_result.scalar.return_value = 10

    mock_session.execute.side_effect = [
        mock_lists_result,
        mock_prod_result,
        mock_max_result,
    ]

    use_case = InventoryIOUseCase(mock_session)

    csv_data = (
        "Codigo;Nombre;Presentacion;Proveedor;Categoria;Costo_IVA_Inc;Precio_Venta_IVA_Inc;Stock\n"
        "EXIST-01;Limpiavidrios Original Actualizado;1 L;Moizo;Limpieza;120.00;180.00;15\n"
        "GAB-100;Silicona Gabriel Auto;500 cc;Química Gabriel;Automotriz;151.00;;25\n"
    ).encode()

    res = await use_case.import_catalog_csv(csv_data)

    assert res["updated_count"] == 1
    assert res["created_count"] == 1
    assert res["total_processed"] == 2
    assert len(res["errors"]) == 0

    # Verify update of existing product
    assert existing_product.name == "Limpiavidrios Original Actualizado"
    assert existing_product.current_stock == 15

    # Verify new product pricing rule (151 * 1.50 = 226.50 -> ceil = 227)
    # The session.add was called for new_prod and its prices
    added_objs = [call.args[0] for call in mock_session.add.call_args_list]
    new_prods = [obj for obj in added_objs if isinstance(obj, ProductORM)]
    assert len(new_prods) == 1
    new_prod = new_prods[0]
    assert new_prod.id == 11
    assert new_prod.name == "Silicona Gabriel Auto"
    assert new_prod.provider == "Química Gabriel"
    assert new_prod.current_stock == 25

    # Check pricing rule
    price_objs = [obj for obj in added_objs if isinstance(obj, ProductPriceORM)]
    assert len(price_objs) == 1
    assert price_objs[0].cost_iva_inc == Decimal("151.00")
    assert price_objs[0].price_iva_inc == Decimal("227")  # math.ceil(151 * 1.5)


@pytest.mark.asyncio
async def test_import_catalog_csv_chatgpt_fences_and_media_urls() -> None:
    mock_session = AsyncMock()
    comm_list = CommercialListORM(id=1, name="General", is_active=True)

    mock_lists_result = MagicMock()
    mock_lists_result.scalars.return_value.all.return_value = [comm_list]
    mock_prod_result = MagicMock()
    mock_prod_result.scalars.return_value.all.return_value = []
    mock_max_result = MagicMock()
    mock_max_result.scalar.return_value = 50

    mock_session.execute.side_effect = [
        mock_lists_result,
        mock_prod_result,
        mock_max_result,
    ]

    use_case = InventoryIOUseCase(mock_session)

    chatgpt_pasted = (
        "```csv\n"
        "Codigo;Nombre;Presentacion;Proveedor;Categoria;Costo_IVA_Inc;Stock;Publicar;Foto_URL;Ficha_PDF_URL\n"
        "NEW-99;Detergente Industrial Concentrado;5 L;Química Gabriel;Limpieza;200;12;SI;/static/uploads/det.webp;/static/uploads/ficha.pdf\n"
        "```\n"
    ).encode()

    res = await use_case.import_catalog_csv(chatgpt_pasted)
    assert res["created_count"] == 1
    assert len(res["errors"]) == 0

    added_objs = [call.args[0] for call in mock_session.add.call_args_list]
    new_prods = [obj for obj in added_objs if isinstance(obj, ProductORM)]
    assert len(new_prods) == 1
    assert new_prods[0].code == "NEW-99"
    assert new_prods[0].is_published is True
    assert new_prods[0].image_url == "/static/uploads/det.webp"
    assert new_prods[0].tech_sheet_url == "/static/uploads/ficha.pdf"
