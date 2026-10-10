"""Graph module (Slice 12).

Writes the Neo4j topic graph on document upload:
    (User)-[:UPLOADED]->(Document)-[:ABOUT]->(Topic)

Public API:
- sync_document_to_graph(user_id, email, doc_id, title, topics) -> bool
- write_document_to_graph_async(..., sync=False) -> Thread | None
- normalize_topics(topics) -> list
- get_related_documents(doc_id, user_id, limit=5) -> list (Slice 13)
"""
try:
    from backend.modules.graph.service import (
        sync_document_to_graph,
        write_document_to_graph_async,
        normalize_topics,
        get_related_documents,
    )
except ImportError:
    from modules.graph.service import (
        sync_document_to_graph,
        write_document_to_graph_async,
        normalize_topics,
        get_related_documents,
    )

__all__ = [
    "sync_document_to_graph",
    "write_document_to_graph_async",
    "normalize_topics",
    "get_related_documents",
]
