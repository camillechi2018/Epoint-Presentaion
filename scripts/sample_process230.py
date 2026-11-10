"""Write fictional five-stage process fill inputs."""
import json,sys
from pathlib import Path

out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
headings=['01\n确认需求','02\n设计方案','03\n实施开发','04\n检查验收','05\n交付复盘']
goals=['明确业务边界','形成可行方案','完成核心功能','核对质量要求','沉淀改进经验']
activities=['访谈相关人员，整理需求并确认优先级。','绘制流程与页面，评估资源及实施路径。','按计划开发功能，每周同步风险和进度。','执行功能检查，记录问题并完成修复。','交付文档和培训，复盘效果与待办。']
outputs=['需求清单与计划','方案与原型','可运行版本','验收记录','交付与复盘报告']
texts={'page.title':'项目推进｜五阶段工作流程'}
for i in range(5):
    for k,v in {'heading':headings[i],'goal_label':'目标','goal':goals[i],
                'activity_label':'活动','activity':activities[i],
                'output_label':'输出','output':outputs[i]}.items():texts[f'steps[{i}].{k}']=v
for theme in ('blue','red'):
    (out/f'content-blue-230-{theme}.json').write_text(json.dumps({'theme':theme,'item_count':5,'texts':texts},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
