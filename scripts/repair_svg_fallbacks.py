"""Restore primary PNG image references lost while PowerPoint merges SVG pictures."""
from __future__ import annotations

import argparse
import io
import json
import uuid
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn


def walk(shapes):
    for shape in shapes:
        yield shape
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from walk(shape.shapes)


def missing_primary(slide):
    for shape in walk(slide.shapes):
        if shape.shape_type != MSO_SHAPE_TYPE.PICTURE:
            continue
        blips = shape._element.xpath('.//a:blip')
        if blips and not blips[0].get(qn('r:embed')):
            yield shape, blips[0]


def repair(input_path: Path, manifest_path: Path | None, check: bool = False) -> dict:
    presentation = Presentation(input_path)
    records = []
    sources = None
    if not check:
        if manifest_path is None:
            raise ValueError('修复模式需要组装清单')
        plan = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
        sources = plan['slides']
        if len(sources) != len(presentation.slides):
            raise ValueError('组装清单页数与成稿不一致')
    for index, slide in enumerate(presentation.slides, 1):
        absent = list(missing_primary(slide))
        if not absent:
            continue
        source_shapes = {}
        if sources is not None:
            source_record = sources[index - 1]
            source_value = source_record.get('path') or source_record.get('input')
            if not source_value:
                raise ValueError(f'第 {index} 页组装清单缺少 path 或 input')
            source_path = Path(source_value)
            if not source_path.is_absolute():
                source_path = manifest_path.parent / source_path
            original = Presentation(source_path).slides[0]
            source_shapes = {shape.shape_id: shape for shape in walk(original.shapes)}
        for shape, blip in absent:
            record = {'slide': index, 'shape_id': shape.shape_id, 'name': shape.name}
            if sources is not None:
                source = source_shapes.get(shape.shape_id)
                if source is None or source.shape_type != MSO_SHAPE_TYPE.PICTURE:
                    raise ValueError(f'第 {index} 页图标 {shape.shape_id} 在单页源文件中不存在')
                source_blips = source._element.xpath('.//a:blip')
                if not source_blips or not source_blips[0].get(qn('r:embed')):
                    raise ValueError(f'第 {index} 页图标 {shape.shape_id} 的单页源文件无主图片')
                blob = source.image.blob
                image_part, rid = slide.part.get_or_add_image_part(io.BytesIO(blob))
                if image_part.content_type != 'image/png':
                    raise ValueError(f'第 {index} 页图标 {shape.shape_id} 的回退图不是 PNG')
                blip.set(qn('r:embed'), rid)
                record['png_bytes'] = len(blob)
            records.append(record)
    if sources is not None and records:
        temp = input_path.with_name(input_path.stem + f'.media-{uuid.uuid4().hex}.pptx')
        presentation.save(temp)
        # PowerPoint COM can release the destination a moment after Close().
        # Retry only the atomic replacement; never treat a locked output as a
        # successful media repair.
        import time
        for attempt in range(10):
            try:
                temp.replace(input_path)
                break
            except PermissionError:
                if attempt == 9:
                    raise
                time.sleep(0.5)
    verified = Presentation(input_path)
    remaining = sum(1 for slide in verified.slides for _ in missing_primary(slide))
    broken = []
    for index, slide in enumerate(verified.slides, 1):
        for shape in walk(slide.shapes):
            if shape.shape_type != MSO_SHAPE_TYPE.PICTURE:
                continue
            blips = shape._element.xpath('.//a:blip')
            if not blips or not blips[0].get(qn('r:embed')):
                continue
            try:
                image = shape.image
                blob = image.blob
                if not blob or (image.content_type == 'image/png' and not blob.startswith(b'\x89PNG\r\n\x1a\n')):
                    raise ValueError('空图片或 PNG 签名无效')
            except Exception as error:
                broken.append({'slide': index, 'shape_id': shape.shape_id, 'error': str(error)})
    return {'slide_count': len(presentation.slides), 'restored': len(records) if not check else 0,
            'missing_primary': remaining, 'broken_primary': broken,
            'records': records, 'passed': remaining == 0 and not broken}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = repair(args.input.resolve(), args.manifest.resolve() if args.manifest else None, args.check)
    if args.report:
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'slide_count': result['slide_count'], 'restored': result['restored'],
                      'missing_primary': result['missing_primary'], 'broken_primary': len(result['broken_primary']),
                      'passed': result['passed']}, ensure_ascii=False))
    if not result['passed']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
