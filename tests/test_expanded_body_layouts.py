"""Short/long content gates for three new structures and three body variants."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw
from pptx import Presentation

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from render_offline_brand import render, validate_page


def make_image(path: Path):
    image = Image.new("RGB", (1200, 700), "#f6f9ff")
    d = ImageDraw.Draw(image)
    d.rectangle((45, 45, 1155, 655), outline="#0154dd", width=5)
    d.rectangle((45, 45, 1155, 125), fill="#0154dd")
    d.rectangle((90, 190, 540, 490), fill="white", outline="#a9c6ef", width=3)
    d.rectangle((630, 190, 1100, 490), fill="white", outline="#a9c6ef", width=3)
    d.line((90, 550, 1090, 550), fill="#0154dd", width=5)
    image.save(path)


def pages(image_path: Path, long=False):
    extra = "，同步记录后续进展" if long else ""
    return [
        {"type": "target_actual_gap", "title": "目标与实际：阶段完成情况", "target": 120,
         "actual": 98, "unit": "项", "period": "本阶段",
         "gap_reason": "实际完成数量低于阶段目标，需逐项确认未完成任务的责任人与预计时间" + extra,
         "data_source": "虚构示意数据，仅用于排版检查"},
        {"type": "decision_matrix", "title": "三种实施方案的多标准评估",
         "criteria": ["实施周期", "维护成本", "跨团队协作", "后续扩展"],
         "options": [{"name": "方案甲", "scores": [4, 3, 5, 3]},
                     {"name": "方案乙", "scores": [3, 5, 3, 4]},
                     {"name": "方案丙", "scores": [5, 2, 4, 3]}],
         "recommended_index": 0,
         "decision_reason": "优先满足跨团队协作与实施周期要求" + ("，并保留下一阶段调整空间" if long else ""),
         "data_source": "虚构评分，仅用于示意；各项满分五分"},
        {"type": "responsibility_swimlane", "title": "跨部门协作与交接职责",
         "phases": ["需求确认", "方案设计", "实施交付", "检查复盘"] if not long else
                   ["需求确认", "方案设计", "实施准备", "实施交付", "检查复盘"],
         "lanes": [
             {"role": "业务部门", "tasks": ["确认目标与边界" + ("及优先级" if long else ""), "复核业务口径", "", "参加验收"] if not long else
              ["确认目标与边界", "复核业务口径", "", "参与业务验收", "确认改进事项"]},
             {"role": "项目团队", "tasks": ["汇总需求", "形成实施方案", "推进任务", "整理复盘记录"] if not long else
              ["汇总需求", "形成实施方案", "配置资源与计划", "按阶段推进任务", "整理复盘记录"]},
             {"role": "管理人员", "tasks": ["", "审定资源", "关注阶段风险", "确认后续安排"] if not long else
              ["", "审定资源与期限", "核对责任分工", "关注阶段风险", "确认后续安排"]},
         ]},
        {"type": "data_table", "variant": "action_tracker", "title": "风险与改进行动跟踪",
         "actions": [
             {"issue": "任务边界未统一", "action": "组织各方确认范围并形成记录" + ("与清单" if long else ""),
              "owner": "业务负责人", "due": "本周五", "status": "进行中"},
             {"issue": "交付材料分散", "action": "汇总文件并指定唯一维护入口" + ("与责任人" if long else ""),
              "owner": "项目经理", "due": "下周二", "status": "待启动"},
             {"issue": "验收口径待核对", "action": "逐项检查标准与责任人" + ("并留痕" if long else ""),
              "owner": "质量负责人", "due": "下周五", "status": "进行中"},
         ], "data_source": "虚构示意任务"},
        {"type": "comparison", "variant": "before_after", "title": "改进前后：任务管理方式",
         "left": {"title": "调整前", "body": "任务分散在多处记录中，交接时需要反复核对责任归属。" + extra},
         "right": {"title": "调整后", "body": "使用统一清单记录负责人、时间、状态与待办事项。" + extra},
         "change_summary": "通过统一入口和定期复核，让任务进展与问题处理可追踪" + extra},
        {"type": "image_case", "variant": "annotated", "title": "页面截图与局部说明",
         "image_path": str(image_path), "case_title": "三处界面信息的核对",
         "annotations": [
             {"x": 0.25, "y": 0.33, "label": "左侧为任务信息区域" + ("，用于核对工作范围" if long else "")},
             {"x": 0.74, "y": 0.35, "label": "右侧为责任与进度区域" + ("，用于确认交接状态" if long else "")},
             {"x": 0.54, "y": 0.82, "label": "底部为统一操作入口" + ("，用于查找后续动作" if long else "")},
         ],
         "takeaway": "图中三个位置分别对应任务、责任与后续动作" + ("，便于讨论时逐项确认" if long else ""),
         "image_caption": "虚构界面示意图"},
    ]


class ExpandedBodyTests(unittest.TestCase):
    def test_all_styles_short_and_long(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image = root / "fixture.png"
            make_image(image)
            for long in (False, True):
                for theme in ("blue", "red", "deep-blue-tech"):
                    with self.subTest(theme=theme, long=long):
                        target = root / f"{theme}-{'long' if long else 'short'}.pptx"
                        result = render({"theme": theme, "complete_deck": False,
                                         "pages": pages(image, long)}, target)
                        self.assertEqual(result["slide_count"], 6)
                        self.assertEqual(len(Presentation(target).slides), 6)

    def test_rejects_unfounded_or_invalid_data(self):
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / "fixture.png"
            make_image(image)
            samples = pages(image)
            samples[0]["actual"] = "98"
            with self.assertRaisesRegex(ValueError, "非负数值"):
                validate_page(samples[0], 1)
            samples = pages(image)
            samples[1]["options"][0]["scores"] = [5, 3]
            with self.assertRaisesRegex(ValueError, "同一标准"):
                validate_page(samples[1], 2)
            samples = pages(image)
            samples[2]["lanes"][0]["tasks"] = ["", "", "", ""]
            with self.assertRaisesRegex(ValueError, "真实任务"):
                validate_page(samples[2], 3)
            samples = pages(image)
            samples[5]["annotations"][0]["x"] = 1.2
            with self.assertRaisesRegex(ValueError, "真实位置"):
                validate_page(samples[5], 6)

    def test_variable_count_boundaries(self):
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / "fixture.png"
            make_image(image)
            samples = pages(image)
            samples[1]["options"].append({"name": "方案丁", "scores": [2, 4, 3, 5]})
            validate_page(samples[1], 1)
            samples[1]["options"].append({"name": "方案戊", "scores": [2, 4, 3, 5]})
            with self.assertRaisesRegex(ValueError, "2–4 个备选方案"):
                validate_page(samples[1], 1)
            samples = pages(image)
            samples[2]["lanes"].append({"role": "外部协作方", "tasks": ["", "复核接口", "提交资料", ""]})
            validate_page(samples[2], 2)
            samples[2]["lanes"].append({"role": "第五角色", "tasks": ["", "", "提交资料", ""]})
            with self.assertRaisesRegex(ValueError, "2–4 个角色"):
                validate_page(samples[2], 2)


if __name__ == "__main__":
    unittest.main()
