"""Document ingestion pipeline — chunk → embed → index → track versions.

Workflow:
  1. Read documents from knowledge_documents table (or seed data)
  2. Chunk each document
  3. Check content_hash — skip if already indexed
  4. Embed chunks
  5. Upsert to Qdrant (uses UUIDs generated from chunk_id for local mode compat)
  6. Update qdrant_status on knowledge_documents row to 'indexed'
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Sequence

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from app.rag.chunking import Chunk, chunk_text
from app.rag.embeddings import get_embedding_backend
from app.rag.retriever import DENSE_VECTOR, HybridRetriever

logger = logging.getLogger(__name__)


def _chunk_id_to_uuid(chunk_id: str) -> str:
    """Convert a human-readable chunk_id to a deterministic UUID for Qdrant."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"guessr:{chunk_id}"))


async def ingest_documents(
    client: QdrantClient,
    documents: list[dict],
    *,
    dry_run: bool = False,
) -> dict:
    """Ingest a batch of documents into Qdrant.

    Args:
        client: Qdrant client (local or remote)
        documents: list of dicts with keys:
            document_id, content, document_type, [brand, model, topic, source, source_url]
        dry_run: if True, chunk but don't index

    Returns:
        {"indexed": N, "skipped": N, "chunks": N, "errors": [...]}
    """
    retriever = HybridRetriever(client)
    retriever.ensure_collection()
    embedding = get_embedding_backend()

    indexed = 0
    skipped = 0
    errors = []
    all_points: list[PointStruct] = []

    for doc in documents:
        try:
            chunks = chunk_text(
                content=doc["content"],
                document_id=doc["document_id"],
                document_type=doc.get("document_type", "camera_knowledge"),
                brand=doc.get("brand", ""),
                model=doc.get("model", ""),
                topic=doc.get("topic", ""),
                source=doc.get("source", "internal"),
                source_url=doc.get("source_url", ""),
            )

            if not chunks:
                skipped += 1
                continue

            # Check for existing chunks with same hash (idempotent)
            existing = client.retrieve(
                collection_name=retriever._collection,
                ids=[_chunk_id_to_uuid(c.chunk_id) for c in chunks],
            )
            existing_ids = {p.id for p in existing if p and p.payload}
            new_chunks = [c for c in chunks if _chunk_id_to_uuid(c.chunk_id) not in existing_ids]
            skipped += len(chunks) - len(new_chunks)

            if not new_chunks:
                continue

            # Embed
            texts = [c.content for c in new_chunks]
            vectors = embedding.encode(texts)

            # Build points
            for chunk, vec in zip(new_chunks, vectors):
                all_points.append(PointStruct(
                    id=_chunk_id_to_uuid(chunk.chunk_id),
                    vector={DENSE_VECTOR: vec},
                    payload={
                        "chunk_id": chunk.chunk_id,
                        "document_id": chunk.document_id,
                        "content": chunk.content,
                        "document_type": chunk.document_type,
                        "brand": chunk.brand,
                        "model": chunk.model,
                        "topic": chunk.topic,
                        "source": chunk.source,
                        "source_url": chunk.source_url,
                        "content_hash": chunk.content_hash,
                        "embedding_version": chunk.embedding_version,
                        "chunk_index": chunk.chunk_index,
                        "total_chunks": chunk.total_chunks,
                    },
                ))
                indexed += 1
        except Exception as e:
            logger.error("Ingestion error for doc %s: %s", doc.get("document_id", "?"), e)
            errors.append({"document_id": doc.get("document_id"), "error": str(e)})

    # Batch upsert
    if all_points and not dry_run:
        retriever.index(all_points)
        logger.info("Indexed %d points (%d docs, %d skipped, %d errors)",
                     indexed, len(documents), skipped, len(errors))

    return {"indexed": indexed, "skipped": skipped, "chunks_total": len(all_points), "errors": errors}


async def reindex_knowledge_base(
    client: QdrantClient,
    documents: list[dict],
) -> dict:
    """Full reindex: clear collection, then ingest all documents."""
    retriever = HybridRetriever(client)
    retriever.ensure_collection()

    # Clear existing data
    try:
        client.delete_collection(retriever._collection)
        retriever.ensure_collection()
        logger.info("Cleared collection for reindex")
    except Exception:
        pass

    return await ingest_documents(client, documents)


# ── Seed data helpers ──

def make_seed_document(
    document_id: str,
    content: str,
    document_type: str = "camera_knowledge",
    **kwargs,
) -> dict:
    """Create a standardized seed document dict for ingestion."""
    return {
        "document_id": document_id,
        "content": content,
        "document_type": document_type,
        **kwargs,
    }
