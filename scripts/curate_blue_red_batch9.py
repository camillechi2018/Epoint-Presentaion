"""Curate the ninth batch, including an editable two-series native chart."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import curate_blue_red_batch5 as common
from curate_blue_red_batch4 import record, dump


SETS={
 143:record('四项管理能力提升','four-management-abilities','four-step-ability-ladder',4,{
 43:('page.title','能力提升｜四项管理能力'),
 3:('abilities[0].heading','自我认知'),
 7:('abilities[1].heading','团队协作'),
 8:('abilities[2].heading','问题判断'),
 9:('abilities[3].heading','时间管理'),
 11:('abilities[0].body','目标：识别自身优势与不足。\n行动：定期复盘工作反馈，调整沟通方式。'),
 12:('abilities[1].body','目标：建立清晰的协作机制。\n行动：明确分工与反馈节奏，及时处理分歧。'),
 13:('abilities[2].body','目标：提高分析与决策质量。\n行动：收集证据，比较方案并记录依据。'),
 14:('abilities[3].body','目标：提升任务执行效率。\n行动：设置优先级和检查节点，减少延误。'),
 },role='framework',note='四级阶梯与四项能力说明固定对应。'),
 149:record('五项能力提升计划','five-capability-development-columns','five-rising-capability-columns',5,{
 68:('page.title','能力建设｜五项提升计划'),
 63:('section.title','五项能力提升计划'),
 46:('abilities[0].heading','专业知识'),
 47:('abilities[1].heading','表达沟通'),
 48:('abilities[2].heading','计划管理'),
 49:('abilities[3].heading','团队带动'),
 50:('abilities[4].heading','问题解决'),
 56:('abilities[0].body','目标：熟悉岗位核心业务。\n行动：每月学习一个典型案例。'),
 58:('abilities[1].body','目标：提高信息传达质量。\n行动：定期汇报并收集反馈。'),
 59:('abilities[2].body','目标：按期完成重要任务。\n行动：拆分节点，检查执行进度。'),
 60:('abilities[3].body','目标：促进小组协作。\n行动：明确责任，分享有效方法。'),
 61:('abilities[4].body','目标：独立处理常见问题。\n行动：记录原因与处理结果。'),
 62:('footer.summary','通过持续学习、实践和复盘，逐步提升岗位能力与协作效率。'),
 },locked=(51,52,53,54,55),role='framework',note='五列能力标题、目标行动和阶梯图形固定对应。'),
 180:record('四领域双亮点展示','four-area-two-highlight-grid','four-column-two-row-highlights',4,{
 4:('page.title','成果展示｜四领域工作亮点'),
 15:('areas[0].heading','协作效率'),
 24:('areas[1].heading','产品体验'),
 25:('areas[2].heading','流程质量'),
 26:('areas[3].heading','团队成长'),
 32:('areas[0].label','亮点01'),
 33:('areas[1].label','亮点02'),
 34:('areas[2].label','亮点03'),
 35:('areas[3].label','亮点04'),
 37:('areas[0].items[0].heading','任务跟踪统一'),
 38:('areas[0].items[0].body','建立共享任务清单，减少重复沟通。\n每周核对责任人和进度。'),
 45:('areas[0].items[1].heading','跨组接口明确'),
 46:('areas[0].items[1].body','统一交接标准，记录待确认事项。\n跨组问题由专人跟进。'),
 39:('areas[1].items[0].heading','常用功能优化'),
 40:('areas[1].items[0].body','收集用户反馈，梳理高频场景。\n优先改进影响体验的问题。'),
 47:('areas[1].items[1].heading','试点验证完善'),
 48:('areas[1].items[1].body','选定试点团队使用新流程。\n依据结果调整设计细节。'),
 41:('areas[2].items[0].heading','验收清单建立'),
 42:('areas[2].items[0].body','明确交付标准与检查项目。\n对关键成果进行复核。'),
 49:('areas[2].items[1].heading','问题闭环跟踪'),
 50:('areas[2].items[1].body','集中记录问题和处理结果。\n按月分析常见原因。'),
 43:('areas[3].items[0].heading','案例学习分享'),
 44:('areas[3].items[0].body','围绕岗位需要安排专题学习。\n整理案例供团队复用。'),
 51:('areas[3].items[1].heading','能力发展计划'),
 52:('areas[3].items[1].body','结合任务表现明确提升目标。\n安排实践机会并定期反馈。'),
 },role='summary',note='四列主题，每列上下两个亮点卡；固定四领域、每领域两例。'),
 202:record('五阶段十年发展路线','five-stage-ten-year-roadmap','five-rising-career-stages',5,{
 5:('page.title','发展规划｜五阶段十年路线'),
 46:('section.title','2027—2036年五阶段规划'),
 63:('section.intro','五阶段规划从基础能力、独立交付到团队统筹逐步提升。'),
 30:('stages[0].label','第一阶段规划'),
 8:('stages[1].label','第二阶段规划'),
 9:('stages[2].label','第三阶段规划'),
 10:('stages[3].label','第四阶段规划'),
 12:('stages[4].label','第五阶段规划'),
  4:('stages[0].heading','熟悉业务与岗位入门'),
  6:('stages[0].body','学习业务流程和常用工具。\n参与团队任务，掌握基础方法。'),
 11:('stages[1].heading','独立执行与能力积累'),
 15:('stages[1].body','承担独立交付任务。\n定期总结问题与改进经验。'),
 47:('stages[2].heading','跨组协作与项目担当'),
 48:('stages[2].body','负责跨组任务推进。\n协调资源并控制关键风险。'),
 49:('stages[3].heading','团队统筹与机制建设'),
 50:('stages[3].body','组织重点项目交付。\n完善团队协作和培养机制。'),
 51:('stages[4].heading','方法沉淀与持续发展'),
 52:('stages[4].body','总结成熟做法并推广。\n规划下一阶段能力发展。'),
 55:('stages[3].skill_label','能力发展'),
 54:('stages[3].skill_body','提升统筹、沟通和风险判断能力。\n形成跨团队协作经验。'),
 56:('stages[4].skill_label','能力发展'),
 53:('stages[4].skill_body','完善决策与管理方法。\n沉淀可复用的组织经验。'),
 57:('stages[0].period','2027年-2028年'),
 58:('stages[1].period','2029年-2030年'),
 59:('stages[2].period','2031年-2032年'),
 60:('stages[3].period','2033年-2034年'),
 61:('stages[4].period','2035年-2036年'),
 },role='timeline',note='五个上升阶段各覆盖连续两年，固定五阶段；后两阶段有额外能力槽。'),
 214:record('六个月项目推进时间线','six-month-project-roadmap','six-month-alternating-project-cards',6,{
 2:('page.title','项目推进｜六个月实施路线'),
 23:('months[0].heading','01.明确目标与范围'),
 26:('months[1].heading','02.完成需求分析'),
 24:('months[2].heading','03.制定实施方案'),
 27:('months[3].heading','04.开展试点验证'),
 25:('months[4].heading','05.扩大应用范围'),
 28:('months[5].heading','06.总结成果经验'),
 10:('months[0].date','2027年1月'),
 17:('months[1].date','2027年2月'),
 18:('months[2].date','2027年3月'),
 19:('months[3].date','2027年4月'),
 20:('months[4].date','2027年5月'),
 21:('months[5].date','2027年6月'),
 45:('months[0].body','明确目标、范围和交付标准。\n落实负责人及关键节点。'),
 48:('months[1].body','访谈用户，梳理高频场景。\n确认问题和需求优先级。'),
 46:('months[2].body','制定方案和实施排期。\n评估资源与潜在风险。'),
 49:('months[3].body','选择场景试点，收集反馈。\n检查流程和交付质量。'),
 47:('months[4].body','组织培训并推广成熟做法。\n提供使用支持和问题处理。'),
 50:('months[5].body','汇总结果和改进事项。\n形成后续迭代计划。'),
 },role='timeline',note='六个月份、上下交错的标题与正文一一对应，日期须连续。'),
 240:record('六步问题处理闭环','six-step-issue-handling-loop','six-step-serpentine-loop',6,{
 11:('page.title','问题处理｜六步闭环'),
 57:('center.title','问题处理闭环'),
 12:('steps[0].heading','接收与登记'),
 19:('steps[1].heading','分类与判断'),
 20:('steps[2].heading','调查与方案'),
 23:('steps[3].heading','沟通与确认'),
 22:('steps[4].heading','执行与验证'),
 21:('steps[5].heading','关闭与跟踪'),
 25:('steps[0].goal','目标：完整记录问题'),
 26:('steps[1].goal','目标：明确影响范围'),
 27:('steps[2].goal','目标：形成可行方案'),
 30:('steps[3].goal','目标：取得处理共识'),
 29:('steps[4].goal','目标：落实解决措施'),
 28:('steps[5].goal','目标：确认问题关闭'),
 32:('steps[0].body','通过统一入口接收问题。\n记录情况、时间及相关人员。'),
 34:('steps[1].body','按类型与紧急程度分类。\n判断影响并确定处理优先级。'),
 35:('steps[2].body','核查事实和相关记录。\n制定方案并评估所需资源。'),
 59:('steps[3].body','说明原因和拟采取的措施。\n确认责任人及完成时间。'),
 58:('steps[4].body','按方案完成处理。\n检查效果并记录过程。'),
 36:('steps[5].body','与相关方确认处理结果。\n整理经验，跟踪是否复发。'),
 },locked=(13,14,15,16,17,18),role='process',note='蛇形路径上方从左至右为一至三步，下方从右至左为四至六步。'),
 258:record('四步往返工作路径','four-step-workflow-path','four-step-serpentine-arrows',4,{
 10:('page.title','工作流程｜四步推进路径'),
 50:('steps[0].heading','第一步：目标确认'),
 52:('steps[1].heading','第二步：方案设计'),
 51:('steps[2].heading','第三步：执行跟踪'),
 53:('steps[3].heading','第四步：验收复盘'),
 56:('steps[0].body','与相关方确认目标和范围。\n形成任务清单与交付标准。'),
 58:('steps[1].body','设计实施方案和时间安排。\n识别资源需求及主要风险。'),
 57:('steps[2].body','按计划推进并定期检查。\n及时处理偏差和跨组依赖。'),
 65:('steps[3].body','对照标准验收成果。\n复盘效果并形成改进事项。'),
 },locked=(46,47,48,49),role='process',note='四个固定 STEP 节点与两侧四个信息框对应。'),
 292:record('四季度营收成本分析','quarter-revenue-cost-analysis','quarter-bars-and-annual-summary',4,{
 3:('page.title','数据图｜年度营收成本分析'),
 7:('analysis.heading','2027年经营数据分析'),
 27:('chart.heading','2027年季度数据（单位：万元）'),
 38:('chart.legend_revenue','营收'),
 40:('chart.legend_cost','成本'),
 41:('metrics.revenue.label','年度营收总额'),
 42:('metrics.cost.label','年度成本总额'),
 25:('metrics.revenue.value','110万元'),
 17:('metrics.cost.value','30万元'),
 31:('metrics.growth.value','15万元'),
 33:('metrics.growth.label','营收较上年增加'),
 48:('analysis.summary','年度营收110万元，成本30万元。营收逐季提升，成本变化总体平稳。'),
 50:('analysis.outlook','后两季度交付规模扩大。后续需持续关注成本变化，并核对项目的实际收益。'),
 },role='data-chart',note='双系列原生柱状图对应四季度；营收、成本与同比增量须由数据校验。'),
}


def add_extra_rules_and_samples(root:Path,samples:Path):
    manifest_path=root/'knowledge-manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf8'))
    extras={
      202:{'consecutive_year_ranges':[f'stages[{i}].period' for i in range(5)]},
      214:{'consecutive_month_labels':[f'months[{i}].date' for i in range(6)]},
      292:{'annual_two_series_consistency':{
       'chart_shape_id':8,'revenue_field':'metrics.revenue.value',
       'cost_field':'metrics.cost.value','growth_field':'metrics.growth.value',
       'previous_year_key':'previous_year_revenue','unit':'万元'}},
    }
    for n,extra in extras.items():
        path=root/f'layouts/content-blue-{n:03d}/layout_rules.json'
        rules=json.loads(path.read_text(encoding='utf8'))
        rules.update(extra);dump(path,rules)
        manifest['files'][path.relative_to(root).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    dump(manifest_path,manifest)
    for theme in ('blue','red'):
        path=samples/f'content-blue-292-{theme}.json'
        data=json.loads(path.read_text(encoding='utf8'))
        data['previous_year_revenue']=95
        data['charts']=[{'shape_id':8,'categories':['Q1','Q2','Q3','Q4'],
                         'series':[{'name':'营收','values':[20,25,30,35]},
                                   {'name':'成本','values':[6,7,8,9]}],
                         'unit':'万元','period':'2027年','source':'演示用虚构数据'}]
        dump(path,data)


if __name__=='__main__':
    common.SETS=SETS
    common.main()
    args=sys.argv
    add_extra_rules_and_samples(Path(args[args.index('--library')+1]).resolve(),
                                Path(args[args.index('--samples')+1]).resolve())
