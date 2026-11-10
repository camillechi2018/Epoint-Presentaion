"""Integration gates for the constrained free-composition body tier."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from pptx import Presentation
from free_composition import validate_free_layout
from plan_deck import resolve
from render_offline_brand import render, read_json, PROFILE


def page():
    return {
        "title": "行动路径与共同决策",
        "type": "free_composition",
        "layout_assessment": {"skill_suitable": False, "reason": "三项并列行动汇入一项跨栏决策，既有结构无法表达汇合关系"},
        "free_layout": {
            "rationale": "三列行动置上，底部跨栏结论汇合",
            "elements": [
                {"kind": "rect", "x": 0.8, "y": 1.7, "w": 3.65, "h": 2.65, "color_role": "surface", "border_role": "border"},
                {"kind": "rect", "x": 4.85, "y": 1.7, "w": 3.65, "h": 2.65, "color_role": "surface", "border_role": "border"},
                {"kind": "rect", "x": 8.9, "y": 1.7, "w": 3.65, "h": 2.65, "color_role": "surface", "border_role": "border"},
                {"kind": "text", "x": 1.1, "y": 2.0, "w": 3.0, "h": 0.65, "text": "确认需求", "size_pt": 25, "color_role": "primary", "font_role": "heading", "bold": True},
                {"kind": "text", "x": 5.15, "y": 2.0, "w": 3.0, "h": 0.65, "text": "形成方案", "size_pt": 25, "color_role": "primary", "font_role": "heading", "bold": True},
                {"kind": "text", "x": 9.2, "y": 2.0, "w": 3.0, "h": 0.65, "text": "检查验收", "size_pt": 25, "color_role": "primary", "font_role": "heading", "bold": True},
                {"kind": "text", "x": 1.1, "y": 2.95, "w": 3.0, "h": 0.8, "text": "明确工作边界", "size_pt": 18, "color_role": "text"},
                {"kind": "text", "x": 5.15, "y": 2.95, "w": 3.0, "h": 0.8, "text": "落实责任与进度", "size_pt": 18, "color_role": "text"},
                {"kind": "text", "x": 9.2, "y": 2.95, "w": 3.0, "h": 0.8, "text": "核对交付口径", "size_pt": 18, "color_role": "text"},
                {"kind": "line", "x": 0.8, "y": 5.05, "w": 11.75, "h": 0.04, "color_role": "primary"},
                {"kind": "text", "x": 1.1, "y": 5.48, "w": 10.8, "h": 0.75, "text": "共同决策：按统一口径推进下一阶段", "size_pt": 26, "color_role": "text", "font_role": "heading", "bold": True},
            ],
        },
    }


class FreeCompositionTests(unittest.TestCase):
    def test_three_style_samples_and_editability(self):
        with tempfile.TemporaryDirectory() as folder:
            for theme in ("blue", "red", "deep-blue-tech"):
                with self.subTest(theme=theme):
                    target = Path(folder) / f"{theme}.pptx"
                    result = render({"theme": theme, "complete_deck": False, "pages": [page()]}, target)
                    self.assertFalse(result["library_used"])
                    self.assertEqual(result["slides"][0]["type"], "free_composition")
                    slide = Presentation(target).slides[0]
                    self.assertEqual(len([s for s in slide.shapes if s.name.startswith("brand:logo:")]), 1)
                    self.assertGreaterEqual(len([s for s in slide.shapes if s.has_text_frame and s.text.strip()]), 5)

    def test_rejects_unregistered_color_and_overlapping_text(self):
        profile = read_json(PROFILE)
        for theme in ("blue", "red", "deep-blue-tech"):
            proposal = page()
            proposal["free_layout"]["elements"][3]["color_role"] = "made_up_color"
            with self.assertRaisesRegex(ValueError, "未登记"):
                validate_free_layout(proposal, profile["themes"][theme], profile["typography"])
            proposal = page()
            proposal["free_layout"]["elements"][4]["x"] = 1.1
            with self.assertRaisesRegex(ValueError, "重叠"):
                validate_free_layout(proposal, profile["themes"][theme], profile["typography"])

    def test_plan_reports_free_source(self):
        library = ROOT / "assets" / "minimal-template-pack"
        content = page()
        request = {"theme": "blue", "style_family": "legacy-blue-red", "allow_draft": True,
                   "pages": [{"role": "body", "purpose": "复杂汇合关系",
                              "content": content}]}
        plan = resolve(library, request)
        self.assertEqual(plan["pages"][0]["selection_mode"], "free_composition")
        self.assertEqual(plan["selection_summary"], {"知识库模板": 0, "技能排版": 0, "自由编排": 1})


if __name__ == "__main__":
    unittest.main()
