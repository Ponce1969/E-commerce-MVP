from decimal import Decimal

from src.domain.models import Product, ProductPrice
from src.domain.services.pricing_service import PricingService


def test_pricing_calculation_exact_decimal() -> None:
    # Test formula: round(cost * (1 + markup/100), 2)
    cost = Decimal("273.00")
    markup = Decimal("55.6777")
    price = PricingService.calculate_price_iva_inc(cost, markup)
    assert price == Decimal("425.00")


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
