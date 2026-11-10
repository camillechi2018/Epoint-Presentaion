"""Build the three 16-slide README galleries from verified knowledge-base previews."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


BLUE_RED_IDS = [
    "content-blue-015", "content-blue-036", "content-blue-050", "content-blue-060",
    "content-blue-070", "content-blue-081", "content-blue-106", "content-blue-112",
    "content-blue-133", "content-blue-150", "content-blue-199", "content-blue-230",
    "content-blue-247", "content-blue-260", "content-blue-268", "content-blue-279",
]
TECH_IDS = [
    "content-tech-016", "content-tech-017", "content-tech-020", "content-tech-021",
    "content-tech-026", "content-tech-028", "content-tech-030", "content-tech-032",
    "content-tech-042", "content-tech-046", "content-tech-053", "content-tech-054",
    "content-tech-063", "schedule-tech-069", "data-chart-tech-071", "data-chart-tech-075",
]


def preview_path(root: Path, row: dict, theme: str) -> Path:
    relative = row["preview"]
    if theme == "red":
        relative = relative.replace("ready-blue.png", "ready-red.png")
        relative = relative.replace("source-previews/blue/", "source-previews/red/")
    result = (root / relative).resolve()
    if not result.is_relative_to(root) or not result.is_file():
        raise FileNotFoundError(result)
    return result


def build(root: Path, output: Path) -> None:
    catalog = json.loads((root / "catalog.json").read_text(encoding="utf-8-sig"))
    rows = {row["id"]: row for row in catalog["layouts"]}
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    output.mkdir(parents=True, exist_ok=True)
    font_path = Path("C:/Windows/Fonts/arial.ttf")
    font = ImageFont.truetype(str(font_path), 23) if font_path.is_file() else ImageFont.load_default()
    manifest = {"knowledge_base_commit": commit, "galleries": {}}

    for theme, ids in (("blue", BLUE_RED_IDS), ("red", BLUE_RED_IDS), ("tech", TECH_IDS)):
        canvas_color = "#F4F7FB" if theme != "tech" else "#07172B"
        text_color = "#17345D" if theme != "tech" else "#DCEEFF"
        border_color = "#CEDBE9" if theme != "tech" else "#23618E"
        accent = {"blue": "#0057D9", "red": "#A10000", "tech": "#00B7F5"}[theme]
        width, height, columns, gap, margin, label_height = 560, 315, 4, 24, 36, 40
        sheet = Image.new("RGB", (columns * width + (columns - 1) * gap + 2 * margin,
                                  4 * (height + label_height) + 3 * gap + 2 * margin), canvas_color)
        draw = ImageDraw.Draw(sheet)
        entries = []
        for index, layout_id in enumerate(ids):
            row = rows[layout_id]
            expected_theme = "deep-blue-tech" if theme == "tech" else theme
            if row.get("classification_status") != "verified" or expected_theme not in row.get("themes", []):
                raise ValueError(f"Not a verified {theme} component: {layout_id}")
            source = preview_path(root, row, theme)
            image = Image.open(source).convert("RGB")
            if abs(image.width / image.height - 16 / 9) > .02:
                raise ValueError(f"Unexpected preview ratio: {source}")
            image = ImageOps.fit(image, (width, height), method=Image.Resampling.LANCZOS)
            x = margin + index % columns * (width + gap)
            y = margin + index // columns * (height + label_height + gap)
            sheet.paste(image, (x, y))
            draw.rectangle((x, y, x + width - 1, y + height - 1), outline=border_color, width=2)
            draw.rectangle((x, y + height + 11, x + 24, y + height + 15), fill=accent)
            draw.text((x + 34, y + height + 5), layout_id, fill=text_color, font=font)
            entries.append({"id": layout_id, "relation": row.get("information_relation"),
                            "family_id": row.get("family_id"), "source": source.relative_to(root).as_posix()})
        filename = f"component-gallery-{theme}-16.png"
        sheet.save(output / filename, optimize=True)
        manifest["galleries"][theme] = {"image": filename, "components": entries}
    (output / "component-gallery-sources.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.library.resolve(), args.output.resolve())
