
from __future__ import annotations
from .models import OrgGraph
from .sciforma_client import SciformaClient


def enforce_ordering(graph: OrgGraph, client: SciformaClient, *, simulation: bool = False) -> int:
    '''PATCH each node so that Sciforma reflects correct ordering and parent.
    Returns number of processed nodes.'''
    processed = 0
    # Ensure we traverse the nodes in reverse order so the last node is processed first.
    nodes = list(graph.all_nodes_in_level_order())
    for node in reversed(nodes):
        if node.id is None:
            # Cannot patch without an ID
            continue
        if not simulation:
            client.patch_organization(
                node.id,
                parent_id=node.parent_id,
                name=node.name,
                next_sibling_id=node.next_sibling_id,
                code=node.code,
            )
        processed += 1
    return processed
