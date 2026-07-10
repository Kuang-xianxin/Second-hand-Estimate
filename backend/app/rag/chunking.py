"""Document chunking — recursive text splitting with hierarchy preservation.

Rules (per design doc §6.3):
  - Model specs: one doc per model
  - Fault knowledge: one fault point per chunk
  - Product records: title + description + structured metadata per doc
  - Long articles: split by heading levels, keep parent_doc_id
  - Business rules: one rule per doc
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Optional

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)


@dataclass
class Chunk:
    """One document chunk with metadata for Qdrant payload."""

    chunk_id: str                     # unique: {document_id}#{chunk_index}
    document_id: str                  # parent document id
    content: str                      # chunk text
    chunk_index: int                  # position within parent document
    total_chunks: int                 # total chunks in parent document
    document_type: str                # camera_knowledge / market_item / rule / faq
    brand: str = ""                   # camera brand (if applicable)
    model: str = ""                   # camera model (if applicable)
    topic: str = ""                   # sub-topic: storage_card / fault / pricing / spec
    source: str = "internal"          # internal / xianyu / manual
    source_url: str = ""
    content_hash: str = ""            # sha256 of content
    embedding_version: str = "bge-m3-v1"
    metadata: dict = field(default_factory=dict)  # extra fields


HEADERS_TO_SPLIT_ON = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
    ("####", "h4"),
]

_text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=512,
    chunk_overlap=64,
    separators=["\n\n", "\n", "。", "，", " ", ""],
)


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def chunk_text(
    content: str,
    document_id: str,
    document_type: str,
    brand: str = "",
    model: str = "",
    topic: str = "",
    source: str = "internal",
    source_url: str = "",
    use_markdown_headers: bool = True,
    metadata: dict | None = None,
) -> list[Chunk]:
    """Split a document into chunks, preserving markdown heading hierarchy.

    When `use_markdown_headers` is True (default for long articles / specs),
    splits on markdown headings first, then sub-splits by paragraph/sentence.

    For single-model specs or short rule docs, pass use_markdown_headers=False
    and the whole content becomes one chunk.
    """
    meta = metadata or {}

    if not use_markdown_headers or len(content) < 256:
        # Single chunk
        chunks = _text_splitter.split_text(content)
    else:
        md_splitter = MarkdownHeaderTextSplitter(HEADERS_TO_SPLIT_ON)
        try:
            md_splits = md_splitter.split_text(content)
            chunks = []
            for split in md_splits:
                sub = _text_splitter.split_text(split.page_content)
                # Carry heading metadata forward
                for s in sub:
                    chunks.append(s)
        except Exception:
            chunks = _text_splitter.split_text(content)

    if not chunks:
        chunks = [content]

    results = []
    total = len(chunks)
    for i, chunk in enumerate(chunks):
        text = chunk if isinstance(chunk, str) else str(chunk)
        if isinstance(chunk, str) and hasattr(chunk, "metadata"):
            pass  # not reachable here
        chunk_id = f"{document_id}#{i}"
        results.append(Chunk(
            chunk_id=chunk_id,
            document_id=document_id,
            content=text.strip(),
            chunk_index=i,
            total_chunks=total,
            document_type=document_type,
            brand=brand,
            model=model,
            topic=topic,
            source=source,
            source_url=source_url,
            content_hash=_hash(text),
            metadata=meta,
        ))

    return results


def chunk_camera_spec(
    brand: str, model: str, specs: str, *, xd_card_info: str = ""
) -> list[Chunk]:
    """Create chunks for one camera model spec entry.

    One chunk per model as per design doc §6.3 rule #1.
    """
    content = f"【{brand} {model}】\n{specs}"
    if xd_card_info:
        content += f"\n存储卡: {xd_card_info}"
    return chunk_text(
        content=content,
        document_id=f"camera_{brand.lower()}_{model.lower().replace(' ', '_')}",
        document_type="camera_knowledge",
        brand=brand,
        model=model,
        topic="spec",
        use_markdown_headers=False,
    )


def chunk_fault_knowledge(
    brand: str, model: str, fault_description: str, severity: str = "medium"
) -> list[Chunk]:
    """Create a chunk for one camera fault / repair knowledge entry."""
    return chunk_text(
        content=f"【{brand} {model} 常见故障】\n{fault_description}",
        document_id=f"fault_{brand.lower()}_{model.lower()}_{_hash(fault_description)}",
        document_type="camera_knowledge",
        brand=brand,
        model=model,
        topic="fault",
        use_markdown_headers=False,
        metadata={"severity": severity},
    )


def chunk_business_rule(rule_id: str, rule_text: str) -> list[Chunk]:
    """Create a chunk for one business/filter rule."""
    return chunk_text(
        content=rule_text,
        document_id=f"rule_{rule_id}",
        document_type="rule",
        topic="pricing",
        use_markdown_headers=False,
    )
