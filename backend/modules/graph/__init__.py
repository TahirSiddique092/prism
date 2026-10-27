"""Graph module (Slice 12).

Writes the Neo4j topic graph on document upload:
    (User)-[:UPLOADED]->(Document)-[:ABOUT]->(Topic)

Public API:
- sync_document_to_graph(user_id, email, doc_id, title, topics) -> bool
- write_document_to_graph_async(..., sync=False) -> Thread | None
- normalize_topics(topics) -> list
- get_related_documents(doc_id, user_id, limit=5) -> list (Slice 13)
- get_document_topics(doc_id, user_id) -> list (Slice 20)
- delete_document_from_graph(doc_id, user_id) -> bool (Slice 24)
"""
try:
    from backend.modules.graph.service import (
        sync_document_to_graph,
        write_document_to_graph_async,
        normalize_topics,
        get_related_documents,
        get_document_topics,
        delete_document_from_graph,
    )
except ImportError:
    from modules.graph.service import (
        sync_document_to_graph,
        write_document_to_graph_async,
        normalize_topics,
        get_related_documents,
        get_document_topics,
        delete_document_from_graph,
    )

__all__ = [
    "sync_document_to_graph",
    "write_document_to_graph_async",
    "normalize_topics",
    "get_related_documents",
    "get_document_topics",
    "delete_document_from_graph",
]
