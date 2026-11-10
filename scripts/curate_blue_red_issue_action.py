"""Curate the paired P133 problem/action layout without rebuilding the library."""
import argparse
import json
from hashlib import sha256
from pathlib import Path


PATHS = {
    "text_5": ("page.title", "page_title", 32, 1),
    "text_32": ("axis.top", "axis_label", 12, 1),
    "text_33": ("axis.bottom", "axis_label", 12, 1),
    "text_4": ("column.problem", "column_label", 8, 1),
    "text_42": ("column.action", "column_label", 8, 1),
    "text_26": ("pairs[0].problem_title", "problem_title", 24, 1),
    "text_29": ("pairs[1].problem_title", "problem_title", 24, 1),
    "text_35": ("pairs[2].problem_title", "problem_title", 24, 1),
    "text_38": ("pairs[0].action_title", "action_title", 24, 1),
    "text_39": ("pairs[1].action_title", "action_title", 24, 1),
    "text_40": ("pairs[2].action_title", "action_title", 24, 1),
    "text_43": ("pairs[0].problem_body", "problem_body", 60, 2),
    "text_44": ("pairs[1].problem_body", "problem_body", 60, 2),
    "text_45": ("pairs[2].problem_body", "problem_body", 60, 2),
    "text_46": ("pairs[0].action_body", "action_body", 60, 2),
    "text_47": ("pairs[1].action_body", "action_body", 60, 2),
    "text_48": ("pairs[2].action_body", "action_body", 60, 2),
}


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", type=Path, required=True)
    args = parser.parse_args()
    root = args.library.resolve()
    directory = root / "layouts/content-blue-133"
    for name in ("bindings.json", "bindings-red.json"):
        path = directory / name
        data = json.loads(path.read_text(encoding="utf-8"))
        fields = {f["field"] for f in data["fields"]}
        if fields != set(PATHS):
            raise ValueError(f"Unexpected field mapping in {name}: {fields ^ set(PATHS)}")
        for field in data["fields"]:
            semantic_path, role, width, lines = PATHS[field["field"]]
            field.update(semantic_path=semantic_path, semantic_role=role,
                         max_width_units=width, max_lines=lines)
            if role in ("problem_body", "action_body"):
                field["max_chars"] = 60
            elif role in ("problem_title", "action_title"):
                field["max_chars"] = 24
        dump(path, data)
    dump(directory / "layout_rules.json", {
        "cardinality_mode": "fixed", "supported_counts": [3], "source_count": 3,
        "reflow_status": "not_implemented", "validation_status": "verified_fixed_count",
        "count_evidence": "three aligned problem/action rows; adding/removing a row requires redesign",
    })
    (directory / "spec.md").write_text(
        "# content-blue-133\n\n来源：蓝／红 P133。三行问题与三行措施逐行对应；中间箭头和双向轴是说明结构。\n\n"
        "用途：固定三组问题—改进措施。输入为 `page.title`、`axis.top/bottom`、"
        "`column.problem/action` 和 `pairs[0..2].problem_title/problem_body/action_title/action_body`。"
        "三组内容按从上到下匹配，不能交换措施。正文每格最多两行，每行最多 60 个视觉宽度单位。"
        "项数变化和换色到蓝红以外主题未验收。\n\n"
        "动效建议：三行按问题、箭头、措施的讲述顺序逐组揭示；目前仍为静态页，未开放动效。"
        "来源 Logo 保留，资产仍待品牌评审。\n", encoding="utf-8")
    catalog_path = root / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    entry = next(e for e in catalog["layouts"] if e["id"] == "content-blue-133")
    entry.update(role="comparison", information_relation="problem-solution", family_id="three-problem-action-rows",
                 classification_status="verified", semantic_review_status="verified_blue_red",
                 composition_tags=["problem-solution", "three-pairs", "aligned-rows"], density="high",
                 media_status="verified_brand_logo_only", pptx_support="verified_static")
    dump(catalog_path, catalog)
    review_path = root / "review/content-blue-133.json"
    dump(review_path, {
        "date": "2026-11-04", "layout_id": "content-blue-133",
        "source_pages": {"blue": 133, "red": 133},
        "status": "verified_static_pptx_draft_pending_review",
        "semantics": "three vertically aligned problem/action pairs; top/bottom axes and center icon are static structure",
        "supported_counts": [3], "editable_shapes": {"blue": 43, "red": 43},
        "preview_paths": ["review/content-blue-133-blue-filled.png", "review/content-blue-133-red-filled.png"],
        "logo_audit": {"blue": 1, "red": 1, "passed": True},
        "media_audit": {"missing_primary": 0, "broken_primary": 0, "passed": True},
        "limits": ["animation not implemented", "HTML not implemented", "other theme colors not verified", "asset draft pending review"],
    })
    manifest_path = root / "knowledge-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for rel in ("catalog.json", "layouts/content-blue-133/bindings.json",
                "layouts/content-blue-133/bindings-red.json",
                "layouts/content-blue-133/layout_rules.json", "layouts/content-blue-133/spec.md",
                "review/content-blue-133.json", "review/content-blue-133-blue-filled.png",
                "review/content-blue-133-red-filled.png"):
        manifest["files"][rel] = sha256((root / rel).read_bytes()).hexdigest()
    dump(manifest_path, manifest)


if __name__ == "__main__":
    main()
