"""Place a source SVG logo with PNG fallback on a PowerPoint slide."""
from __future__ import annotations

import hashlib
import io
import json
import statistics
from pathlib import Path

from PIL import Image
from lxml import etree
from pptx.enum.shapes import MSO_SHAPE
from pptx.dml.color import RGBColor
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.opc.package import Part
from pptx.opc.packuri import PackURI
from pptx.oxml.ns import qn

PT = 12700
SVG_NS = "http://schemas.microsoft.com/office/drawing/2016/SVG/main"
SVG_EXT_URI = "{96DAC541-7B7A-43D3-8B79-37D633B846F1}"
POSITIONS = {"top_right", "bottom_right", "top_left", "bottom_left"}
APPEARANCES = {"auto", "color", "white", "black"}
VARIANTS = {"full", "epoint"}
EMBEDDINGS = {"png", "svg_with_png_fallback"}
DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "assets" / "brand" / "logo-config.json"


def load_config(path: Path | None = None) -> tuple[dict, Path]:
    source = Path(path or DEFAULT_CONFIG).resolve()
    config = json.loads(source.read_text(encoding="utf-8-sig"))
    if config.get("schema_version") != "1.0":
        raise ValueError("Logo 配置版本不受支持")
    return config, source.parent


def settings(config: dict, override: dict | bool | None) -> dict:
    result = dict(config["default"])
    if override is False:
        result["enabled"] = False
    elif override is True or override is None:
        pass
    elif isinstance(override, dict):
        if set(override) - set(result):
            raise ValueError("Logo 配置包含未知字段")
        result.update(override)
    else:
        raise ValueError("logo 只能是布尔值或配置对象")
    if not isinstance(result["enabled"], bool):
        raise ValueError("logo.enabled 必须是布尔值")
    if result["variant"] not in VARIANTS or result["appearance"] not in APPEARANCES:
        raise ValueError("Logo 版本或外观无效")
    if result.get("embedding", "png") not in EMBEDDINGS:
        raise ValueError("Logo 嵌入方式无效")
    if result["position"] != "auto" and result["position"] not in POSITIONS:
        raise ValueError("Logo 位置无效")
    for key in ("width_pt", "margin_pt"):
        if isinstance(result[key], bool) or not isinstance(result[key], (int, float)) or result[key] <= 0:
            raise ValueError(f"logo.{key} 必须是正数")
    if not isinstance(result["plate"], bool):
        raise ValueError("logo.plate 必须是布尔值")
    return result


def _contrast(rgb: tuple[int, int, int], ink: tuple[int, int, int]) -> float:
    def lum(values):
        vals = [v / 255 for v in values]
        linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in vals]
        return sum(v * w for v, w in zip(linear, (.2126, .7152, .0722)))
    a, b = sorted((lum(rgb), lum(ink)), reverse=True)
    return (a + .05) / (b + .05)


def _appearance(preview: Path | None, rect: tuple[int, int, int, int], slide_size: tuple[int, int], brand_colors: dict) -> tuple[str, dict]:
    if preview is None or not preview.is_file():
        return "color", {"source": "no_preview", "review_required": True}
    with Image.open(preview) as image:
        image = image.convert("RGB")
        x, y, w, h = rect
        sw, sh = slide_size
        crop = image.crop((int(x / sw * image.width), int(y / sh * image.height), int((x+w) / sw * image.width), int((y+h) / sh * image.height)))
        crop.thumbnail((80, 30))
        pixels = list(crop.getdata())
    if not pixels:
        return "color", {"source": "empty_preview_crop", "review_required": True}
    rgb = tuple(int(statistics.median(p[i] for p in pixels)) for i in range(3))
    luminances = [sum(p[i] * w for i, w in enumerate((.2126, .7152, .0722))) for p in pixels]
    spread = statistics.pstdev(luminances) if len(luminances) > 1 else 0
    def parse_hex(value):
        return tuple(int(value[i:i+2], 16) for i in (1, 3, 5))
    color_contrast = min(_contrast(rgb, parse_hex(brand_colors["brand_blue"])), _contrast(rgb, parse_hex(brand_colors["brand_red"])))
    white_contrast = _contrast(rgb, (255, 255, 255))
    choice = "white" if white_contrast > color_contrast else "color"
    return choice, {"source": str(preview), "median_rgb": rgb, "luminance_spread": round(spread, 1), "review_required": spread > 38 or max(color_contrast, white_contrast) < 3}


def _candidates(sw: int, sh: int, w: int, h: int, margin: int) -> dict[str, tuple[int, int, int, int]]:
    return {
        "top_right": (sw-margin-w, margin, w, h),
        "bottom_right": (sw-margin-w, sh-margin-h, w, h),
        "top_left": (margin, margin, w, h),
        "bottom_left": (margin, sh-margin-h, w, h),
    }


def _overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> int:
    return max(0, min(a[0]+a[2], b[0]+b[2])-max(a[0], b[0])) * max(0, min(a[1]+a[3], b[1]+b[3])-max(a[1], b[1]))


def _position(slide, positions: dict, priority: list[str], sw: int, sh: int) -> tuple[str, dict]:
    # Shapes covering most of the canvas are backgrounds; their paint is checked via preview.
    scored = []
    for rank, name in enumerate(priority):
        rect = positions[name]
        score = rank * 3
        conflicts = []
        padded = (rect[0]-6*PT, rect[1]-6*PT, rect[2]+12*PT, rect[3]+12*PT)
        for shape in slide.shapes:
            box = (shape.left, shape.top, shape.width, shape.height)
            if shape.width * shape.height > sw * sh * .35:
                continue
            overlap = _overlap(rect, box)
            if not overlap:
                if _overlap(padded, box):
                    score += 1
                continue
            ratio = overlap / max(1, rect[2] * rect[3])
            text = shape.has_text_frame and bool(shape.text.strip())
            weight = 1000 if text or shape.has_chart or shape.has_table else 35
            score += ratio * weight
            if text or ratio > .1:
                conflicts.append({"shape_id": shape.shape_id, "name": shape.name, "text": bool(text)})
        scored.append((score, name, conflicts))
    score, name, conflicts = min(scored)
    return name, {"score": round(score, 1), "conflicts": conflicts, "review_required": bool(conflicts)}


def add_logo(presentation, slide, layout: dict, library: Path, config_path: Path | None = None, override: dict | bool | None = None, anchor_shape=None, replace_existing: bool = False, *, theme: str | None = None) -> dict:
    config, asset_dir = load_config(config_path)
    opts = settings(config, override)
    if theme == "red" and opts["appearance"] == "color":
        raise ValueError("红色风格只允许黑、白单色 Logo；不能指定彩色 Logo")
    existing = [shape for shape in slide.shapes if shape.name.startswith("brand:logo:")]
    if not opts["enabled"]:
        if replace_existing:
            for shape in existing:
                shape._element.getparent().remove(shape._element)
            if anchor_shape is not None and anchor_shape not in existing:
                anchor_shape._element.getparent().remove(anchor_shape._element)
        return {"added": False, "reason": "disabled"}
    if existing and not replace_existing:
        return {"added": False, "reason": "already_present"}
    if existing and replace_existing and anchor_shape is None:
        anchor_shape = next((shape for shape in existing if shape.name != "brand:logo:plate"), None)
    variant = opts["variant"]
    source_svg = asset_dir / config["assets"][variant]["color"]
    from xml.etree import ElementTree as ET
    viewbox = ET.fromstring(source_svg.read_bytes()).attrib["viewBox"].split()
    aspect = float(viewbox[2]) / float(viewbox[3])
    w = int(opts["width_pt"] * PT)
    h = int(w / aspect)
    margin = int(opts["margin_pt"] * PT)
    sw, sh = presentation.slide_width, presentation.slide_height
    candidates = _candidates(sw, sh, w, h, margin)
    if anchor_shape is not None and opts["position"] == "auto":
        if replace_existing and (anchor_shape.width < 457200 or anchor_shape.height < 91440):
            raise ValueError("来源 Logo 使用组内坐标，不能按子图尺寸重建；请保留原 Logo 或在原图片上替换素材")
        w = min(w, anchor_shape.width, int(anchor_shape.height * aspect))
        h = int(w / aspect)
        rect = (anchor_shape.left, anchor_shape.top + (anchor_shape.height - h)//2, w, h)
        reused = anchor_shape.name.startswith("brand:logo:")
        name, placement_qa = ("existing_logo" if reused else "brand_slot"), {"score": 0, "conflicts": [], "review_required": False, "replaced_placeholder": not reused, "replaced_existing": reused}
    elif opts["position"] == "auto":
        name, placement_qa = _position(slide, candidates, config["position_priority"], sw, sh)
        if placement_qa["conflicts"]:
            for width_pt in (96, 86, 76, 66):
                if width_pt >= opts["width_pt"]:
                    continue
                trial_w = int(width_pt * PT)
                trial_h = int(trial_w / aspect)
                trial = _candidates(sw, sh, trial_w, trial_h, margin)
                trial_name, trial_qa = _position(slide, trial, config["position_priority"], sw, sh)
                if not trial_qa["conflicts"]:
                    w, h, candidates, name, placement_qa = trial_w, trial_h, trial, trial_name, trial_qa
                    break
    else:
        name, placement_qa = _position(slide, candidates, [opts["position"]], sw, sh)
    if name not in ("brand_slot", "existing_logo"):
        rect = candidates[name]
    preview_rel = layout.get("blank_preview") or layout.get("preview")
    preview = (library / preview_rel) if preview_rel else None
    if opts["appearance"] == "auto":
        appearance, appearance_qa = _appearance(preview, rect, (sw, sh), config["colors"])
        if appearance_qa["review_required"] and opts["position"] == "auto" and anchor_shape is None:
            for alternative in config["position_priority"]:
                if alternative == name:
                    continue
                alt_name, alt_placement = _position(slide, candidates, [alternative], sw, sh)
                if alt_placement["conflicts"]:
                    continue
                alt_appearance, alt_qa = _appearance(preview, candidates[alternative], (sw, sh), config["colors"])
                if not alt_qa["review_required"]:
                    name, placement_qa, rect, appearance, appearance_qa = alt_name, alt_placement, candidates[alternative], alt_appearance, alt_qa
                    break
    else:
        appearance, appearance_qa = opts["appearance"], {"source": "explicit", "review_required": False}
    if theme == "red" and appearance == "color":
        appearance = "black"
        appearance_qa["monochrome_policy"] = "red_light_background_black_logo"
    svg_path = asset_dir / config["assets"][variant][appearance]
    png_path = svg_path.with_suffix(".png")
    if not svg_path.is_file() or not png_path.is_file():
        raise FileNotFoundError("Logo SVG 或 PNG 回退图缺失：" + str(svg_path))
    if opts["plate"]:
        plate = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, rect[0]-5*PT, rect[1]-4*PT, rect[2]+10*PT, rect[3]+8*PT)
        plate.name = "brand:logo:plate"
        plate.fill.solid()
        plate.fill.fore_color.rgb = RGBColor(255, 255, 255) if appearance != "white" else RGBColor(15, 20, 35)
        plate.line.fill.background()
    picture = slide.shapes.add_picture(io.BytesIO(png_path.read_bytes()), *rect)
    picture.name = f"brand:logo:{variant}:{appearance}"
    embedding = opts.get("embedding", "png")
    if embedding == "svg_with_png_fallback":
        svg_bytes = svg_path.read_bytes()
        sha = hashlib.sha256(svg_bytes).hexdigest()[:16]
        part = Part(PackURI(f"/ppt/media/brand-logo-{sha}.svg"), "image/svg+xml", slide.part.package, svg_bytes)
        rid = slide.part.relate_to(part, RT.IMAGE)
        blip = picture._element.xpath(".//a:blip")[0]
        ext_list = etree.SubElement(blip, qn("a:extLst"))
        ext = etree.SubElement(ext_list, qn("a:ext"), uri=SVG_EXT_URI)
        svg_blip = etree.SubElement(ext, f"{{{SVG_NS}}}svgBlip", nsmap={"asvg": SVG_NS})
        svg_blip.set(qn("r:embed"), rid)
    if anchor_shape is not None:
        anchor_shape._element.getparent().remove(anchor_shape._element)
    if replace_existing:
        for shape in existing:
            if anchor_shape is None or shape.shape_id != anchor_shape.shape_id:
                parent=shape._element.getparent()
                if parent is not None:
                    parent.remove(shape._element)
    return {"added": True, "variant": variant, "appearance": appearance, "embedding": embedding, "position": name, "width_pt": round(rect[2]/PT, 1), "shape_id": picture.shape_id, "source_svg": str(svg_path), "placement_qa": placement_qa, "appearance_qa": appearance_qa, "visual_qa": "not_run"}
