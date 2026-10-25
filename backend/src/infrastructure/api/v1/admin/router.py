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
from src.application.use_cases.catalog.upload_attachment import UploadAttachmentUseCase
from src.application.use_cases.quotes.generate_quote_pdf import GenerateQuotePdfUseCase
from src.domain.exceptions import (
    BusinessRuleViolationException,
    EntityNotFoundException,
)
from src.infrastructure.db.session import get_db_session
from src.infrastructure.security.dependencies import require_admin

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
    limit: int = Query(50, ge=1, le=500),
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
    session: AsyncSession = Depends(get_db_session),
) -> ProductAdminDetailDTO:
    use_case = AdminCatalogUseCase(session)
    return await use_case.create_product(data)


@router.put("/products/{product_id}/prices", response_model=list[ProductPriceDetailDTO])
async def update_product_prices(
    product_id: int,
    data: ProductUpdatePricesDTO,
    session: AsyncSession = Depends(get_db_session),
) -> list[ProductPriceDetailDTO]:
    use_case = AdminCatalogUseCase(session)
    try:
        return await use_case.update_prices(product_id, data.prices)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.put("/products/{product_id}/stock", response_model=ProductAdminDetailDTO)
async def update_product_stock(
    product_id: int,
    data: ProductStockUpdateDTO,
    session: AsyncSession = Depends(get_db_session),
) -> ProductAdminDetailDTO:
    use_case = AdminCatalogUseCase(session)
    try:
        return await use_case.update_stock(product_id, data)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.patch("/products/{product_id}/publish")
async def toggle_product_publish(
    product_id: int,
    data: ProductTogglePublishDTO,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, bool]:
    use_case = AdminCatalogUseCase(session)
    try:
        new_state = await use_case.toggle_publication(product_id, data.is_published)
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
