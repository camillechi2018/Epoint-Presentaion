"""Register the reviewed four-column P38 process as an internal prototype."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


UNITS = [
    [31, 22, 26, 30, 49, 56, 74],
    [68, 69, 70, 71, 50, 55, 80],
    [63, 64, 65, 66, 51, 54, 87],
    [58, 59, 60, 61, 52, 53, 90],
]
FIELDS = [
    {'number': 'text_31', 'title': 'text_49', 'body': 'text_56'},
    {'number': 'text_68', 'title': 'text_50', 'body': 'text_55'},
    {'number': 'text_63', 'title': 'text_51', 'body': 'text_54'},
    {'number': 'text_58', 'title': 'text_52', 'body': 'text_53'},
]


def curate(root: Path, update_manifest: bool = True):
    from import_tech_style import VERSION, digest, dump

    root = Path(root)
    catalog_path = root / 'catalog.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    entry = next(e for e in catalog['layouts'] if e['id'] == 'content-tech-038')
    folder = root / 'layouts' / entry['id']
    tree = json.loads((folder / 'shape-tree.json').read_text(encoding='utf-8'))
    top = {s['shape_id'] for s in tree['recursive_shapes'] if not s['group_path']}
    required = {sid for unit in UNITS for sid in unit}
    if not required <= top or len(required) != sum(map(len, UNITS)):
        raise ValueError('P38 source object membership changed')
    bindings = json.loads((folder / 'bindings.json').read_text(encoding='utf-8'))
    by_name = {f['field']: f for f in bindings['fields']}
    for i, fields in enumerate(FIELDS, 1):
        if {by_name[v]['shape_id'] for v in fields.values()} - set(UNITS[i - 1]):
            raise ValueError(f'P38 field membership changed: {i}')
        for role, field in fields.items():
            by_name[field]['semantic_key'] = f'item_{i}.{role}'
            by_name[field]['semantic_role'] = 'computed_item_number' if role == 'number' else 'item_field_reviewed'
    by_name['text_6']['semantic_path'] = 'heading'
    by_name['text_7']['semantic_path'] = 'summary'
    dump(folder / 'bindings.json', bindings)
    groups = {
        'status': 'reviewed_internal_prototype', 'source_count': 4,
        'target_counts': [2, 3, 4], 'geometry_family': 'process-columns',
        'units': [{'semantic_index': i, 'source_shape_ids': ids, 'fields': FIELDS[i - 1]}
                  for i, ids in enumerate(UNITS, 1)],
        'shared_shape_ids': [], 'auto_grouped_count': 0,
        'review_note': '每步包含分散的编号、卡、顶边、图标底座、标题、正文及底部图标；页眉与 Logo 静态。',
    }
    dump(folder / 'item-groups.json', groups)
    rules = json.loads((folder / 'layout_rules.json').read_text(encoding='utf-8'))
    rules.update(cardinality_mode='tech_process_columns', source_count=4,
                 supported_counts=[2, 3, 4], candidate_counts=[2, 3, 4],
                 validation_status='prototype_requires_visual_review',
                 reflow_status='internal_prototype', grouping_status='reviewed_internal_prototype',
                 units=UNITS, item_fields=FIELDS, anchor_shape_ids=[22, 69, 64, 59],
                 canvas_width_emu=12192000, spacing_emu=2850000)
    dump(folder / 'layout_rules.json', rules)
    logo_id = entry.get('source_logo_shape_id')
    motion = {
        'layout_id': entry['id'], 'source_animation': False, 'source_transition': False,
        'motion_suitability': 'A', 'status': 'prototype', 'preset': 'step-reveal',
        'effect': 'fade', 'duration_seconds': 0.35,
        'groups': [{'step': i, 'shape_ids': ids, 'semantic_unit': f'step_{i}'}
                   for i, ids in enumerate(UNITS, 1)],
        'static_shape_ids': [2] + ([logo_id] if logo_id else []),
        'brand_static': True, 'final_state_complete': True,
        'playback_review': 'not_signed_off',
        'group_generation_rule': 'animate seven retained top-level objects per semantic step',
    }
    dump(folder / 'motion.json', motion)
    review_path = folder / 'semantic-review.json'
    review = json.loads(review_path.read_text(encoding='utf-8'))
    review.update(field_binding_status='four_step_fields_reviewed',
                  cardinality_status='2_to_4_internal_prototype',
                  motion_status='step_reveal_internal_prototype_playback_pending',
                  review_status='visual_structure_and_final_frame_reviewed',
                  normal_use_status='not_verified')
    dump(review_path, review)
    entry['item_group_status'] = groups['status']
    entry['item_group_field_count'] = 12
    entry['cardinality_status'] = 'internal_prototype_requires_visual_review'
    entry['motion_support'] = 'prototype_requires_playback_review'
    dump(catalog_path, catalog)
    if update_manifest:
        files = {p.relative_to(root).as_posix(): digest(p) for p in root.rglob('*')
                 if p.is_file() and '.git' not in p.parts and p.name not in
                 ('knowledge-manifest.json', 'audit-report.json', 'blank.pptx', 'blank-red.pptx')
                 and 'source-pages' not in p.relative_to(root).parts}
        dump(root / 'knowledge-manifest.json', {'schema_version': '1.0', 'version': VERSION,
                                               'status': 'draft_pending_review',
                                               'file_count': len(files), 'files': files})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--library', type=Path, required=True)
    curate(parser.parse_args().library)
