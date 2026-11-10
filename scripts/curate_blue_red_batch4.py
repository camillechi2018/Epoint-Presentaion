"""Curate eight blue/red source pages as fixed-count static report components."""
from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
from pathlib import Path


def record(title, relation, family, count, fields, locked=(), role='content', note=''):
    return dict(title=title, relation=relation, family=family, count=count,
                fields=fields, locked=set(locked), role=role, note=note)


SETS = {
    76: record('四方向工作展望', 'four-direction-outlook', 'four-quadrant-cycle', 4, {
        7: ('page.title', '年度规划｜四方向发展展望'),
        30: ('center.title', '下一阶段\n发展展望'),
        10: ('directions[0].heading', '01.服务体验优化'),
        23: ('directions[1].heading', '02.产品能力升级'),
        24: ('directions[2].heading', '03.组织协同提升'),
        22: ('directions[3].heading', '04.运营质量巩固'),
        2: ('directions[0].body', '统一服务入口，缩短需求响应时间。\n建立问题跟踪机制，按月复盘体验。'),
        25: ('directions[1].body', '完善核心功能，优化常用业务流程。\n围绕反馈安排小步迭代。'),
        27: ('directions[2].body', '明确跨团队职责与交付标准。\n建立共享资料和协作节奏。'),
        26: ('directions[3].body', '持续监测质量和效率指标。\n形成改进清单并跟进闭环。'),
        28: ('directions[0].short', '方向一'),
        31: ('directions[1].short', '方向二'),
        32: ('directions[2].short', '方向三'),
        33: ('directions[3].short', '方向四'),
    }, note='四个象限与中心环相互绑定，方向数固定为四。'),
    102: record('五节点项目时间线', 'five-milestone-roadmap', 'ascending-milestone-timeline', 5, {
        2: ('page.title', '项目推进｜五个关键节点'),
        82: ('range.start', '2026.1'), 83: ('range.end', '2026.10'),
        102: ('milestones[0].date', '2026年1月'),
        107: ('milestones[1].date', '2026年3月'),
        111: ('milestones[2].date', '2026年5月'),
        115: ('milestones[3].date', '2026年7月'),
        119: ('milestones[4].date', '2026年10月'),
        85: ('milestones[0].heading', '需求'),
        90: ('milestones[1].heading', '方案'),
        92: ('milestones[2].heading', '试点'),
        97: ('milestones[3].heading', '推广'),
        99: ('milestones[4].heading', '复盘'),
        84: ('milestones[0].body', '梳理使用场景和关键需求。\n确定交付范围与验收标准。'),
        89: ('milestones[1].body', '完成方案设计与评审。\n明确责任分工和实施排期。'),
        91: ('milestones[2].body', '选择两个业务场景开展试点。\n记录问题并验证改进效果。'),
        96: ('milestones[3].body', '将试点经验复制到更多团队。\n提供培训和使用支持。'),
        98: ('milestones[4].body', '汇总指标、反馈与交付成果。\n形成下一轮优化清单。'),
    }, role='timeline', note='固定五个从左到右递进的时间节点；日期文字与阶段区间需一致，暂不改变节点位置。'),
    112: record('四项成果清单', 'four-achievement-list', 'numbered-achievement-rows', 4, {
        5: ('page.title', '阶段成果｜四项重点进展'),
        23: ('items[0].heading', '交付质量'),
        25: ('items[1].heading', '流程效率'),
        26: ('items[2].heading', '团队协作'),
        19: ('items[3].heading', '客户体验'),
        30: ('items[0].body', '统一验收口径，关键交付物按计划完成。\n问题记录与处理结果可追溯。'),
        31: ('items[1].body', '优化审批和交接流程，减少重复录入。\n常见事项形成标准操作说明。'),
        32: ('items[2].body', '每周同步任务与风险，明确责任人。\n跨组问题由专题会议集中处理。'),
        29: ('items[3].body', '建立定期回访机制，汇总高频建议。\n改进事项按优先级进入迭代计划。'),
    }, locked=(13, 43, 44, 18), role='summary', note='四条编号栏与右侧说明一一对应，数量固定为四。'),
    119: record('六步问题解决法', 'six-step-problem-solving', 'hub-spoke-six-actions', 6, {
        5: ('page.title', '问题处理｜六步闭环方法'),
        37: ('center.title', '问题解决闭环'),
        30: ('center.focus[0]', '定位原因'),
        31: ('center.focus[1]', '制定方案'),
        32: ('center.focus[2]', '跟踪反馈'),
        33: ('center.focus[3]', '复盘沉淀'),
        38: ('steps[0].heading', '识别问题根源'),
        42: ('steps[1].heading', '组织协同分析'),
        44: ('steps[2].heading', '形成解决方案'),
        46: ('steps[3].heading', '执行关键措施'),
        48: ('steps[4].heading', '收集反馈调整'),
        50: ('steps[5].heading', '复盘并分享'),
        41: ('steps[0].body', '收集现象和影响范围。\n用事实确认主要原因。'),
        43: ('steps[1].body', '邀请相关团队共同分析。\n明确问题责任和协作方式。'),
        45: ('steps[2].body', '列出可执行措施。\n评估投入、风险和完成时间。'),
        47: ('steps[3].body', '优先处理关键阻塞。\n按责任分工推进落实。'),
        49: ('steps[4].body', '跟踪结果与使用反馈。\n必要时调整措施和排期。'),
        51: ('steps[5].body', '记录成效和遗留问题。\n提炼可复用的处理经验。'),
    }, locked=(18, 19, 20, 21, 22, 23), role='process', note='六个图标、编号、说明围绕中心构图，数量固定为六。'),
    146: record('四季度能力提升阶梯', 'four-quarter-capability-plan', 'quarter-staircase', 4, {
        45: ('page.title', '能力建设｜四季度提升计划'),
        3: ('quarters[0].label', '第一季度计划'),
        8: ('quarters[1].label', '第二季度计划'),
        30: ('quarters[2].label', '第三季度计划'),
        31: ('quarters[3].label', '第四季度计划'),
        26: ('goals[0].heading', '专业技能提升'),
        27: ('goals[1].heading', '协作能力提升'),
        28: ('goals[2].heading', '执行效率提升'),
        29: ('goals[3].heading', '复盘能力建设'),
        33: ('quarters[0].body', '目标：掌握基础工具与工作规范。\n行动：完成培训并实践应用。'),
        34: ('quarters[1].body', '目标：提升跨组沟通效率。\n行动：建立协作台账和例会机制。'),
        39: ('quarters[2].body', '目标：缩短常见事项处理周期。\n行动：优化任务分配与检查节点。'),
        36: ('quarters[3].body', '目标：形成持续改进习惯。\n行动：总结案例并更新工作指引。'),
        35: ('annotation', '每月检查目标进展，及时调整行动安排。'),
        46: ('closing', '通过季度计划持续提升能力，并将经验沉淀到团队。'),
    }, role='timeline', note='四个季度阶梯与目标区域绑定，固定四季；季度说明应按时间顺序对应。'),
    181: record('四层能力成长', 'four-layer-capability-growth', 'concentric-four-layer-model', 4, {
        5: ('page.title', '能力成长｜四个方面的提升'),
        9: ('layers[0].heading', '01.沟通表达能力'),
        10: ('layers[1].heading', '02.任务管理能力'),
        11: ('layers[2].heading', '03.跨组协作能力'),
        30: ('layers[3].heading', '04.问题处理能力'),
        32: ('layers[0].body', '明确沟通目标和结论。\n使用共享记录减少理解偏差。'),
        34: ('layers[1].body', '按影响和期限安排任务。\n定期核对进度与交付质量。'),
        35: ('layers[2].body', '主动对齐上下游需求。\n及时协调资源和待解决问题。'),
        36: ('layers[3].body', '基于事实定位原因。\n形成措施并复核处理效果。'),
    }, locked=(4, 27, 28, 29), role='framework', note='四层同心圆与四项说明一一对应，固定四层。'),
    244: record('六维阶段总结', 'six-dimension-stage-summary', 'six-aspect-central-summary', 6, {
        2: ('page.title', '阶段总结｜六个工作维度'),
        42: ('center.title', '阶段工作总结'),
        48: ('center.subtitle', 'Stage summary'),
        50: ('aspects[0].heading', '01.目标规划'),
        89: ('aspects[1].heading', '02.资源配置'),
        56: ('aspects[2].heading', '03.进度跟踪'),
        93: ('aspects[3].heading', '04.风险处理'),
        63: ('aspects[4].heading', '05.质量检查'),
        99: ('aspects[5].heading', '06.协同沟通'),
        55: ('aspects[0].body', '明确阶段目标、任务边界和关键交付。'),
        91: ('aspects[1].body', '按优先级安排人员、时间与工具。'),
        58: ('aspects[2].body', '定期核对里程碑，及时处理偏差。'),
        96: ('aspects[3].body', '识别影响因素并准备应对措施。'),
        66: ('aspects[4].body', '复核成果质量，记录改进事项。'),
        102: ('aspects[5].body', '同步进展与问题，保持各方信息一致。'),
    }, role='summary', note='中心标题与六个周边领域构成固定六维信息图。'),
    256: record('四步执行流程', 'four-step-execution', 'four-horizontal-arrow-rows', 4, {
        6: ('page.title', '项目执行｜四步推进流程'),
        72: ('steps[0].heading', 'STEP 01：启动对齐'),
        73: ('steps[1].heading', 'STEP 02：方案制定'),
        74: ('steps[2].heading', 'STEP 03：执行跟进'),
        75: ('steps[3].heading', 'STEP 04：验收复盘'),
        8: ('steps[0].body', '确认目标、范围和验收口径。\n明确负责人及主要时间节点。'),
        9: ('steps[1].body', '形成实施方案和任务清单。\n评估资源、依赖与潜在风险。'),
        10: ('steps[2].body', '按排期推进工作并同步进度。\n对阻塞事项及时协调处理。'),
        11: ('steps[3].body', '对照标准检查成果并收集反馈。\n归档记录，形成下一轮改进项。'),
    }, role='process', note='四条长箭头与说明及图标绑定，固定四步。'),
}


def dump(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def visual_width_units(value):
    return sum(2 if unicodedata.east_asian_width(ch) in ('W', 'F') else 1 for ch in value)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--library', type=Path, required=True)
    ap.add_argument('--samples', type=Path, required=True)
    ap.add_argument('--reviewed', action='store_true')
    args = ap.parse_args()
    root = args.library.resolve()
    args.samples.mkdir(parents=True, exist_ok=True)
    catalog_path = root / 'catalog.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8-sig'))
    manifest_path = root / 'knowledge-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    touched = {'catalog.json'}
    for n, spec in SETS.items():
        lid = f'content-blue-{n:03d}'
        base = root / 'layouts' / lid
        ids = set(spec['fields']) | spec['locked']
        for name in ('bindings.json', 'bindings-red.json'):
            path = base / name
            binding = json.loads(path.read_text(encoding='utf-8-sig'))
            found = {x['shape_id'] for x in binding['fields']}
            if found != ids:
                raise ValueError(f'{lid}/{name}: shape ID mismatch {sorted(found ^ ids)}')
            for field in binding['fields']:
                sid = field['shape_id']
                if sid in spec['locked']:
                    field.update(semantic_role='decoration_locked')
                    continue
                key, value = spec['fields'][sid]
                if len(value) > field['max_chars']:
                    raise ValueError(f'{lid} shape {sid}: sample exceeds capacity')
                field.update(semantic_path=key,
                             semantic_role='body' if '.body' in key else 'label',
                             max_chars=min(field['max_chars'], len(value)),
                             max_lines=len(value.split('\n')),
                             max_width_units=max(visual_width_units(line) for line in value.split('\n')))
            dump(path, binding)
            touched.add(path.relative_to(root).as_posix())
        entry = next(x for x in catalog['layouts'] if x['id'] == lid)
        entry.update(role=spec['role'], information_relation=spec['relation'],
                     family_id=spec['family'],
                     classification_status='verified' if args.reviewed else 'visual_reviewed',
                     pptx_support='verified_static' if args.reviewed else 'pending_render',
                     batch_status='fixed_native_count_verified' if args.reviewed else 'fields_mapped_pending_render',
                     semantic_review_status='verified_blue_red' if args.reviewed else 'fields_mapped_pending_render')
        rules_path = base / 'layout_rules.json'
        rules = json.loads(rules_path.read_text(encoding='utf-8-sig'))
        rules.update(cardinality_mode='fixed', source_count=spec['count'],
                     supported_counts=[spec['count']],
                     verified_counts=[spec['count']] if args.reviewed else [],
                     validation_status='verified_fixed_count' if args.reviewed else 'pending_render',
                     count_evidence=spec['note'])
        if n == 102:
            rules['ordered_date_fields'] = {
                'start': 'range.start', 'end': 'range.end',
                'milestones': [f'milestones[{i}].date' for i in range(5)]}
        dump(rules_path, rules)
        touched.add(rules_path.relative_to(root).as_posix())
        spec_path = base / 'spec.md'
        spec_path.write_text(
            f"# {spec['title']}\n\n来源：蓝红 P{n:03d}。信息关系：`{spec['relation']}`。"
            f"{spec['note']}当前仅支持原生 {spec['count']} 项，增减项数需要重新排版与验收。"
            + ('蓝红短文案实填和 PowerPoint 渲染已通过。' if args.reviewed else '字段已绑定，蓝红渲染待验收。')
            + 'Logo 原位保留；动效、HTML、其他色系和长文案未验收。\n', encoding='utf-8')
        touched.add(spec_path.relative_to(root).as_posix())
        for theme in ('blue', 'red'):
            content = {'theme': theme, 'item_count': spec['count'],
                       'texts': {key: value for key, value in spec['fields'].values()}}
            dump(args.samples / f'{lid}-{theme}.json', content)
    dump(catalog_path, catalog)
    for rel in touched:
        manifest['files'][rel] = hashlib.sha256((root / rel).read_bytes()).hexdigest()
    dump(manifest_path, manifest)
    print(json.dumps({'curated': len(SETS), 'reviewed': args.reviewed,
                      'touched': len(touched)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
