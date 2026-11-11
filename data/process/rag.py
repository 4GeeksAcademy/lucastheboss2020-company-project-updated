"""Local embedding, source chunking, and Qdrant indexing/retrieval for TrackFlow RAG."""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol, Sequence

import numpy as np
from fastembed import TextEmbedding
from qdrant_client import QdrantClient, models

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_DIR = REPOSITORY_ROOT / "docs" / "company-knowledge-base"
COLLECTION_NAME = "trackflow_knowledge"
COMPANY = "trackflow"
LANGUAGE = "en"
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_MIN_SCORE = 0.35
MAX_CHUNK_CHARS = 500
MIN_CHUNKS_PER_DOCUMENT = 3
SOURCE_DOCUMENTS = {
    "trackflow-sla-delivery.en.md": "sla-delivery",
    "trackflow-returns-policy.en.md": "returns-policy",
    "trackflow-carrier-coverage.en.md": "carrier-coverage",
    "trackflow-storage-pricing.en.md": "storage-pricing",
}


class RagStoreError(RuntimeError):
    """Base error for knowledge-store configuration and operations."""


class KnowledgeBaseNotIndexedError(RagStoreError):
    """Raised when retrieval is requested before source documents are indexed."""


class EmbeddingProvider(Protocol):
    model_name: str

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


@dataclass(frozen=True)
class KnowledgeChunk:
    point_id: str
    payload: dict[str, str | int]


@dataclass(frozen=True)
class RetrievedChunk:
    score: float
    payload: dict[str, str | int]


def _split_long_paragraph(paragraph: str, max_chars: int) -> list[str]:
    """Split long paragraphs on sentence/word boundaries without dropping text."""
    if len(paragraph) <= max_chars:
        return [paragraph]
    sentences = re.split(r"(?<=[.!?])\s+", paragraph)
    pieces: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > max_chars:
            words = sentence.split()
            for word in words:
                if current and len(current) + len(word) + 1 > max_chars:
                    pieces.append(current)
                    current = ""
                current = f"{current} {word}".strip()
            continue
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > max_chars:
            pieces.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces


def chunk_markdown(
    markdown: str,
    source_document: str,
    max_chars: int = MAX_CHUNK_CHARS,
    min_chunks: int = MIN_CHUNKS_PER_DOCUMENT,
) -> list[KnowledgeChunk]:
    """Chunk Markdown by headings and paragraph boundaries, retaining section labels."""
    if source_document not in set(SOURCE_DOCUMENTS.values()):
        raise ValueError(f"Unsupported TrackFlow source document: {source_document}")
    if max_chars < 100:
        raise ValueError("max_chars must be at least 100 to preserve useful source context.")

    section = "Introduction"
    paragraph_lines: list[str] = []
    paragraphs: list[tuple[str, str]] = []

    def flush_paragraph() -> None:
        if paragraph_lines:
            text = " ".join(line.strip() for line in paragraph_lines).strip()
            if text:
                paragraphs.append((section, text))
            paragraph_lines.clear()

    for line in markdown.splitlines():
        stripped = line.strip()
        heading = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", stripped)
        if heading:
            flush_paragraph()
            section = heading.group(1).strip()
        elif not stripped:
            flush_paragraph()
        else:
            paragraph_lines.append(stripped)
    flush_paragraph()

    grouped: list[tuple[str, str]] = []
    active_section = ""
    active_parts: list[str] = []
    active_length = 0

    def flush_group() -> None:
        nonlocal active_section, active_parts, active_length
        if active_parts:
            grouped.append((active_section, "\n\n".join(active_parts)))
        active_section = ""
        active_parts = []
        active_length = 0

    for paragraph_section, paragraph in paragraphs:
        for piece in _split_long_paragraph(paragraph, max_chars):
            added_length = len(piece) + (2 if active_parts else 0)
            if active_parts and (paragraph_section != active_section or active_length + added_length > max_chars):
                flush_group()
            if not active_parts:
                active_section = paragraph_section
            active_parts.append(piece)
            active_length += len(piece) + (2 if len(active_parts) > 1 else 0)
    flush_group()

    while len(grouped) < min_chunks:
        if not grouped:
            break
        split_index = max(range(len(grouped)), key=lambda index: len(grouped[index][1]))
        split_section, text = grouped[split_index]
        sentences = re.split(r"(?<=[.!?])\s+", text)
        if len(sentences) < 2:
            words = text.split()
            if len(words) < 2:
                break
            midpoint = len(words) // 2
            parts = [" ".join(words[:midpoint]), " ".join(words[midpoint:])]
        else:
            midpoint = len(sentences) // 2
            parts = [" ".join(sentences[:midpoint]), " ".join(sentences[midpoint:])]
        grouped[split_index:split_index + 1] = [(split_section, part) for part in parts if part]

    chunks: list[KnowledgeChunk] = []
    for chunk_index, (chunk_section, text) in enumerate(grouped):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{COMPANY}:{source_document}:{chunk_index}"))
        chunks.append(
            KnowledgeChunk(
                point_id=point_id,
                payload={
                    "company": COMPANY,
                    "source_document": source_document,
                    "section": chunk_section,
                    "language": LANGUAGE,
                    "chunk_index": chunk_index,
                    "text": text,
                },
            )
        )
    if len(chunks) < min_chunks:
        raise ValueError(f"{source_document} produced fewer than {min_chunks} non-empty chunks.")
    return chunks


@lru_cache(maxsize=1)
def _load_fastembed_model(model_name: str) -> TextEmbedding:
    return TextEmbedding(model_name=model_name)


class FastEmbedProvider:
    """Credential-free local English embedding model used identically for docs and queries."""

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or os.getenv("RAG_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
        self._model: TextEmbedding | None = None

    @property
    def model(self) -> TextEmbedding:
        if self._model is None:
            self._model = _load_fastembed_model(self.model_name)
        return self._model

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [np.asarray(vector, dtype=np.float32).tolist() for vector in self.model.embed(list(texts))]

    def embed_query(self, text: str) -> list[float]:
        vector = next(iter(self.model.query_embed(text)))
        return np.asarray(vector, dtype=np.float32).tolist()


def qdrant_client_from_env() -> QdrantClient:
    url = os.getenv("QDRANT_URL", "http://localhost:6333").strip()
    api_key = os.getenv("QDRANT_API_KEY") or None
    if not url:
        raise RagStoreError("QDRANT_URL must point to a local or approved Qdrant service.")
    return QdrantClient(url=url, api_key=api_key, timeout=10)


def _vector_size(info: object) -> int | None:
    vector_config = info.config.params.vectors
    if isinstance(vector_config, dict):
        sizes = {config.size for config in vector_config.values()}
        return sizes.pop() if len(sizes) == 1 else None
    return vector_config.size


def _ensure_collection(client: QdrantClient, vector_size: int) -> None:
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        )
        return
    info = client.get_collection(COLLECTION_NAME)
    existing_size = _vector_size(info)
    if existing_size != vector_size:
        raise RagStoreError(
            f"Collection {COLLECTION_NAME} uses vector size {existing_size}, but the configured embedding model "
            f"produces {vector_size}; do not reuse the collection with an incompatible embedding model."
        )


def _existing_company_ids(client: QdrantClient) -> set[str]:
    existing: set[str] = set()
    offset = None
    company_filter = models.Filter(
        must=[models.FieldCondition(key="company", match=models.MatchValue(value=COMPANY))]
    )
    while True:
        points, offset = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=company_filter,
            limit=256,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )
        existing.update(str(point.id) for point in points)
        if offset is None:
            return existing


def setup(
    client: QdrantClient | None = None,
    embedder: EmbeddingProvider | None = None,
    source_dir: Path = DEFAULT_SOURCE_DIR,
    max_chars: int = MAX_CHUNK_CHARS,
) -> int:
    """Idempotently index all four approved sources into `trackflow_knowledge`."""
    qdrant = client or qdrant_client_from_env()
    embedding = embedder or FastEmbedProvider()
    chunks: list[KnowledgeChunk] = []
    for filename, source_slug in SOURCE_DOCUMENTS.items():
        path = source_dir / filename
        if not path.is_file():
            raise FileNotFoundError(f"Required TrackFlow source document is missing: {path}")
        document_chunks = chunk_markdown(path.read_text(encoding="utf-8"), source_slug, max_chars=max_chars)
        if len(document_chunks) < MIN_CHUNKS_PER_DOCUMENT:
            raise ValueError(f"{filename} must produce at least {MIN_CHUNKS_PER_DOCUMENT} chunks.")
        chunks.extend(document_chunks)

    vectors = embedding.embed_documents([str(chunk.payload["text"]) for chunk in chunks])
    if len(vectors) != len(chunks) or not vectors:
        raise RagStoreError("The embedding provider returned an invalid number of vectors.")
    vector_size = len(vectors[0])
    if vector_size == 0 or any(len(vector) != vector_size or not np.isfinite(vector).all() for vector in vectors):
        raise RagStoreError("The embedding provider returned empty, inconsistent, or non-finite vectors.")

    _ensure_collection(qdrant, vector_size)
    previous_ids = _existing_company_ids(qdrant)
    points = [
        models.PointStruct(id=chunk.point_id, vector=vector, payload=chunk.payload)
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    qdrant.upsert(collection_name=COLLECTION_NAME, points=points, wait=True)
    current_ids = {chunk.point_id for chunk in chunks}
    stale_ids = previous_ids - current_ids
    if stale_ids:
        qdrant.delete(
            collection_name=COLLECTION_NAME,
            points_selector=models.PointIdsList(points=sorted(stale_ids)),
            wait=True,
        )
    return len(chunks)


def retrieve(
    query: str,
    client: QdrantClient | None = None,
    embedder: EmbeddingProvider | None = None,
    limit: int = 5,
    min_score: float | None = None,
) -> list[RetrievedChunk]:
    """Retrieve only above-threshold TrackFlow chunks; never expose raw vectors."""
    if not query.strip():
        raise ValueError("Question must not be empty.")
    qdrant = client or qdrant_client_from_env()
    embedding = embedder or FastEmbedProvider()
    if not qdrant.collection_exists(COLLECTION_NAME):
        raise KnowledgeBaseNotIndexedError("Knowledge base is not indexed; run `python -m scripts.setup_knowledge_base`.")
    threshold = float(os.getenv("RAG_MIN_SCORE", str(DEFAULT_MIN_SCORE))) if min_score is None else min_score
    if not 0 <= threshold <= 1:
        raise ValueError("RAG_MIN_SCORE must be a cosine similarity threshold between 0 and 1.")
    response = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=embedding.embed_query(query),
        query_filter=models.Filter(
            must=[models.FieldCondition(key="company", match=models.MatchValue(value=COMPANY))]
        ),
        limit=limit,
        score_threshold=threshold,
        with_payload=True,
        with_vectors=False,
    )
    return [
        RetrievedChunk(score=float(point.score), payload=dict(point.payload or {}))
        for point in response.points
        if point.payload and point.payload.get("company") == COMPANY
    ]
