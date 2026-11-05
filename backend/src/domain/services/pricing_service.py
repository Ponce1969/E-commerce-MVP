from decimal import ROUND_HALF_UP, Decimal


def round_commercial_uyu(amount: Decimal) -> Decimal:
    """
    Aplica redondeo comercial a pesos uruguayos enteros:
    - 0.01 a 0.49 redondea hacia abajo.
    - 0.50 a 0.99 redondea hacia arriba.
    Mantiene tipo Decimal con precisión de centavos .00.
    """
    return amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP).quantize(Decimal("0.01"))


class PricingService:
    """Domain service executing financial calculations in Decimal arithmetic."""

    TWO_PLACES = Decimal("0.01")
    FOUR_PLACES = Decimal("0.0001")
    round_commercial_uyu = staticmethod(round_commercial_uyu)

    @classmethod
    def calculate_price_iva_inc(
        cls,
        cost_iva_inc: Decimal,
        markup_percentage: Decimal,
    ) -> Decimal:
        """
        Calculates final sale price with VAT included applying commercial integer rounding (UYU).
        Formula: round_commercial_uyu(Costo_con_IVA * (1 + Recargo / 100))
        """
        multiplier = Decimal("1") + (markup_percentage / Decimal("100"))
        final_price = cost_iva_inc * multiplier
        return round_commercial_uyu(final_price)

    @classmethod
    def calculate_markup_from_price(
        cls,
        cost_iva_inc: Decimal,
        price_iva_inc: Decimal,
    ) -> Decimal:
        """
        Calculates exact markup percentage from target sale price and cost.
        Formula: round(((price_iva_inc / cost_iva_inc) - 1) * 100, 4)
        """
        if cost_iva_inc <= Decimal("0"):
            return Decimal("0.0000")
        raw_markup = ((price_iva_inc / cost_iva_inc) - Decimal("1")) * Decimal("100")
        return raw_markup.quantize(cls.FOUR_PLACES, rounding=ROUND_HALF_UP)

    @classmethod
    def calculate_item_subtotal(
        cls,
        unit_price: Decimal,
        quantity: int,
        discount_percentage: Decimal = Decimal("0.0000"),
    ) -> Decimal:
        """
        Calculates subtotal for a line item applying optional manual discount.
        Formula: round(unit_price * quantity * (1 - discount / 100), 2)
        """
        base_amount = unit_price * Decimal(quantity)
        discount_factor = Decimal("1") - (discount_percentage / Decimal("100"))
        subtotal = base_amount * discount_factor
        return subtotal.quantize(cls.TWO_PLACES, rounding=ROUND_HALF_UP)
