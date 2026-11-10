"""Build the verified relation index without promoting unreviewed layouts."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


ROLE_RELATIONS = {
    'cover': 'visual-story', 'directory': 'navigation', 'section': 'chapter-divider',
    'closing': 'closing-message', 'framework': 'framework', 'process': 'process',
    'timeline': 'timeline', 'comparison': 'comparison', 'summary': 'summary',
    'schedule': 'schedule', 'data-chart': 'data-chart', 'data-table': 'data-table',
    'progress': 'progress', 'parallel': 'parallel-points', 'cycle': 'cycle',
}
CONTENT_RELATIONS = {
    'hierarchy': 'hierarchy', 'metrics': 'metrics', 'parallel-points': 'parallel-points',
    'process': 'process', 'comparison': 'comparison', 'cycle': 'cycle',
    'single-focus': 'single-focus', 'timeline': 'timeline',
    'four-direction-outlook': 'parallel-points',
    'key-points': 'parallel-points',
}
ALIASES = {
    'visual-story': ['封面', '视觉封面'],
    'navigation': ['目录', '导航'],
    'chapter-divider': ['章节', '章节页'],
    'closing-message': ['封底', '结束页'],
    'framework': ['框架', '模型', '体系'],
    'hierarchy': ['层级', '分层', '架构'],
    'parallel-points': ['并列', '要点', '多点说明'],
    'process': ['流程', '步骤', '阶段', '工作流', 'workflow'],
    'cycle': ['循环', '闭环', '环形流程'],
    'comparison': ['对比', '比较', '问题措施', '问题解决', '差异'],
    'timeline': ['时间线', '里程碑', '路线图', '时间轴'],
    'schedule': ['计划', '排期', '甘特图', '任务安排'],
    'metrics': ['指标', '关键指标', '数据卡片'],
    'data-chart': ['图表', '趋势图', '数据图'],
    'data-table': ['表格', '明细表', '数据表'],
    'summary': ['总结', '成果', '工作总结'],
    'progress': ['进度', '完成度', '项目进展'],
    'single-focus': ['单一重点', '核心观点'],
}
SEARCH_LABELS = {
    'content-blue-015': '五项进度卡',
    'content-blue-060': '四步工作流程',
    'content-blue-133': '三组问题与措施',
    'content-blue-150': '五项并列要点',
    'content-blue-260': '四步循环闭环',
    'content-blue-270': '双指标趋势',
    'content-blue-279': '季度明细表',
}


def build(root: Path) -> dict:
    catalog_path = root / 'catalog.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8-sig'))
    grouped = defaultdict(set)
    count = 0
    for entry in catalog['layouts']:
        if entry.get('classification_status') != 'verified':
            continue
        if entry['id'] == 'content-tech-021':
            # Its verified semantic review says key-points, not process.
            entry['information_relation'] = 'key-points'
        role = entry['role']
        relation = entry['information_relation']
        category = (CONTENT_RELATIONS.get(relation) if role == 'content'
                    else ROLE_RELATIONS.get(role))
        if not category:
            raise ValueError(f"未审定关系映射：{entry['id']} / {role} / {relation}")
        entry['canonical_relation'] = category
        heading = (root / entry['spec']).read_text(encoding='utf-8-sig').splitlines()[0].lstrip('# ').strip()
        label = SEARCH_LABELS.get(entry['id'], heading)
        if label and label != entry['id'] and not label.startswith(('content-', 'cover-', 'closing-', 'directory-', 'schedule-', 'data-chart-')):
            entry['search_label'] = label
        grouped[category].add(relation)
        count += 1
    taxonomy = {
        'schema_version': '1.0',
        'description': '仅对 classification_status=verified 的组件建立检索同义关系；原始 information_relation 保留为精确子类型。',
        'relations': {name: {'aliases': aliases,
                             'specific_relations': sorted(grouped.get(name, set()))}
                      for name, aliases in ALIASES.items()},
    }
    # Ambiguous aliases would silently merge unrelated structures.
    seen = {}
    for name, group in taxonomy['relations'].items():
        for value in [name, *group['aliases'], *group['specific_relations']]:
            key = value.casefold()
            if key in seen and seen[key] != name:
                raise ValueError(f'关系词歧义：{value} => {seen[key]} / {name}')
            seen[key] = name
    catalog['relation_taxonomy'] = 'relation-taxonomy.json'
    (root / 'relation-taxonomy.json').write_text(json.dumps(taxonomy, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'verified_indexed': count, 'categories': len(taxonomy['relations'])}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--library', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.library), ensure_ascii=False))
