import re
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dtos.catalog_dto import UploadAttachmentResponseDTO
from src.domain.exceptions import BusinessRuleViolationException, EntityNotFoundException
from src.infrastructure.db.models import ProductORM

UPLOAD_DIR = Path("uploads")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit


def _matches_magic_bytes(ext: str, content: bytes) -> bool:
    """Validates binary file signature (magic bytes) against declared extension."""
    if ext in (".jpg", ".jpeg"):
        return content.startswith(b"\xff\xd8\xff")
    if ext == ".png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if ext == ".webp":
        return len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"
    if ext == ".pdf":
        return content.startswith(b"%PDF-")
    return False


class UploadAttachmentUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute(
        self,
        file: UploadFile,
        product_id: int | None = None,
        attachment_type: str | None = None,
    ) -> UploadAttachmentResponseDTO:
        if not file.filename:
            raise BusinessRuleViolationException("El archivo debe tener un nombre válido.")

        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise BusinessRuleViolationException(
                f"Extensión '{ext}' no permitida. Formatos aceptados: JPG, PNG, WEBP, PDF."
            )

        content = await file.read()
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise BusinessRuleViolationException(
                f"El archivo excede el tamaño máximo permitido de 10 MB (tamaño actual: {len(content) / (1024 * 1024):.1f} MB)."
            )
        if len(content) == 0:
            raise BusinessRuleViolationException("El archivo subido está vacío.")

        if not _matches_magic_bytes(ext, content):
            raise BusinessRuleViolationException(
                f"El contenido binario del archivo no coincide con un formato válido para '{ext}'."
            )

        subfolder = "documents" if ext == ".pdf" else "images"
        target_dir = UPLOAD_DIR / subfolder
        target_dir.mkdir(parents=True, exist_ok=True)

        safe_stem = (
            re.sub(r"[^a-zA-Z0-9_-]", "_", Path(file.filename).stem)[:48].strip("_") or "file"
        )
        unique_filename = f"{uuid.uuid4().hex[:12]}_{safe_stem}{ext}"
        destination = target_dir / unique_filename

        with open(destination, "wb") as f:
            f.write(content)

        relative_url = f"/static/uploads/{subfolder}/{unique_filename}"

        # If associated with a product, update ORM
        if product_id is not None:
            stmt = select(ProductORM).where(ProductORM.id == product_id)
            result = await self.session.execute(stmt)
            product = result.scalar_one_or_none()
            if not product:
                raise EntityNotFoundException(f"Producto con ID {product_id} no encontrado.")

            if attachment_type == "image":
                product.image_url = relative_url
            elif attachment_type == "tech_sheet":
                product.tech_sheet_url = relative_url

            await self.session.commit()

        return UploadAttachmentResponseDTO(
            url=relative_url,
            filename=unique_filename,
            file_type=subfolder,
        )
