from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest
from qdrant_client import QdrantClient, models

from data.pipelines.rag import (
    INSUFFICIENT_INFORMATION,
    OpenAICompatibleGenerationProvider,
    ProviderConfigurationError,
    answer_question,
    generate_answer,
)
import services.knowledge_query as knowledge_query
from data.process.rag import (
    COLLECTION_NAME,
    FastEmbedProvider,
    RetrievedChunk,
    chunk_markdown,
    retrieve,
    setup,
)

SOURCE_DIR = Path(__file__).resolve().parents[2] / "docs" / "company-knowledge-base"
EXPECTED_FILES = {
    "trackflow-sla-delivery.en.md": "sla-delivery",
    "trackflow-returns-policy.en.md": "returns-policy",
    "trackflow-carrier-coverage.en.md": "carrier-coverage",
    "trackflow-storage-pricing.en.md": "storage-pricing",
}


class FakeEmbedder:
    model_name = "test-fake-vector"

    def embed_documents(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]

    def embed_query(self, text):
        return [1.0, 0.0, 0.0]


class FakeGenerator:
    def __init__(self, answer: str):
        self.answer = answer
        self.calls: list[tuple[str, str]] = []

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return self.answer


def test_all_sources_create_at_least_three_chunks_with_required_payload() -> None:
    for filename, source_slug in EXPECTED_FILES.items():
        markdown = (SOURCE_DIR / filename).read_text(encoding="utf-8")
        chunks = chunk_markdown(markdown, source_slug)

        assert len(chunks) >= 3
        assert [chunk.payload["chunk_index"] for chunk in chunks] == list(range(len(chunks)))
        for chunk in chunks:
            assert set(chunk.payload) == {
                "company",
                "source_document",
                "section",
                "language",
                "chunk_index",
                "text",
            }
            assert chunk.payload["company"] == "trackflow"
            assert chunk.payload["source_document"] == source_slug
            assert chunk.payload["language"] == "en"
            assert chunk.payload["section"]
            assert chunk.payload["text"]


def test_local_qdrant_setup_is_idempotent_and_replaces_stale_points(tmp_path: Path) -> None:
    client = QdrantClient(":memory:")
    embedder = FakeEmbedder()
    count_first = setup(client, embedder, SOURCE_DIR)
    count_second = setup(client, embedder, SOURCE_DIR)

    assert client.collection_exists(COLLECTION_NAME)
    assert count_first == count_second
    assert client.count(COLLECTION_NAME, exact=True).count == count_first

    changed_dir = tmp_path / "sources"
    changed_dir.mkdir()
    for filename in EXPECTED_FILES:
        source = (SOURCE_DIR / filename).read_text(encoding="utf-8")
        if filename == "trackflow-storage-pricing.en.md":
            source += "\n## New local test section\n" + ("Temporary evidence. " * 200)
        (changed_dir / filename).write_text(source, encoding="utf-8")
    changed_count = setup(client, embedder, changed_dir)
    assert client.count(COLLECTION_NAME, exact=True).count == changed_count
    assert changed_count > count_first


def test_local_qdrant_retrieval_returns_payload_without_vectors() -> None:
    client = QdrantClient(":memory:")
    setup(client, FakeEmbedder(), SOURCE_DIR)

    chunks = retrieve("What is the standard return window?", client, FakeEmbedder(), limit=3)

    assert len(chunks) == 3
    assert all(chunk.payload["company"] == "trackflow" for chunk in chunks)
    assert all("text" in chunk.payload for chunk in chunks)
    assert all(isinstance(chunk.score, float) for chunk in chunks)


def test_generation_uses_retrieved_context_and_cites_source() -> None:
    chunk = RetrievedChunk(
        score=0.82,
        payload={
            "company": "trackflow",
            "source_document": "returns-policy",
            "section": "Returns Policy",
            "language": "en",
            "chunk_index": 0,
            "text": "Standard return window: 30 days from delivery.",
        },
    )
    provider = FakeGenerator("The standard window is 30 days from delivery. [returns-policy | Returns Policy]")

    answer = generate_answer("What's the return window?", [chunk], provider)

    assert "30 days from delivery" in answer
    assert "[returns-policy | Returns Policy]" in answer
    assert len(provider.calls) == 1
    assert "Standard return window" in provider.calls[0][1]


def test_empty_context_still_calls_generator_then_returns_honest_answer() -> None:
    client = QdrantClient(":memory:")
    client.create_collection(
        COLLECTION_NAME,
        vectors_config=models.VectorParams(size=3, distance=models.Distance.COSINE),
    )
    provider = FakeGenerator("There are 30 days; I am guessing.")

    answer = answer_question("Question with no evidence", provider, client=client, embedder=FakeEmbedder())

    assert len(provider.calls) == 1
    assert "NO RELEVANT EVIDENCE" in provider.calls[0][1]
    assert answer == INSUFFICIENT_INFORMATION
    assert "30 days" not in answer


def _policy_prompt(policy: str, question: str) -> str:
    source = knowledge_query._POLICIES[policy]
    evidence = " ".join(source["evidence"])
    return (
        f"<context>\n[source_document: {source['source']} | section: {source['section']} | score: 0.9]\n"
        f"{evidence}\n</context>\n\nQuestion: {question}"
    )


@pytest.mark.parametrize(
    ("question", "policy", "safe_answer"),
    [
        (
            "Can we guarantee an SLA on Black Friday?",
            "peak_delivery",
            "TrackFlow does not guarantee delivery SLA during Black Friday; delivery can extend up to 40%, and clients must be informed proactively. [sla-delivery | Delivery SLA]",
        ),
        (
            "Are international returns automatic?",
            "international_returns",
            "No. International returns are not covered by the standard automated process and require manual handling by Sofía Ramos's team. [returns-policy | Returns Policy]",
        ),
        (
            "Can we offer a storage discount?",
            "storage_discount",
            "Clients over 50 cubic meters can negotiate a preferential rate, but the negotiation must go through Miguel Torres. [storage-pricing | Storage Pricing]",
        ),
        (
            "Can the account manager choose a carrier exception manually?",
            "carrier_exception",
            "An account manager may manually choose a carrier only for an exception approved by Carlos Vega. [carrier-coverage | Carrier Coverage]",
        ),
    ],
)
def test_safe_source_backed_policy_paraphrases_pass(question, policy, safe_answer) -> None:
    provider = FakeGenerator(safe_answer)
    guarded = knowledge_query._GuardedGenerationProvider(provider, question)

    answer = guarded.generate("system", _policy_prompt(policy, question))

    assert answer == safe_answer
    assert len(provider.calls) == 1


@pytest.mark.parametrize(
    ("question", "policy", "contradiction", "safe_caveat"),
    [
        (
            "Is the SLA guaranteed on Black Friday?", "peak_delivery",
            "The SLA is guaranteed on Black Friday.",
            "TrackFlow does not guarantee delivery SLA during Black Friday; delivery can extend up to 40%, and clients must be informed proactively. [sla-delivery | Delivery SLA]",
        ),
        (
            "Are international returns automatic?", "international_returns",
            "International returns are automatic.",
            "International returns are not covered by the standard automated process and require manual handling. [returns-policy | Returns Policy]",
        ),
        (
            "Can I offer a storage discount?", "storage_discount",
            "You can offer a discount without approval.",
            "Clients above 50 cubic meters can negotiate a preferential rate through Miguel Torres. [storage-pricing | Storage Pricing]",
        ),
        (
            "Can I manually choose a carrier exception?", "carrier_exception",
            "You can choose any carrier without approval.",
            "A carrier exception must be approved by Carlos Vega. [carrier-coverage | Carrier Coverage]",
        ),
    ],
)
def test_query_guard_rejects_contradiction_even_when_caveat_is_appended(question, policy, contradiction, safe_caveat) -> None:
    provider = FakeGenerator(f"{contradiction}\n{safe_caveat}")
    guarded = knowledge_query._GuardedGenerationProvider(provider, question)

    with pytest.raises(knowledge_query.UnsafeGeneratedAnswerError):
        guarded.generate("system", _policy_prompt(policy, question))
    assert len(provider.calls) == 1


def test_provider_reports_actionable_missing_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("RAG_API_BASE_URL", "RAG_API_KEY", "RAG_GENERATION_MODEL"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ProviderConfigurationError) as error:
        OpenAICompatibleGenerationProvider.from_env()

    message = str(error.value)
    assert "RAG_API_BASE_URL" in message
    assert "RAG_API_KEY" in message
    assert "RAG_GENERATION_MODEL" in message
    assert "No external model request was made" in message


def test_query_question_wrapper_returns_generated_string(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = FakeGenerator("Grounded answer. [sla-delivery | Delivery SLA]")
    observed: list[tuple[str, object]] = []

    def fake_answer(question: str, selected_provider: object) -> str:
        observed.append((question, selected_provider))
        return provider.answer

    monkeypatch.setattr(knowledge_query.OpenAICompatibleGenerationProvider, "from_env", lambda: provider)
    monkeypatch.setattr(knowledge_query, "answer_question", fake_answer)

    answer = knowledge_query.query("What is the standard SLA?")

    assert answer == provider.answer
    assert observed[0][0] == "What is the standard SLA?"
    assert observed[0][1].provider is provider


@pytest.mark.parametrize(
    ("question", "policy", "contradiction"),
    [
        ("Is the SLA guaranteed on Black Friday?", "peak_delivery", "The SLA is guaranteed on Black Friday."),
        ("Are international returns automatic?", "international_returns", "International returns are automatic."),
        ("Can I offer a storage discount?", "storage_discount", "You can offer a discount without approval."),
        ("Can I manually choose a carrier exception?", "carrier_exception", "You can choose any carrier without approval."),
    ],
)
def test_query_guard_rejects_contradictory_text_even_with_a_caveat(question, policy, contradiction) -> None:
    source = knowledge_query._POLICIES[policy]
    provider = FakeGenerator(f"{contradiction}\n{source['evidence'][0]}")
    guarded = knowledge_query._GuardedGenerationProvider(provider, question)

    with pytest.raises(knowledge_query.UnsafeGeneratedAnswerError):
        guarded.generate("system", _policy_prompt(policy, question))
    assert len(provider.calls) == 1


def test_query_guard_accepts_only_the_source_backed_exact_policy_answer() -> None:
    question = "Are international returns automatic?"
    source = knowledge_query._POLICIES["international_returns"]
    expected = "International returns are not covered by the standard automated process and require manual handling. [returns-policy | Returns Policy]"
    provider = FakeGenerator(expected)
    guarded = knowledge_query._GuardedGenerationProvider(provider, question)

    assert guarded.generate("system", _policy_prompt("international_returns", question)) == expected
    assert provider.calls[0][0] == "system"


def test_query_guard_fails_closed_when_critical_source_evidence_is_incomplete() -> None:
    provider = FakeGenerator("Delivery is guaranteed.")
    guarded = knowledge_query._GuardedGenerationProvider(provider, "Is the SLA guaranteed on Black Friday?")

    with pytest.raises(knowledge_query.UnsafeGeneratedAnswerError):
        guarded.generate("system", "<context>Black Friday may be busy.</context>")


def test_query_guard_rejects_unexpected_critical_policy_claim() -> None:
    provider = FakeGenerator("International returns are automatic.")
    guarded = knowledge_query._GuardedGenerationProvider(provider, "What is the standard return window?")

    with pytest.raises(knowledge_query.UnsafeGeneratedAnswerError):
        guarded.generate("system", "<context>Standard returns are accepted for 30 days.</context>")


def test_guarded_query_still_calls_generator_when_context_is_empty() -> None:
    client = QdrantClient(":memory:")
    client.create_collection(
        COLLECTION_NAME,
        vectors_config=models.VectorParams(size=3, distance=models.Distance.COSINE),
    )
    provider = FakeGenerator("Delivery is guaranteed on Black Friday.")
    guarded = knowledge_query._GuardedGenerationProvider(provider, "Is the SLA guaranteed on Black Friday?")

    answer = answer_question(
        "Is the SLA guaranteed on Black Friday?", guarded, client=client, embedder=FakeEmbedder()
    )

    assert len(provider.calls) == 1
    assert answer == INSUFFICIENT_INFORMATION


def test_local_embedding_adapter_uses_one_model_for_documents_and_queries() -> None:
    provider = FastEmbedProvider(model_name="BAAI/bge-small-en-v1.5")

    assert provider.model_name == "BAAI/bge-small-en-v1.5"
    assert provider._model is None
