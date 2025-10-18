
from __future__ import annotations
from typing import Tuple
from .models import OrgGraph, LEVELS, TOP_PARENT_ID
from .sciforma_client import SciformaClient


def resolve_or_create_ids(graph: OrgGraph, client: SciformaClient, *, simulation: bool = False) -> Tuple[int, int]:
    '''For every node, top-down by level: lookup by description, else create.
    Returns (found_count, created_count).'''
    found = 0
    created = 0

    # Ensure parent nodes are created before children
    for level in LEVELS:
        # stable processing order: by encounter order of roots then children
        for (lvl, _), node in list(graph.nodes.items()):
            if lvl != level:
                continue

            # Update parent_id from current parent object if known
            node.parent_id = node.parent.id if (node.parent and node.parent.id is not None) else (TOP_PARENT_ID if node.parent is None else node.parent_id)

            # 1) Try to resolve by description
            existing = client.get_org_by_description(node.description)
            if existing and isinstance(existing, dict) and existing.get('id'):
                node.id = int(existing['id'])
                found += 1
                continue

            # 2) Create if missing and not simulation
            if not simulation:
                created_obj = client.create_organization(parent_id=node.parent_id, name=node.name, description=node.description)
                node.id = int(created_obj.get('id')) if created_obj.get('id') is not None else node.id
                created += 1
            else:
                # in simulation, leave id as-is (None)
                pass

    # After IDs exist for as many nodes as possible, compute sibling id links
    graph.compute_sibling_id_links()

    return found, created
