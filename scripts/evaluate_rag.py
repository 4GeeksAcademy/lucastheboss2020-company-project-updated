#!/usr/bin/env python3
"""Measure labeled retrieval Recall@3 using local embeddings and Qdrant only.

This evaluation does not call an LLM and must not be presented as a generation or
faithfulness evaluation. Run setup_knowledge_base.py before running this script.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from data.process.rag import FastEmbedProvider, qdrant_client_from_env, retrieve

DEFAULT_QUERIES = REPOSITORY_ROOT / "data" / "eval" / "test-queries.json"
DEFAULT_OUTPUT = REPOSITORY_ROOT / "data" / "eval" / "recall_at_3.json"
RECALL_TARGET = 0.80


def evaluate_recall_at_3(query_path: Path = DEFAULT_QUERIES, output_path: Path = DEFAULT_OUTPUT) -> dict[str, object]:
    queries = json.loads(query_path.read_text(encoding="utf-8"))
    client = qdrant_client_from_env()
    embedder = FastEmbedProvider()
    results = []
    hits = 0
    for case in queries:
        retrieved = retrieve(case["question"], client=client, embedder=embedder, limit=3)
        hit = any(
            chunk.payload.get("source_document") == case["expected_source_document"]
            and chunk.payload.get("section") == case["expected_section"]
            and case["expected_evidence"].casefold() in str(chunk.payload.get("text", "")).casefold()
            for chunk in retrieved
        )
        hits += int(hit)
        results.append(
            {
                "id": case["id"],
                "hit_at_3": hit,
                "expected_source_document": case["expected_source_document"],
                "expected_section": case["expected_section"],
                "expected_evidence": case["expected_evidence"],
                "retrieved": [
                    {
                        "source_document": chunk.payload.get("source_document"),
                        "section": chunk.payload.get("section"),
                        "chunk_index": chunk.payload.get("chunk_index"),
                        "score": chunk.score,
                    }
                    for chunk in retrieved
                ],
            }
        )

    score = hits / len(queries) if queries else 0.0
    report = {
        "evaluation_type": "retrieval_only_local_embedding_model",
        "embedding_model": embedder.model_name,
        "generation_model_evaluated": False,
        "metric": "Recall@3",
        "hits": hits,
        "total_questions": len(queries),
        "recall_at_3": score,
        "target": RECALL_TARGET,
        "target_met": score >= RECALL_TARGET,
        "queries": results,
        "limitation": (
            "This measures local embedding retrieval only. It is not a course-provider evaluation, "
            "LLM answer faithfulness score, or evidence of live generation."
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Local retrieval Recall@3: {hits}/{len(queries)} = {score:.1%} (target {RECALL_TARGET:.0%})")
    print(f"Detailed results: {output_path}")
    return report


def main() -> None:
    report = evaluate_recall_at_3()
    if not report["target_met"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
