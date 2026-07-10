"""Tests for RAG module — chunking, retriever, ingestion, evaluation."""
import os
import tempfile

from qdrant_client import QdrantClient

from app.rag import chunking
from app.rag.chunking import (
    Chunk,
    chunk_camera_spec,
    chunk_fault_knowledge,
    chunk_text,
)
from app.rag.citations import (
    EvidenceReport,
    make_knowledge_citation,
    make_market_citation,
)
from app.rag.embeddings import SimpleHashEmbedding, get_embedding_backend
from app.rag.evaluation import (
    EvalQuery,
    EvalMetrics,
    _ndcg_at_k,
    _precision_at_k,
    _recall_at_k,
    evaluate_retrieval,
)
from app.rag.ingestion import ingest_documents
from app.rag.reranker import IdentityReranker
from app.rag.retriever import HybridRetriever, RetrievalConfig, RetrievalResult


# ── Chunking tests ──

def test_chunk_text_single_short_document():
    chunks = chunk_text(
        "佳能 IXUS 130 是一款1400万像素的CCD卡片机。",
        document_id="test-001",
        document_type="camera_knowledge",
        use_markdown_headers=False,
    )
    assert len(chunks) >= 1
    assert all(isinstance(c, Chunk) for c in chunks)
    assert chunks[0].document_id == "test-001"
    assert chunks[0].document_type == "camera_knowledge"


def test_chunk_camera_spec():
    chunks = chunk_camera_spec(
        brand="Canon",
        model="IXUS 130",
        specs="1400万像素 CCD, 4倍光学变焦, SD卡存储",
    )
    assert len(chunks) >= 1
    assert "Canon" in chunks[0].content
    assert "IXUS 130" in chunks[0].content
    assert chunks[0].brand == "Canon"
    assert chunks[0].model == "IXUS 130"


def test_chunk_fault_knowledge():
    chunks = chunk_fault_knowledge(
        brand="Fujifilm",
        model="F30",
        fault_description="镜头伸缩卡顿，需更换排线。",
    )
    assert len(chunks) >= 1
    assert "Fujifilm" in chunks[0].content
    assert "F30" in chunks[0].content
    assert "镜头" in chunks[0].content


def test_chunk_long_markdown_document():
    content = """# CCD相机选购指南

## 存储卡类型

CCD相机使用多种存储卡，包括xD卡、SD卡和CF卡。

### xD卡

xD卡已经停产，价格较高。常见于富士和奥林巴斯相机。

### SD卡

SD卡是最通用的存储卡类型。

## 常见故障

### 镜头故障

镜头排线断裂是最常见的问题。
"""
    chunks = chunk_text(
        content,
        document_id="guide-001",
        document_type="faq",
        use_markdown_headers=True,
    )
    assert len(chunks) >= 1
    # Check that heading structure is preserved in at least one chunk
    contents = " ".join(c.content for c in chunks)
    assert "存储卡" in contents
    assert "镜头" in contents


def test_chunk_content_hash_deterministic():
    chunks1 = chunk_text("same content", "doc-1", "rule", use_markdown_headers=False)
    chunks2 = chunk_text("same content", "doc-1", "rule", use_markdown_headers=False)
    assert chunks1[0].content_hash == chunks2[0].content_hash


# ── Embedding tests ──

def test_simple_hash_embedding_deterministic():
    emb = SimpleHashEmbedding()
    v1 = emb.encode_query("佳能IXUS130")
    v2 = emb.encode_query("佳能IXUS130")
    assert v1 == v2
    assert len(v1) == 256


def test_simple_hash_different_queries():
    emb = SimpleHashEmbedding()
    v1 = emb.encode_query("佳能")
    v2 = emb.encode_query("索尼")
    assert v1 != v2


def test_simple_hash_batch_encode():
    emb = SimpleHashEmbedding()
    vecs = emb.encode(["a", "b", "c"])
    assert len(vecs) == 3
    assert all(len(v) == 256 for v in vecs)


def test_get_embedding_backend_returns_simple_hash():
    backend = get_embedding_backend()
    assert isinstance(backend, SimpleHashEmbedding)


# ── Retrieval tests (local Qdrant) ──

def _make_client() -> QdrantClient:
    """Create an in-memory Qdrant client for testing."""
    tmpdir = tempfile.mkdtemp()
    return QdrantClient(path=tmpdir)


def _seed_test_data(client: QdrantClient) -> HybridRetriever:
    """Seed a few documents and return a retriever."""
    import asyncio
    docs = [
        {
            "document_id": "cam-ixus130",
            "document_type": "camera_knowledge",
            "brand": "Canon",
            "model": "IXUS 130",
            "topic": "spec",
            "content": "佳能 IXUS 130 是一款 CCD 卡片机，使用 SD 卡存储。",
        },
        {
            "document_id": "cam-f30",
            "document_type": "camera_knowledge",
            "brand": "Fujifilm",
            "model": "FinePix F30",
            "topic": "spec",
            "content": "富士 FinePix F30 是一款 CCD 相机，使用 xD 卡存储。",
        },
        {
            "document_id": "storage-xd",
            "document_type": "camera_knowledge",
            "topic": "storage_card",
            "content": "xD Picture Card 是富士和奥林巴斯推出的存储卡标准，已停产。",
        },
    ]
    asyncio.run(ingest_documents(client, docs))
    return HybridRetriever(client)


def test_retrieve_returns_results():
    client = _make_client()
    retriever = _seed_test_data(client)
    results = retriever.retrieve("佳能 IXUS 130")
    assert len(results) >= 1
    assert any("IXUS" in r.content for r in results)


def test_retrieve_with_brand_filter():
    client = _make_client()
    retriever = _seed_test_data(client)
    cfg = RetrievalConfig(brand_filter="Canon")
    results = retriever.retrieve("卡片机", cfg)
    assert all(r.brand == "Canon" for r in results)


def test_retrieve_dense_only():
    client = _make_client()
    retriever = _seed_test_data(client)
    cfg = RetrievalConfig(enable_sparse=False)
    results = retriever.retrieve("xD 卡存储", cfg)
    assert len(results) >= 1


# ── Evaluation metrics tests ──

def test_recall_at_k_perfect():
    assert _recall_at_k(["a", "b", "c"], ["a", "c"], 3) == 1.0


def test_recall_at_k_partial():
    assert _recall_at_k(["a", "b", "c"], ["a", "d"], 3) == 0.5


def test_precision_at_k():
    assert _precision_at_k(["a", "x", "y"], ["a", "b"], 3) == 1.0 / 3


def test_ndcg_perfect():
    assert _ndcg_at_k(["a", "b", "c"], ["a", "b", "c"], 10) == 1.0


# ── Citations tests ──

def test_market_citation():
    c = make_market_citation("估价区间 ¥300-500", "23条样本，中位数¥400", doc_id="M1")
    assert c.fact_type.value == "market_fact"
    assert c.source_id == "M1"


def test_knowledge_citation():
    c = make_knowledge_citation("富士F30使用xD卡", "存储介质说明", doc_id="K01")
    assert c.fact_type.value == "knowledge_fact"


def test_evidence_report_format():
    report = EvidenceReport(
        market_facts=[make_market_citation("估价¥400", "数据", "M1")],
        knowledge_facts=[make_knowledge_citation("xD卡", "说明", "K1")],
        is_sufficient=True,
    )
    summary = report.summary()
    assert "M1" in summary
    assert "K1" in summary


# ── Reranker tests ──

def test_identity_reranker():
    reranker = IdentityReranker()
    results = [
        RetrievalResult(chunk_id="1", document_id="d1", content="a", score=0.5),
        RetrievalResult(chunk_id="2", document_id="d2", content="b", score=0.9),
        RetrievalResult(chunk_id="3", document_id="d3", content="c", score=0.3),
    ]
    reranked = reranker.rerank("query", results, top_k=2)
    assert len(reranked) == 2
    assert reranked[0].score == 0.9
