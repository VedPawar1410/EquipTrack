"""The /ai endpoints with recording fake chat models: no real LLM is ever called in tests."""
import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from app.main import app
from app.services.llm import get_chat_model
from tests.test_documents import upload
from tests.test_retrieval import LATHE_E12, LATHE_E47, LOCKOUT

ZERO = "00000000-0000-0000-0000-000000000000"


class RecordingChat(BaseChatModel):
    reply: str = "E-47 means the spindle encoder lost position [1]. Check the encoder cable [1]."
    fail: bool = False
    calls: list = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "recording-fake"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls.append(messages)
        if self.fail:
            raise RuntimeError("provider is down")
        return ChatResult(generations=[ChatGeneration(
            message=AIMessage(content=self.reply, response_metadata={"model_name": "fake-model"}))])


@pytest.fixture
def use_chat():
    def _use(chat):
        app.dependency_overrides[get_chat_model] = lambda: chat
        return chat
    yield _use
    app.dependency_overrides[get_chat_model] = lambda: None


@pytest.fixture
async def lathe(supervisor, make_equipment):
    machine = await make_equipment(name="CNC Lathe A3")
    for body, title, eid in [(LATHE_E47, "Lathe errors", machine["id"]), (LATHE_E12, "Lathe coolant", machine["id"]),
                             (LOCKOUT, "Plant LOTO", None)]:
        await upload(supervisor, body.encode(), title=title, equipment_id=eid)
    return machine


async def test_ask_answers_from_sources_with_citations(technician, lathe, use_chat):
    chat = use_chat(RecordingChat())
    body = (await technician.post("/ai/ask", json={"question": "What does E-47 mean?", "equipment_id": lathe["id"]})).json()
    assert body["mode"] == "llm" and body["model"] == "fake-model" and body["confidence"] == "high"
    assert body["answer"].startswith("E-47 means")
    assert body["sources"][0]["title"] == "Lathe errors" and body["sources"][0]["cited"] is True
    system, human = chat.calls[0]
    assert "ONLY from the numbered manual excerpts" in system.content
    assert "[1] Lathe errors" in human.content and "Question: What does E-47 mean?" in human.content


async def test_answer_typography_is_normalised(technician, lathe, use_chat):
    # Full-width citations and non-breaking hyphens/spaces, as gpt-oss produces them.
    use_chat(RecordingChat(reply="Order part TL\u2011ENC\u201104 within\u202f2\u202fdays 【1】."))
    body = (await technician.post("/ai/ask", json={"question": "E-47"})).json()
    assert body["answer"] == "Order part TL-ENC-04 within 2 days [1]." and body["sources"][0]["cited"] is True


async def test_nothing_relevant_means_no_llm_call(technician, lathe, use_chat):
    chat = use_chat(RecordingChat())
    body = (await technician.post("/ai/ask", json={"question": "What is the capital of France?"})).json()
    assert body["mode"] == "not_found" and body["confidence"] == "none" and body["sources"] == []
    assert chat.calls == []


async def test_without_any_model_the_answer_is_excerpts(technician, lathe):
    body = (await technician.post("/ai/ask", json={"question": "E-47", "equipment_id": lathe["id"]})).json()
    assert body["mode"] == "extractive" and body["model"] is None
    assert "No AI model is available" in body["answer"] and "Lathe errors" in body["answer"]


async def test_fallback_provider_answers_when_the_first_fails(technician, lathe, use_chat):
    primary, backup = RecordingChat(fail=True), RecordingChat(reply="From the backup [1].")
    use_chat(primary.with_fallbacks([backup]))
    body = (await technician.post("/ai/ask", json={"question": "E-47"})).json()
    assert body["mode"] == "llm" and body["answer"] == "From the backup [1]."
    assert len(primary.calls) == 1 and len(backup.calls) == 1


async def test_every_provider_failing_degrades_to_excerpts(technician, lathe, use_chat):
    use_chat(RecordingChat(fail=True).with_fallbacks([RecordingChat(fail=True)]))
    body = (await technician.post("/ai/ask", json={"question": "E-47"})).json()
    assert body["mode"] == "extractive"


async def test_diagnose_uses_machine_history_and_open_issue_codes(technician, lathe, use_chat):
    await technician.post(f"/equipment/{lathe['id']}/maintenance",
                          json={"log_type": "Cleaning", "performed_at": "2026-11-01", "description": "Flushed coolant lines"})
    await technician.post("/issues", json={"equipment_id": lathe["id"], "title": "Coolant warning",
                                           "severity": "High", "error_code": "E-12"})
    chat = use_chat(RecordingChat(reply="Likely a clogged filter [1]."))
    # The symptom has no code in it: the E-12 from the open issue is what finds the coolant manual.
    body = (await technician.post(f"/ai/diagnose/{lathe['id']}", json={"symptom": "warning light on the panel"})).json()
    assert body["mode"] == "llm" and body["sources"][0]["title"] == "Lathe coolant"
    prompt = chat.calls[0][1].content
    assert "Health score 80/100" in prompt and "Flushed coolant lines" in prompt and "(error E-12)" in prompt


async def test_validation_and_not_found(technician, anon, users):
    assert (await anon.post("/ai/ask", json={"question": "E-47?"})).status_code == 401
    assert (await technician.post("/ai/ask", json={"question": "hi"})).status_code == 422
    assert (await technician.post("/ai/ask", json={"question": "E-47?", "equipment_id": ZERO})).status_code == 404
    assert (await technician.post(f"/ai/diagnose/{ZERO}", json={"symptom": "noise"})).status_code == 404
