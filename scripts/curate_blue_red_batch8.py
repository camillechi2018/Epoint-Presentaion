"""Curate the eighth batch of fixed-count blue/red report components."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import curate_blue_red_batch5 as common
from curate_blue_red_batch4 import record, dump


SETS = {
 147: record('五节点能力成长路径','five-skill-growth-milestones','ascending-five-milestones',5,{
 64:('page.title','能力发展｜五节点成长路径'),
 35:('section.title','个人能力成长计划'),
 43:('steps[0].goal','专业能力'),
 49:('steps[1].goal','表达沟通'),
 50:('steps[2].goal','时间管理'),
 51:('steps[3].goal','独立决策'),
 52:('steps[4].goal','问题解决'),
 3:('steps[0].label','提升计划01'),
 11:('steps[1].label','提升计划02'),
 36:('steps[2].label','提升计划03'),
 53:('steps[3].label','提升计划04'),
 61:('steps[4].label','提升计划05'),
 8:('steps[0].body','目标：掌握岗位核心方法。\n行动：每月完成一次案例学习。'),
 12:('steps[1].body','目标：提高跨组沟通效率。\n行动：记录决策并及时同步。'),
 37:('steps[2].body','目标：按期完成重点任务。\n行动：拆分节点，定期检查进度。'),
 54:('steps[3].body','目标：独立处理常见问题。\n行动：对照数据评估处理方案。'),
 62:('steps[4].body','目标：形成可复用的解决方法。\n行动：复盘难题并沉淀处理指引。'),
 },role='timeline',note='五个抬升节点、底部目标和计划说明一一对应，固定五步。'),
 160: record('四方面年度工作总结','four-area-work-summary','four-area-work-summary-arrow',4,{
 50:('page.title','工作总结｜四方面复盘'),
 25:('areas[0].heading','目标完成情况'),
 37:('areas[1].heading','团队协作进展'),
 29:('areas[2].heading','流程效率改进'),
 33:('areas[3].heading','问题与风险分析'),
 49:('areas[0].point_a','重点任务按计划推进，主要交付节点均完成。'),
 51:('areas[0].point_b','对未完成事项分析原因，列出下阶段补救措施。'),
 52:('areas[1].point_a','通过案例分享和专题培训，统一团队工作方法。'),
 53:('areas[1].point_b','明确跨组责任人和沟通节奏，减少交接遗漏。'),
 59:('areas[2].point_a','精简重复审批步骤，建立统一任务跟踪清单。'),
 60:('areas[2].point_b','将常见问题形成操作指引，提高处理效率。'),
 56:('areas[3].point_a','识别关键资源和排期风险，安排替代方案。'),
 57:('areas[3].point_b','持续跟踪外部变化，及时调整实施顺序。'),
 10:('summary[0].label','工作成果01'),
 11:('summary[1].label','协作进展02'),
 22:('summary[2].label','流程优化03'),
 46:('summary[3].label','问题复盘04'),
 47:('summary.year','2027'),
 64:('conclusion.heading','阶段结论'),
 63:('conclusion.body','总体进展平稳，下一阶段将重点处理协作衔接和风险闭环。'),
 },role='summary',note='四个上下区块与中部四项总结箭头对应；固定四方面。'),
 182: record('四象限重点工作方法','four-method-execution-quadrants','four-quadrant-execution-methods',4,{
 2:('page.title','重点工作｜四象限执行方法'),
 23:('center.title','重点工作\n执行方法'),
 11:('methods[0].heading','目标与范围明确'),
 15:('methods[1].heading','资源安排到位'),
 13:('methods[2].heading','协作机制清晰'),
 17:('methods[3].heading','质量检查闭环'),
 24:('methods[0].body','召开启动会，明确目标、交付标准和负责人。\n将任务拆到具体节点，形成可追踪清单。'),
 28:('methods[1].body','评估人员、工具和时间需求，提前协调资源。\n根据优先级安排重点任务。'),
 27:('methods[2].body','建立固定沟通节奏，及时同步决策与风险。\n跨组事项由责任人跟进闭环。'),
 29:('methods[3].body','对照验收标准检查关键成果。\n记录问题和改进措施，定期复核。'),
 },locked=(19,20,21,22),role='framework',note='四象限数字与四侧说明锁定对应，固定四项。'),
 204: record('上半年六个月工作时间线','six-month-work-timeline','six-month-alternating-plan',6,{
 7:('page.title','半年复盘｜六个月重点事项'),
 8:('months[0].heading','01.完成目标与任务拆解'),
 19:('months[1].heading','02.建立跨组协作机制'),
 17:('months[2].heading','03.推进试点并收集反馈'),
 23:('months[3].heading','04.优化流程与交付质量'),
 11:('months[4].heading','05.扩大应用和培训范围'),
 21:('months[5].heading','06.总结经验与后续计划'),
 34:('months[0].body','明确阶段目标和衡量方式。\n梳理任务清单并落实责任人。'),
 48:('months[1].body','确定团队接口和沟通频率。\n建立共享记录和问题台账。'),
 37:('months[2].body','选择典型场景开展小范围试点。\n按周记录使用反馈和风险。'),
 49:('months[3].body','根据反馈调整操作流程。\n复核关键交付物的质量。'),
 40:('months[4].body','将成熟做法推广到更多团队。\n组织培训并提供使用支持。'),
 50:('months[5].body','汇总成果、问题和待办。\n形成下半年实施计划。'),
 },locked=(4,43,44,45,46,47),role='timeline',note='月份标签固定一月至六月；上下交错的六组内容对应六个月。'),
 208: record('四季度交错工作计划','four-quarter-alternating-plan','four-quarter-alternating-milestones',4,{
 8:('page.title','年度计划｜四季度工作重点'),
 18:('quarters[0].heading','01.明确目标与责任'),
 73:('quarters[1].heading','02.推进试点与交付'),
 74:('quarters[2].heading','03.扩大应用与优化'),
 75:('quarters[3].heading','04.复盘成果与规划'),
 22:('quarters[0].short','梳理任务，配置资源'),
 29:('quarters[1].short','推进执行，收集反馈'),
 34:('quarters[2].short','推广做法，检查质量'),
 39:('quarters[3].short','总结经验，明确方向'),
 49:('quarters[0].body','细化年度目标与阶段任务。\n明确团队分工和交付标准。\n评估资源及关键风险。'),
 50:('quarters[1].body','选定场景推进试点。\n按月检查执行情况。\n及时处理跨组依赖。'),
 51:('quarters[2].body','推广已经验证的方法。\n整理培训和支持材料。\n复核交付质量和效果。'),
 52:('quarters[3].body','汇总全年成果与不足。\n收集用户和团队反馈。\n形成下一年度优化计划。'),
 },locked=(69,70,71,72),role='schedule',note='四季度标签、上下交错正文和底部阶段槽对应，固定四季度。'),
 235: record('四阶段项目里程碑','four-project-milestones','four-project-delivery-milestones',4,{
 2:('page.title','项目推进｜四阶段里程碑'),
 23:('stages[0].heading','启动与规划'),
 24:('stages[1].heading','执行与跟踪'),
 36:('stages[2].heading','风险与质量'),
 27:('stages[3].heading','交付与复盘'),
 48:('stages[0].body','确认项目范围和预期成果。\n明确成员分工与实施排期。'),
 49:('stages[1].body','按任务清单推进执行。\n定期检查进度并处理依赖。'),
 50:('stages[2].body','识别关键风险和质量问题。\n按优先级安排应对措施。'),
 52:('stages[3].body','对照标准验收交付物。\n整理经验和待改进事项。'),
 53:('stages[0].note','输出范围、目标和阶段计划。'),
 54:('stages[1].note','持续同步进展与问题。'),
 55:('stages[2].note','复核风险、质量与解决结果。'),
 56:('stages[3].note','完成验收并形成复盘报告。'),
 },locked=(13,14,20,17),role='process',note='四个阶段标题、正文、提示及底部阶段标签固定对应。'),
 247: record('五方向改变与成效','five-change-outcome-columns','five-change-outcome-comparison',5,{
 5:('page.title','流程优化｜五方向改变与成效'),
 94:('items[0].heading','需求入口\n统一'),
 95:('items[1].heading','任务分工\n明确'),
 96:('items[2].heading','流程节点\n简化'),
 97:('items[3].heading','风险响应\n提速'),
 98:('items[4].heading','经验方法\n沉淀'),
 99:('items[0].change','建立统一需求入口和分类规则，减少重复登记。'),
 101:('items[1].change','明确每项任务的负责人、配合方和完成标准。'),
 103:('items[2].change','合并重复审批环节，形成清晰的处理路径。'),
 105:('items[3].change','建立风险记录和处理时限，按优先级跟进。'),
 107:('items[4].change','把高频问题整理为案例和操作指引。'),
 100:('items[0].outcome','需求记录更集中，后续分析和跟踪更方便。'),
 102:('items[1].outcome','任务交接更清楚，跨组协作中的遗漏减少。'),
 104:('items[2].outcome','常规事项处理步骤减少，推进节奏更稳定。'),
 106:('items[3].outcome','重要问题能够及时上报并形成闭环记录。'),
 108:('items[4].outcome','团队可以复用已有方法，减少重复摸索。'),
 },locked=(34,39),role='comparison',note='五列上方主题与上下两行改变、成效对应，固定五方向。'),
 263: record('六项重点工作环','six-priority-work-ring','six-priority-ring-spokes',6,{
 5:('page.title','工作规划｜六项重点任务'),
 31:('center.title','六项重点\n工作任务'),
 32:('items[0].heading','市场需求识别'),
 40:('items[1].heading','产品功能优化'),
 36:('items[2].heading','流程效率提升'),
 34:('items[3].heading','团队能力建设'),
 42:('items[4].heading','技术工具应用'),
 38:('items[5].heading','风险与质量管理'),
 33:('items[0].body','梳理客户场景和使用问题，明确优先需求。'),
 41:('items[1].body','结合反馈改进常用功能，验证交付效果。'),
 37:('items[2].body','减少重复步骤，形成统一操作与检查清单。'),
 35:('items[3].body','安排专题培训和案例交流，提升协作能力。'),
 43:('items[4].body','推广适用的协作工具，支持任务跟踪。'),
 39:('items[5].body','定期识别风险，检查质量并跟进处理结果。'),
 51:('footer.summary','以目标为导向推进工作，并按阶段复盘和调整。'),
 },locked=(11,13,12,22,24,23),role='framework',note='环形六个数字与左右六组说明固定对应。'),
}


def add_extra_rules(root:Path):
    manifest_path=root/'knowledge-manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf8'))
    for n in (147,160):
        path=root/f'layouts/content-blue-{n:03d}/layout_rules.json'
        rules=json.loads(path.read_text(encoding='utf8'))
        if n==147:
            rules['numbered_heading_suffix']=[{'field':f'steps[{i}].label','suffix':f'{i+1:02d}'} for i in range(5)]
        else:
            rules['year_fields']=['summary.year']
        dump(path,rules)
        manifest['files'][path.relative_to(root).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    dump(manifest_path,manifest)


if __name__=='__main__':
    common.SETS=SETS
    common.main()
    args=sys.argv
    add_extra_rules(Path(args[args.index('--library')+1]).resolve())
