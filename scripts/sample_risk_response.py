"""Create fictional QA inputs for risk/response P050."""
import json
from pathlib import Path
import sys

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
texts = {
 'page.title':'风险复盘｜四项问题与改进措施',
 'page.risk_heading':'风险\n管理', 'page.response_heading':'应对\n策略',
 'risks[0].title':'01.需求变化频繁','risks[0].detail':'需求确认较晚，导致交付范围多次调整。',
 'risks[1].title':'02.资源协调缓慢','risks[1].detail':'跨团队排期冲突，关键任务等待时间较长。',
 'risks[2].title':'03.质量反馈滞后','risks[2].detail':'缺陷集中到验收阶段，返工压力增加。',
 'risks[3].title':'04.责任边界不清','risks[3].detail':'交接标准不一致，事项跟进出现遗漏。',
 'responses[0].title':'01.锁定需求范围','responses[0].detail':'建立需求确认清单，变更统一评估。',
 'responses[1].title':'02.提前协调资源','responses[1].detail':'按月排定关键人员和协作窗口。',
 'responses[1].detail_2':'对冲突任务明确优先级和负责人。',
 'responses[2].title':'03.前移质量检查','responses[2].detail':'每周检查交付物，及时关闭缺陷。',
 'responses[3].title':'04.明确交接责任','responses[3].detail':'按事项设置责任人和完成标准。',
 'responses[3].detail_2':'交接时逐项核对并保留记录。',
 'principles[0]':'需求变化及时评估',
 'principles[1]':'协作事项有人负责',
 'principles[2]':'质量问题尽早关闭',
}
for theme in ('blue','red'):
 (out / f'content-blue-050-{theme}.json').write_text(json.dumps({'theme':theme,'texts':texts},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
