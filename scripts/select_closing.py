"""Select an explicitly requested closing page without treating it as a cover."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from library_location import get_library

IMPACT = {"high": 3, "medium-high": 2, "medium": 1}


def select(root: Path, request: dict):
    catalog = json.loads((root / "catalog.json").read_text(encoding="utf-8"))
    family = request.get("style_family")
    if not family: family = "legacy-blue-red"
    theme = request.get("theme", "blue")
    excludes = set(request.get("exclude_ids", []))
    ranked, decisions = [], []
    for entry in catalog["layouts"]:
        if entry.get("role") != "closing": continue
        reasons = []
        if entry.get("style_family", "legacy-blue-red") != family: reasons.append("style_family_mismatch")
        if theme not in entry.get("themes", []): reasons.append("theme_mismatch")
        if entry["id"] in excludes: reasons.append("excluded")
        if entry.get("classification_status") != "verified" and not request.get("allow_draft"):
            reasons.append("not_verified")
        if reasons: decisions.append({"id": entry["id"], "excluded_reasons": reasons}); continue
        score = IMPACT.get(entry.get("visual_impact"), 0) * 10
        if request.get("style") == entry.get("style"): score += 8
        if request.get("subject_tag") in entry.get("subject_tags", []): score += 4
        ranked.append((score, entry["id"], entry))
        decisions.append({"id": entry["id"], "score": score})
    ranked.sort(key=lambda x: (-x[0], x[1]))
    best = ranked[0][2] if ranked else None
    return {"status": "candidate_requires_visual_review" if best else "no_verified_match",
            "selected_id": best["id"] if best else None,
            "source_page": best["source_page"] if best else None,
            "style_family": family, "theme": theme, "decision_log": decisions,
            "warning": "封底背景、Logo 锚点和真实落款仍需逐页视觉复核" if best else
                       "没有符合此风格与主题的已验收封底"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--library", type=Path)
    p.add_argument("--request", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    root = args.library or get_library()
    report = select(root, json.loads(args.request.read_text(encoding="utf-8-sig")))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"selected_id": report["selected_id"], "status": report["status"]}, ensure_ascii=False))


if __name__ == "__main__": main()
