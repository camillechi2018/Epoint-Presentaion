"""Curate eight native blue/red layouts in the sixth representative batch."""
from __future__ import annotations

import json
import hashlib
import sys
from pathlib import Path

import curate_blue_red_batch5 as common
from curate_blue_red_batch4 import record, dump


SETS = {
    71: record('三阶段六任务安排', 'three-phase-six-task-plan', 'three-lane-six-card-plan', 3, {
        12: ('page.title', '项目安排｜三阶段六项重点工作'),
        30: ('phases[0].heading', '01.明确目标与实施范围'),
        31: ('phases[1].heading', '02.形成方案并组织试点'),
        32: ('phases[2].heading', '03.全面推进与质量复核'),
        38: ('phases[0].tasks[0].heading', '梳理业务需求'),
        40: ('phases[0].tasks[0].body', '访谈相关团队，形成需求清单和验收标准。'),
        41: ('phases[0].tasks[1].heading', '明确责任分工'),
        42: ('phases[0].tasks[1].body', '确定负责人、协作方式与关键交付节点。'),
        43: ('phases[1].tasks[0].heading', '制定实施方案'),
        44: ('phases[1].tasks[0].body', '评估资源和风险，完成方案评审与排期。'),
        45: ('phases[1].tasks[1].heading', '开展业务试点'),
        46: ('phases[1].tasks[1].body', '选择典型场景，记录问题与初步成效。'),
        47: ('phases[2].tasks[0].heading', '推广成熟做法'),
        48: ('phases[2].tasks[0].body', '根据试点反馈优化流程，再逐步扩大范围。'),
        49: ('phases[2].tasks[1].heading', '复核交付质量'),
        50: ('phases[2].tasks[1].body', '对照验收口径检查成果，沉淀改进事项。'),
    }, role='schedule', note='三个横向阶段各绑定两张任务卡，固定三阶段、六任务。'),
    106: record('五项工作成果清单', 'five-achievement-rows', 'five-icon-result-rows', 5, {
        27: ('page.title', '工作成果｜五项重点进展'),
        26: ('items[0].heading', '项目交付'),
        29: ('items[1].heading', '流程优化'),
        30: ('items[2].heading', '客户服务'),
        31: ('items[3].heading', '质量提升'),
        32: ('items[4].heading', '团队协作'),
        33: ('items[0].body', '按计划完成阶段成果交付。\n关键问题有记录、有负责人。'),
        46: ('items[1].body', '梳理高频事项并减少重复交接。\n统一常用流程的操作说明。'),
        56: ('items[2].body', '定期汇总客户反馈与诉求。\n将共性问题纳入改进清单。'),
        57: ('items[3].body', '建立成果复核和问题回访机制。\n持续跟踪整改完成情况。'),
        58: ('items[4].body', '加强跨组信息同步。\n通过案例分享提升协作效率。'),
    }, locked=(34,35,41,42,43), role='summary', note='五个编号、图标、横条和说明固定对应。'),
    138: record('双维度四象限平衡', 'two-dimension-four-quadrant-balance', 'dual-center-four-corner', 4, {
        36: ('page.title', '工作管理｜效率与质量平衡'),
        3: ('center.top', '效率管理'),
        7: ('center.bottom', '质量管理'),
        15: ('quadrants[0].heading', '01.合理安排时间'),
        19: ('quadrants[1].heading', '02.明确任务优先级'),
        17: ('quadrants[2].heading', '03.坚持质量检查'),
        21: ('quadrants[3].heading', '04.形成改进习惯'),
        13: ('quadrants[0].body', '预留重点工作时段，避免多任务相互挤占。\n每周检查进度，及时调整排期。'),
        18: ('quadrants[1].body', '按影响程度和截止时间排序任务。\n明确可延期事项和协调边界。'),
        16: ('quadrants[2].body', '对关键成果设置复核节点。\n记录常见问题和处理方法。'),
        20: ('quadrants[3].body', '定期收集使用反馈和质量数据。\n把可执行建议转为下一轮任务。'),
        52: ('quadrants[0].tag_a', '计划清晰'),
        53: ('quadrants[0].tag_b', '时间可控'),
        56: ('quadrants[1].tag_a', '优先排序'),
        57: ('quadrants[1].tag_b', '任务边界'),
        59: ('quadrants[2].tag_a', '标准统一'),
        60: ('quadrants[2].tag_b', '结果复核'),
        62: ('quadrants[3].tag_a', '收集反馈'),
        63: ('quadrants[3].tag_b', '持续改进'),
    }, role='comparison', note='四角内容围绕效率与质量双中心，固定四象限。'),
    161: record('五方向发展展望', 'five-direction-outlook', 'five-column-outlook', 5, {
        64: ('page.title', '发展展望｜五项建设方向'),
        46: ('items[0].heading', '数字流程建设'),
        47: ('items[1].heading', '灵活协作机制'),
        48: ('items[2].heading', '跨域能力培养'),
        49: ('items[3].heading', '服务体验提升'),
        50: ('items[4].heading', '可持续运营'),
        27: ('items[0].body_a', '梳理高频事项，推动流程线上办理。'),
        30: ('items[0].body_b', '建立数据看板，跟踪处理效率。'),
        51: ('items[1].body_a', '明确跨组交付要求和接口责任。'),
        52: ('items[1].body_b', '通过共享台账同步任务与风险。'),
        54: ('items[2].body_a', '开展岗位培训和项目实践。'),
        55: ('items[2].body_b', '沉淀跨领域案例与可复用方法。'),
        57: ('items[3].body_a', '持续收集客户和一线反馈。'),
        58: ('items[3].body_b', '按优先级推进体验改进事项。'),
        60: ('items[4].body_a', '建立质量监测和例行复盘机制。'),
        61: ('items[4].body_b', '兼顾资源效率与长期服务能力。'),
        62: ('items[0].tag_a', '流程统一'), 63: ('items[0].tag_b', '效率提升'),
        66: ('items[1].tag_a', '协作清晰'), 67: ('items[1].tag_b', '信息同步'),
        69: ('items[2].tag_a', '能力成长'), 70: ('items[2].tag_b', '案例沉淀'),
        72: ('items[3].tag_a', '反馈闭环'), 73: ('items[3].tag_b', '服务优化'),
        75: ('items[4].tag_a', '质量可控'), 76: ('items[4].tag_b', '长期发展'),
    }, role='framework', note='五个栏目各有两段正文和两个标签，固定五列。'),
    201: record('十年规划时间轴', 'ten-year-roadmap', 'serpentine-ten-year-timeline', 10, {
        3: ('page.title', '发展规划｜十年能力路线'),
        97: ('years[0].label', '2027年规划'),
        98: ('years[1].label', '2028年规划'),
        99: ('years[2].label', '2029年规划'),
        100: ('years[3].label', '2030年规划'),
        106: ('years[4].label', '2031年规划'),
        105: ('years[5].label', '2032年规划'),
        101: ('years[6].label', '2033年规划'),
        102: ('years[7].label', '2034年规划'),
        103: ('years[8].label', '2035年规划'),
        104: ('years[9].label', '2036年规划'),
        107: ('years[0].body', '熟悉业务流程与岗位要求。'),
        108: ('years[1].body', '独立完成常规交付任务。'),
        109: ('years[2].body', '建立跨组协作和沟通机制。'),
        110: ('years[3].body', '负责重点项目的阶段推进。'),
        117: ('years[4].body', '协调多方资源和任务依赖。'),
        116: ('years[5].body', '形成可复用的项目管理方法。'),
        111: ('years[6].body', '拓展新业务场景与服务范围。'),
        112: ('years[7].body', '参与关键方案讨论与决策。'),
        113: ('years[8].body', '带动团队能力和交付质量提升。'),
        114: ('years[9].body', '复盘长期成果，规划下一阶段。'),
        57: ('corner.top_a', '基础建设'),
        58: ('corner.top_b', '能力提升'),
        2: ('corner.bottom_a', '统筹推进'),
        55: ('corner.bottom_b', '总结复盘'),
    }, role='timeline', note='十个年份沿回折时间轴依次排列，年份须连续递增，固定十项。'),
    231: record('四步申请审批流程', 'four-step-approval-process', 'four-branch-approval-arrows', 4, {
        2: ('page.title', '审批流程｜四步办理闭环'),
        10: ('steps[0].heading', '提交业务申请'),
        23: ('steps[1].heading', '开展材料审核'),
        24: ('steps[2].heading', '发送审批结果'),
        25: ('steps[3].heading', '收集办理反馈'),
        27: ('steps[0].card_heading', '提交业务申请'),
        33: ('steps[1].card_heading', '开展材料审核'),
        47: ('steps[2].card_heading', '发送审批结果'),
        48: ('steps[3].card_heading', '收集办理反馈'),
        32: ('steps[0].body', '填写申请内容与相关材料。\n提交前核对信息完整性。'),
        35: ('steps[1].body', '审核条件、材料和时间安排。\n发现问题时退回补正。'),
        49: ('steps[2].body', '通过后发送办理确认。\n未通过时说明原因和下一步。'),
        53: ('steps[3].body', '收集办理评价与改进建议。\n将共性问题纳入优化清单。'),
        50: ('decision.review', '审核'),
        51: ('decision.verify', '复核'),
        52: ('decision.pass', '通过'),
        36: ('decision.fail', '退回'),
        37: ('decision.success', '办结'),
        40: ('decision.retry', '补正'),
    }, locked=(28,29,30,31), role='process', note='四条输入箭头、四张说明卡及审核分支构成固定四步闭环。'),
    241: record('三阶段数据决策流程', 'three-stage-data-decision', 'three-lane-decision-arrow', 3, {
        2: ('page.title', '决策流程｜数据分析与执行'),
        39: ('section.title', '数据辅助决策'),
        30: ('steps[0].heading', '01.收集与整理数据'),
        31: ('steps[1].heading', '02.分析与识别问题'),
        32: ('steps[2].heading', '03.形成并执行决策'),
        28: ('cards[0].body', '明确要解决的问题与所需指标。\n汇总业务数据，检查来源和口径。'),
        36: ('cards[1].body', '使用适合的方法分析现状。\n对关键结论进行交叉核对。'),
        37: ('cards[2].body', '比较可行方案及实施条件。\n明确责任人、节点和验证方式。'),
        33: ('tools[0].label', '数据检查'),
        34: ('tools[1].label', '原因分析'),
        35: ('tools[2].label', '结果复盘'),
    }, locked=(38,40,41), role='process', note='三段汇流箭头与三个说明区域及三个方法标签固定绑定。'),
    249: record('四层品牌价值模型', 'four-layer-brand-value', 'brand-house-four-levels', 4, {
        2: ('page.title', '品牌建设｜四层价值路径'),
        13: ('levels[0].label', '品牌愿景\nVISION'),
        18: ('levels[1].label', '品牌执行\nACTION'),
        21: ('levels[2].label', '品牌策略\nSTRATEGY'),
        24: ('levels[3].label', '品牌定位\nPOSITION'),
        39: ('details[0].heading', '品牌定位  POSITION'),
        38: ('details[0].body', '分析目标客户与市场需求，明确品牌定位和服务边界。'),
        43: ('details[1].heading', '品牌执行  ACTION'),
        42: ('details[1].body', '统一服务表达和视觉呈现，保障各接触点体验一致。'),
        47: ('details[2].heading', '品牌策略  STRATEGY'),
        46: ('details[2].body', '明确价值主张和传播重点，制定可执行的推进计划。'),
        51: ('details[3].heading', '品牌价值  VALUE'),
        50: ('details[3].body', '定期收集反馈与指标，评估品牌建设的阶段成果。'),
        25: ('metrics[0].value', '74%'),
        26: ('metrics[0].body', '示例调研中的品牌认知比例，用于演示指标位置。'),
        31: ('metrics[1].value', '81%'),
        32: ('metrics[1].body', '示例调研中的品牌信任比例，用于演示指标位置。'),
    }, locked=(12,17,20,23), role='framework', note='四层品牌屋与两侧说明固定对应；两处百分比为输入指标，须在 0–100% 内。'),
}


def add_extra_rules(root: Path):
    manifest_path=root/'knowledge-manifest.json';manifest=json.loads(manifest_path.read_text(encoding='utf8'))
    for n in (201,249):
        path=root/f'layouts/content-blue-{n:03d}/layout_rules.json'
        rules=json.loads(path.read_text(encoding='utf8'))
        if n==201:rules['consecutive_year_fields']=[f'years[{i}].label' for i in range(10)]
        if n==249:
            rules['percentage_fields']=['metrics[0].value','metrics[1].value']
            rules['percentage_text_fit']=[
                {'field':'metrics[0].value','shape_id':25,'four_char_font_pt':42},
                {'field':'metrics[1].value','shape_id':31,'four_char_font_pt':42},
            ]
        dump(path,rules);rel=path.relative_to(root).as_posix()
        manifest['files'][rel]=hashlib.sha256(path.read_bytes()).hexdigest()
    dump(manifest_path,manifest)


if __name__=='__main__':
    common.SETS=SETS
    common.main()
    args=sys.argv
    root=Path(args[args.index('--library')+1]).resolve()
    add_extra_rules(root)
