"""Neo4j topic-graph writes for document upload (Slice 12).

Graph schema:
    (User {user_id, email})
    (Document {doc_id, title})
    (Topic {name})
    (User)-[:UPLOADED]->(Document)
    (Document)-[:ABOUT]->(Topic)

All nodes use MERGE so repeated uploads never create duplicate User/Topic nodes.
Topic names are normalised (trimmed + lowercased + de-duplicated) so
"Normalization" and "normalization" map to a single node.

Graph writes degrade gracefully: any failure (including an unreachable Neo4j)
is logged and swallowed so the upload response is never blocked or failed.
"""
import logging
import threading

try:
    from backend.modules.graph.client import get_driver
except ImportError:
    from modules.graph.client import get_driver

logger = logging.getLogger(__name__)

# Single idempotent write. UNWIND over an empty topics list is a no-op, so the
# User/Document/UPLOADED portion still runs when a document has no topics.
WRITE_CYPHER = """
MERGE (u:User {user_id: $user_id})
SET u.email = $email
MERGE (d:Document {doc_id: $doc_id})
SET d.title = $title
MERGE (u)-[:UPLOADED]->(d)
WITH d
UNWIND $topics AS topic_name
MERGE (t:Topic {name: topic_name})
MERGE (d)-[:ABOUT]->(t)
"""


# Related documents by shared topics (Slice 13). Both the source document (d1)
# and each candidate (d2) must be UPLOADED by the same user, so results are
# scoped to the authenticated user's documents only.
RELATED_CYPHER = """
MATCH (u:User {user_id: $user_id})-[:UPLOADED]->(d1:Document {doc_id: $doc_id})-[:ABOUT]->(t:Topic)<-[:ABOUT]-(d2:Document)<-[:UPLOADED]-(u)
WHERE d2.doc_id <> $doc_id
RETURN d2.doc_id AS doc_id, d2.title AS title, COUNT(t) AS shared_topics
ORDER BY shared_topics DESC
LIMIT $limit
"""


def normalize_topics(topics) -> list:
    """Trim, lowercase, drop empties, and de-duplicate topic names (order-preserving)."""
    seen = set()
    result = []
    for t in topics or []:
        if not isinstance(t, str):
            continue
        name = t.strip().lower()
        if name and name not in seen:
            seen.add(name)
            result.append(name)
    return result


def sync_document_to_graph(user_id, email, doc_id, title, topics) -> bool:
    """Write the user, document, and topic nodes/relationships to Neo4j.

    Returns True on success, False if Neo4j is unconfigured/unreachable or the
    write fails. Never raises — a graph failure must not affect the upload.
    """
    normalized = normalize_topics(topics)
    try:
        driver = get_driver()
        if driver is None:
            logger.warning("Neo4j not configured; skipping graph write for doc %s", doc_id)
            return False
        with driver.session() as session:
            session.run(
                WRITE_CYPHER,
                user_id=user_id,
                email=email,
                doc_id=doc_id,
                title=title,
                topics=normalized,
            )
        return True
    except Exception as e:
        logger.warning("Graph write failed for doc %s: %s", doc_id, e)
        return False


def get_related_documents(doc_id, user_id, limit=5) -> list:
    """Return documents that share the most topics with ``doc_id`` (Slice 13).

    Scoped to the authenticated user's own documents. Returns a list of
    ``{doc_id, title, shared_topics}`` ordered by shared_topics descending,
    capped at ``limit``. Returns [] (never raises) if Neo4j is unconfigured or
    unreachable, or if there are no related documents.
    """
    try:
        driver = get_driver()
        if driver is None:
            logger.warning("Neo4j not configured; returning no related docs for %s", doc_id)
            return []
        with driver.session() as session:
            result = session.run(
                RELATED_CYPHER,
                doc_id=doc_id,
                user_id=user_id,
                limit=limit,
            )
            return [
                {
                    "doc_id": record["doc_id"],
                    "title": record["title"],
                    "shared_topics": record["shared_topics"],
                }
                for record in result
            ]
    except Exception as e:
        logger.warning("Related-documents query failed for doc %s: %s", doc_id, e)
        return []


def write_document_to_graph_async(user_id, email, doc_id, title, topics, sync=False):
    """Dispatch the graph write without blocking the HTTP response.

    If sync=True, runs synchronously (useful for test assertions).
    """
    if sync:
        sync_document_to_graph(user_id, email, doc_id, title, topics)
        return None

    t = threading.Thread(
        target=sync_document_to_graph,
        args=(user_id, email, doc_id, title, topics),
        daemon=True,
    )
    t.start()
    return t
