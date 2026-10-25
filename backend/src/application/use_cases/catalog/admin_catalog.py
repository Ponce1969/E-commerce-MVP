from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.application.dtos.catalog_dto import (
    ProductAdminDetailDTO,
    ProductCreateDTO,
    ProductPriceDetailDTO,
    ProductPriceUpdateItemDTO,
    ProductStockUpdateDTO,
)
from src.domain.exceptions import (
    BusinessRuleViolationException,
    EntityNotFoundException,
)
from src.domain.services.pricing_service import PricingService
from src.infrastructure.db.models import CommercialListORM, ProductORM, ProductPriceORM


class AdminCatalogUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_products(
        self,
        category: str | None = None,
        provider: str | None = None,
        is_published: bool | None = None,
        has_conflict: bool | None = None,
        is_incomplete: bool | None = None,
        stock_status: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ProductAdminDetailDTO]:
        query = select(ProductORM).options(
            selectinload(ProductORM.prices).selectinload(ProductPriceORM.commercial_list)
        )

        if category:
            query = query.where(ProductORM.category == category)
        if provider:
            query = query.where(ProductORM.provider == provider)
        if is_published is not None:
            query = query.where(ProductORM.is_published == is_published)
        if search:
            query = query.where(ProductORM.name.ilike(f"%{search}%"))

        if stock_status == "low":
            query = query.where(ProductORM.current_stock <= ProductORM.min_stock_alert)
        elif stock_status == "out":
            query = query.where(ProductORM.current_stock <= 0)

        if has_conflict is not None:
            conflict_subq = (
                select(ProductPriceORM.product_id).where(ProductPriceORM.has_conflict == True)  # noqa: E712
            )
            if has_conflict:
                query = query.where(ProductORM.id.in_(conflict_subq))
            else:
                query = query.where(~ProductORM.id.in_(conflict_subq))

        query = query.order_by(ProductORM.id.asc()).limit(limit).offset(offset)
        result = await self.session.execute(query)
        products = result.scalars().all()

        dtos: list[ProductAdminDetailDTO] = []
        for p in products:
            prices_dto: list[ProductPriceDetailDTO] = []
            missing_price_data = False

            if not p.prices:
                missing_price_data = True

            for pr in p.prices:
                if pr.cost_iva_inc is None or pr.markup_percentage is None:
                    missing_price_data = True

                prices_dto.append(
                    ProductPriceDetailDTO(
                        commercial_list_id=pr.commercial_list_id,
                        commercial_list_name=(
                            pr.commercial_list.name if pr.commercial_list else ""
                        ),
                        cost_iva_inc=pr.cost_iva_inc,
                        markup_percentage=pr.markup_percentage,
                        price_iva_inc=pr.price_iva_inc,
                        has_conflict=pr.has_conflict,
                        conflict_detail=pr.conflict_detail,
                    )
                )

            is_draft = (
                not (p.presentation and p.presentation.strip())
                or not (p.provider and p.provider.strip())
                or missing_price_data
            )

            # Apply filters that depend on price relations if specified
            if is_incomplete is not None and is_incomplete != is_draft:
                continue

            dtos.append(
                ProductAdminDetailDTO(
                    id=p.id,
                    code=p.code,
                    name=p.name,
                    presentation=p.presentation,
                    provider=p.provider,
                    category=p.category,
                    iva_rate=p.iva_rate,
                    is_published=p.is_published,
                    is_pending_draft=is_draft,
                    tech_sheet_url=p.tech_sheet_url,
                    image_url=p.image_url,
                    is_active=p.is_active,
                    current_stock=p.current_stock,
                    min_stock_alert=p.min_stock_alert,
                    allow_backorder=p.allow_backorder,
                    is_low_stock=p.current_stock <= p.min_stock_alert,
                    is_out_of_stock=p.current_stock <= 0,
                    prices=prices_dto,
                )
            )

        return dtos

    async def create_product(self, data: ProductCreateDTO) -> ProductAdminDetailDTO:
        # Get next ID
        max_id_stmt = select(func.max(ProductORM.id))
        max_res = await self.session.execute(max_id_stmt)
        max_id = max_res.scalar() or 0
        new_id = max_id + 1

        product = ProductORM(
            id=new_id,
            name=data.name.strip(),
            code=data.code.strip() if data.code else None,
            presentation=data.presentation.strip() if data.presentation else None,
            provider=data.provider.strip() if data.provider else None,
            category=data.category.strip() if data.category else "General",
            iva_rate=data.iva_rate,
            is_published=False,
            is_active=True,
            current_stock=0,
            min_stock_alert=5,
            allow_backorder=False,
        )
        self.session.add(product)
        await self.session.flush()

        # Attach default price rows for active commercial lists
        lists_stmt = select(CommercialListORM).where(CommercialListORM.is_active == True)  # noqa: E712
        lists_res = await self.session.execute(lists_stmt)
        all_lists = lists_res.scalars().all()

        prices_dto: list[ProductPriceDetailDTO] = []
        for cl in all_lists:
            price_row = ProductPriceORM(
                product_id=product.id,
                commercial_list_id=cl.id,
                cost_iva_inc=None,
                markup_percentage=None,
                price_iva_inc=None,
                has_conflict=False,
            )
            self.session.add(price_row)
            prices_dto.append(
                ProductPriceDetailDTO(
                    commercial_list_id=cl.id,
                    commercial_list_name=cl.name,
                    cost_iva_inc=None,
                    markup_percentage=None,
                    price_iva_inc=None,
                    has_conflict=False,
                )
            )

        await self.session.commit()

        return ProductAdminDetailDTO(
            id=product.id,
            code=product.code,
            name=product.name,
            presentation=product.presentation,
            provider=product.provider,
            category=product.category,
            iva_rate=product.iva_rate,
            is_published=product.is_published,
            is_pending_draft=True,  # Brand new product without cost/markup is draft
            tech_sheet_url=product.tech_sheet_url,
            image_url=product.image_url,
            is_active=product.is_active,
            current_stock=product.current_stock,
            min_stock_alert=product.min_stock_alert,
            allow_backorder=product.allow_backorder,
            is_low_stock=product.current_stock <= product.min_stock_alert,
            is_out_of_stock=product.current_stock <= 0,
            prices=prices_dto,
        )

    async def update_prices(
        self,
        product_id: int,
        price_updates: list[ProductPriceUpdateItemDTO],
    ) -> list[ProductPriceDetailDTO]:
        stmt = (
            select(ProductORM)
            .options(selectinload(ProductORM.prices).selectinload(ProductPriceORM.commercial_list))
            .where(ProductORM.id == product_id)
        )
        result = await self.session.execute(stmt)
        product = result.scalar_one_or_none()
        if not product:
            raise EntityNotFoundException(f"Producto con ID {product_id} no encontrado.")

        price_map = {p.commercial_list_id: p for p in product.prices}

        for item in price_updates:
            calculated_price = PricingService.calculate_price_iva_inc(
                item.cost_iva_inc, item.markup_percentage
            )

            if item.commercial_list_id in price_map:
                record = price_map[item.commercial_list_id]
                record.cost_iva_inc = item.cost_iva_inc
                record.markup_percentage = item.markup_percentage
                record.price_iva_inc = calculated_price
            else:
                new_record = ProductPriceORM(
                    product_id=product.id,
                    commercial_list_id=item.commercial_list_id,
                    cost_iva_inc=item.cost_iva_inc,
                    markup_percentage=item.markup_percentage,
                    price_iva_inc=calculated_price,
                    has_conflict=False,
                )
                self.session.add(new_record)

        await self.session.commit()

        # Re-fetch updated prices
        stmt_refresh = (
            select(ProductPriceORM)
            .options(selectinload(ProductPriceORM.commercial_list))
            .where(ProductPriceORM.product_id == product_id)
        )
        res_refresh = await self.session.execute(stmt_refresh)
        updated_prices = res_refresh.scalars().all()

        return [
            ProductPriceDetailDTO(
                commercial_list_id=p.commercial_list_id,
                commercial_list_name=p.commercial_list.name if p.commercial_list else "",
                cost_iva_inc=p.cost_iva_inc,
                markup_percentage=p.markup_percentage,
                price_iva_inc=p.price_iva_inc,
                has_conflict=p.has_conflict,
                conflict_detail=p.conflict_detail,
            )
            for p in updated_prices
        ]

    async def toggle_publication(self, product_id: int, is_published: bool) -> bool:
        """
        UC-ADM-05: Marcar producto como publicado (is_published = True) solo si
        no presenta campos obligatorios pendientes (Ficha Incompleta = False).
        """
        stmt = (
            select(ProductORM)
            .options(selectinload(ProductORM.prices))
            .where(ProductORM.id == product_id)
        )
        result = await self.session.execute(stmt)
        product = result.scalar_one_or_none()
        if not product:
            raise EntityNotFoundException(f"Producto con ID {product_id} no encontrado.")

        if is_published:
            if not product.presentation or not product.presentation.strip():
                raise BusinessRuleViolationException(
                    "No se puede publicar el producto: falta la presentación."
                )
            if not product.provider or not product.provider.strip():
                raise BusinessRuleViolationException(
                    "No se puede publicar el producto: falta el proveedor."
                )
            if not product.prices:
                raise BusinessRuleViolationException(
                    "No se puede publicar el producto: no tiene condiciones de precio registradas."
                )
            # Check that at least one price has complete cost and markup
            has_valid_price = any(
                p.cost_iva_inc is not None and p.markup_percentage is not None
                for p in product.prices
            )
            if not has_valid_price:
                raise BusinessRuleViolationException(
                    "No se puede publicar el producto: requiere al menos una lista con costo y recargo definidos."
                )

        product.is_published = is_published
        await self.session.commit()
        return product.is_published

    async def update_stock(
        self, product_id: int, data: ProductStockUpdateDTO
    ) -> ProductAdminDetailDTO:
        """
        Actualizar los niveles de inventario físico y alertas de stock de un producto.
        """
        stmt = (
            select(ProductORM)
            .options(selectinload(ProductORM.prices).selectinload(ProductPriceORM.commercial_list))
            .where(ProductORM.id == product_id)
        )
        result = await self.session.execute(stmt)
        product = result.scalar_one_or_none()
        if not product:
            raise EntityNotFoundException(f"Producto con ID {product_id} no encontrado.")

        product.current_stock = data.current_stock
        product.min_stock_alert = data.min_stock_alert
        product.allow_backorder = data.allow_backorder
        await self.session.commit()

        prices_dto: list[ProductPriceDetailDTO] = [
            ProductPriceDetailDTO(
                commercial_list_id=pr.commercial_list_id,
                commercial_list_name=(pr.commercial_list.name if pr.commercial_list else ""),
                cost_iva_inc=pr.cost_iva_inc,
                markup_percentage=pr.markup_percentage,
                price_iva_inc=pr.price_iva_inc,
                has_conflict=pr.has_conflict,
                conflict_detail=pr.conflict_detail,
            )
            for pr in product.prices
        ]

        missing_price_data = not product.prices or any(
            pr.cost_iva_inc is None or pr.markup_percentage is None for pr in product.prices
        )
        is_draft = (
            not (product.presentation and product.presentation.strip())
            or not (product.provider and product.provider.strip())
            or missing_price_data
        )

        return ProductAdminDetailDTO(
            id=product.id,
            code=product.code,
            name=product.name,
            presentation=product.presentation,
            provider=product.provider,
            category=product.category,
            iva_rate=product.iva_rate,
            is_published=product.is_published,
            is_pending_draft=is_draft,
            tech_sheet_url=product.tech_sheet_url,
            image_url=product.image_url,
            is_active=product.is_active,
            current_stock=product.current_stock,
            min_stock_alert=product.min_stock_alert,
            allow_backorder=product.allow_backorder,
            is_low_stock=product.current_stock <= product.min_stock_alert,
            is_out_of_stock=product.current_stock <= 0,
            prices=prices_dto,
        )
