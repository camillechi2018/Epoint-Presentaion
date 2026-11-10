"""Curate four representative blue/red daily-report layouts in an existing KB."""
import argparse
import json
from hashlib import sha256
from pathlib import Path


def spec(path, role, width, lines=1):
    return {"semantic_path": path, "semantic_role": role,
            "max_width_units": width, "max_lines": lines}


FIELDS = {
    60: {
        "text_30": spec("page.title", "page_title", 45),
        "text_29": spec("page.goal", "goal", 40),
        **{f"text_{9+i}": spec(f"steps[{i}].number", "step_number", 2) for i in range(4)},
        **{f"text_{21+i}": spec(f"steps[{i}].title", "step_title", 20) for i in range(4)},
        **{f"text_{25+i}": spec(f"steps[{i}].body", "step_body", 28, 2) for i in range(4)},
        **{f"text_{13+i}": spec(f"steps[{i}].outcome", "step_outcome", 18) for i in range(4)},
    },
    150: {
        "text_56": spec("page.title", "page_title", 48),
        "text_39": spec("page.summary", "page_summary", 80, 2),
        **{f"text_{n}": spec(f"items[{i}].title", "item_title", 16) for i,n in enumerate((96,112,116,120,124))},
        **{f"text_{n}": spec(f"items[{i}].detail_1", "item_detail", 22, 3) for i,n in enumerate((95,111,115,119,123))},
        **{f"text_{n}": spec(f"items[{i}].detail_2", "item_detail", 22, 3) for i,n in enumerate((107,113,117,121,125))},
        **{f"text_{n}": spec(f"items[{i}].footer", "item_footer", 20) for i,n in enumerate((127,129,130,131,132))},
    },
    270: {
        "text_2": spec("page.title", "page_title", 48),
        "text_10": spec("metrics[0].chart_title", "chart_title", 28),
        "text_126": spec("metrics[1].chart_title", "chart_title", 28),
        "text_21": spec("metrics[0].value", "metric_value", 12),
        "text_123": spec("metrics[1].value", "metric_value", 12),
        "text_22": spec("metrics[0].caption", "metric_caption", 28),
        "text_124": spec("metrics[1].caption", "metric_caption", 28),
        "text_118": spec("metrics[0].insight", "metric_insight", 58, 2),
        "text_128": spec("metrics[1].insight", "metric_insight", 58, 2),
    },
    279: {
        "text_2": spec("page.title", "page_title", 48),
        "text_7": spec("page.section_title", "section_title", 24),
        "text_47": spec("page.rate_title", "rate_title", 24),
        **{f"text_{n}": spec(f"quarter_rates[{i}]", "quarter_rate", 8) for i,n in enumerate((45,17,21,24))},
        "text_49": spec("notes[0].title", "note_title", 20),
        "text_50": spec("notes[1].title", "note_title", 20),
        "text_51": spec("notes[0].body", "note_body", 39, 2),
        "text_58": spec("notes[1].body", "note_body", 39, 2),
    },
}

INFO = {
    60: ("process", "ordered-steps", "four-step-arrow", [4], "medium"),
    150: ("parallel", "parallel-items", "five-parallel-cards", [5], "medium"),
    270: ("data-chart", "two-metric-period-trend", "two-trend-panels", [2], "medium"),
    279: ("data-table", "quarterly-detail", "quarterly-table-insights", [7], "high"),
}


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--pages", nargs="+", type=int, choices=sorted(FIELDS), required=True)
    parser.add_argument("--reviewed", action="store_true", help="mark only after rendered QA has passed")
    args = parser.parse_args()
    root = args.library.resolve()
    catalog_path = root / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    touched = {"catalog.json"}
    for page in args.pages:
        name = f"content-blue-{page:03d}"
        directory = root / "layouts" / name
        mapping = FIELDS[page]
        for filename in ("bindings.json", "bindings-red.json"):
            path = directory / filename
            data = json.loads(path.read_text(encoding="utf-8"))
            fields = {field["field"] for field in data["fields"]}
            if fields != set(mapping):
                raise ValueError(f"{name}/{filename} has unexpected fields: {fields ^ set(mapping)}")
            for field in data["fields"]:
                field.update(mapping[field["field"]])
                role = field["semantic_role"]
                if role in ("item_detail", "step_body", "metric_insight", "note_body"):
                    field["max_chars"] = min(field["max_chars"], 85)
                elif role in ("item_title", "step_title", "note_title"):
                    field["max_chars"] = min(field["max_chars"], 24)
                elif role in ("quarter_rate", "step_number"):
                    field["max_chars"] = 5
            dump(path, data)
            touched.add(str(path.relative_to(root)).replace("\\", "/"))
        role, relation, family, counts, density = INFO[page]
        entry = next(e for e in catalog["layouts"] if e["id"] == name)
        entry.update(role=role, information_relation=relation, family_id=family,
                     classification_status="verified" if args.reviewed else "visual_reviewed",
                     semantic_review_status="verified_blue_red" if args.reviewed else "fields_mapped_pending_render",
                     composition_tags=[relation, family], density=density,
                     media_status="verified_brand_logo_only" if args.reviewed else "unreviewed")
        if args.reviewed:
            entry["pptx_support"] = "verified_static"
        rules_path = directory / "layout_rules.json"
        rules = json.loads(rules_path.read_text(encoding="utf-8"))
        if page == 60:
            rules["verified_counts"] = [4] if args.reviewed else []
            rules["render_overrides"] = {
                "red": {"shape_height_pt_by_shape_id": {str(i): 52 for i in (25,26,27,28)}}
            }
        else:
            rules.update(cardinality_mode="fixed", supported_counts=counts,
                         source_count=counts[0], reflow_status="not_implemented",
                         validation_status="verified_fixed_count" if args.reviewed else "pending_render")
            if page == 279:
                rules["render_overrides"] = {
                    "red": {"text_color_by_shape_id": {"51":"000000","58":"000000"},
                            "table_body_text_color_rgb":"000000"}
                }
                rules["rate_bars"] = [
                    {"value_field":f"quarter_rates[{i}]", "track_shape_id":track,
                     "bar_shape_id":bar}
                    for i,(track,bar) in enumerate(((44,46),(16,18),(20,22),(23,25)))
                ]
            if page == 270:
                rules["paired_chart_consistency"] = {
                    "chart_shape_ids":[117,127],
                    "metrics":[
                        {"chart_shape_id":117,"value_field":"metrics[0].value","display_unit":"万"},
                        {"chart_shape_id":127,"value_field":"metrics[1].value","display_unit":"万"},
                    ]
                }
        dump(rules_path, rules)
        touched.add(str(rules_path.relative_to(root)).replace("\\", "/"))
        spec_path = directory / "spec.md"
        descriptions = {
            60: "四步顺序流程；编号、标题、正文、阶段结果逐步绑定。正文每项最多两行。原有 2／3 步重排仍是内部原型；正式静态版仅开放四步。红稿短正文框自动收紧高度以保证 PowerPoint 正确渲染。",
            150: "五项同层级并列要点；每项含标题、两条说明及底部标签。没有因果或时间顺序。数量变化尚未验收。",
            270: "左右双指标趋势；两张原生图表必须各填真实分类和系列数据、单位、周期及来源。两图分类和周期一致，数值须等于各自系列合计；洞察由同一数据得出，不复用源稿示例。",
            279: "七行季度明细及两块解读；8×6 原生表格含一行表头。四个季度达标率由项目数据提供，填充时同步修改对应进度条长度，不能沿用源稿。",
        }
        spec_path.write_text(f"# {name}\n\n来源：蓝 P{page:03d}／红 P{entry['red_source_page']:03d}。{descriptions[page]}\n\n"
                             "字段语义见 `bindings.json`；蓝红版均保持原生可编辑对象。Logo 保留原锚点。"
                             "资产仍为 `draft_pending_review`；动效、HTML 和其他色系按独立能力状态验收。\n", encoding="utf-8")
        touched.add(str(spec_path.relative_to(root)).replace("\\", "/"))
        if args.reviewed:
            review_path = root / "review" / f"{name}.json"
            dump(review_path, {"date":"2026-11-04", "layout_id":name,
                               "source_pages":{"blue":page,"red":entry["red_source_page"]},
                               "status":"verified_static_pptx_draft_pending_review",
                               "supported_counts":counts, "role":role, "information_relation":relation,
                               "preview_paths":[f"review/{name}-blue-filled.png",f"review/{name}-red-filled.png"],
                               "limits":["HTML not implemented", "motion requires separate review",
                                         "other theme colors not verified", "asset draft pending review"]})
            touched.add(str(review_path.relative_to(root)).replace("\\", "/"))
            touched.update({f"review/{name}-{theme}-filled.png" for theme in ("blue", "red")})
    dump(catalog_path, catalog)
    manifest_path = root / "knowledge-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for rel in touched:
        manifest["files"][rel] = sha256((root / rel).read_bytes()).hexdigest()
    dump(manifest_path, manifest)


if __name__ == "__main__":
    main()
