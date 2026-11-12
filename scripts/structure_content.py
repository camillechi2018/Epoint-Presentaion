"""Prepare page content without rewriting source bodies or guessing relationships.

The host Agent supplies concise item_titles from the material. This portable
step converts those labels plus verbatim bodies into existing card contracts.
Unprepared prose is returned as actionable work, never as fabricated cards.
"""
import argparse
import copy
import json
from pathlib import Path

PARALLEL = {'parallel-points', 'summary', 'framework'}
STRUCTURAL = {'cover', 'directory', 'section', 'closing'}


def prepare(request):
    if not isinstance(request, dict) or not isinstance(request.get('pages', []), list):
        raise ValueError('REQUEST_PAGES_INVALID')
    result = copy.deepcopy(request)
    changes, tasks, retained = [], [], []
    for index, page in enumerate(result.get('pages', []), 1):
        if not isinstance(page, dict):
            raise ValueError('PAGE_INVALID: ' + str(index))
        content = page.get('content')
        if page.get('role') in STRUCTURAL or not isinstance(content, dict):
            continue
        if content.get('type') != 'bullets':
            continue
        items = content.get('items')
        if not isinstance(items, list) or not items:
            continue
        info = {'page': index, 'page_id': page.get('page_id'),
                'title': page.get('title') or content.get('title'),
                'source_refs': page.get('source_refs', [])}
        reason = content.get('keep_bullets_reason')
        if isinstance(reason, str) and reason.strip():
            retained.append(dict(info, reason=reason))
            continue
        relation = page.get('matching_relation') or page.get('information_relation')
        titles = content.get('item_titles')
        issue = None
        if relation not in PARALLEL:
            issue = 'RELATION_NEEDS_STRUCTURED_CONTENT'
        elif not all(isinstance(item, str) and item.strip() for item in items):
            issue = 'ITEMS_NEED_REVIEW'
        elif (not isinstance(titles, list) or len(titles) != len(items)
              or not all(isinstance(title, str) and title.strip() for title in titles)):
            issue = 'ITEM_TITLES_REQUIRED'
        if issue:
            tasks.append(dict(info, code=issue, information_relation=relation,
                              original_items=copy.deepcopy(items),
                              action=('依据材料明确顺序、层级或对比等关系，提交相应结构化内容；'
                                      '确需保留纯列表时填写 keep_bullets_reason。'
                                      if issue == 'RELATION_NEEDS_STRUCTURED_CONTENT' else
                                      '为每条原文提供对应 item_titles 短标题；保留 items 原文，'
                                      '不新增业务结论。确需纯列表时填写 keep_bullets_reason。')))
            continue
        content['type'] = 'cards'
        content['items'] = [{'title': title.strip(), 'body': body}
                            for title, body in zip(titles, items)]
        del content['item_titles']
        evidence = dict(info, operation='verbatim_bullets_to_cards',
                        body_preserved=True, title_review='host_agent_provided',
                        item_mapping=[{'source_path': f'pages[{index-1}].content.items[{i}]',
                                       'target_path': f'pages[{index-1}].content.items[{i}].body',
                                       'title': title.strip()}
                                      for i, title in enumerate(titles)])
        page['content_preparation'] = evidence
        changes.append(evidence)
    report = {'schema_version': 1,
              'status': 'needs_agent_structure' if tasks else 'ready_for_matching',
              'changed_pages': changes, 'tasks': tasks, 'retained_bullet_pages': retained,
              'scope': 'content organization only; no template fill or visual acceptance'}
    return result, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True, help='Prepared request, or draft if tasks remain')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        paths = [args.request.resolve(), args.out.resolve(), args.report.resolve()]
        if len(set(paths)) != 3 or args.out.exists() or args.report.exists():
            raise ValueError('OUTPUT_PATH_CONFLICT')
        prepared, report = prepare(json.loads(args.request.read_text(encoding='utf-8-sig')))
        for path, data in ((args.out, prepared), (args.report, report)):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'status': report['status'], 'changed_pages': len(report['changed_pages']),
                          'pending_pages': len(report['tasks']), 'report': str(args.report)}, ensure_ascii=True))
        return 2 if report['tasks'] else 0
    except (OSError, ValueError) as exc:
        print(json.dumps({'status': 'blocked', 'error_code': str(exc)[:300]}, ensure_ascii=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
