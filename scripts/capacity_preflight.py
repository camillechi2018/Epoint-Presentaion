"""Read binding and reviewed long-copy limits before trying a source layout."""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from content_adapters import adapt_for_layout
from fill_layout import visual_width_units


@lru_cache(maxsize=8)
def _review(root: str):
    library = Path(root)
    capacity_path = library / 'review' / 'body-longcopy-capacity.json'
    policy_path = library / 'review' / 'body-capacity-preflight-policy.json'
    if not capacity_path.is_file():
        return {}, {}, None, None
    capacity = json.loads(capacity_path.read_text(encoding='utf-8-sig'))
    policy = (json.loads(policy_path.read_text(encoding='utf-8-sig'))
              if policy_path.is_file() else {'near_hard_limit_ratio': .85,
                                             'near_recommended_limit_ratio': .9})
    by_layout = {item['layout_id']: {field['semantic_path']: field
                                    for field in item.get('fields', [])}
                 for item in capacity.get('layouts', [])}
    return (by_layout, policy, hashlib.sha256(capacity_path.read_bytes()).hexdigest(),
            hashlib.sha256(policy_path.read_bytes()).hexdigest() if policy_path.is_file() else None)


@lru_cache(maxsize=2048)
def _bindings(path: str):
    file = Path(path)
    return json.loads(file.read_text(encoding='utf-8-sig'))['fields'], hashlib.sha256(file.read_bytes()).hexdigest()


def _two_line_wrap(value: str, width: int, max_lines: int, max_chars: int) -> str | None:
    if '\n' in value or max_lines < 2 or len(value) + 1 > max_chars:
        return None
    choices = []
    for at in range(1, len(value)):
        left, right = value[:at], value[at:]
        lw, rw = visual_width_units(left), visual_width_units(right)
        if lw <= width and rw <= width:
            choices.append((abs(lw-rw), at, left + '\n' + right))
    return min(choices)[2] if choices else None


def preflight(library: Path, entry: dict, content: dict, page_title: str | None,
              theme: str) -> dict:
    """Return hard binding failures, advisory long-copy pressure and wrap options."""
    library = Path(library).resolve()
    mapped, adapter = adapt_for_layout(entry['id'], content, page_title, entry=entry)
    texts = mapped.get('texts') if isinstance(mapped.get('texts'), dict) else {}
    binding_rel = (entry.get('red_bindings') if theme == 'red' and entry.get('red_bindings')
                   else entry['bindings'])
    bindings, binding_sha = _bindings(str(library / binding_rel))
    longcopy, policy, longcopy_sha, policy_sha = _review(str(library))
    reviewed_fields = longcopy.get(entry['id'], {})
    hard, advisory, wrap_suggestions, details = [], [], {}, []
    margins = []
    near_hard = policy.get('near_hard_limit_ratio', .85)
    near_reviewed = policy.get('near_recommended_limit_ratio', .9)
    for field in bindings:
        semantic = field.get('semantic_path')
        key = semantic if semantic in texts else field['field'] if field['field'] in texts else None
        if key is None:
            continue
        value = texts[key]
        if not isinstance(value, str):
            continue
        char_limit = field.get('max_chars')
        line_limit = field.get('max_lines')
        width_limit = field.get('max_width_units')
        lines = value.split('\n')
        widths = [visual_width_units(line) for line in lines]
        reasons = []
        if isinstance(char_limit, int) and len(value) > char_limit:
            reasons.append('max_chars')
        if isinstance(line_limit, int) and len(lines) > line_limit:
            reasons.append('max_lines')
        if isinstance(width_limit, (int, float)) and max(widths, default=0) > width_limit:
            suggestion = _two_line_wrap(value, int(width_limit), line_limit or 1,
                                        char_limit or 9999)
            if suggestion and not reasons:
                wrap_suggestions[key] = suggestion
            else:
                reasons.append('max_width_units')
        for reason in reasons:
            hard.append({'field': semantic or field['field'], 'rule': reason,
                         'actual_chars': len(value), 'binding_field': field['field']})
        field_margins = []
        if isinstance(char_limit, int) and char_limit > 0:
            field_margins.append((char_limit-len(value))/char_limit)
            if len(value) >= char_limit*near_hard:
                advisory.append({'field': semantic or field['field'], 'rule': 'near_binding_chars'})
        if isinstance(width_limit, (int, float)) and width_limit > 0:
            field_margins.append((width_limit-max(widths, default=0))/width_limit)
            if max(widths, default=0) >= width_limit*near_hard and key not in wrap_suggestions:
                advisory.append({'field': semantic or field['field'], 'rule': 'near_binding_width'})
        if field_margins:
            margins.append(min(field_margins))
        reviewed = reviewed_fields.get(semantic, {})
        recommended = reviewed.get('recommended_max_cjk_chars')
        if (isinstance(recommended, int) and recommended > 0 and '\n' not in value):
            cjk_equivalent = visual_width_units(value) / 2
            if cjk_equivalent >= recommended*near_reviewed:
                advisory.append({'field': semantic, 'rule': 'near_reviewed_longcopy',
                                 'recommended_cjk_chars': recommended,
                                 'actual_cjk_equivalent': round(cjk_equivalent, 1)})
        details.append({'field': semantic or field['field'], 'role': field.get('semantic_role'),
                        'actual_chars': len(value), 'max_chars': char_limit,
                        'actual_lines': len(lines), 'max_lines': line_limit,
                        'max_visual_width_units': max(widths, default=0),
                        'binding_max_width_units': width_limit,
                        'reviewed_recommended_cjk_chars': recommended})
    rules_rel = entry.get('layout_rules')
    rules_file = library / rules_rel if rules_rel else None
    rules = json.loads(rules_file.read_text(encoding='utf-8-sig')) if rules_file and rules_file.is_file() else {}
    rules_sha = hashlib.sha256(rules_file.read_bytes()).hexdigest() if rules_file and rules_file.is_file() else None
    title_pressure = rules.get('title_pressure_test') or {}
    safe_title_chars = title_pressure.get('safe_title_chars')
    if isinstance(safe_title_chars, int) and page_title and len(page_title) > safe_title_chars:
        advisory.append({'field': 'page.title', 'rule': 'layout_title_pressure',
                         'actual_chars': len(page_title), 'safe_title_chars': safe_title_chars})
    return {'status': ('hard_overflow' if hard else 'wrap_possible' if wrap_suggestions else
                       'ready' if texts else 'awaiting_mapping'),
            'content_adapter': adapter, 'hard_issues': hard, 'advisory': advisory,
            'wrap_suggestions': wrap_suggestions, 'capacity_margin': min(margins) if margins else None,
            'fields': details, 'binding_path': binding_rel, 'binding_sha256': binding_sha,
            'longcopy_sha256': longcopy_sha, 'policy_sha256': policy_sha,
            'layout_rules_sha256': rules_sha,
            'layout_title_pressure_safe_chars': safe_title_chars}
