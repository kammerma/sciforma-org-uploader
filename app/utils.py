
from __future__ import annotations
import csv
from pathlib import Path
from .models import OrgGraph, LEVELS, LEVEL_CODE_FIELDS, LEVEL_NAME_FIELDS


def build_graph_from_csv(csv_path: str) -> OrgGraph:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    graph = OrgGraph()

    with path.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        required = [
            'division_code','division','facility_code','facility',
            'department_code','department','bu_code','bu','bsu_code','bsu'
        ]
        missing = [h for h in required if h not in reader.fieldnames]
        if missing:
            raise ValueError(f"CSV missing headers: {missing}")

        for row in reader:
            parent = None
            for level in LEVELS:
                code_field = LEVEL_CODE_FIELDS[level]
                name_field = LEVEL_NAME_FIELDS[level]
                code = (row.get(code_field) or '').strip()
                name = (row.get(name_field) or '').strip()
                if not code and not name:
                    # skip empty levels if any (but spec expects all present)
                    continue
                node = graph.get_or_add(level, code, name, parent=parent)
                parent = node

    return graph
