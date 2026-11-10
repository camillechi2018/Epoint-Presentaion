"""Keep the Skill's offline RGB roles tied to the existing source templates."""
import argparse
import json
import re
from pathlib import Path
from zipfile import ZipFile

from lxml import etree

SKILL = Path(__file__).resolve().parents[1]
PROFILE = SKILL / "assets/brand/brand-baseline.json"
LOCK = SKILL / "assets/brand/brand-palette-lock.json"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
HEX = re.compile(r"[0-9A-F]{6}")


def locked_colors(theme):
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    if lock.get("status") != "template_derived_locked":
        raise ValueError("品牌配色锁状态无效")
    if set(profile["themes"]) != set(lock["themes"]):
        raise ValueError("品牌主题与配色锁不一致")
    if theme not in profile["themes"]:
        raise ValueError("未登记的品牌主题：" + theme)
    selected = profile["themes"][theme]
    registered = lock["themes"][theme]
    roles = {key: value for key, value in selected.items()
             if key not in ("source", "logo_appearance", "neutral")}
    if selected["source"] != Path(registered["theme_json"]).name:
        raise ValueError("品牌主题未绑定登记的来源主题文件：" + theme)
    if roles != registered["roles"] or selected["neutral"] != registered["neutral"]:
        raise ValueError("品牌配色与模板配色锁不一致：" + theme)
    values = list(roles.values()) + list(selected["neutral"].values())
    if any(not isinstance(value, str) or not HEX.fullmatch(value) for value in values):
        raise ValueError("品牌配色包含非法 RGB：" + theme)
    return set(values)


def source_xml_colors(path):
    colors = set()
    with ZipFile(path) as package:
        for name in package.namelist():
            if not name.startswith("ppt/") or not name.endswith(".xml"):
                continue
            root = etree.fromstring(package.read(name))
            for element in root.iter():
                if element.tag == f"{{{A}}}srgbClr":
                    value = element.get("val")
                elif element.tag == f"{{{A}}}sysClr":
                    value = element.get("lastClr") or element.get("val")
                else:
                    continue
                if value and HEX.fullmatch(value.upper()):
                    colors.add(value.upper())
    return colors


def audit(library):
    from PIL import Image

    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    rows = []
    for theme, registered in lock["themes"].items():
        values = locked_colors(theme)
        source_colors = set()
        preview_colors = set()
        for relative in registered["source_pptx"]:
            source_colors.update(source_xml_colors(library / relative))
        for relative in registered.get("source_preview", []):
            with Image.open(library / relative) as image:
                preview_colors.update("%02X%02X%02X" % pixel[:3]
                                      for pixel in image.convert("RGB").get_flattened_data())
        unsupported = sorted(values - source_colors - preview_colors)
        theme_json = json.loads((library / registered["theme_json"]).read_text(encoding="utf-8"))
        neutral_matches = theme_json["neutral_tokens"] == profile["themes"][theme]["neutral"]
        roles_match = (theme_json.get("free_composition_status") == "source_derived_draft"
                       and theme_json.get("free_composition_roles") == registered["roles"])
        semantic = theme_json["semantic_roles"]
        role_names = ("primary", "secondary") if theme != "deep-blue-tech" else ("primary", "secondary", "tertiary")
        slot_names = ("primary", "secondary") if theme != "deep-blue-tech" else ("brand_primary", "tech_cyan", "tech_teal")
        slot_mismatches = {role: theme_json["color_slots"][semantic[slot]]
                           for role, slot in zip(role_names, slot_names)
                           if profile["themes"][theme][role] != theme_json["color_slots"][semantic[slot]]}
        rows.append({"theme": theme, "colors": len(values), "unsupported": unsupported,
                     "neutral_matches_knowledge_base": neutral_matches,
                     "free_composition_roles_match": roles_match,
                     "semantic_slot_mismatches": slot_mismatches,
                     "source_xml_colors": len(values & source_colors),
                     "source_preview_only_colors": len((values - source_colors) & preview_colors),
                     "passed": not unsupported and neutral_matches and roles_match and not slot_mismatches})
    return {"passed": all(row["passed"] for row in rows), "themes": rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.library.resolve())
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["passed"] else 2)


if __name__ == "__main__":
    main()
