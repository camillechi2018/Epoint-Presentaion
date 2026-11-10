"""Keep recovered editable placeholder text at its single-page XML coordinates."""
import argparse
import json
from pathlib import Path
from pptx import Presentation


def fix(deck: Path, manifest: Path) -> dict:
    records = json.loads(manifest.read_text(encoding="utf-8-sig"))["slides"]
    target = Presentation(deck)
    changed = []
    for index, (slide, record) in enumerate(zip(target.slides, records), 1):
        source = Presentation(record.get("path") or record.get("input")).slides[0]
        source_by_id = {shape.shape_id: shape for shape in source.shapes}
        for shape in slide.shapes:
            if not shape.name.startswith("field:recovered:"):
                continue
            original = source_by_id.get(int(shape.name.rsplit(":", 1)[1]))
            if original is None:
                raise ValueError(f"第 {index} 页缺少恢复文本的源形状")
            geometry = (original.left, original.top, original.width, original.height)
            if (shape.left, shape.top, shape.width, shape.height) != geometry:
                shape.left, shape.top, shape.width, shape.height = geometry
                changed.append({"slide": index, "shape": shape.name})
    if changed:
        target.save(deck)
    return {"changed": changed, "count": len(changed)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(fix(args.input, args.manifest), ensure_ascii=False))
