from decimal import ROUND_HALF_UP, Decimal


class FinancialService:
    @staticmethod
    def calculate_cogs(
        unit_cost: Decimal | None,
        unit_price: Decimal,
        markup_percentage: Decimal | None,
        quantity: int,
    ) -> Decimal:
        """
        Calcula el Costo de Mercadería Vendida (COGS) para una línea de pedido.
        Si se conoce el costo unitario con IVA, se utiliza directamente.
        Si no, se deduce a partir del precio de venta y el recargo porcentual.
        """
        qty_dec = Decimal(str(quantity))

        if unit_cost is not None and unit_cost > Decimal("0.00"):
            total_cogs = unit_cost * qty_dec
        elif markup_percentage is not None and markup_percentage > Decimal("0.00"):
            # precio = costo * (1 + markup/100) -> costo = precio / (1 + markup/100)
            factor = Decimal("1.00") + (markup_percentage / Decimal("100.00"))
            estimated_unit_cost = unit_price / factor
            total_cogs = estimated_unit_cost * qty_dec
        else:
            total_cogs = Decimal("0.00")

        return total_cogs.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def calculate_gross_margin(gross_revenue: Decimal, cogs: Decimal) -> Decimal:
        """Margen Bruto = Facturación Bruta - Costo de Mercadería Vendida"""
        return (gross_revenue - cogs).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def calculate_net_profit(gross_margin: Decimal, total_expenses: Decimal) -> Decimal:
        """Ganancia Neta = Margen Bruto - Gastos Operativos Totales"""
        return (gross_margin - total_expenses).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def calculate_margin_percentage(gross_margin: Decimal, gross_revenue: Decimal) -> Decimal:
        """Retorno / Margen sobre ventas (%)"""
        if gross_revenue <= Decimal("0.00"):
            return Decimal("0.00")
        percentage = (gross_margin / gross_revenue) * Decimal("100.00")
        return percentage.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
