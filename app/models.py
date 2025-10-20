
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple

# Special constants from specification
TOP_PARENT_ID = 1
NO_SIBLING_ID = -10

LEVELS = ["division", "facility", "department", "bu", "bsu"]
LEVEL_CODE_FIELDS = {
    "division": "division_code",
    "facility": "facility_code",
    "department": "department_code",
    "bu": "bu_code",
    "bsu": "bsu_code",
}
LEVEL_NAME_FIELDS = {
    "division": "division",
    "facility": "facility",
    "department": "department",
    "bu": "bu",
    "bsu": "bsu",
}

@dataclass(slots=True)
class Node:
    level: str
    code: str
    name: str
    organization_code: str
    parent: Optional["Node"] = None
    children: List["Node"] = field(default_factory=list)

    # Sciforma-related identifiers
    id: Optional[int] = None
    parent_id: int = TOP_PARENT_ID

    # Sibling linkage in-memory
    previous_sibling: Optional["Node"] = None
    next_sibling: Optional["Node"] = None

    # Persisted sibling IDs (computed after IDs known)
    previous_sibling_id: int = NO_SIBLING_ID
    next_sibling_id: int = NO_SIBLING_ID

    def to_dict(self) -> Dict:
        return {
            "parent_id": self.parent_id,
            "previous_sibling_id": self.previous_sibling_id,
            "name": self.name,
            "organization_code": self.organization_code,
            "id": self.id,
            "next_sibling_id": self.next_sibling_id,
            "level": self.level,
            "code": self.code,
        }

    def attach_child(self, child: "Node") -> None:
        if self.children:
            # set sibling pointers based on encounter order
            prev = self.children[-1]
            prev.next_sibling = child
            child.previous_sibling = prev
        self.children.append(child)
        child.parent = self
        child.parent_id = self.id if self.id is not None else (self.parent_id if self.parent_id != TOP_PARENT_ID else TOP_PARENT_ID)


class OrgGraph:
    # Holds all nodes keyed by (level, code)

    def __init__(self) -> None:
        self.nodes: Dict[Tuple[str, str], Node] = {}
        self.roots_in_order: List[Node] = []  # top-level divisions in encounter order

    def get_or_add(self, level: str, code: str, name: str, *, parent: Optional[Node]) -> Node:
        key = (level, code)
        if key in self.nodes:
            node = self.nodes[key]
            # If coming from a new parent, ensure parent-child linkage is set once
            if parent and node.parent is None:
                parent.attach_child(node)
            return node
        node = Node(level=level, code=code, name=name, organization_code=code)
        self.nodes[key] = node
        if parent:
            parent.attach_child(node)
        else:
            # top-level root
            if self.roots_in_order:
                prev = self.roots_in_order[-1]
                prev.next_sibling = node
                node.previous_sibling = prev
            self.roots_in_order.append(node)
        return node

    def all_nodes_in_level_order(self) -> List[Node]:
        # Top-down by levels to ensure parents are processed before children for ID resolution
        ordered: List[Node] = []
        for lvl in LEVELS:
            for (level, _), node in self.nodes.items():
                if level == lvl:
                    ordered.append(node)
        return ordered

    def compute_sibling_id_links(self) -> None:
        for node in self.nodes.values():
            node.previous_sibling_id = node.previous_sibling.id if (node.previous_sibling and node.previous_sibling.id is not None) else NO_SIBLING_ID
            node.next_sibling_id = node.next_sibling.id if (node.next_sibling and node.next_sibling.id is not None) else NO_SIBLING_ID
            node.parent_id = node.parent.id if (node.parent and node.parent.id is not None) else (TOP_PARENT_ID if node.parent is None else node.parent_id)

    def as_list(self) -> List[dict]:
        return [n.to_dict() for n in self.all_nodes_in_level_order()]
