from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.application.dtos.catalog_dto import (
    PriceListCreateDTO,
    PriceListDTO,
    PriceListUpdateDTO,
    ProductAdminDetailDTO,
    ProductCreateDTO,
    ProductPriceDetailDTO,
    ProductPriceListItemDetailDTO,
    ProductPriceUpdateItemDTO,
    ProductStockUpdateDTO,
    ProductUpdateDTO,
)
from src.domain.exceptions import (
    BusinessRuleViolationException,
    EntityNotFoundException,
)
from src.domain.services.pricing_service import PricingService, round_commercial_uyu
from src.infrastructure.db.models import (
    CommercialListORM,
    OrderItemORM,
    PriceListORM,
    ProductORM,
    ProductPriceListItemORM,
    ProductPriceORM,
)


class AdminCatalogUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # =========================================================================
    # ABM DE LISTAS DE PRECIOS DINÁMICAS (SPEC-004 RF-04)
    # =========================================================================

    async def list_price_lists(self, only_active: bool = False) -> list[PriceListDTO]:
        """Listar todas las listas de precios ordenadas por id."""
        stmt = select(PriceListORM)
        if only_active:
            stmt = stmt.where(PriceListORM.is_active == True)  # noqa: E712
        stmt = stmt.order_by(PriceListORM.id.asc())
        res = await self.session.execute(stmt)
        lists = res.scalars().all()
        return [
            PriceListDTO(
                id=item_pl.id,
                code=item_pl.code,
                name=item_pl.name,
                description=item_pl.description,
                is_active=item_pl.is_active,
            )
            for item_pl in lists
        ]

    async def create_price_list(self, data: PriceListCreateDTO) -> PriceListDTO:
        """Crea una nueva lista de precios validando unicidad de código."""
        clean_code = data.code.strip().upper()
        existing_stmt = select(PriceListORM).where(PriceListORM.code == clean_code)
        existing_res = await self.session.execute(existing_stmt)
        if existing_res.scalar_one_or_none():
            raise BusinessRuleViolationException(
                f"Ya existe una lista de precios con el código '{clean_code}'."
            )

        max_id_stmt = select(func.max(PriceListORM.id))
        max_res = await self.session.execute(max_id_stmt)
        max_id = max_res.scalar() or 0
        new_id = max_id + 1

        price_list = PriceListORM(
            id=new_id,
            code=clean_code,
            name=data.name.strip(),
            description=data.description.strip() if data.description else None,
            is_active=data.is_active,
        )
        self.session.add(price_list)

        # También sincronizar en commercial_lists para retrocompatibilidad
        legacy_cl = CommercialListORM(
            id=new_id,
            name=price_list.name,
            description=price_list.description,
            is_active=price_list.is_active,
        )
        self.session.add(legacy_cl)

        await self.session.commit()
        await self.session.refresh(price_list)

        return PriceListDTO(
            id=price_list.id,
            code=price_list.code,
            name=price_list.name,
            description=price_list.description,
            is_active=price_list.is_active,
        )

    async def update_price_list(self, price_list_id: int, data: PriceListUpdateDTO) -> PriceListDTO:
        """Actualizar atributos de una lista de precios existente."""
        stmt = select(PriceListORM).where(PriceListORM.id == price_list_id)
        res = await self.session.execute(stmt)
        price_list = res.scalar_one_or_none()
        if not price_list:
            raise EntityNotFoundException(f"Lista de precios #{price_list_id} no encontrada.")

        if data.name is not None:
            price_list.name = data.name.strip()
        if data.description is not None:
            price_list.description = data.description.strip() if data.description else None
        if data.is_active is not None:
            price_list.is_active = data.is_active

        # Sincronizar en commercial_lists si existe
        legacy_stmt = select(CommercialListORM).where(CommercialListORM.id == price_list_id)
        legacy_res = await self.session.execute(legacy_stmt)
        legacy_cl = legacy_res.scalar_one_or_none()
        if legacy_cl:
            if data.name is not None:
                legacy_cl.name = price_list.name
            if data.description is not None:
                legacy_cl.description = price_list.description
            if data.is_active is not None:
                legacy_cl.is_active = price_list.is_active

        await self.session.commit()
        await self.session.refresh(price_list)

        return PriceListDTO(
            id=price_list.id,
            code=price_list.code,
            name=price_list.name,
            description=price_list.description,
            is_active=price_list.is_active,
        )

    # =========================================================================
    # CATÁLOGO DE PRODUCTOS
    # =========================================================================

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
        query = (
            select(ProductORM)
            .options(
                selectinload(ProductORM.prices).selectinload(ProductPriceORM.commercial_list),
                selectinload(ProductORM.price_list_items).selectinload(
                    ProductPriceListItemORM.price_list
                ),
            )
            .where(ProductORM.is_active == True)  # noqa: E712
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
            conflict_subq = select(ProductPriceORM.product_id).where(
                ProductPriceORM.has_conflict == True  # noqa: E712
            )
            if has_conflict:
                query = query.where(ProductORM.id.in_(conflict_subq))
            else:
                query = query.where(~ProductORM.id.in_(conflict_subq))

        query = query.order_by(ProductORM.id.asc()).limit(limit).offset(offset)
        result = await self.session.execute(query)
        products = result.scalars().all()

        dtos = [self._to_admin_dto(p) for p in products]

        if is_incomplete is not None:
            dtos = [d for d in dtos if d.is_pending_draft == is_incomplete]

        return dtos

    async def create_product(self, data: ProductCreateDTO) -> ProductAdminDetailDTO:
        # Get next ID
        max_id_stmt = select(func.max(ProductORM.id))
        max_res = await self.session.execute(max_id_stmt)
        max_id = max_res.scalar() or 0
        new_id = max_id + 1

        cost_val = data.cost_iva_inc
        markup_val = data.markup_percentage
        if cost_val is not None and markup_val is None:
            markup_val = Decimal("50.00")

        calc_price = None
        if cost_val is not None and markup_val is not None:
            calc_price = PricingService.calculate_price_iva_inc(cost_val, markup_val)

        has_complete_fields = bool(
            data.presentation
            and data.presentation.strip()
            and data.provider
            and data.provider.strip()
            and cost_val is not None
            and markup_val is not None
        )
        can_publish = bool(data.is_published and has_complete_fields)

        product = ProductORM(
            id=new_id,
            name=data.name.strip(),
            code=data.code.strip() if data.code else None,
            presentation=data.presentation.strip() if data.presentation else None,
            provider=data.provider.strip() if data.provider else None,
            category=data.category.strip() if data.category else "General",
            iva_rate=data.iva_rate,
            is_published=can_publish,
            current_stock=data.current_stock,
            min_stock_alert=5,
            allow_backorder=False,
        )
        self.session.add(product)
        await self.session.flush()

        # Cargar listas de precios disponibles
        lists_stmt = select(PriceListORM).where(PriceListORM.is_active == True)  # noqa: E712
        lists_res = await self.session.execute(lists_stmt)
        all_price_lists = lists_res.scalars().all()

        # Si se definieron listas específicas, asignar a ellas; de lo contrario a todas las activas
        target_list_ids = (
            set(data.price_list_ids) if data.price_list_ids else {pl.id for pl in all_price_lists}
        )

        for pl in all_price_lists:
            if pl.id in target_list_ids:
                pli = ProductPriceListItemORM(
                    product_id=product.id,
                    price_list_id=pl.id,
                    sale_price=calc_price or Decimal("0.00"),
                    is_active=True,
                )
                self.session.add(pli)

        # Sincronización en tabla legada product_prices
        comm_lists_stmt = select(CommercialListORM).where(
            CommercialListORM.is_active == True  # noqa: E712
        )
        comm_lists_res = await self.session.execute(comm_lists_stmt)
        all_comm_lists = comm_lists_res.scalars().all()

        for cl in all_comm_lists:
            is_active_for_list = cl.id in target_list_ids
            price_row = ProductPriceORM(
                product_id=product.id,
                commercial_list_id=cl.id,
                cost_iva_inc=cost_val if is_active_for_list else None,
                markup_percentage=markup_val if is_active_for_list else None,
                price_iva_inc=calc_price if is_active_for_list else None,
                has_conflict=False,
            )
            self.session.add(price_row)

        await self.session.commit()

        # Recargar con relaciones para DTO completo
        stmt = (
            select(ProductORM)
            .where(ProductORM.id == product.id)
            .options(
                selectinload(ProductORM.prices).selectinload(ProductPriceORM.commercial_list),
                selectinload(ProductORM.price_list_items).selectinload(
                    ProductPriceListItemORM.price_list
                ),
            )
        )
        reloaded = (await self.session.execute(stmt)).scalar_one()
        return self._to_admin_dto(reloaded)

    async def update_prices(
        self,
        product_id: int,
        price_updates: list[ProductPriceUpdateItemDTO],
        price_list_ids: list[int] | None = None,
        cost_iva_inc: Decimal | None = None,
        markup_percentage: Decimal | None = None,
        price_iva_inc: Decimal | None = None,
    ) -> list[ProductPriceDetailDTO]:
        stmt = (
            select(ProductORM)
            .options(
                selectinload(ProductORM.prices).selectinload(ProductPriceORM.commercial_list),
                selectinload(ProductORM.price_list_items).selectinload(
                    ProductPriceListItemORM.price_list
                ),
            )
            .where(ProductORM.id == product_id)
        )
        result = await self.session.execute(stmt)
        product = result.scalar_one_or_none()
        if not product:
            raise EntityNotFoundException(f"Producto con ID {product_id} no encontrado.")

        # Determinar precio de venta redondeado
        target_sale_price: Decimal | None = None
        target_cost = cost_iva_inc
        target_markup = markup_percentage

        if price_iva_inc is not None and price_iva_inc > Decimal("0"):
            target_sale_price = round_commercial_uyu(price_iva_inc)
            if target_cost and target_cost > Decimal("0"):
                target_markup = PricingService.calculate_markup_from_price(
                    target_cost, target_sale_price
                )
        elif target_cost is not None and target_markup is not None:
            target_sale_price = PricingService.calculate_price_iva_inc(target_cost, target_markup)
        elif price_updates:
            first_up = price_updates[0]
            if first_up.price_iva_inc and first_up.price_iva_inc > Decimal("0"):
                target_sale_price = round_commercial_uyu(first_up.price_iva_inc)
                target_cost = first_up.cost_iva_inc
                target_markup = first_up.markup_percentage
            elif first_up.cost_iva_inc and first_up.markup_percentage:
                target_cost = first_up.cost_iva_inc
                target_markup = first_up.markup_percentage
                target_sale_price = PricingService.calculate_price_iva_inc(
                    target_cost, target_markup
                )

        # 1. Sincronización N:M en product_price_list_items
        if price_list_ids is not None:
            existing_pli_map = {item.price_list_id: item for item in product.price_list_items}
            target_ids_set = set(price_list_ids)

            # Actualizar o agregar listas seleccionadas
            for lid in target_ids_set:
                if lid in existing_pli_map:
                    pli = existing_pli_map[lid]
                    if target_sale_price is not None:
                        pli.sale_price = target_sale_price
                    pli.is_active = True
                else:
                    new_pli = ProductPriceListItemORM(
                        product_id=product.id,
                        price_list_id=lid,
                        sale_price=target_sale_price or Decimal("0.00"),
                        is_active=True,
                    )
                    self.session.add(new_pli)

            # Desvincular listas desmarcadas
            for lid, pli in existing_pli_map.items():
                if lid not in target_ids_set:
                    await self.session.delete(pli)

        # 2. Sincronización en tabla legada product_prices
        price_map = {p.commercial_list_id: p for p in product.prices}

        for item in price_updates:
            calculated_price = (
                round_commercial_uyu(item.price_iva_inc)
                if item.price_iva_inc is not None and item.price_iva_inc > Decimal("0")
                else target_sale_price
            )
            markup = item.markup_percentage or target_markup
            if item.cost_iva_inc > Decimal("0") and calculated_price is not None and markup is None:
                markup = PricingService.calculate_markup_from_price(
                    item.cost_iva_inc, calculated_price
                )

            if item.commercial_list_id in price_map:
                record = price_map[item.commercial_list_id]
                record.cost_iva_inc = item.cost_iva_inc
                record.markup_percentage = markup
                record.price_iva_inc = calculated_price
                record.has_conflict = False
            else:
                new_price = ProductPriceORM(
                    product_id=product.id,
                    commercial_list_id=item.commercial_list_id,
                    cost_iva_inc=item.cost_iva_inc,
                    markup_percentage=markup,
                    price_iva_inc=calculated_price,
                    has_conflict=False,
                )
                self.session.add(new_price)

        # Si se pasó price_list_ids pero no items individuales, sincronizar todas las seleccionadas
        if price_list_ids is not None and not price_updates and target_sale_price is not None:
            for lid in price_list_ids:
                if lid in price_map:
                    rec = price_map[lid]
                    rec.cost_iva_inc = target_cost
                    rec.markup_percentage = target_markup
                    rec.price_iva_inc = target_sale_price
                    rec.has_conflict = False
                else:
                    new_p = ProductPriceORM(
                        product_id=product.id,
                        commercial_list_id=lid,
                        cost_iva_inc=target_cost,
                        markup_percentage=target_markup,
                        price_iva_inc=target_sale_price,
                        has_conflict=False,
                    )
                    self.session.add(new_p)

        await self.session.commit()

        # Retornar precios actualizados
        stmt_refresh = (
            select(ProductPriceORM)
            .where(ProductPriceORM.product_id == product_id)
            .options(selectinload(ProductPriceORM.commercial_list))
        )
        refresh_res = await self.session.execute(stmt_refresh)
        updated_prices = refresh_res.scalars().all()

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

    async def update_product_info(
        self, product_id: int, data: ProductUpdateDTO
    ) -> ProductAdminDetailDTO:
        stmt = (
            select(ProductORM)
            .where(ProductORM.id == product_id)
            .options(
                selectinload(ProductORM.prices).selectinload(ProductPriceORM.commercial_list),
                selectinload(ProductORM.price_list_items).selectinload(
                    ProductPriceListItemORM.price_list
                ),
            )
        )
        res = await self.session.execute(stmt)
        product = res.scalar_one_or_none()
        if not product:
            raise EntityNotFoundException(f"Producto con ID #{product_id} no encontrado.")

        product.name = data.name.strip()
        product.category = data.category.strip()
        product.code = data.code.strip() if data.code else None
        product.presentation = data.presentation.strip() if data.presentation else None
        product.provider = data.provider.strip() if data.provider else None
        if data.iva_rate is not None:
            product.iva_rate = data.iva_rate

        await self.session.commit()
        await self.session.refresh(product)
        return self._to_admin_dto(product)

    async def delete_product(self, product_id: int) -> dict[str, Any]:
        """
        Eliminación segura con validación de integridad referencial:
        - Si posee órdenes históricas: soft-delete (is_active = False, is_published = False).
        - Si no tiene ventas históricas: hard-delete en cascada.
        """
        stmt = (
            select(ProductORM)
            .where(ProductORM.id == product_id)
            .options(
                selectinload(ProductORM.prices),
                selectinload(ProductORM.price_list_items),
            )
        )
        res = await self.session.execute(stmt)
        product = res.scalar_one_or_none()
        if not product:
            raise EntityNotFoundException(f"Producto con ID #{product_id} no encontrado.")

        order_stmt = select(func.count(OrderItemORM.id)).where(
            OrderItemORM.product_id == product_id
        )
        order_res = await self.session.execute(order_stmt)
        order_count = order_res.scalar() or 0

        if order_count > 0:
            product.is_active = False
            product.is_published = False
            await self.session.commit()
            return {
                "action": "soft_delete",
                "message": (
                    f"Producto #{product_id} archivado (soft-delete) por registrar "
                    f"{order_count} pedidos históricos."
                ),
            }

        await self.session.delete(product)
        await self.session.commit()
        return {
            "action": "hard_delete",
            "message": f"Producto #{product_id} eliminado físicamente sin dependencias históricas.",
        }

    async def toggle_publication(self, product_id: int, is_published: bool) -> bool:
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
        stmt = (
            select(ProductORM)
            .options(
                selectinload(ProductORM.prices).selectinload(ProductPriceORM.commercial_list),
                selectinload(ProductORM.price_list_items).selectinload(
                    ProductPriceListItemORM.price_list
                ),
            )
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
        return self._to_admin_dto(product)

    async def get_providers(self) -> list[str]:
        stmt = (
            select(ProductORM.provider)
            .where(ProductORM.provider.isnot(None), ProductORM.provider != "")
            .distinct()
            .order_by(ProductORM.provider.asc())
        )
        result = await self.session.execute(stmt)
        return [str(p).strip() for p in result.scalars().all() if p and str(p).strip()]

    def _to_admin_dto(self, product: ProductORM) -> ProductAdminDetailDTO:
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

        price_list_items_dto: list[ProductPriceListItemDetailDTO] = []
        active_list_ids: list[int] = []
        if hasattr(product, "price_list_items") and product.price_list_items:
            for pli in product.price_list_items:
                if pli.is_active:
                    active_list_ids.append(pli.price_list_id)
                price_list_items_dto.append(
                    ProductPriceListItemDetailDTO(
                        price_list_id=pli.price_list_id,
                        price_list_code=pli.price_list.code if pli.price_list else "",
                        price_list_name=pli.price_list.name if pli.price_list else "",
                        sale_price=pli.sale_price,
                        is_active=pli.is_active,
                    )
                )

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
            price_list_items=price_list_items_dto,
            active_price_list_ids=active_list_ids,
        )
