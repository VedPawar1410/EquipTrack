from typing import Optional
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, Column, Computed, ForeignKey, LargeBinary, Text, text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlmodel import Field, Relationship, SQLModel

from app.models.equipment import EquipmentTable
from app.schemas.document import DocumentShared
from app.services.embeddings import EMBEDDING_DIM


class DocumentTable(DocumentShared, table=True):
    __tablename__ = "documents"  # type: ignore
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    equipment_id: Optional[UUID] = Field(default=None, foreign_key="equipment.id")  # nullable: general documents
    uploaded_by: Optional[str] = Field(default=None, max_length=100)
    uploaded_by_id: Optional[UUID] = Field(default=None, foreign_key="users.id")
    content_type: Optional[str] = Field(default=None, max_length=100)
    index_error: Optional[str] = None

    equipment: Optional[EquipmentTable] = Relationship(back_populates="documents")


class DocumentFileTable(SQLModel, table=True):
    """The uploaded bytes, kept out of `documents` so listing documents never loads file contents."""
    __tablename__ = "document_files"  # type: ignore
    document_id: UUID = Field(sa_column=Column(ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True))
    content: bytes = Field(sa_column=Column(LargeBinary, nullable=False))


class DocumentChunkTable(SQLModel, table=True):
    """One searchable piece of a document, with its three search channels (see migration v1.5)."""
    __tablename__ = "document_chunks"  # type: ignore
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    document_id: UUID = Field(foreign_key="documents.id")
    equipment_id: Optional[UUID] = Field(default=None, foreign_key="equipment.id")
    chunk_index: int
    page: Optional[int] = None
    content: str
    codes: list[str] = Field(default_factory=list,
                             sa_column=Column(ARRAY(Text), nullable=False, server_default=text("'{}'")))
    embedding: list[float] = Field(sa_column=Column(Vector(EMBEDDING_DIM), nullable=False))
    # Computed by Postgres (GENERATED ALWAYS ... STORED); the ORM never writes it.
    content_tsv: Optional[str] = Field(
        default=None, sa_column=Column(TSVECTOR, Computed("to_tsvector('english', content)", persisted=True)))
