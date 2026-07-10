"""RAG module — document ingestion, embedding, retrieval, reranking.

Architecture:
  Ingestion → Chunking → Embedding → Qdrant (hybrid index)
  Query → Embedding → Dense+Sparse+RRF → Reranker → Top-K → Citations
"""
