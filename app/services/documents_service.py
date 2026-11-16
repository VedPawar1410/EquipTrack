"""Background indexing: file -> text -> chunks -> embeddings -> document_chunks rows."""
import asyncio
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.document import DocumentChunkTable, DocumentFileTable, DocumentTable
from app.services.embeddings import get_embedder
from app.services.text_processing import Chunk, ExtractionError, chunk_pages, extract_pages


async def index_document(session_maker: async_sessionmaker, document_id: UUID) -> None:
    """Runs after the upload response is sent (FastAPI BackgroundTasks), with its own session.

    Re-running it is safe: old chunks are replaced. Any failure is recorded on the document
    (is_indexed=False, index_error=...) instead of being lost in a log.
    """
    async with session_maker() as db:
        document = await db.get(DocumentTable, document_id)
        file = await db.get(DocumentFileTable, document_id)
        if document is None or file is None:
            return
        try:
            # Parsing and embedding are CPU-bound: run them in a worker thread so the
            # event loop keeps serving other requests meanwhile.
            chunks = await asyncio.to_thread(_chunk, file.content, document.content_type or "")
            vectors = await asyncio.to_thread(get_embedder().embed_documents, [c.text for c in chunks])
            await db.execute(delete(DocumentChunkTable).where(DocumentChunkTable.document_id == document_id))
            db.add_all(
                DocumentChunkTable(document_id=document_id, equipment_id=document.equipment_id,
                                   chunk_index=c.index, page=c.page, content=c.text, codes=c.codes, embedding=v)
                for c, v in zip(chunks, vectors, strict=True)
            )
            document.is_indexed, document.index_error = True, None
            await db.commit()
        except Exception as exc:  # record every failure on the document; nothing is silently lost
            await db.rollback()
            await _mark_failed(db, document_id, exc)


def _chunk(content: bytes, content_type: str) -> list[Chunk]:
    chunks = chunk_pages(extract_pages(content, content_type))
    if not chunks:
        raise ExtractionError("No extractable text found (is it a scanned PDF without a text layer?)")
    return chunks


async def _mark_failed(db: AsyncSession, document_id: UUID, exc: Exception) -> None:
    document = await db.get(DocumentTable, document_id)
    if document is not None:
        document.is_indexed = False
        document.index_error = f"{type(exc).__name__}: {exc}"[:500]
        await db.commit()
