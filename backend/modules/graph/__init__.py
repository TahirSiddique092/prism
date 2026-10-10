"""Graph module (Slice 12).

Writes the Neo4j topic graph on document upload:
    (User)-[:UPLOADED]->(Document)-[:ABOUT]->(Topic)

Public API:
- sync_document_to_graph(user_id, email, doc_id, title, topics) -> bool
- write_document_to_graph_async(..., sync=False) -> Thread | None
- normalize_topics(topics) -> list
"""
try:
    from backend.modules.graph.service import (
        sync_document_to_graph,
        write_document_to_graph_async,
        normalize_topics,
    )
except ImportError:
    from modules.graph.service import (
        sync_document_to_graph,
        write_document_to_graph_async,
        normalize_topics,
    )

__all__ = [
    "sync_document_to_graph",
    "write_document_to_graph_async",
    "normalize_topics",
]
