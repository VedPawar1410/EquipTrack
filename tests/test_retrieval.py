"""Hybrid retrieval against real Postgres (pgvector + full-text), with the deterministic test embedder."""
import pytest

from app.core.config import settings
from app.services import retrieval
from tests.test_documents import upload

LATHE_E47 = "Error E-47: spindle encoder fault. The encoder lost its position signal. Check the encoder cable and reseat the connector."
LATHE_E12 = "Coolant system. Error E-12 means coolant pressure is low. Inspect coolant pump P-3 and clean the filter."
PRESS_E47 = "Error E-47 on this press means the die clamp is open. Close the clamp before cycling."
LOCKOUT = "Lockout tagout procedure. Before any maintenance, isolate electrical power and attach your personal lock."


@pytest.fixture
async def library(supervisor, make_equipment):
    """Two machines whose manuals both use E-47 for different faults, plus one plant-wide document."""
    lathe = await make_equipment(name="CNC Lathe A3")
    press = await make_equipment(name="Press 7", equipment_type="Stamping Press")
    for body, machine, title in [(LATHE_E47, lathe, "Lathe errors"), (LATHE_E12, lathe, "Lathe coolant"),
                                 (PRESS_E47, press, "Press errors"), (LOCKOUT, None, "Plant LOTO")]:
        response = await upload(supervisor, body.encode(), title=title,
                                equipment_id=machine["id"] if machine else None)
        assert response.status_code == 202
    return {"lathe": lathe, "press": press}


async def test_code_match_is_exact_whatever_the_formatting(session_maker, library):
    async with session_maker() as db:
        hits = await retrieval.search(db, "what does e47 mean", library["lathe"]["id"])
    assert hits[0].title == "Lathe errors" and "code" in hits[0].matched_by
    assert retrieval.confidence(hits) == "high"


async def test_search_is_scoped_to_the_machine_plus_general_documents(session_maker, library):
    async with session_maker() as db:
        lathe_only = {h.title for h in await retrieval.search(db, "E-47", library["lathe"]["id"])}
        everywhere = {h.title for h in await retrieval.search(db, "E-47")}
        general = {h.title for h in await retrieval.search(db, "lockout tagout procedure", library["lathe"]["id"])}
    assert "Press errors" not in lathe_only and "Lathe errors" in lathe_only
    assert {"Lathe errors", "Press errors"} <= everywhere
    assert "Plant LOTO" in general                       # general documents apply to every machine


async def test_word_channel_uses_stemming(session_maker, library, monkeypatch):
    monkeypatch.setattr(settings, "rag_min_similarity", 0.0)   # isolate the word channel from the relevance gate
    async with session_maker() as db:
        hits = await retrieval.search(db, "inspecting pumps", library["lathe"]["id"])
    top = hits[0]
    assert top.title == "Lathe coolant" and "words" in top.matched_by    # "inspecting pumps" ~ "Inspect ... pump"


async def test_irrelevant_question_returns_nothing(session_maker, library):
    async with session_maker() as db:
        assert await retrieval.search(db, "what is the capital of France") == []
        assert retrieval.confidence([]) == "none"


async def test_matches_in_several_channels_rank_first(session_maker, library, monkeypatch):
    monkeypatch.setattr(settings, "rag_min_similarity", 0.0)   # let every chunk through so ranking is visible
    async with session_maker() as db:
        hits = await retrieval.search(db, "E-12 coolant pressure low", library["lathe"]["id"])
    assert hits[0].title == "Lathe coolant" and set(hits[0].matched_by) == {"code", "words", "meaning"}
    assert len(hits) > 1 and all(hits[0].score > other.score for other in hits[1:])


async def test_partial_word_overlap_alone_is_not_evidence(session_maker, library):
    # "before" and "cycling" appear in manuals, but no chunk has all the words, no code, no close meaning.
    async with session_maker() as db:
        assert await retrieval.search(db, "cycling before lunch breaks") == []
