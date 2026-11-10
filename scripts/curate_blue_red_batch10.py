"""Curate eight fixed-count blue/red process layouts for automatic selection."""
from __future__ import annotations

import hashlib
import json
import sys
import unicodedata
from pathlib import Path

import curate_blue_red_batch5 as common
from curate_blue_red_batch4 import record, dump


def fields(pairs):
    return {sid: (path, value) for sid, path, value in pairs}


SETS = {
    257: record('五阶段工作流程', 'five-stage-workflow', 'ascending-five-stage-flow', 5, fields([
        (7, 'page.title', '项目推进｜五阶段工作流程'), (46, 'section.title', '五阶段实施计划'),
        (11, 'stages[0].heading', '明确项目需求'), (14, 'stages[1].heading', '拆解重点任务'),
        (15, 'stages[2].heading', '准备实施资源'), (16, 'stages[3].heading', '推进任务执行'),
        (17, 'stages[4].heading', '复盘交付成果'),
        (23, 'stages[0].body', '访谈相关人员，梳理目标与边界。\n形成需求清单并完成确认。'),
        (43, 'stages[1].body', '拆解交付事项，明确责任人和完成时间。'),
        (26, 'stages[2].body', '盘点人员、资料与工具。\n完成关键资源调配。'),
        (32, 'stages[3].body', '按节点执行任务并跟踪进度。\n及时协调阻塞事项。'),
        (41, 'stages[4].body', '验收成果并收集反馈。\n复盘问题，沉淀改进清单。'),
    ]), locked=(3, 4, 5, 6, 9), role='process', note='五个上升阶段固定对应五组说明，STEP 编号锁定。'),
    259: record('五阶段活动推进', 'five-stage-event-plan', 'fan-shaped-five-stage-plan', 5, fields([
        (3, 'page.title', '活动筹备｜五阶段推进计划'), (145, 'section.title', '活动筹备\n推进计划'),
        (53, 'stages[0].heading', '明确活动目标'), (136, 'stages[0].date', '2027年2月'),
        (146, 'stages[0].body', '确定活动主题和目标。\n梳理参与对象与预期成果。'),
        (137, 'stages[1].heading', '制定预算方案'), (138, 'stages[1].date', '2027年3月'),
        (147, 'stages[1].body', '列出场地、设备和人员费用。\n确认预算与审批路径。'),
        (139, 'stages[2].heading', '落实场地设计'), (140, 'stages[2].date', '2027年4月'),
        (148, 'stages[2].body', '选择适合的活动场地。\n完成动线和区域布置。'),
        (141, 'stages[3].heading', '排定活动日程'), (142, 'stages[3].date', '2027年5月'),
        (149, 'stages[3].body', '明确各环节时间和负责人。\n组织流程演练与检查。'),
        (143, 'stages[4].heading', '宣传与报名管理'), (144, 'stages[4].date', '2027年6月'),
        (150, 'stages[4].body', '按计划发布宣传信息。\n跟踪报名并确认到场名单。'),
        (2, 'footer.summary', '五阶段依次推进，按节点检查筹备情况，确保活动如期交付。'),
        (7, 'metrics.progress.value', '85%'),
    ]), role='timeline', note='固定五阶段，日期连续递增；百分比须有材料依据，不得凭空生成。'),
    261: record('六步闭环流程', 'six-step-closed-loop', 'circular-six-step-flow', 6, fields([
        (104, 'page.title', '项目管理｜六步闭环流程'), (28, 'center.title', '工作\n闭环'),
        (108, 'steps[0].heading', '第一步：明确目标'), (107, 'steps[0].body', '明确项目目标和交付范围。\n落实责任人与启动计划。'),
        (30, 'steps[1].heading', '第二步：需求分析'), (29, 'steps[1].body', '收集使用需求和业务约束。\n形成经确认的需求清单。'),
        (41, 'steps[2].heading', '第三步：方案设计'), (40, 'steps[2].body', '制定实施方案并组织评审。\n确认关键路径和验收标准。'),
        (118, 'steps[3].heading', '第四步：资源准备'), (117, 'steps[3].body', '盘点所需人员与工具。\n完成预算和资源调配。'),
        (15, 'steps[4].heading', '第五步：执行推进'), (13, 'steps[4].body', '按计划推进任务和风险检查。\n及时处理跨组依赖。'),
        (20, 'steps[5].heading', '第六步：验收总结'), (18, 'steps[5].body', '验收成果并复盘问题。\n归档材料和改进措施。'),
    ]), locked=(7, 32, 33, 103, 16, 17), role='process', note='六个环形节点固定对应六组标题与正文。'),
    262: record('四步规划闭环', 'four-step-planning-cycle', 'circular-four-step-plan', 4, fields([
        (11, 'page.title', '项目规划｜四步实施闭环'), (20, 'center.title', '项目规划'),
        (26, 'steps[0].heading', '第一步：目标共识'), (25, 'steps[0].body', '与相关方确认目标、范围和成果标准。\n召开启动会，明确责任与协作方式。'),
        (34, 'steps[1].heading', '第二步：方案分解'), (33, 'steps[1].body', '制定执行方案，拆解任务与关键节点。\n确认资源、工期和检查方式。'),
        (36, 'steps[2].heading', '第三步：执行管控'), (35, 'steps[2].body', '按计划推进并定期检查进度。\n及时协调偏差和资源问题。'),
        (28, 'steps[3].heading', '第四步：验收复盘'), (27, 'steps[3].body', '对照标准验收成果并收集反馈。\n复盘问题，归档可复用经验。'),
    ]), locked=(21, 22, 23, 24), role='process', note='固定四步圆环，数字 01—04 锁定；长正文未验收。'),
    264: record('六阶段曲折流程', 'six-stage-serpentine-workflow', 'two-column-six-step-serpentine', 6, fields([
        (44, 'page.title', '项目实施｜六阶段工作计划'),
        (5, 'steps[0].heading', '启动规划'), (12, 'steps[0].body', '确认目标、范围和成果标准。\n明确责任分工与启动安排。'),
        (6, 'steps[1].heading', '需求调研'), (13, 'steps[1].body', '访谈相关人员并整理需求。\n确认项目范围与优先级。'),
        (7, 'steps[2].heading', '方案设计'), (14, 'steps[2].body', '制定实施方案并完成评审。\n明确关键节点与验收方式。'),
        (10, 'steps[3].heading', '资源准备'), (15, 'steps[3].body', '落实预算、人员与工具。\n确认实施条件已经具备。'),
        (9, 'steps[4].heading', '执行推进'), (16, 'steps[4].body', '按计划推进重点任务。\n定期检查进度并处理问题。'),
        (8, 'steps[5].heading', '验收复盘'), (17, 'steps[5].body', '对照标准验收项目成果。\n总结经验，形成改进清单。'),
    ]), locked=(28, 29, 30, 34, 35, 36), role='process', note='六步折返路径，第四至第六步以视觉顺序为准。'),
    265: record('四阶段环形流程', 'four-stage-phase-workflow', 'circular-four-phase-with-center', 4, fields([
        (114, 'page.title', '项目管理｜四阶段交付流程'), (3, 'center.title', '交付流程'),
        (5, 'stages[0].heading', '启动规划'), (7, 'stages[0].body', '明确项目目标与范围。\n确认交付标准和责任分工。'),
        (8, 'stages[1].heading', '方案设计'), (9, 'stages[1].body', '制定方案并完成评审。\n确定关键节点和实施资源。'),
        (10, 'stages[2].heading', '执行推进'), (11, 'stages[2].body', '按计划推进任务。\n及时协调进度和风险问题。'),
        (12, 'stages[3].heading', '验收复盘'), (13, 'stages[3].body', '对照标准完成验收。\n沉淀经验和后续改进项。'),
        (14, 'stages[0].tag_a', '目标明确'), (15, 'stages[0].tag_b', '团队对齐'),
        (16, 'stages[1].tag_a', '方案评审'), (17, 'stages[1].tag_b', '路径优化'),
        (18, 'stages[2].tag_a', '有序执行'), (19, 'stages[2].tag_b', '进度跟踪'),
        (20, 'stages[3].tag_a', '成果验收'), (21, 'stages[3].tag_b', '质量复盘'),
    ]), locked=(109, 110, 111, 112, 49), role='process', note='四步圆环，中心中文标题限四字；英文副标题与 STEP 编号固定。'),
    266: record('六阶段方形闭环', 'six-stage-square-loop', 'square-six-stage-loop', 6, fields([
        (8, 'page.title', '项目推进｜六阶段闭环计划'),
        (2, 'steps[0].heading', '启动筹备阶段'), (4, 'steps[0].body', '明确工作小组与职责分工。\n收集基础资料，召开启动会。'),
        (10, 'steps[1].heading', '调研分析阶段'), (12, 'steps[1].body', '开展访谈与现场调研。\n整理问题和核心需求。'),
        (13, 'steps[2].heading', '方案制定阶段'), (14, 'steps[2].body', '形成实施方案并组织评审。\n按意见修改执行路径。'),
        (46, 'steps[3].heading', '试点验证阶段'), (47, 'steps[3].body', '选择代表场景开展试点。\n收集反馈并优化方案。'),
        (44, 'steps[4].heading', '全面推进阶段'), (45, 'steps[4].body', '按方案扩大实施范围。\n跟踪进度、质量与风险。'),
        (42, 'steps[5].heading', '总结验收阶段'), (43, 'steps[5].body', '验收实施成果并完成复盘。\n归档资料和改进建议。'),
    ]), locked=(5, 6, 7, 48, 50, 51), role='process', note='六阶段方形闭环，步骤数字固定，按实际流向绑定。'),
    267: record('四阶段纵向箭头流程', 'four-stage-vertical-arrow', 'vertical-four-step-arrow', 4, fields([
        (4, 'page.title', '项目实施｜四阶段工作计划'),
        (5, 'steps[0].heading', '目标确认'), (7, 'steps[0].body', '与相关方确认目标、范围和交付标准。\n明确团队职责与关键节点。'),
        (14, 'steps[1].heading', '方案规划'), (9, 'steps[1].body', '制定实施方案并组织评审。\n落实资源和检查机制。'),
        (16, 'steps[2].heading', '执行推进'), (10, 'steps[2].body', '按计划推进任务，跟踪进度和质量。\n及时解决阻塞与依赖。'),
        (18, 'steps[3].heading', '验收复盘'), (11, 'steps[3].body', '对照标准完成验收并收集反馈。\n总结经验和改进事项。'),
    ]), locked=(3, 12, 15, 17), role='process', note='固定四条纵向箭头；短正文实填，长正文未验收。'),
}


if __name__ == '__main__':
    common.SETS = SETS
    common.main()
    args = sys.argv
    root = Path(args[args.index('--library') + 1]).resolve()
    catalog_path = root / 'catalog.json'
    taxonomy_path = root / 'relation-taxonomy.json'
    manifest_path = root / 'knowledge-manifest.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8-sig'))
    taxonomy = json.loads(taxonomy_path.read_text(encoding='utf-8-sig'))
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    for number, spec in SETS.items():
        entry = next(e for e in catalog['layouts'] if e['id'] == f'content-blue-{number:03d}')
        relation = 'timeline' if number == 259 else 'process'
        entry['canonical_relation'] = relation
        entry['search_label'] = f"{spec['title']} {spec['note']} {spec['count']}项 固定项数"
        base = root / 'layouts' / entry['id']
        for filename in ('bindings.json', 'bindings-red.json'):
            path = base / filename
            binding = json.loads(path.read_text(encoding='utf-8-sig'))
            for field in binding['fields']:
                if field.get('semantic_role') != 'body':
                    continue
                source = field['source_text']
                field['max_chars'] = len(source)
                field['max_lines'] = len(source.split('\n'))
                field['max_width_units'] = max(
                    sum(2 if unicodedata.east_asian_width(char) in ('W', 'F') else 1
                        for char in line) for line in source.split('\n'))
            dump(path, binding)
            manifest['files'][path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        rules_path = base / 'layout_rules.json'
        rules = json.loads(rules_path.read_text(encoding='utf-8-sig'))
        rules['normal_body_weight'] = {'weight': 'regular', 'semantic_roles': ['body']}
        rules['long_copy_validation'] = {'status': 'source_length_rephrased_blue_red_verified',
                                         'scope': 'body_fields_only', 'max_lines': 'per_binding'}
        dump(rules_path, rules)
        manifest['files'][rules_path.relative_to(root).as_posix()] = hashlib.sha256(rules_path.read_bytes()).hexdigest()
        spec_path = base / 'spec.md'
        spec_text = spec_path.read_text(encoding='utf8').replace(
            '动效、HTML、其他色系和长文案未验收。',
            '正文已按原稿等长改写完成蓝红 PowerPoint 长文案渲染和边界验收；超过各字段容量需拆页。动效、HTML 和其他色系未验收。')
        spec_path.write_text(spec_text, encoding='utf8')
        manifest['files'][spec_path.relative_to(root).as_posix()] = hashlib.sha256(spec_path.read_bytes()).hexdigest()
        specific = taxonomy['relations'][relation]['specific_relations']
        if spec['relation'] not in specific:
            specific.append(spec['relation'])
    for path, data in ((catalog_path, catalog), (taxonomy_path, taxonomy)):
        dump(path, data)
        manifest['files'][path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    dump(manifest_path, manifest)
