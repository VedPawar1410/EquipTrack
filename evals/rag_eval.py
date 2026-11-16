"""Evaluate the RAG pipeline on the sample manuals: retrieval quality, the relevance threshold, and answers.

    python -m evals.rag_eval              # retrieval metrics + threshold sweep (free, no LLM calls)
    python -m evals.rag_eval --with-llm   # also generate answers with the LLM keys in .env (~23 calls)

Runs on a throwaway Postgres migrated by Liquibase (needs Docker) with the real embedding model.
Writes reports/rag_eval.json and reports/rag_eval.md.
"""
import argparse
import asyncio
import json
import logging
import os
import pathlib
import statistics
from datetime import date

# Settings need these to import; the eval builds its own database and never uses them.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://unused:unused@localhost:1/unused")
os.environ.setdefault("JWT_SECRET_KEY", "eval-only-secret-key-that-signs-nothing-01234")

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.models.document import DocumentFileTable, DocumentTable  # noqa: E402
from app.models.equipment import EquipmentTable  # noqa: E402
from app.services import ai_service, retrieval  # noqa: E402
from app.services.documents_service import index_document  # noqa: E402
from app.services.llm import get_chat_model  # noqa: E402
from tests.migrated_db import migrated_postgres  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANUALS = ROOT / "sample_data" / "manuals"
REPORTS = ROOT / "reports"
MACHINES = {  # key used in rag_cases.json -> (name, equipment type, manual file stem)
    "lathe": ("Northfield TL-300", "CNC Machine", "northfield_tl300_lathe"),
    "press": ("Northfield SP-800", "Stamping Press", "northfield_sp800_press"),
    "compressor": ("Northfield AC-55", "Air Compressor", "northfield_ac55_compressor"),
}
THRESHOLDS = [round(0.40 + 0.05 * i, 2) for i in range(8)]   # 0.40 .. 0.75


async def seed(session_maker) -> tuple[dict, dict]:
    machine_ids, stems = {}, {}
    async with session_maker() as db:
        for key, (name, kind, _) in MACHINES.items():
            machine = EquipmentTable(name=name, serial_number=f"EVAL-{key}", equipment_type=kind,
                                     location="Eval", department="Eval")
            db.add(machine)
            machine_ids[key] = machine.id
        await db.commit()
    owner = {stem: machine_ids[key] for key, (_, _, stem) in MACHINES.items()}
    for path in sorted(MANUALS.glob("*.md")):
        content = path.read_bytes()
        async with session_maker() as db:
            doc = DocumentTable(title=path.stem, blob_url="eval", content_type="text/markdown",
                                doc_type="Service Manual" if path.stem in owner else "Lockout/Tagout Procedure",
                                file_size_bytes=len(content), equipment_id=owner.get(path.stem))
            db.add(doc)
            await db.flush()
            db.add(DocumentFileTable(document_id=doc.id, content=content))
            await db.commit()
            stems[doc.id] = path.stem
        await index_document(session_maker, doc.id)
    return machine_ids, stems


def passes(hit: dict, threshold: float) -> bool:
    """Same rule as retrieval.Hit.relevant, replayed offline for every candidate threshold."""
    return "code" in hit["matched_by"] or hit["all_words"] or hit["similarity"] >= threshold


def retrieval_metrics(results: list[dict], threshold: float) -> dict:
    found1 = found3 = refused_ok = 0
    in_scope = [r for r in results if r["expect_doc"]]
    refusals = [r for r in results if not r["expect_doc"]]
    for r in results:
        kept = [h["doc"] for h in r["hits"] if passes(h, threshold)][: settings.rag_top_k]
        r.setdefault("kept", {})[str(threshold)] = kept
        if r["expect_doc"]:
            found1 += kept[:1] == [r["expect_doc"]]
            found3 += r["expect_doc"] in kept[:3]
        else:
            refused_ok += not kept
    return {"threshold": threshold, "hit_at_1": found1 / len(in_scope), "hit_at_3": found3 / len(in_scope),
            "refusal_accuracy": refused_ok / len(refusals),
            "overall": (found3 + refused_ok) / len(results)}


async def main(with_llm: bool, args_pause: float) -> None:
    cases = json.loads((ROOT / "evals" / "rag_cases.json").read_text())["cases"]
    with migrated_postgres() as url:
        engine = create_async_engine(url)
        session_maker = async_sessionmaker(engine, expire_on_commit=False)
        machine_ids, stems = await seed(session_maker)

        # Pass 1: every scored chunk per question (gate off), so thresholds can be compared offline.
        top_k, settings.rag_min_similarity, settings.rag_top_k = settings.rag_top_k, -1.0, 100
        results = []
        async with session_maker() as db:
            for case in cases:
                hits = await retrieval.search(db, case["question"], machine_ids.get(case["machine"]))
                results.append({**case, "hits": [
                    {"doc": stems[h.document_id], "similarity": h.similarity, "matched_by": h.matched_by,
                     "all_words": h.all_words} for h in hits]})
        settings.rag_top_k = top_k
        sweep = [retrieval_metrics(results, t) for t in THRESHOLDS]
        # The costs are asymmetric: an off-topic question that gets through still meets an LLM told to refuse,
        # but a relevant chunk filtered out here can never be answered. So: best hit@3 first, then refusals,
        # then the stricter threshold.
        best = max(sweep, key=lambda m: (m["hit_at_3"], m["refusal_accuracy"], m["threshold"]))

        answers = None
        if with_llm:
            chat = get_chat_model()
            if chat is None:
                raise SystemExit("--with-llm needs GROQ_API_KEY or GEMINI_API_KEY in .env")
            settings.rag_min_similarity = best["threshold"]
            answers = []
            async with session_maker() as db:
                for case in cases:
                    res = await ai_service.ask(db, chat, case["question"], machine_ids.get(case["machine"]))
                    refused = res.mode == "not_found" or ai_service.NOT_COVERED in res.answer
                    facts_ok = all(f.lower() in res.answer.lower() for f in case["facts"])
                    answers.append({"id": case["id"], "mode": res.mode, "model": res.model, "refused": refused,
                                    "correct": refused if not case["expect_doc"] else (not refused and facts_ok),
                                    "cited": any(s.cited for s in res.sources), "latency_ms": res.latency_ms,
                                    "answer": res.answer})
                    # RAG prompts are a few thousand tokens: pace calls under free-tier tokens-per-minute limits.
                    await asyncio.sleep(args_pause)
        await engine.dispose()

    report = {"date": str(date.today()), "cases": len(cases), "embedding_model": settings.embedding_model,
              "llm": {"order": settings.llm_order, "groq": settings.groq_model, "gemini": settings.gemini_model},
              "threshold_sweep": sweep, "chosen_threshold": best["threshold"], "retrieval": results, "answers": answers}
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "rag_eval.json").write_text(json.dumps(report, indent=2, default=str))
    (REPORTS / "rag_eval.md").write_text(render_markdown(report))
    print(render_markdown(report))


def render_markdown(r: dict) -> str:
    lines = [f"# RAG evaluation ({r['date']})", "",
             f"{r['cases']} questions over `sample_data/manuals` (fictional). Embeddings: `{r['embedding_model']}`. "
             "Generated by `python -m evals.rag_eval`.", "", "## Relevance threshold sweep (retrieval only)", "",
             "| threshold | hit@1 | hit@3 | refusal accuracy | overall |", "|---|---|---|---|---|"]
    for m in r["threshold_sweep"]:
        mark = " **chosen**" if m["threshold"] == r["chosen_threshold"] else ""
        lines.append(f"| {m['threshold']:.2f}{mark} | {m['hit_at_1']:.0%} | {m['hit_at_3']:.0%} | "
                     f"{m['refusal_accuracy']:.0%} | {m['overall']:.0%} |")
    t = str(r["chosen_threshold"])
    misses = [c for c in r["retrieval"] if (c["expect_doc"] and c["expect_doc"] not in c["kept"][t][:3])
              or (not c["expect_doc"] and c["kept"][t])]
    lines += ["", f"Retrieval misses at {r['chosen_threshold']:.2f}: "
              + (", ".join(f"`{c['id']}`" for c in misses) or "none")]
    if r["answers"]:
        a = r["answers"]
        lat = sorted(x["latency_ms"] for x in a if x["mode"] == "llm")
        lines += ["", "## Answers (LLM)", "",
                  f"- Correct: **{sum(x['correct'] for x in a)}/{len(a)}** (facts present, or correctly refused)",
                  f"- Answered by an LLM: {sum(x['mode'] == 'llm' for x in a)}, refused before any LLM call: "
                  f"{sum(x['mode'] == 'not_found' for x in a)}, extractive fallback: "
                  f"{sum(x['mode'] == 'extractive' for x in a)}",
                  f"- Answers with at least one citation: {sum(x['cited'] for x in a if x['mode'] == 'llm')}"
                  f"/{sum(x['mode'] == 'llm' for x in a)}",
                  (f"- LLM latency: median {statistics.median(lat):.0f} ms, max {max(lat)} ms" if lat
                   else "- no LLM answers"),
                  "", "| case | correct | mode | model | answer (start) |", "|---|---|---|---|---|"]
        for x in a:
            text = x["answer"].replace("\n", " ").replace("|", "/")[:90]
            verdict = "yes" if x["correct"] else "**no**"
            lines.append(f"| `{x['id']}` | {verdict} | {x['mode']} | {x['model'] or '-'} | {text} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--with-llm", action="store_true")
    parser.add_argument("--pause", type=float, default=8.0, help="seconds between LLM calls")
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    args = parser.parse_args()
    asyncio.run(main(args.with_llm, args.pause))
