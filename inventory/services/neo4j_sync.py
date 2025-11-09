"""
Neo4j sync utilities for GraphNode/GraphEdge.

Optional: Controlled by settings.NEO4J_ENABLED (default False).
Requires neo4j Python driver when enabled.

Usage:
    from inventory.services.neo4j_sync import sync_graph_to_neo4j
    sync_graph_to_neo4j()
"""
from __future__ import annotations

import logging
from typing import Optional

from django.conf import settings

from ..models import GraphNode, GraphEdge

logger = logging.getLogger(__name__)


def _get_neo4j_driver():
    try:
        from neo4j import GraphDatabase  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dep
        logger.error("Neo4j driver not installed: %s", exc)
        return None, None

    uri = getattr(settings, "NEO4J_URI", "bolt://localhost:7687")
    user = getattr(settings, "NEO4J_USER", "neo4j")
    password = getattr(settings, "NEO4J_PASSWORD", "neo4jpassword")
    return GraphDatabase.driver(uri, auth=(user, password)), GraphDatabase


def sync_graph_to_neo4j(clear_first: bool = True) -> Optional[int]:
    """Sync all GraphNode and GraphEdge to Neo4j.

    Returns number of nodes synced, or None when disabled/unavailable.
    """
    if not getattr(settings, "NEO4J_ENABLED", False):  # pragma: no cover - runtime flag
        logger.info("NEO4J_ENABLED is False; skipping sync")
        return None

    driver, _ = _get_neo4j_driver()
    if driver is None:
        return None

    def _run(tx, query, **params):
        return tx.run(query, **params)

    with driver.session() as session:  # type: ignore[attr-defined]
        if clear_first:
            session.write_transaction(_run, "MATCH (n) DETACH DELETE n")

        # Nodes
        count = 0
        for node in GraphNode.objects.all():
            session.write_transaction(
                _run,
                "MERGE (n:GraphNode {key: $key}) SET n.label=$label, n.group=$group, n.pos_x=$x, n.pos_y=$y, n.data=$data",
                key=node.key,
                label=node.label,
                group=node.group,
                x=node.pos_x,
                y=node.pos_y,
                data=node.data or {},
            )
            count += 1

        # Edges
        for edge in GraphEdge.objects.select_related("source", "target"):
            session.write_transaction(
                _run,
                """
                MATCH (s:GraphNode {key: $source})
                MATCH (t:GraphNode {key: $target})
                MERGE (s)-[r:ROUTE {label: $label}]->(t)
                SET r.weight=$weight, r.directed=$directed, r.data=$data
                """,
                source=edge.source.key,
                target=edge.target.key,
                label=edge.label or "",
                weight=float(edge.weight),
                directed=bool(edge.directed),
                data=edge.data or {},
            )

    driver.close()
    logger.info("Neo4j sync complete: %s nodes, %s edges", GraphNode.objects.count(), GraphEdge.objects.count())
    return count
