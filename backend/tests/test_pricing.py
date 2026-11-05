from decimal import Decimal

import pytest
from src.domain.models import Product, ProductPrice
from src.domain.services.pricing_service import PricingService, round_commercial_uyu


@pytest.mark.parametrize(
    ("input_amount", "expected_amount"),
    [
        (Decimal("150.00"), Decimal("150.00")),
        (Decimal("150.01"), Decimal("150.00")),
        (Decimal("150.49"), Decimal("150.00")),
        (Decimal("150.50"), Decimal("151.00")),
        (Decimal("150.51"), Decimal("151.00")),
        (Decimal("150.99"), Decimal("151.00")),
        (Decimal("0.49"), Decimal("0.00")),
        (Decimal("0.50"), Decimal("1.00")),
        (Decimal("10.004"), Decimal("10.00")),
        (Decimal("10.500"), Decimal("11.00")),
    ],
)
def test_round_commercial_uyu_edge_cases(input_amount: Decimal, expected_amount: Decimal) -> None:
    result = round_commercial_uyu(input_amount)
    assert result == expected_amount
    assert str(result).endswith(".00")


def test_pricing_calculation_exact_decimal() -> None:
    # Test formula: round_commercial_uyu(cost * (1 + markup/100))
    cost = Decimal("273.00")
    markup = Decimal("55.6777")
    price = PricingService.calculate_price_iva_inc(cost, markup)
    assert price == Decimal("425.00")


def test_pricing_calculation_rounds_commercial_uyu_integer() -> None:
    # 100 * 1.5049 = 150.49 -> 150.00
    cost = Decimal("100.00")
    markup_down = Decimal("50.49")
    price_down = PricingService.calculate_price_iva_inc(cost, markup_down)
    assert price_down == Decimal("150.00")

    # 100 * 1.5050 = 150.50 -> 151.00
    markup_up = Decimal("50.50")
    price_up = PricingService.calculate_price_iva_inc(cost, markup_up)
    assert price_up == Decimal("151.00")


def test_pricing_with_zero_discount() -> None:
    unit_price = Decimal("425.00")
    quantity = 3
    subtotal = PricingService.calculate_item_subtotal(unit_price, quantity)
    assert subtotal == Decimal("1275.00")


def test_pricing_with_discretionary_discount() -> None:
    unit_price = Decimal("100.00")
    quantity = 2
    discount = Decimal("15.0000")  # 15% manual discount
    subtotal = PricingService.calculate_item_subtotal(unit_price, quantity, discount)
    assert subtotal == Decimal("170.00")


def test_pending_draft_property() -> None:
    # Product missing presentation is an incomplete draft
    prod = Product(
        id=1,
        name="Test Incomplete Product",
        presentation=None,
        provider="Moizo",
        prices=[
            ProductPrice(
                id=1,
                product_id=1,
                commercial_list_id=1,
                cost_iva_inc=Decimal("100.00"),
                markup_percentage=Decimal("50.0000"),
                price_iva_inc=Decimal("150.00"),
            )
        ],
    )
    assert prod.is_pending_draft is True


def test_calculate_markup_from_price_exact_decimal() -> None:
    # Caso Mariana Rejilla 33x35: Costo 26.18, Precio final 53.00
    cost = Decimal("26.18")
    target_price = Decimal("53.00")
    markup = PricingService.calculate_markup_from_price(cost, target_price)
    assert markup == Decimal("102.4446")

    # Verificación de ida y vuelta en Decimal
    calculated_price = PricingService.calculate_price_iva_inc(cost, markup)
    assert calculated_price == target_price
