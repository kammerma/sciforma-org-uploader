
from __future__ import annotations
import csv
from pathlib import Path
from .models import OrgGraph, LEVELS, LEVEL_CODE_FIELDS, LEVEL_NAME_FIELDS


def build_graph_from_csv(csv_path: str) -> OrgGraph:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    graph = OrgGraph()

    # Many regional CSV exports (e.g., from Excel in some locales) use ';' as the
    # delimiter instead of ','. Explicitly set the delimiter so semicolon-delimited
    # files are parsed correctly.
    # Use 'utf-8-sig' to automatically strip a UTF-8 BOM if present. Some
    # Windows/Excel exports include a BOM which corrupts the first fieldname
    # (e.g. '\ufeffdivision_code') and causes header validation to fail.
    with path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')

        # Normalize header names: strip whitespace and lower-case them so the
        # required header check is robust to casing/extra spaces and BOMs.
        if reader.fieldnames:
            reader.fieldnames = [fn.strip().lower() for fn in reader.fieldnames]

        required = [
            'division_code', 'division', 'facility_code', 'facility',
            'department_code', 'department', 'bu_code', 'bu', 'bsu_code', 'bsu'
        ]

        missing = [h for h in required if not reader.fieldnames or h not in reader.fieldnames]
        if missing:
            raise ValueError(f"CSV missing headers: {missing}")

        for row in reader:
            parent = None
            for level in LEVELS:
                code_field = LEVEL_CODE_FIELDS[level]
                name_field = LEVEL_NAME_FIELDS[level]
                # The DictReader fieldnames were normalized to lower-case; ensure
                # we lookup using the same normalized keys.
                code = (row.get(code_field) or row.get(code_field.lower()) or '').strip()
                name = (row.get(name_field) or row.get(name_field.lower()) or '').strip()
                if not code and not name:
                    # skip empty levels if any (but spec expects all present)
                    continue
                node = graph.get_or_add(level, code, name, parent=parent)
                parent = node

    return graph
