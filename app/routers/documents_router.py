import re
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlmodel import select

from app.core.config import settings
from app.core.database import get_db, get_session_maker
from app.dependencies import get_current_user, require_role
from app.models.document import DocumentFileTable, DocumentTable
from app.models.equipment import EquipmentTable
from app.models.user import UserTable
from app.schemas.document import DOCTYPE, DocumentOut
from app.schemas.user import Role
from app.services.documents_service import index_document
from app.services.text_processing import detect_type

router = APIRouter(prefix="/documents", tags=["documents"], dependencies=[Depends(get_current_user)])


async def get_document_or_404(document_id: UUID, db: AsyncSession = Depends(get_db)) -> DocumentTable:
    document = await db.get(DocumentTable, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.post("/upload", response_model=DocumentOut, status_code=202)
async def upload_document(
    background: BackgroundTasks,
    file: UploadFile = File(description="PDF, .txt or .md"),
    title: str = Form(min_length=1, max_length=100),
    doc_type: DOCTYPE = Form(),
    equipment_id: Optional[UUID] = Form(default=None, description="Leave empty for a general document"),
    user: UserTable = Depends(require_role(Role.SUPERVISOR)),
    db: AsyncSession = Depends(get_db),
    session_maker: async_sessionmaker = Depends(get_session_maker),
):
    """Store the file and return 202 Accepted at once; chunking and embedding run in the background.
    Poll GET /documents/{id} until is_indexed is true (or index_error explains the failure)."""
    limit = settings.max_upload_mb * 1024 * 1024
    content = await file.read(limit + 1)  # read one byte past the limit: never buffer an unbounded upload
    if len(content) > limit:
        raise HTTPException(status_code=413, detail=f"File is larger than {settings.max_upload_mb} MB")
    if not content:
        raise HTTPException(status_code=422, detail="File is empty")
    content_type = detect_type(file.filename or "", file.content_type, content)
    if content_type is None:
        raise HTTPException(status_code=415, detail="Only PDF, .txt and .md files are supported")
    if equipment_id is not None and await db.get(EquipmentTable, equipment_id) is None:
        raise HTTPException(status_code=404, detail="Equipment not found")

    document_id = uuid4()
    document = DocumentTable(
        id=document_id, title=title, doc_type=doc_type, equipment_id=equipment_id,
        blob_url=f"/api/v1/documents/{document_id}/file", file_size_bytes=len(content), content_type=content_type,
        uploaded_by=user.username, uploaded_by_id=user.id, is_indexed=False,
    )
    db.add(document)
    # Flush the parent first: SQLAlchemy orders INSERTs by relationship() links, not bare foreign keys,
    # so without this it may insert the file row before the document row it references.
    await db.flush()
    db.add(DocumentFileTable(document_id=document_id, content=content))
    await db.commit()
    await db.refresh(document)
    background.add_task(index_document, session_maker, document_id)
    return document


@router.get("", response_model=List[DocumentOut])
async def list_documents(
    equipment_id: Optional[UUID] = None,
    doc_type: Optional[DOCTYPE] = None,
    db: AsyncSession = Depends(get_db),
):
    statement = select(DocumentTable)
    if equipment_id is not None:
        statement = statement.where(DocumentTable.equipment_id == equipment_id)
    if doc_type is not None:
        statement = statement.where(DocumentTable.doc_type == doc_type)
    statement = statement.order_by(DocumentTable.uploaded_at.desc())  # type: ignore[attr-defined]
    return (await db.execute(statement)).scalars().all()


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(document: DocumentTable = Depends(get_document_or_404)):
    return document


@router.get("/{document_id}/file")
async def download_document(
    document: DocumentTable = Depends(get_document_or_404),
    db: AsyncSession = Depends(get_db),
):
    file = await db.get(DocumentFileTable, document.id)
    if file is None:
        raise HTTPException(status_code=404, detail="File not found")
    extension = {"application/pdf": "pdf", "text/markdown": "md"}.get(document.content_type or "", "txt")
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", document.title).strip("_") or "document"
    return Response(
        content=file.content,
        media_type=document.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{safe_name}.{extension}"'},
    )


@router.post("/{document_id}/reindex", response_model=DocumentOut, status_code=202,
             dependencies=[Depends(require_role(Role.SUPERVISOR))])
async def reindex_document(
    background: BackgroundTasks,
    document: DocumentTable = Depends(get_document_or_404),
    db: AsyncSession = Depends(get_db),
    session_maker: async_sessionmaker = Depends(get_session_maker),
):
    """Re-run indexing, e.g. after a failure or an embedding-model change."""
    document.is_indexed, document.index_error = False, None
    await db.commit()
    await db.refresh(document)
    background.add_task(index_document, session_maker, document.id)
    return document


@router.delete("/{document_id}", status_code=204, dependencies=[Depends(require_role(Role.ADMIN))])
async def delete_document(
    document: DocumentTable = Depends(get_document_or_404),
    db: AsyncSession = Depends(get_db),
):
    """The stored file and every chunk go with it (ON DELETE CASCADE)."""
    await db.delete(document)
    await db.commit()
    return Response(status_code=204)
