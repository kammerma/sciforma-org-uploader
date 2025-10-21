
from __future__ import annotations
from .models import OrgGraph
from .sciforma_client import SciformaClient
import time


def enforce_ordering(graph: OrgGraph, client: SciformaClient, *, simulation: bool = False) -> int:
    '''PATCH each node so that Sciforma reflects correct ordering and parent.
    Returns number of processed nodes.'''
    processed = 0
    # Traverse nodes in normal (level) order, starting with the first node.
    nodes = list(graph.all_nodes_in_level_order())
    for node in nodes:
        if node.id is None:
            # Cannot patch without an ID
            continue
        if not simulation:
            client.patch_organization(
                node.id,
                parent_id=node.parent_id,
                name=node.name,
                next_sibling_id=-10, # Move node to the bottom of their slibling list
            )
            # Pause briefly between PATCH requests to allow Sciforma to process them (likely not necessary)
            # time.sleep(3)
        processed += 1
    return processed
