"""Lightweight content-shape routing for editable body fallback layouts."""
from __future__ import annotations

import json
from pathlib import Path


RULES = Path(__file__).resolve().parents[1] / "assets" / "layouts" / "fallback-layouts.json"


def fallback_type(page: dict) -> str:
    if page.get("type"):
        return page["type"]
    if all(key in page for key in ("target", "actual", "gap_reason")):
        return "target_actual_gap"
    if isinstance(page.get("criteria"), list) and isinstance(page.get("options"), list):
        return "decision_matrix"
    if isinstance(page.get("phases"), list) and isinstance(page.get("lanes"), list):
        return "responsibility_swimlane"
    if isinstance(page.get("actions"), list):
        return "data_table"
    if isinstance(page.get("categories"), list) and isinstance(page.get("series"), list):
        return "comparison_chart"
    if isinstance(page.get("series"), list):
        return "assertion_evidence"
    if isinstance(page.get("lead"), dict) and isinstance(page.get("support"), list):
        return "priority_grid"
    if isinstance(page.get("sections"), list):
        return "evidence_matrix"
    if all(isinstance(page.get(key), dict) for key in ("problem", "solution", "outcome")):
        return "problem_solution_outcome"
    if isinstance(page.get("layers"), list):
        return "layered_architecture"
    if isinstance(page.get("paragraphs"), list) and isinstance(page.get("metric"), dict):
        return "longform_metric"
    if isinstance(page.get("columns"), list) and isinstance(page.get("rows"), list):
        return "data_table"
    if isinstance(page.get("milestones"), list):
        return "milestone_timeline"
    if page.get("image_path") and page.get("case_title"):
        return "image_case"
    return "bullets"


def fallback_catalog() -> dict:
    data = json.loads(RULES.read_text(encoding="utf-8-sig"))
    return {row["id"]: row for row in data["layouts"]}
