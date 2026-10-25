from decimal import ROUND_HALF_UP, Decimal


class PricingService:
    """Domain service executing financial calculations in Decimal arithmetic."""

    TWO_PLACES = Decimal("0.01")
    FOUR_PLACES = Decimal("0.0001")

    @classmethod
    def calculate_price_iva_inc(
        cls,
        cost_iva_inc: Decimal,
        markup_percentage: Decimal,
    ) -> Decimal:
        """
        Calculates final sale price with VAT included.
        Formula: round(Costo_con_IVA * (1 + Recargo / 100), 2)
        """
        multiplier = Decimal("1") + (markup_percentage / Decimal("100"))
        final_price = cost_iva_inc * multiplier
        return final_price.quantize(cls.TWO_PLACES, rounding=ROUND_HALF_UP)

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
