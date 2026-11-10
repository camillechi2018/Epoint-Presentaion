"""Curate eight fixed-count blue/red diagrams for the seventh representative batch."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import curate_blue_red_batch5 as common
from curate_blue_red_batch4 import record, dump


SETS={
 122:record('四项重点工作执行方式','four-work-execution-methods','four-quadrant-execution-wheel',4,{
 50:('page.title','重点工作｜四项执行方式'),48:('center.title','工作执行\n方法'),
 14:('methods[0].heading','目标与任务明确'),
 94:('methods[1].heading','资源与排期匹配'),
 93:('methods[2].heading','过程与质量检查'),
 92:('methods[3].heading','部门沟通协调'),
 29:('methods[0].body_a','明确工作目标和验收标准，形成可执行任务清单。'),
 30:('methods[0].body_b','按阶段设置交付节点，及时核对完成情况。'),
 33:('methods[1].body_a','评估人员和工具需求，提前协调关键资源。'),
 34:('methods[1].body_b','根据任务优先级调整排期与支持力度。'),
 35:('methods[2].body_a','建立质量检查清单，复核重要交付物。'),
 36:('methods[2].body_b','定期发现风险和偏差，推动问题闭环。'),
 37:('methods[3].body_a','确定沟通渠道和责任人，及时同步进展。'),
 38:('methods[3].body_b','通过共享记录追踪跨组待办和决策。'),
 },locked=(73,74,75,76),role='framework',note='中心四扇区与四角说明一一对应，固定四项。'),
 123:record('三组风险与应对','three-risk-response-pairs','opposed-three-risk-cards',3,{
 70:('page.title','风险管理｜三类风险与应对'),
 77:('risks[0].heading','01.排期延误风险'),
 78:('risks[1].heading','02.协作衔接风险'),
 79:('risks[2].heading','03.资源不足风险'),
 80:('responses[0].heading','01.设置检查节点'),
 81:('responses[1].heading','02.明确协作责任'),
 82:('responses[2].heading','03.提前准备资源'),
 89:('risks[0].body','关键依赖未及时确认，可能影响交付时间。'),
 90:('risks[1].body','信息同步不完整，容易出现任务遗漏或重复。'),
 91:('risks[2].body','人员或工具准备不足，可能降低执行效率。'),
 92:('responses[0].body','分阶段复核里程碑，发现延期及时调整排期。'),
 94:('responses[1].body','确定责任人与共享记录，每周同步进展。'),
 93:('responses[2].body','提前评估需求，准备备用人力和工具。'),
 },locked=(64,65,69),role='comparison',note='左侧三项风险与右侧三项策略逐行成对，固定三组。'),
 128:record('四种协作改进举措','four-improvement-practices','four-diamond-improvement',4,{
 49:('page.title','协作改进｜四种实施举措'),
 42:('practices[0].heading','01.跨组协同'),
 43:('practices[1].heading','02.持续学习'),
 44:('practices[2].heading','03.技术协同'),
 45:('practices[3].heading','04.试点验证'),
 15:('practices[0].body','建立跨组例会，提前识别任务依赖。\n共享决策记录，减少信息偏差。'),
 16:('practices[1].body','围绕岗位需要安排培训和案例学习。\n将有效方法沉淀到团队知识库。'),
 17:('practices[2].body','打通系统和工具连接。\n使用共享数据减少重复沟通。'),
 18:('practices[3].body','选择典型场景先行验证。\n记录效果，再决定推广范围。'),
 29:('practices[0].tag_a','协作对齐'),36:('practices[0].tag_b','减少偏差'),
 54:('practices[1].tag_a','岗位培训'),55:('practices[1].tag_b','案例积累'),
 57:('practices[2].tag_a','工具连通'),58:('practices[2].tag_b','信息共享'),
 60:('practices[3].tag_a','试点验证'),61:('practices[3].tag_b','总结经验'),
 },role='framework',note='四个菱形图标与四栏正文及底部成对标签绑定，固定四项。'),
 152:record('三目标靶心','three-goal-target','three-arrow-target',3,{
 5:('page.title','能力发展｜三个阶段目标'),
 2:('goals[0].heading','01.建立清晰沟通机制'),
 39:('goals[1].heading','02.提升交付能力'),
 40:('goals[2].heading','03.形成复盘习惯'),
 8:('goals[0].body','定期与相关团队对齐任务目标，记录关键结论与待办。'),
 33:('goals[1].body','通过项目实践和专题学习，提升独立处理问题的能力。'),
 35:('goals[2].body','每月检查成果和不足，将经验转化为下一阶段行动。'),
 },locked=(41,),role='framework',note='三条箭头共同指向靶心，固定三个目标。'),
 207:record('四季度工作计划','four-quarter-plan','looped-quarter-plan',4,{
 2:('page.title','年度计划｜四季度重点任务'),
 33:('center.title','2027年季度工作计划'),
 8:('quarters[0].label','第一季度工作计划'),
 9:('quarters[1].label','第二季度工作计划'),
 15:('quarters[2].label','第三季度工作计划'),
 10:('quarters[3].label','第四季度工作计划'),
 24:('quarters[0].heading','明确目标与资源安排'),
 25:('quarters[1].heading','推进试点与流程优化'),
 27:('quarters[2].heading','扩大应用与质量复核'),
 26:('quarters[3].heading','年度复盘与后续规划'),
 32:('quarters[0].body','梳理重点需求，明确年度目标。\n评估资源和时间安排。'),
 49:('quarters[1].body','选择业务场景开展试点。\n收集反馈并调整流程。'),
 37:('quarters[2].body','推广成熟做法，检查执行质量。\n及时处理跨组依赖问题。'),
 50:('quarters[3].body','汇总成果与改进事项。\n形成下一年度工作计划。'),
 },role='timeline',note='四季度内容在回环路径上按一至四季度对应，固定四项。'),
 246:record('五步项目推进流程','five-step-project-delivery','five-chevron-delivery-rows',5,{
 3:('page.title','项目推进｜五步执行闭环'),
 37:('steps[0].heading','明确任务目标'),
 38:('steps[1].heading','准备所需资源'),
 39:('steps[2].heading','执行与过程跟踪'),
 40:('steps[3].heading','质量检查反馈'),
 41:('steps[4].heading','总结与经验沉淀'),
 42:('steps[0].body','确定目标、范围和交付标准，并明确负责人。'),
 43:('steps[1].body','核对人员、工具及依赖事项，安排关键节点。'),
 44:('steps[2].body','按计划推进任务，每周检查进度与风险。'),
 45:('steps[3].body','对照验收标准复核成果，记录问题和处理意见。'),
 46:('steps[4].body','归档交付材料，复盘经验并形成改进清单。'),
 },locked=(22,29,31,33,36),role='process',note='五条箭头、图标、编号及说明固定一一对应。'),
 253:record('五步品牌推进','five-step-brand-plan','five-fan-brand-steps',5,{
 6:('page.title','品牌建设｜五步推进路径'),
 53:('center.title','品牌推进\nBRAND PLAN'),
 24:('steps[0].heading','品牌现状调研  #01'),
 34:('steps[1].heading','目标与受众明确  #02'),
 30:('steps[2].heading','传播策略制定  #03'),
 4:('steps[3].heading','活动执行跟踪  #04'),
 26:('steps[4].heading','阶段成效评估  #05'),
 19:('steps[0].body','分析目标客户需求和现有品牌认知，形成基线。'),
 20:('steps[1].body','确定传播目标与重点受众，明确阶段衡量口径。'),
 21:('steps[2].body','制定内容计划和渠道安排，统一对外表达。'),
 22:('steps[3].body','按计划执行活动，跟踪反馈和重要指标。'),
 25:('steps[4].body','总结阶段结果与问题，安排下一轮优化。'),
 },locked=(9,10,13,15,16),role='process',note='五瓣扇形数字与右侧五段说明逐项对应，固定五步。'),
 254:record('四组问题与方案','four-issue-solution-columns','four-column-issue-solutions',4,{
 2:('page.title','团队协作｜四组问题与方案'),
 34:('pairs[0].issue.heading','职责分工不清'),
 81:('pairs[1].issue.heading','技能经验不足'),
 39:('pairs[2].issue.heading','任务排期冲突'),
 44:('pairs[3].issue.heading','反馈响应滞后'),
 24:('pairs[0].issue.body','工作边界模糊，任务交接中容易出现遗漏。'),
 85:('pairs[1].issue.body','部分岗位缺少处理新场景所需的方法。'),
 25:('pairs[2].issue.body','多项任务同时到期，关键资源安排紧张。'),
 26:('pairs[3].issue.body','问题记录分散，处理结果未及时回传。'),
 27:('pairs[0].solution','明确责任人和交付标准。\n用共享清单跟踪交接结果。'),
 86:('pairs[1].solution','安排专题培训和案例复盘。\n建立常见问题处理指引。'),
 67:('pairs[2].solution','统一优先级和排期依据。\n预留关键任务的协调时间。'),
 69:('pairs[3].solution','建立反馈入口和处理时限。\n定期核对改进措施是否落实。'),
 },locked=(32,35,36,37),role='comparison',note='四列各由问题、说明、方案和图形构成，固定四组。'),
}


def add_extra_rules(root:Path):
 manifest_path=root/'knowledge-manifest.json';manifest=json.loads(manifest_path.read_text(encoding='utf8'))
 for n in (123,207,253):
  path=root/f'layouts/content-blue-{n:03d}/layout_rules.json';rules=json.loads(path.read_text(encoding='utf8'))
  if n==123:rules['text_box_expand_pt']=[{'shape_id':69,'vertical_extra_pt':24}]
  if n==207:rules['quarter_plan_fields']={'center':'center.title','labels':[f'quarters[{i}].label' for i in range(4)]}
  if n==253:rules['numbered_heading_suffix']=[{'field':f'steps[{i}].heading','suffix':f'#{i+1:02d}'} for i in range(5)]
  dump(path,rules);manifest['files'][path.relative_to(root).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
 dump(manifest_path,manifest)


if __name__=='__main__':
 common.SETS=SETS;common.main()
 args=sys.argv;root=Path(args[args.index('--library')+1]).resolve();add_extra_rules(root)
