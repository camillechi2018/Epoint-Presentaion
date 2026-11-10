"""Produce fictitious, reproducible QA inputs for the representative set."""
import argparse
import json
from pathlib import Path


def make(page, theme):
    if page == 60:
        data = {"page.title": "项目推进｜四步执行路径", "page.goal": "年度重点任务按四阶段推进"}
        steps = [
            ("目标确认", "明确交付范围。\n确定责任与验收标准。", "目标口径统一"),
            ("任务分解", "拆分关键节点。\n形成任务和时间清单。", "计划可执行"),
            ("过程跟踪", "每周核对进度。\n及时处理偏差与阻塞。", "问题及时闭环"),
            ("结果复盘", "核验实际成果。\n记录经验与改进项。", "经验持续沉淀"),
        ]
        for i,(title,body,outcome) in enumerate(steps):
            data.update({f"steps[{i}].number":f"{i+1:02d}",f"steps[{i}].title":title,
                         f"steps[{i}].body":body,f"steps[{i}].outcome":outcome})
        return {"theme":theme,"texts":data}
    if page == 150:
        data = {"page.title":"能力建设｜五项并列举措",
                "page.summary":"围绕目标、协同、质量、数据和复盘五个方向，建立可执行的改进动作。"}
        items = [
            ("目标管理","明确年度目标。\n拆解到责任团队。","每月复核进度。\n及时调整重点。"),
            ("团队协同","建立周度例会。\n同步事项与阻塞。","明确接口责任。\n形成共享记录。"),
            ("质量控制","设定检查清单。\n关键节点先自检。","开展交叉复核。\n记录典型问题。"),
            ("数据分析","统一指标口径。\n定期核对数据。","识别异常变化。\n形成分析结论。"),
            ("经验复盘","完成阶段总结。\n沉淀有效做法。","跟踪改进事项。\n验证实施效果。"),
        ]
        for i,(title,a,b) in enumerate(items):
            data.update({f"items[{i}].title":title,f"items[{i}].detail_1":a,
                         f"items[{i}].detail_2":b,f"items[{i}].footer":f"举措{i+1:02d}"})
        return {"theme":theme,"texts":data}
    if page == 270:
        revenue = [310,320,290,360,400,350,370]
        cost = [120,130,140,150,160,155,165]
        data = {"page.title":"经营数据｜1—7月趋势对照",
                "metrics[0].chart_title":"1—7月营收趋势", "metrics[1].chart_title":"1—7月成本趋势",
                "metrics[0].value":f"{sum(revenue)}万", "metrics[1].value":f"{sum(cost)}万",
                "metrics[0].caption":"累计营收（示例）", "metrics[1].caption":"累计成本（示例）",
                "metrics[0].insight":"5月营收为阶段高点。\n4月以后整体维持较高水平。",
                "metrics[1].insight":"成本随业务量温和上升。\n7月处于本期较高水平。"}
        cats=[f"{i}月" for i in range(1,8)]
        charts=[{"shape_id":id,"categories":cats,"series":[{"name":name,"values":values}],
                 "unit":"万元","period":"2026年1—7月（虚构示例）","source":"内部演示虚构数据"}
                for id,name,values in ((117,"营收",revenue),(127,"成本",cost))]
        return {"theme":theme,"texts":data,"charts":charts}
    if page == 279:
        numbers = [[53,62,68,76],[46,55,52,63],[60,58,68,72],
                   [50,54,56,65],[45,49,55,59],[66,72,70,78],[58,63,69,74]]
        rows=[["业务组","Q1","Q2","Q3","Q4","合计"]]
        for i,quarters in enumerate(numbers,1):
            rows.append([f"业务组{i:02d}"]+[f"{v}万" for v in quarters]+[f"{sum(quarters)}万"])
        data = {"page.title":"季度经营｜业务组业绩明细", "page.section_title":"季度业绩明细",
                "page.rate_title":"各季度目标达成率", "quarter_rates[0]":"65%",
                "quarter_rates[1]":"72%", "quarter_rates[2]":"80%", "quarter_rates[3]":"90%",
                "notes[0].title":"业务组表现", "notes[1].title":"季度变化",
                "notes[0].body":"业务组06全年合计较高。\n业务组05仍有提升空间。",
                "notes[1].body":"四季度总量高于一季度。\n达标率逐季稳步提升。"}
        return {"theme":theme,"texts":data,"tables":[{"shape_id":8,"rows":rows}]}
    raise ValueError(page)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    for page in (60,150,270,279):
        for theme in ("blue","red"):
            path=args.out/f"content-blue-{page:03d}-{theme}-semantic.json"
            path.write_text(json.dumps(make(page,theme),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


if __name__=="__main__":
    main()
