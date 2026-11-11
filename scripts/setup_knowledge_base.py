#!/usr/bin/env python3
"""Idempotently index approved TrackFlow documents in the local Qdrant collection."""

from __future__ import annotations

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from data.process.rag import FastEmbedProvider, qdrant_client_from_env, setup


def main() -> None:
    client = qdrant_client_from_env()
    count = setup(client=client, embedder=FastEmbedProvider())
    print(f"Indexed {count} TrackFlow chunks into trackflow_knowledge.")


if __name__ == "__main__":
    main()
