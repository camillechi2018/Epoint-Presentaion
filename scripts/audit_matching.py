"""Replay real page requests against one fixed knowledge-base checkout.

Planning and single-page fill are kept separate, so a recalled component is
never counted as reusable merely because it passed the catalog filter.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

from fill_layout import fill
from plan_deck import resolve
from content_adapters import (adapt_for_layout, classify_trial_failure,
                              structural_mapping_issue, field_source_evidence)
from capacity_preflight import preflight


def unmapped_binding_paths(library: Path, layout_id: str, content: dict, theme: str) -> list[str]:
    catalog = json.loads((library / 'catalog.json').read_text(encoding='utf-8-sig'))
    entry = next(item for item in catalog['layouts'] if item['id'] == layout_id)
    binding = entry.get('red_bindings') if theme == 'red' and entry.get('red_bindings') else entry['bindings']
    fields = json.loads((library / binding).read_text(encoding='utf-8-sig'))['fields']
    texts = content.get('texts') if isinstance(content.get('texts'), dict) else {}
    return sorted({field.get('semantic_path') or field['field'] for field in fields
                   if field.get('semantic_role') not in
                   ('brand_locked', 'decoration_locked', 'computed_item_count')
                   and field['field'] != 'brand'
                   and field['field'] not in texts and field.get('semantic_path') not in texts})


def library_commit(library: Path) -> str:
    if (library / '.git').exists():
        return subprocess.check_output(['git', '-C', str(library), 'rev-parse', 'HEAD'], text=True).strip()
    manifest = json.loads((library / 'knowledge-manifest.json').read_text(encoding='utf-8-sig'))
    return manifest['source_commit']


def audit(library: Path, request_path: Path, work: Path, trial: bool) -> dict:
    request = json.loads(request_path.read_text(encoding='utf-8-sig'))
    planning_request = dict(request)
    planning_request['allow_draft'] = request.get('asset_policy', 'verified_draft') != 'approved_only'
    planning_request['allow_provisional'] = request.get('asset_policy') == 'provisional_manual'
    plan = resolve(library, planning_request)
    pages = []
    counters = Counter()
    for index, (source, choice) in enumerate(zip(request['pages'], plan['pages']), 1):
        is_body = source.get('role') not in ('cover', 'directory', 'section', 'closing')
        if not is_body:
            continue
        counters['body_pages'] += 1
        counters['template_attempted'] += 1  # resolve examined every catalog entry
        candidate_ids = choice.get('candidate_ids', [])
        if candidate_ids:
            counters['eligible_pages'] += 1
        row = {'page': index, 'purpose': source['purpose'],
               'relation': source.get('information_relation') or
                           (source.get('content') or {}).get('type'),
               'candidate_ids': candidate_ids,
               'rejected_reasons': choice.get('rejected_reasons', {}),
               'normalization': choice.get('request_normalization', []),
               'trials': [], 'source_template_used': False}
        if trial and candidate_ids:
            content = dict(source.get('content') or {})
            content['theme'] = request['theme']
            content['library_commit'] = library_commit(library)
            if 'items' not in content and isinstance(source.get('items'), list):
                content['items'] = source['items']
            work.mkdir(parents=True, exist_ok=True)
            content_path = work / f'P{index:03d}-content.json'
            content_path.write_text(json.dumps(content, ensure_ascii=False), encoding='utf-8')
            for order, layout_id in enumerate(candidate_ids, 1):
                output = work / f'P{index:03d}-trial-{order}.pptx'
                catalog = json.loads((library / 'catalog.json').read_text(encoding='utf-8-sig'))
                entry = next(e for e in catalog['layouts'] if e['id'] == layout_id)
                candidate_content, adapter = adapt_for_layout(layout_id, content, source.get('title'), entry=entry)
                if not adapter and entry.get('matching_activation') in ('structure_ready', 'pilot_verified'):
                    issue = structural_mapping_issue(entry, content, source.get('title'))
                    if issue:
                        counters[issue['reason_code']] += 1
                        row['trials'].append({
                            'layout_id': layout_id, 'status': 'rejected',
                            'reason_code': issue['reason_code'],
                            'unmapped_semantic_paths': issue['paths'],
                            'content_adapter': None})
                        continue
                capacity_check = preflight(library, entry, content, source.get('title'), request['theme'])
                if capacity_check['hard_issues']:
                    counters['TEXT_OVER_CAPACITY'] += 1
                    row['trials'].append({'layout_id': layout_id, 'status': 'rejected',
                                          'reason_code': 'TEXT_OVER_CAPACITY',
                                          'capacity_preflight': capacity_check,
                                          'content_adapter': adapter})
                    continue
                wrap_applied = capacity_check['wrap_suggestions']
                if wrap_applied and isinstance(candidate_content.get('texts'), dict):
                    candidate_content = dict(candidate_content)
                    candidate_content['texts'] = dict(candidate_content['texts'], **wrap_applied)
                trial_content_path = content_path
                if adapter or wrap_applied:
                    trial_content_path = work / f'P{index:03d}-trial-{order}-content.json'
                    trial_content_path.write_text(json.dumps(candidate_content, ensure_ascii=False), encoding='utf-8')
                try:
                    fill(library, layout_id, trial_content_path, output, allow_draft=planning_request['allow_draft'])
                    row['trials'].append({'layout_id': layout_id, 'status': 'filled',
                                          'visual_qa': 'not_run', 'content_adapter': adapter,
                                          'capacity_preflight': capacity_check,
                                          'wrap_applied': wrap_applied,
                                          'field_source_evidence': field_source_evidence(
                                              dict(content, source_refs=source.get('source_refs', [])),
                                              candidate_content) if adapter else {}})
                    row['source_template_used'] = True
                    counters['trial_filled_pages'] += 1
                    break
                except (ValueError, KeyError, FileNotFoundError) as exc:
                    code = classify_trial_failure(str(exc))
                    counters[code] += 1
                    rejection = {'layout_id': layout_id, 'status': 'rejected',
                                 'reason_code': code, 'detail': str(exc)[:300],
                                 'capacity_preflight': capacity_check,
                                 'wrap_applied': wrap_applied,
                                 'content_adapter': adapter}
                    if code == 'MISSING_REQUIRED_FIELD':
                        rejection['unmapped_semantic_paths'] = unmapped_binding_paths(
                            library, layout_id, candidate_content, request['theme'])
                    row['trials'].append(rejection)
            if not row['source_template_used']:
                counters['no_fit_after_trial_pages'] += 1
        pages.append(row)
    total = counters['body_pages']
    return {'request': str(request_path), 'library': str(library),
            'library_commit': library_commit(library),
            'trial_enabled': trial, 'metrics': {
                'body_pages': total,
                'template_attempt_rate': counters['template_attempted'] / total if total else 0,
                'eligible_candidate_pages': counters['eligible_pages'],
                'eligible_candidate_rate': counters['eligible_pages'] / total if total else 0,
                'trial_filled_pages': counters['trial_filled_pages'] if trial else None,
                'trial_pass_rate': counters['trial_filled_pages'] / counters['eligible_pages']
                                   if trial and counters['eligible_pages'] else None,
                'body_source_template_rate': counters['trial_filled_pages'] / total if trial and total else None,
                'trial_rejection_reasons': {key: value for key, value in counters.items()
                                            if key in ('MISSING_REQUIRED_FIELD', 'TEXT_OVER_CAPACITY',
                                                       'IMAGE_SLOT_MISMATCH', 'ITEM_COUNT_MISMATCH',
                                                       'TRIAL_REJECTED')},
            }, 'pages': pages}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--trial', action='store_true')
    args = parser.parse_args()
    if args.out.exists():
        parser.error('输出报告已存在')
    result = audit(args.library.resolve(), args.request.resolve(),
                   args.out.parent / (args.out.stem + '-trial'), args.trial)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result['metrics'], ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
