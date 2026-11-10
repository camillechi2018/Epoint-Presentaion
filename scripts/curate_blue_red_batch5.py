"""Curate eight more blue/red native-shape layouts with field and count contracts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from curate_blue_red_batch4 import record, dump, visual_width_units


SETS = {
    81: record('三目标达成概览', 'three-goal-achievement', 'goal-kpi-three-columns', 3, {
        2: ('page.title', '目标复盘｜三项重点任务'),
        12: ('goals[0].heading', '01.服务流程优化'),
        13: ('goals[1].heading', '02.重点项目交付'),
        14: ('goals[2].heading', '03.团队能力提升'),
        26: ('goals[0].body', '统一受理口径，缩短需求流转时间。\n上线问题跟踪表，持续检查处理质量。'),
        28: ('goals[1].body', '完成试点方案与阶段验收。\n及时协调依赖事项，按计划交付成果。'),
        29: ('goals[2].body', '建立知识分享和协作机制。\n围绕项目实践开展专题培训。'),
        30: ('kpis.total.label', '目标总数'),
        31: ('kpis.done.label', '已完成'),
        32: ('kpis.pending.label', '待完成'),
        33: ('kpis.rate.label', '完成率'),
        36: ('kpis.total.value', '3项'),
        37: ('kpis.done.value', '2项'),
        38: ('kpis.pending.value', '1项'),
        39: ('kpis.rate.value', '67%'),
        40: ('summary.label', '目标推进情况'),
        15: ('goals[0].tag_a', '流程优化'),
        19: ('goals[0].tag_b', '时效提升'),
        43: ('goals[1].tag_a', '试点交付'),
        44: ('goals[1].tag_b', '质量保障'),
        46: ('goals[2].tag_a', '能力培养'),
        47: ('goals[2].tag_b', '协作机制'),
    }, role='summary', note='三项任务与顶部四个统计指标组成固定构图；四个指标值必须自洽。'),
    89: record('四方向发展路径', 'four-career-development-directions', 'four-column-development', 4, {
        60: ('page.title', '能力建设｜四个发展方向'),
        36: ('items[0].heading', '强化专业技能'),
        37: ('items[1].heading', '拓展协作网络'),
        38: ('items[2].heading', '明确成长目标'),
        39: ('items[3].heading', '提升决策能力'),
        51: ('items[0].tag_a', '问题解决'), 52: ('items[0].tag_b', '知识沉淀'),
        55: ('items[1].tag_a', '跨组交流'), 56: ('items[1].tag_b', '共享经验'),
        58: ('items[2].tag_a', '目标清晰'), 59: ('items[2].tag_b', '定期复核'),
        61: ('items[3].tag_a', '综合判断'), 62: ('items[3].tag_b', '执行跟进'),
        65: ('items[0].body_a', '学习常用工具与工作规范，提升独立处理能力。'),
        66: ('items[0].body_b', '复盘真实项目案例，形成可复用的经验材料。'),
        68: ('items[1].body_a', '参加跨组交流，了解上下游工作需求。'),
        69: ('items[1].body_b', '共享任务进展与风险，建立稳定协作关系。'),
        71: ('items[2].body_a', '将年度目标拆分到季度和关键任务。'),
        72: ('items[2].body_b', '每月检查结果，按实际情况调整行动。'),
        74: ('items[3].body_a', '结合数据和现场反馈评估方案。'),
        75: ('items[3].body_b', '明确决策依据、责任人与跟进节点。'),
        63: ('items[0].summary', '以技能提升支撑更稳定的交付。'),
        67: ('items[1].summary', '通过协作减少任务衔接损耗。'),
        70: ('items[2].summary', '让成长目标与实际工作对应。'),
        73: ('items[3].summary', '提高判断和推进的整体效率。'),
    }, role='framework', note='四个栏目各有两个标签、两段正文和一条总结，固定四列。'),
    92: record('四目标工作环', 'four-work-goals', 'four-goals-circle', 4, {
        47: ('page.title', '工作规划｜四项核心目标'),
        10: ('center.title', '工作\n目标'),
        17: ('goals[0].heading', '01.提高交付效率'),
        30: ('goals[1].heading', '02.优化服务体验'),
        27: ('goals[2].heading', '03.完善协作流程'),
        33: ('goals[3].heading', '04.建设团队能力'),
        36: ('goals[0].short', '目标一'),
        37: ('goals[1].short', '目标二'),
        39: ('goals[2].short', '目标三'),
        40: ('goals[3].short', '目标四'),
        38: ('goals[0].body', '梳理高频事项，压缩重复交接步骤。\n按月追踪关键任务完成时间。'),
        52: ('goals[1].body', '建立反馈收集渠道，及时处理共性问题。\n将建议纳入下一轮优化计划。'),
        53: ('goals[2].body', '统一任务台账和交付标准。\n对跨组依赖设置明确的协调节点。'),
        54: ('goals[3].body', '开展岗位培训和案例分享。\n通过实践提升团队独立交付能力。'),
    }, role='framework', note='中心四环与四侧说明一一对应，固定四目标。'),
    129: record('四种创新工作方式', 'four-innovation-methods', 'four-innovation-quadrants', 4, {
        55: ('page.title', '方法改进｜四种创新工作方式'),
        10: ('methods[0].heading', '跨组协作沟通'),
        42: ('methods[1].heading', '数据辅助决策'),
        39: ('methods[2].heading', '敏捷任务推进'),
        45: ('methods[3].heading', '员工自主改进'),
        31: ('methods[0].vertical', '创\n新\n方\n式\n一'),
        32: ('methods[1].vertical', '创\n新\n方\n式\n二'),
        33: ('methods[2].vertical', '创\n新\n方\n式\n三'),
        34: ('methods[3].vertical', '创\n新\n方\n式\n四'),
        9: ('methods[0].body_a', '定期召开跨组会议，提前协调任务依赖。'),
        37: ('methods[0].body_b', '使用共享台账，确保信息可追踪。'),
        40: ('methods[1].body_a', '收集关键指标，识别高频问题。'),
        41: ('methods[1].body_b', '依据数据明确优先级和改进目标。'),
        38: ('methods[2].body_a', '将任务拆分为可验收的小阶段。'),
        43: ('methods[2].body_b', '每周复核进度并及时调整安排。'),
        44: ('methods[3].body_a', '鼓励员工提出现场改进建议。'),
        46: ('methods[3].body_b', '安排案例分享与实践反馈。'),
        54: ('summary.heading', '总结'),
        56: ('summary.body', '以跨组协作、数据判断、分段推进和员工改进四种方式，提高日常工作的质量与效率。'),
    }, role='comparison', note='四个象限的标题、竖排编号和两条说明绑定，底部有统一结论。'),
    142: record('四项能力提升计划', 'four-capability-improvement', 'four-arc-capabilities', 4, {
        65: ('page.title', '能力建设｜四项提升计划'),
        54: ('center.title', '提升\n计划'),
        60: ('items[0].heading', '技术能力提升'),
        61: ('items[1].heading', '协作能力提升'),
        62: ('items[2].heading', '管理能力提升'),
        63: ('items[3].heading', '创新思维提升'),
        55: ('items[0].body', '学习常用工具与技术规范，完成岗位实践。'),
        57: ('items[1].body', '主动对齐需求，提升跨团队任务协作效率。'),
        58: ('items[2].body', '建立任务清单与进度检查机制。'),
        59: ('items[3].body', '结合项目复盘提出可执行的改进方案。'),
    }, locked=(48,50,51,52), role='framework', note='四段扇形能力环与四项说明绑定，固定四项。'),
    157: record('四任务季度执行计划', 'four-task-quarter-plan', 'quarter-four-task-matrix', 4, {
        5: ('page.title', '执行计划｜四项季度重点任务'),
        32: ('quarters[0].heading', '第三季度重点任务'),
        33: ('quarters[1].heading', '第四季度重点任务'),
        24: ('tasks[0].label', '工作任务一'),
        25: ('tasks[1].label', '工作任务二'),
        26: ('tasks[2].label', '工作任务三'),
        27: ('tasks[3].label', '工作任务四'),
        20: ('tasks[0].period', '2026年7月-8月'),
        21: ('tasks[1].period', '2026年7月-9月'),
        22: ('tasks[2].period', '2026年10月-11月'),
        23: ('tasks[3].period', '2026年10月-12月'),
        4: ('tasks[0].heading', '服务流程梳理'),
        47: ('tasks[1].heading', '协作机制优化'),
        51: ('tasks[2].heading', '系统功能改进'),
        55: ('tasks[3].heading', '成果复盘推广'),
        43: ('tasks[0].goal', '任务：梳理高频服务事项，形成统一清单。'),
        46: ('tasks[1].goal', '任务：规范跨组沟通和任务交接方式。'),
        50: ('tasks[2].goal', '任务：优化常用功能，提升处理效率。'),
        54: ('tasks[3].goal', '任务：总结试点经验，形成推广材料。'),
        44: ('tasks[0].method', '措施：访谈一线人员，确认问题和改进优先级。'),
        48: ('tasks[1].method', '措施：建立共享台账，每周同步进度与风险。'),
        52: ('tasks[2].method', '措施：分阶段开发验证，收集使用反馈。'),
        56: ('tasks[3].method', '措施：整理成果和待办，组织经验分享。'),
    }, locked=(45,49,53,57), role='schedule', note='第三、四季度各两项任务；日期须落在所属季度且起止月递增。'),
    199: record('五年发展时间轴', 'five-year-roadmap', 'five-year-alternating-timeline', 5, {
        7: ('page.title', '发展规划｜未来五年路线'),
        8: ('years[0].label', '2026年'),
        9: ('years[1].label', '2027年'),
        10: ('years[2].label', '2028年'),
        11: ('years[3].label', '2029年'),
        12: ('years[4].label', '2030年'),
        82: ('years[0].heading', '01.建立工作基础'),
        94: ('years[1].heading', '02.提升专业能力'),
        63: ('years[2].heading', '03.形成协作机制'),
        91: ('years[3].heading', '04.拓展管理能力'),
        69: ('years[4].heading', '05.沉淀团队经验'),
        83: ('years[0].body', '熟悉业务流程，建立关键事项清单。'),
        95: ('years[1].body', '掌握常用方法，承担独立交付任务。'),
        64: ('years[2].body', '推动跨组协作，形成稳定执行机制。'),
        92: ('years[3].body', '提升统筹能力，负责重点任务推进。'),
        70: ('years[4].body', '总结经验，完善团队知识与培养体系。'),
    }, role='timeline', note='五个年份、图标、说明在上下交错时间轴中绑定；年份必须连续递增。'),
    252: record('三阶段项目逻辑', 'three-stage-project-logic', 'three-goal-flow', 3, {
        4: ('page.title', '项目规划｜三阶段工作逻辑'),
        37: ('stages[0].heading', '需求\n调研'),
        43: ('stages[1].heading', '制定\n方案'),
        44: ('stages[2].heading', '落地\n验证'),
        49: ('links[0].label', '汇总关键使用场景'),
        48: ('links[1].label', '对齐实施节奏'),
        51: ('stages[0].item_a', '访谈一线业务人员'),
        53: ('stages[0].item_b', '分析现有流程效率'),
        55: ('stages[0].item_c', '确认需求优先级'),
        57: ('stages[1].item_a', '明确阶段交付目标'),
        59: ('stages[1].item_b', '制定可执行任务清单'),
        61: ('stages[1].item_c', '评估资源与关键风险'),
        63: ('stages[2].item_a', '安排实施和验收节点'),
        65: ('stages[2].item_b', '选择试点场景'),
        67: ('stages[2].item_c', '对照标准检查成果'),
        69: ('stages[0].summary', '梳理场景和问题'),
        70: ('stages[1].summary', '形成实施方案'),
        71: ('stages[2].summary', '依据反馈优化'),
        73: ('footer.caption', '从需求识别到实施验证，形成可复用的项目推进方法'),
    }, role='process', note='顶部三目标与下方三列说明绑定，固定三阶段；底部总结对应各阶段。'),
}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--library',type=Path,required=True)
    ap.add_argument('--samples',type=Path,required=True)
    ap.add_argument('--reviewed',action='store_true')
    args=ap.parse_args();root=args.library.resolve();args.samples.mkdir(parents=True,exist_ok=True)
    catalog_path=root/'catalog.json';catalog=json.loads(catalog_path.read_text(encoding='utf-8-sig'))
    manifest_path=root/'knowledge-manifest.json';manifest=json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    touched={'catalog.json'}
    for n,spec in SETS.items():
        lid=f'content-blue-{n:03d}';base=root/'layouts'/lid
        ids=set(spec['fields'])|spec['locked']
        for name in ('bindings.json','bindings-red.json'):
            path=base/name;binding=json.loads(path.read_text(encoding='utf-8-sig'))
            found={x['shape_id'] for x in binding['fields']}
            if found!=ids:raise ValueError(f'{lid}/{name} shape IDs differ: {sorted(found^ids)}')
            for field in binding['fields']:
                sid=field['shape_id']
                if sid in spec['locked']:
                    field.update(semantic_role='decoration_locked');continue
                key,value=spec['fields'][sid]
                source_limit=max(field['max_chars'],len(field['source_text']))
                if len(value)>source_limit:raise ValueError(f'{lid} shape {sid} sample over capacity')
                field.update(semantic_path=key,
                             semantic_role='body' if any(mark in key for mark in ('.body','.method','.goal')) else 'label',
                             max_chars=len(value),
                             max_lines=len(value.split('\n')),
                             max_width_units=max(visual_width_units(line) for line in value.split('\n')))
                if n==249 and key in ('metrics[0].value','metrics[1].value'):
                    field.update(max_chars=4,max_width_units=4)
            dump(path,binding);touched.add(path.relative_to(root).as_posix())
        entry=next(x for x in catalog['layouts'] if x['id']==lid)
        entry.update(role=spec['role'],information_relation=spec['relation'],family_id=spec['family'],
                     classification_status='verified' if args.reviewed else 'visual_reviewed',
                     pptx_support='verified_static' if args.reviewed else 'pending_render',
                     batch_status='fixed_native_count_verified' if args.reviewed else 'fields_mapped_pending_render',
                     semantic_review_status='verified_blue_red' if args.reviewed else 'fields_mapped_pending_render')
        rules_path=base/'layout_rules.json';rules=json.loads(rules_path.read_text(encoding='utf-8-sig'))
        rules.update(cardinality_mode='fixed',source_count=spec['count'],supported_counts=[spec['count']],
                     verified_counts=[spec['count']] if args.reviewed else [],
                     validation_status='verified_fixed_count' if args.reviewed else 'pending_render',
                     count_evidence=spec['note'])
        if n==81:rules['goal_kpi_consistency']={'goal_count':3,'total':'kpis.total.value','done':'kpis.done.value','pending':'kpis.pending.value','rate':'kpis.rate.value'}
        if n==157:rules['quarter_task_periods']={'fields':[f'tasks[{i}].period' for i in range(4)],'quarters':[3,3,4,4]}
        if n==199:rules['consecutive_year_fields']=[f'years[{i}].label' for i in range(5)]
        dump(rules_path,rules);touched.add(rules_path.relative_to(root).as_posix())
        spec_path=base/'spec.md'
        spec_path.write_text(f"# {spec['title']}\n\n来源：蓝红 P{n:03d}。信息关系：`{spec['relation']}`。{spec['note']}"
                             f"当前仅支持原生 {spec['count']} 项；增减需重新排版验收。"
                             +('蓝红短文案实填及 PowerPoint 渲染通过。' if args.reviewed else '语义字段已绑定，蓝红实填渲染待验收。')
                             +'Logo 保留；动效、HTML、其他色系和长文案未验收。\n',encoding='utf8')
        touched.add(spec_path.relative_to(root).as_posix())
        for theme in ('blue','red'):
            dump(args.samples/f'{lid}-{theme}.json',{'theme':theme,'item_count':spec['count'],
                                                     'texts':{key:value for key,value in spec['fields'].values()}})
    dump(catalog_path,catalog)
    for rel in touched:manifest['files'][rel]=hashlib.sha256((root/rel).read_bytes()).hexdigest()
    dump(manifest_path,manifest)
    print(json.dumps({'curated':len(SETS),'reviewed':args.reviewed,'touched':len(touched)},ensure_ascii=False))


if __name__=='__main__':main()
