"""Canonical information relations and compatible body roles for catalog queries."""
from __future__ import annotations

import json
from pathlib import Path

STRUCTURAL_ROLES = frozenset({'cover', 'directory', 'section', 'closing'})
BODY_ROLES = frozenset({'body', 'content', 'framework', 'process', 'timeline', 'comparison',
                        'summary', 'schedule', 'data-chart', 'data-table',
                        'progress', 'parallel', 'cycle'})


def load_taxonomy(root: Path, catalog: dict) -> dict:
    path = root / catalog.get('relation_taxonomy', 'relation-taxonomy.json')
    return json.loads(path.read_text(encoding='utf-8-sig'))


def canonical(value: str | None, taxonomy: dict) -> str | None:
    if not value:
        return None
    key = value.strip().casefold()
    for name, group in taxonomy['relations'].items():
        if key == name.casefold() or key in (v.casefold() for v in group.get('aliases', [])) \
                or key in (v.casefold() for v in group.get('specific_relations', [])):
            return name
    return None


def is_generic(value: str, taxonomy: dict) -> bool:
    key = value.strip().casefold()
    return any(key == name.casefold() or key in (alias.casefold() for alias in group.get('aliases', []))
               for name, group in taxonomy['relations'].items())


def match_relation(entry: dict, requested: str | None, taxonomy: dict) -> bool:
    if not requested:
        return True
    actual = entry.get('information_relation')
    aliases = entry.get('relation_aliases', [])
    if requested == actual or requested in aliases:
        return True
    if not is_generic(requested, taxonomy):
        return False
    wanted = canonical(requested, taxonomy)
    return bool(wanted and wanted == entry.get('canonical_relation')
                and canonical(actual, taxonomy) == wanted)


def match_role(entry: dict, requested_role: str | None, requested_relation: str | None,
               taxonomy: dict) -> bool:
    if not requested_role:
        return True
    actual = entry.get('role')
    if actual == requested_role:
        return True
    # Only body pages may cross role labels, and only with a known relation.
    if not requested_relation or requested_role not in BODY_ROLES or actual not in BODY_ROLES \
            or entry.get('classification_status') != 'verified':
        return False
    wanted = canonical(requested_relation, taxonomy)
    return bool(wanted and match_relation(entry, requested_relation, taxonomy))
