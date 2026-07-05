"""
Wrapper around the Neo4j driver exposing high-level graph operations used
by the Graph Agent: entity/relationship ingestion and Cypher-based querying.
"""
from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncGraphDatabase, AsyncDriver

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_driver: AsyncDriver | None = None


async def get_driver() -> AsyncDriver:
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
    return _driver


def _open_session(driver: AsyncDriver):
    """Omit database name when unset so Aura uses the instance default."""
    if settings.neo4j_database:
        return driver.session(database=settings.neo4j_database)
    return driver.session()


async def close_driver() -> None:
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None


async def verify_connectivity() -> bool:
    driver = await get_driver()
    try:
        await driver.verify_connectivity()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Neo4j connectivity check failed: %s", exc)
        return False


async def ensure_constraints() -> None:
    """Create uniqueness constraints so MERGE operations stay idempotent."""
    driver = await get_driver()
    async with _open_session(driver) as session:
        await session.run(
            "CREATE CONSTRAINT entity_name IF NOT EXISTS "
            "FOR (e:Entity) REQUIRE e.name IS UNIQUE"
        )


async def upsert_triples(triples: list[tuple[str, str, str]], document_id: str) -> int:
    """
    Merge (subject)-[relation]->(object) triples into the graph, tagging each
    relationship with the source document for provenance.
    """
    driver = await get_driver()
    query = """
    UNWIND $rows AS row
    MERGE (s:Entity {name: row.subject})
    MERGE (o:Entity {name: row.object})
    MERGE (s)-[r:RELATES {type: row.relation}]->(o)
    SET r.document_id = $document_id, r.updated_at = datetime()
    RETURN count(r) AS created
    """
    rows = [{"subject": s, "relation": r, "object": o} for s, r, o in triples]
    async with _open_session(driver) as session:
        result = await session.run(query, rows=rows, document_id=document_id)
        record = await result.single()
        return record["created"] if record else 0


async def run_cypher(cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Execute an arbitrary read-only Cypher query and return records as dicts."""
    driver = await get_driver()
    async with _open_session(driver) as session:
        result = await session.run(cypher, params or {})
        return [dict(record) async for record in result]


async def find_connections(entity_a: str, entity_b: str, max_hops: int = 3) -> list[dict[str, Any]]:
    """Find shortest paths between two entities, up to max_hops relationships."""
    cypher = f"""
    MATCH p = shortestPath((a:Entity {{name: $entity_a}})-[*1..{max_hops}]-(b:Entity {{name: $entity_b}}))
    RETURN [n IN nodes(p) | n.name] AS path_nodes,
           [r IN relationships(p) | r.type] AS path_relations
    LIMIT 5
    """
    return await run_cypher(cypher, {"entity_a": entity_a, "entity_b": entity_b})


async def neighbors_of(entity: str, limit: int = 20) -> list[dict[str, Any]]:
    cypher = """
    MATCH (e:Entity {name: $entity})-[r:RELATES]-(n:Entity)
    RETURN n.name AS neighbor, r.type AS relation, type(startNode(r) = e) AS outgoing
    LIMIT $limit
    """
    return await run_cypher(cypher, {"entity": entity, "limit": limit})


async def delete_by_document(document_id: str) -> int:
    """Remove relationships (and any entities left with no remaining edges) for a document."""
    driver = await get_driver()
    query = """
    MATCH ()-[r:RELATES {document_id: $document_id}]->()
    WITH r, startNode(r) AS s, endNode(r) AS o
    DELETE r
    WITH collect(s) + collect(o) AS candidates
    UNWIND candidates AS n
    WITH DISTINCT n
    WHERE NOT (n)--()
    DELETE n
    RETURN count(n) AS orphans_removed
    """
    async with _open_session(driver) as session:
        result = await session.run(query, document_id=document_id)
        record = await result.single()
        return record["orphans_removed"] if record else 0
