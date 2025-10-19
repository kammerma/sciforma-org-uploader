
from __future__ import annotations
from typing import Tuple
import random
from .models import OrgGraph, LEVELS, TOP_PARENT_ID
from .sciforma_client import SciformaClient

_generated_ids = set()

def _generate_unique_id(existing_ids: set[int]) -> int:
    """Generate a unique 6-digit integer ID (100000-999999)."""
    while True:
        val = random.randint(100000, 999999)
        if val not in existing_ids and val not in _generated_ids:
            _generated_ids.add(val)
            return val

def resolve_or_create_ids(graph: OrgGraph, client: SciformaClient, *, simulation: bool = False) -> Tuple[int, int]:
    """For every node, top-down by level: lookup by description, else create/synthesize.
    Returns (found_count, created_count).
    """
    found = 0
    created = 0

    for level in LEVELS:
        for (lvl, _), node in list(graph.nodes.items()):
            if lvl != level:
                continue

            node.parent_id = node.parent.id if (node.parent and node.parent.id is not None) else (TOP_PARENT_ID if node.parent is None else node.parent_id)

            existing = client.get_org_by_description(node.description)
            if existing and isinstance(existing, dict) and existing.get('id') is not None:
                node.id = int(existing['id']) if not isinstance(existing['id'], int) else existing['id']
                found += 1
                continue

            if not simulation:
                created_obj = client.create_organization(parent_id=node.parent_id, name=node.name, description=node.description)
                try:
                    node.id = int(created_obj.get('id')) if created_obj.get('id') is not None else node.id
                except Exception:
                    node.id = created_obj.get('id')
                created += 1
            else:
                # In simulation mode, synthesize a 6-digit id when GET returns nothing
                existing_ids = {n.id for n in graph.nodes.values() if n.id is not None}
                node.id = _generate_unique_id(existing_ids)

    graph.compute_sibling_id_links()
    return found, created
