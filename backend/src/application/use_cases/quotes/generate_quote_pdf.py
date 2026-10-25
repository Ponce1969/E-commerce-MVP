from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Flowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.application.dtos.quote_dto import QuoteCreateDTO
from src.domain.exceptions import (
    BusinessRuleViolationException,
    EntityNotFoundException,
)
from src.domain.services.pricing_service import PricingService
from src.infrastructure.db.models import CommercialListORM, ProductORM, ProductPriceORM


class GenerateQuotePdfUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute(self, quote_data: QuoteCreateDTO) -> bytes:
        # 1. Fetch Commercial List
        list_stmt = select(CommercialListORM).where(
            CommercialListORM.id == quote_data.commercial_list_id
        )
        list_res = await self.session.execute(list_stmt)
        commercial_list = list_res.scalar_one_or_none()
        if not commercial_list:
            raise EntityNotFoundException(
                f"Lista comercial con ID {quote_data.commercial_list_id} no encontrada."
            )

        # 2. Fetch Products and resolve sale prices
        product_ids = [item.product_id for item in quote_data.items]
        prod_stmt = (
            select(ProductORM)
            .options(selectinload(ProductORM.prices).selectinload(ProductPriceORM.commercial_list))
            .where(ProductORM.id.in_(product_ids))
        )
        prod_res = await self.session.execute(prod_stmt)
        products_map = {p.id: p for p in prod_res.scalars().all()}

        items_detail = []
        total_amount = Decimal("0.00")

        for item in quote_data.items:
            product = products_map.get(item.product_id)
            if not product:
                raise EntityNotFoundException(
                    f"Producto con ID {item.product_id} no encontrado en catálogo."
                )

            # Find matching price for this commercial list
            price_row = next(
                (
                    pr
                    for pr in product.prices
                    if pr.commercial_list_id == quote_data.commercial_list_id
                ),
                None,
            )

            if not price_row or price_row.price_iva_inc is None:
                raise BusinessRuleViolationException(
                    f"El producto '{product.name}' no tiene precio asignado para la lista '{commercial_list.name}'."
                )

            unit_price = price_row.price_iva_inc
            subtotal = PricingService.calculate_item_subtotal(
                unit_price=unit_price,
                quantity=item.quantity,
                discount_percentage=item.discount_percentage,
            )
            total_amount += subtotal

            items_detail.append(
                {
                    "name": product.name,
                    "presentation": product.presentation or "-",
                    "quantity": item.quantity,
                    "unit_price": unit_price,
                    "discount": item.discount_percentage,
                    "subtotal": subtotal,
                }
            )

        # 3. Build PDF with ReportLab
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        elements: list[Flowable] = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#1e3a8a"),
        )
        subtitle_style = ParagraphStyle(
            "DocSubTitle",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#4b5563"),
        )
        header_meta = ParagraphStyle(
            "HeaderMeta",
            parent=styles["Normal"],
            fontSize=9,
            leading=13,
            alignment=2,  # Right align
        )
        table_cell = ParagraphStyle(
            "TableCell",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
        )
        table_cell_bold = ParagraphStyle(
            "TableCellBold",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            fontName="Helvetica-Bold",
        )

        # Header section
        header_table_data = [
            [
                Paragraph("<b>2 RODRÍGUEZ DISTRIBUIDORA</b>", title_style),
                Paragraph(
                    f"<b>Fecha:</b> {date.today().strftime('%d/%m/%Y')}<br/>"
                    f"<b>Vigencia:</b> {(quote_data.valid_until or (date.today() + timedelta(days=15))).strftime('%d/%m/%Y')}",
                    header_meta,
                ),
            ],
            [
                Paragraph(
                    "Artículos de Limpieza, Higiene y Químicos Profesionales<br/>"
                    "Paso Molino, Montevideo | Tel / WhatsApp: 099 549 330",
                    subtitle_style,
                ),
                Paragraph(
                    f"<b>Condición Comercial:</b> {commercial_list.name}",
                    header_meta,
                ),
            ],
        ]
        header_table = Table(header_table_data, colWidths=[4.0 * inch, 3.0 * inch])
        header_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.append(header_table)
        elements.append(Spacer(1, 15))

        # Client info section
        client_text = f"<b>Cliente / Razón Social:</b> {quote_data.client_name}<br/>"
        if quote_data.client_phone:
            client_text += (
                f"<b>Teléfono / Contacto:</b> {quote_data.client_phone} &nbsp;&nbsp;&nbsp;&nbsp;"
            )
        if quote_data.client_email:
            client_text += f"<b>Email:</b> {quote_data.client_email}"

        elements.append(Paragraph(client_text, styles["Normal"]))
        elements.append(Spacer(1, 15))

        # Items Table
        table_data = [
            [
                Paragraph("<b>Artículo</b>", table_cell_bold),
                Paragraph("<b>Presentación</b>", table_cell_bold),
                Paragraph("<b>Cant.</b>", table_cell_bold),
                Paragraph("<b>P. Unit (IVA inc)</b>", table_cell_bold),
                Paragraph("<b>Desc.</b>", table_cell_bold),
                Paragraph("<b>Subtotal</b>", table_cell_bold),
            ]
        ]

        for it in items_detail:
            disc_val = it["discount"]
            disc_str = (
                f"{disc_val}%" if isinstance(disc_val, Decimal) and disc_val > Decimal("0") else "-"
            )
            table_data.append(
                [
                    Paragraph(str(it["name"]), table_cell),
                    Paragraph(str(it["presentation"]), table_cell),
                    Paragraph(str(it["quantity"]), table_cell),
                    Paragraph(f"${it['unit_price']:.2f}", table_cell),
                    Paragraph(disc_str, table_cell),
                    Paragraph(f"${it['subtotal']:.2f}", table_cell_bold),
                ]
            )

        # Total Row
        table_data.append(
            [
                Paragraph("", table_cell),
                Paragraph("", table_cell),
                Paragraph("", table_cell),
                Paragraph("", table_cell),
                Paragraph("<b>TOTAL:</b>", table_cell_bold),
                Paragraph(f"<b>${total_amount:.2f}</b>", title_style),
            ]
        )

        items_table = Table(
            table_data,
            colWidths=[
                2.8 * inch,
                1.1 * inch,
                0.6 * inch,
                1.1 * inch,
                0.6 * inch,
                1.0 * inch,
            ],
        )
        items_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111827")),
                    ("ALIGN", (2, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#d1d5db")),
                    ("INNERGRID", (0, 0), (-1, -2), 0.5, colors.HexColor("#e5e7eb")),
                    ("BOX", (0, 0), (-1, -2), 1, colors.HexColor("#d1d5db")),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LINEABOVE", (-2, -1), (-1, -1), 1.5, colors.HexColor("#1e3a8a")),
                ]
            )
        )
        elements.append(items_table)
        elements.append(Spacer(1, 20))

        # Footer notes
        footer_text = (
            "<i>Nota: Precios finales en Pesos Uruguayos con IVA incluido. "
            "Excluye costos de envío salvo acuerdo previo. Retiros en local Paso Molino sin costo. "
            "Documento de validez comercial emitido automáticamente.</i>"
        )
        elements.append(Paragraph(footer_text, subtitle_style))

        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
