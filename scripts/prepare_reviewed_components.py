"""Materialize reviewed knowledge-base components as single-page editable PPTX."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pptx import Presentation

from fill_layout import (
    apply_body_text_presentation,
    apply_page_background_role,
    apply_normal_body_weight,
    select_source_page,
    set_text,
    walk,
)
from materialize_component_colors import freeze as freeze_component_colors
from normalize_fonts import normalize


def prepare(root: Path, layout_id: str, theme: str) -> Path:
    catalog=json.loads((root/'catalog.json').read_text(encoding='utf-8'))
    entry=next(x for x in catalog['layouts'] if x['id']==layout_id)
    source=root/(entry['red_source'] if theme=='red' else entry['source'])
    page=entry['red_source_page'] if theme=='red' else entry['source_page']
    bindings_rel=entry['red_bindings'] if theme=='red' else entry['bindings']
    bindings=json.loads((root/bindings_rel).read_text(encoding='utf-8'))['fields']
    rules=json.loads((root/entry['layout_rules']).read_text(encoding='utf-8'))
    presentation=Presentation(source)
    slide=select_source_page(presentation,page)
    shapes={shape.shape_id:shape for shape in walk(slide.shapes)}
    # Deliberately neutral examples: the ready component is a reusable layout,
    # never a source of project facts.
    for field in bindings:
        semantic=field.get('semantic_path')
        shape=shapes.get(field.get('shape_id'))
        if not semantic or shape is None or not shape.has_text_frame:
            continue
        value=('页面标题' if semantic=='page.title' else
               '正文内容' if semantic.endswith('.body') else
               '标题' if semantic.endswith('.heading') else None)
        if value is not None:
            set_text(shape,value)
    apply_body_text_presentation(slide,rules,bindings)
    apply_normal_body_weight(slide,rules,bindings)
    apply_page_background_role(slide,rules,theme,presentation.slide_width,presentation.slide_height,allow_source_scheme=True)
    dest=root/'layouts'/layout_id/f'ready-{theme}.pptx'
    presentation.save(dest)
    normalize(dest,dest)
    freeze_component_colors(dest,dest,None,source,page)
    return dest


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument('--library',required=True,type=Path)
    parser.add_argument('--ids-file',type=Path)
    args=parser.parse_args()
    root=args.library.resolve()
    ids=(json.loads(args.ids_file.read_text(encoding='utf-8')) if args.ids_file else
         ['content-blue-106','content-blue-112'])
    for layout_id in ids:
        for theme in ('blue','red'):
            print(prepare(root,layout_id,theme))


if __name__=='__main__':
    main()
