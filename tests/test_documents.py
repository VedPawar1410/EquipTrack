import pytest
from sqlalchemy import text

from tests.conftest import make_pdf

ZERO = "00000000-0000-0000-0000-000000000000"
MANUAL = ("Section 4: Error codes.\n\nE-47 means the spindle encoder lost position. Check the encoder cable.\n\n"
          "E-12 means coolant pressure is low. Inspect pump P-3.")


async def upload(client, content=MANUAL.encode(), filename="manual.txt", title="Lathe manual",
                 doc_type="Error Code Reference", equipment_id=None):
    data = {"title": title, "doc_type": doc_type}
    if equipment_id:
        data["equipment_id"] = equipment_id
    return await client.post("/documents/upload", data=data, files={"file": (filename, content)})


async def test_upload_indexes_in_background(supervisor, engine, equipment):
    response = await upload(supervisor, equipment_id=equipment["id"])
    assert response.status_code == 202
    accepted = response.json()
    assert accepted["is_indexed"] is False and accepted["uploaded_by"] == "sup"
    assert accepted["blob_url"] == f"/api/v1/documents/{accepted['id']}/file"

    # The background task has finished by the time the in-process call returns.
    document = (await supervisor.get(f"/documents/{accepted['id']}")).json()
    assert document["is_indexed"] is True and document["index_error"] is None
    async with engine.connect() as conn:
        rows = (await conn.execute(text(
            "SELECT codes, equipment_id::text, vector_dims(embedding), content_tsv IS NOT NULL "
            "FROM document_chunks WHERE document_id = :id"), {"id": accepted["id"]})).all()
    assert rows and all(dims == 384 and has_tsv for _, _, dims, has_tsv in rows)
    assert {"E47", "E12", "P3"} <= {code for codes, *_ in rows for code in codes}
    assert all(eid == equipment["id"] for _, eid, *_ in rows)


async def test_pdf_upload_records_pages(supervisor, engine):
    doc = (await upload(supervisor, make_pdf(["Spindle error E-47", "Coolant pump P-3"]), "m.pdf")).json()
    assert doc["content_type"] == "application/pdf"
    async with engine.connect() as conn:
        pages = (await conn.execute(text("SELECT page FROM document_chunks WHERE document_id = :id ORDER BY page"),
                                    {"id": doc["id"]})).scalars().all()
    assert pages == [1, 2]


async def test_pdf_without_text_records_the_reason(supervisor):
    doc = (await upload(supervisor, make_pdf([""]), "scan.pdf")).json()
    stored = (await supervisor.get(f"/documents/{doc['id']}")).json()
    assert stored["is_indexed"] is False and "No extractable text" in stored["index_error"]


@pytest.mark.parametrize("content, filename, status", [
    (b"", "empty.txt", 422),
    (b"MZ\x90\x00", "tool.exe", 415),
])
async def test_rejected_uploads(supervisor, content, filename, status):
    assert (await upload(supervisor, content, filename)).status_code == status


async def test_too_large_is_413(supervisor, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "max_upload_mb", 0)
    assert (await upload(supervisor)).status_code == 413


async def test_unknown_equipment_is_404(supervisor):
    assert (await upload(supervisor, equipment_id=ZERO)).status_code == 404


async def test_technician_reads_but_cannot_upload(technician, supervisor):
    assert (await upload(technician)).status_code == 403
    doc = (await upload(supervisor)).json()
    assert [d["id"] for d in (await technician.get("/documents")).json()] == [doc["id"]]
    downloaded = await technician.get(f"/documents/{doc['id']}/file")
    assert downloaded.content == MANUAL.encode() and "Lathe_manual.txt" in downloaded.headers["content-disposition"]


async def test_list_filters(technician, supervisor, equipment):
    machine_doc = (await upload(supervisor, equipment_id=equipment["id"])).json()
    await upload(supervisor, title="Plant safety", doc_type="Safety Guide")
    assert [d["id"] for d in (await technician.get(f"/documents?equipment_id={equipment['id']}")).json()] == [machine_doc["id"]]
    assert len((await technician.get("/documents?doc_type=Safety Guide")).json()) == 1


async def test_reindex_after_fixing_nothing_is_idempotent(supervisor, engine):
    doc = (await upload(supervisor)).json()
    assert (await supervisor.post(f"/documents/{doc['id']}/reindex")).status_code == 202
    async with engine.connect() as conn:
        count = (await conn.execute(text("SELECT count(*) FROM document_chunks WHERE document_id = :id"),
                                    {"id": doc["id"]})).scalar_one()
    assert count == 1 and (await supervisor.get(f"/documents/{doc['id']}")).json()["is_indexed"] is True


async def test_delete_is_admin_only_and_cascades(admin, supervisor, engine):
    doc = (await upload(supervisor)).json()
    assert (await supervisor.delete(f"/documents/{doc['id']}")).status_code == 403
    assert (await admin.delete(f"/documents/{doc['id']}")).status_code == 204
    assert (await admin.get(f"/documents/{doc['id']}")).status_code == 404
    async with engine.connect() as conn:
        left = (await conn.execute(text("SELECT (SELECT count(*) FROM document_chunks) + (SELECT count(*) FROM document_files)"))).scalar_one()
    assert left == 0


async def test_hard_deleting_equipment_keeps_its_documents_as_general(admin, supervisor, engine, equipment):
    doc = (await upload(supervisor, equipment_id=equipment["id"])).json()
    await admin.delete(f"/equipment/{equipment['id']}/hard")
    assert (await admin.get(f"/documents/{doc['id']}")).json()["equipment_id"] is None   # ON DELETE SET NULL
    async with engine.connect() as conn:
        assert (await conn.execute(text("SELECT count(*) FROM document_chunks WHERE equipment_id IS NULL"))).scalar_one() == 1


async def test_unknown_document_is_404(technician):
    assert (await technician.get(f"/documents/{ZERO}")).status_code == 404
    assert (await technician.get(f"/documents/{ZERO}/file")).status_code == 404
