from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession
from src.application.dtos.catalog_dto import (
    ProductAdminDetailDTO,
    ProductCreateDTO,
    ProductPriceDetailDTO,
    ProductStockUpdateDTO,
    ProductTogglePublishDTO,
    ProductUpdatePricesDTO,
    UploadAttachmentResponseDTO,
)
from src.application.dtos.quote_dto import QuoteCreateDTO
from src.application.use_cases.catalog.admin_catalog import AdminCatalogUseCase
from src.application.use_cases.catalog.inventory_io import InventoryIOUseCase
from src.application.use_cases.catalog.upload_attachment import UploadAttachmentUseCase
from src.application.use_cases.quotes.generate_quote_pdf import GenerateQuotePdfUseCase
from src.domain.exceptions import (
    BusinessRuleViolationException,
    EntityNotFoundException,
)
from src.infrastructure.db.session import get_db_session
from src.infrastructure.security.audit import audit_log
from src.infrastructure.security.dependencies import require_admin
from src.infrastructure.security.jwt import TokenData

router = APIRouter(
    prefix="/admin",
    tags=["Backoffice Mariana (Admin)"],
    dependencies=[Depends(require_admin)],
)


@router.get("/products", response_model=list[ProductAdminDetailDTO])
async def list_products(
    category: str | None = Query(None, description="Filtrar por categoría"),
    provider: str | None = Query(None, description="Filtrar por proveedor"),
    is_published: bool | None = Query(None, description="Filtrar por estado de publicación"),
    has_conflict: bool | None = Query(
        None, description="Filtrar productos con conflictos históricos"
    ),
    is_incomplete: bool | None = Query(
        None, description="Filtrar fichas incompletas (PendingDraft)"
    ),
    stock_status: str | None = Query(
        None, description="Filtrar por stock ('low' para crítico, 'out' para agotado)"
    ),
    search: str | None = Query(None, description="Buscador por nombre"),
    limit: int = Query(50, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> list[ProductAdminDetailDTO]:
    use_case = AdminCatalogUseCase(session)
    return await use_case.list_products(
        category=category,
        provider=provider,
        is_published=is_published,
        has_conflict=has_conflict,
        is_incomplete=is_incomplete,
        stock_status=stock_status,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/products",
    response_model=ProductAdminDetailDTO,
    status_code=status.HTTP_201_CREATED,
)
async def create_product(
    data: ProductCreateDTO,
    admin_user: TokenData = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> ProductAdminDetailDTO:
    use_case = AdminCatalogUseCase(session)
    product = await use_case.create_product(data)
    audit_log(
        action="CREATE_PRODUCT",
        target_entity="product",
        target_id=product.id,
        actor=admin_user,
        details={"name": product.name, "category": product.category},
    )
    return product


@router.put("/products/{product_id}/prices", response_model=list[ProductPriceDetailDTO])
async def update_product_prices(
    product_id: int,
    data: ProductUpdatePricesDTO,
    admin_user: TokenData = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> list[ProductPriceDetailDTO]:
    use_case = AdminCatalogUseCase(session)
    try:
        updated = await use_case.update_prices(product_id, data.prices)
        audit_log(
            action="UPDATE_PRODUCT_PRICES",
            target_entity="product",
            target_id=product_id,
            actor=admin_user,
            details={"updated_prices_count": len(updated)},
        )
        return updated
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.put("/products/{product_id}/stock", response_model=ProductAdminDetailDTO)
async def update_product_stock(
    product_id: int,
    data: ProductStockUpdateDTO,
    admin_user: TokenData = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> ProductAdminDetailDTO:
    use_case = AdminCatalogUseCase(session)
    try:
        product = await use_case.update_stock(product_id, data)
        audit_log(
            action="UPDATE_PRODUCT_STOCK",
            target_entity="product",
            target_id=product_id,
            actor=admin_user,
            details={"current_stock": product.current_stock},
        )
        return product
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.patch("/products/{product_id}/publish")
async def toggle_product_publish(
    product_id: int,
    data: ProductTogglePublishDTO,
    admin_user: TokenData = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, bool]:
    use_case = AdminCatalogUseCase(session)
    try:
        new_state = await use_case.toggle_publication(product_id, data.is_published)
        audit_log(
            action="TOGGLE_PRODUCT_PUBLISH",
            target_entity="product",
            target_id=product_id,
            actor=admin_user,
            details={"is_published": new_state},
        )
        return {"is_published": new_state}
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except BusinessRuleViolationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post("/attachments", response_model=UploadAttachmentResponseDTO)
async def upload_attachment(
    file: UploadFile = File(...),
    product_id: int | None = Form(None),
    attachment_type: str | None = Form(None),
    session: AsyncSession = Depends(get_db_session),
) -> UploadAttachmentResponseDTO:
    use_case = UploadAttachmentUseCase(session)
    try:
        return await use_case.execute(file, product_id, attachment_type)
    except (BusinessRuleViolationException, EntityNotFoundException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post("/quotes/pdf")
async def generate_quote_pdf(
    data: QuoteCreateDTO,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    use_case = GenerateQuotePdfUseCase(session)
    try:
        pdf_bytes = await use_case.execute(data)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=presupuesto_2_rodriguez.pdf"},
        )
    except (EntityNotFoundException, BusinessRuleViolationException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("/providers", response_model=list[str])
async def list_providers(
    session: AsyncSession = Depends(get_db_session),
) -> list[str]:
    use_case = AdminCatalogUseCase(session)
    return await use_case.get_providers()


@router.get("/inventory/export")
async def export_inventory_csv(
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    use_case = InventoryIOUseCase(session)
    csv_bytes = await use_case.export_inventory_csv()
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=inventario_2rodriguez.csv"},
    )


@router.post("/inventory/import")
async def import_inventory_csv(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    content = await file.read()
    use_case = InventoryIOUseCase(session)
    return await use_case.import_inventory_csv(content)


@router.get("/catalog/template")
async def get_catalog_template() -> Response:
    use_case = InventoryIOUseCase(None)  # type: ignore[arg-type]
    csv_bytes = use_case.get_catalog_template_csv()
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=plantilla_catalogo_2rodriguez.csv"},
    )


@router.post("/catalog/import")
async def import_catalog_csv(
    file: UploadFile = File(...),
    admin_user: TokenData = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    content = await file.read()
    use_case = InventoryIOUseCase(session)
    result = await use_case.import_catalog_csv(content)
    audit_log(
        action="IMPORT_CATALOG_CSV",
        target_entity="catalog",
        actor=admin_user,
        details={
            "created": result.get("created_count", 0),
            "updated": result.get("updated_count", 0),
            "errors_count": len(result.get("errors", [])),
        },
    )
    return result
