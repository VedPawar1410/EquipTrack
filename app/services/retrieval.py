"""Hybrid retrieval: three searches in SQL over document_chunks, merged by reciprocal rank fusion.

  code    exact match on normalised codes       codes && :codes           (GIN)     "E-47" == "e47"
  words   English full-text, any word matches   content_tsv @@ OR-query   (GIN)     "vibrating" ~ "vibration"
          (all_words = the chunk contains every word of the question, which counts as strong evidence)
  meaning cosine similarity of embeddings       embedding <=> :vector     (HNSW)    "wobbles" ~ "vibration"

Reciprocal rank fusion scores each chunk by sum(weight / (60 + rank)) over the lists it appears in.
It uses ranks, not raw scores, so the three very different score scales never need calibrating.
"""
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.embeddings import get_embedder
from app.services.text_processing import extract_codes, without_codes

RRF_K = 60
WEIGHTS = {"code": 2.0, "words": 1.0, "meaning": 1.0}   # an exact code match is the strongest signal
CANDIDATES_PER_CHANNEL = 20

_SCOPE = "(CAST(:eid AS uuid) IS NULL OR c.equipment_id = CAST(:eid AS uuid) OR c.equipment_id IS NULL)"
_SELECT = """SELECT c.id, c.document_id, d.title, d.doc_type, c.page, c.content,
                    1 - (c.embedding <=> CAST(:vec AS vector)) AS similarity"""
_FROM = f"FROM document_chunks c JOIN documents d ON d.id = c.document_id WHERE {_SCOPE}"
_ANY_WORD = "replace(plainto_tsquery('english', :words)::text, '&', '|')::tsquery"   # AND -> OR

CODE_SQL = text(f"""{_SELECT} {_FROM}
       AND c.codes && CAST(:codes AS text[])
     ORDER BY cardinality(ARRAY(SELECT unnest(c.codes) INTERSECT SELECT unnest(CAST(:codes AS text[])))) DESC
     LIMIT {CANDIDATES_PER_CHANNEL}""")
# plainto_tsquery ANDs the words; the OR version lets a natural question match chunks sharing only some
# of its words (ranked by how well they match). all_words records whether the chunk has every word.
WORDS_SQL = text(f"""{_SELECT}, c.content_tsv @@ plainto_tsquery('english', :words) AS all_words {_FROM}
       AND c.content_tsv @@ {_ANY_WORD}
     ORDER BY ts_rank_cd(c.content_tsv, {_ANY_WORD}) DESC
     LIMIT {CANDIDATES_PER_CHANNEL}""")
MEANING_SQL = text(f"""{_SELECT} {_FROM}
     ORDER BY c.embedding <=> CAST(:vec AS vector)
     LIMIT {CANDIDATES_PER_CHANNEL}""")


@dataclass
class Hit:
    chunk_id: UUID
    document_id: UUID
    title: str
    doc_type: str
    page: int | None
    content: str
    similarity: float
    score: float = 0.0
    matched_by: list[str] = field(default_factory=list)
    all_words: bool = False

    @property
    def relevant(self) -> bool:
        """Evidence that passes: an exact code match, a chunk containing every word of the question,
        or close enough meaning. Partial word overlap ("machine", "check") only improves ranking."""
        return "code" in self.matched_by or self.all_words or self.similarity >= settings.rag_min_similarity


async def search(db: AsyncSession, query: str, equipment_id: UUID | None = None,
                 extra_codes: list[str] | None = None) -> list[Hit]:
    """Relevant chunks for `query`, best first, at most settings.rag_top_k of them."""
    codes = sorted(set(extract_codes(query)) | set(extra_codes or []))
    words = without_codes(query)
    vector = str(get_embedder().embed_query(query))
    params = {"eid": str(equipment_id) if equipment_id else None, "vec": vector}

    channels: dict[str, list] = {"meaning": (await db.execute(MEANING_SQL, params)).all()}
    if codes:
        channels["code"] = (await db.execute(CODE_SQL, {**params, "codes": codes})).all()
    if any(ch.isalpha() for ch in words):
        channels["words"] = (await db.execute(WORDS_SQL, {**params, "words": words})).all()

    hits: dict[UUID, Hit] = {}
    for channel, rows in channels.items():
        for rank, row in enumerate(rows, start=1):
            hit = hits.setdefault(row.id, Hit(row.id, row.document_id, row.title, row.doc_type, row.page,
                                               row.content, round(float(row.similarity), 4)))
            hit.score += WEIGHTS[channel] / (RRF_K + rank)
            hit.all_words = hit.all_words or bool(getattr(row, "all_words", False))
            hit.matched_by.append(channel)

    ranked = sorted((h for h in hits.values() if h.relevant), key=lambda h: h.score, reverse=True)
    return ranked[: settings.rag_top_k]


def confidence(hits: list[Hit]) -> str:
    """From retrieval evidence, not from asking the model how sure it is (LLMs are poor judges of that)."""
    if not hits:
        return "none"
    top = hits[0]
    if "code" in top.matched_by or (len(top.matched_by) >= 2 and top.similarity >= 0.7):
        return "high"
    return "medium"
