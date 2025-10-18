
from __future__ import annotations
from .models import OrgGraph
from .sciforma_client import SciformaClient


def enforce_ordering(graph: OrgGraph, client: SciformaClient, *, simulation: bool = False) -> int:
    '''PATCH each node so that Sciforma reflects correct ordering and parent.
    Returns number of processed nodes.'''
    processed = 0
    for node in graph.all_nodes_in_level_order():
        if node.id is None:
            # Cannot patch without an ID
            continue
        if not simulation:
            client.patch_organization(
                node.id,
                parent_id=node.parent_id,
                name=node.name,
                next_sibling_id=node.next_sibling_id,
            )
        processed += 1
    return processed
