"""Review native repeated item membership and prototype P09/P49/P69 reflow."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from import_tech_style import dump, digest, VERSION

FIELD_MAP = {
    9: [('number', 'title', 'english')],
    49: [('title', 'description')],
    51: [('description', 'title')],
    69: [('time', 'activity', 'owner')],
}
P69_FIELDS = [
    {'time': 'text_22', 'activity': 'text_15', 'owner': 'text_32'},
    {'time': 'text_29', 'activity': 'text_19', 'owner': 'text_36'},
    {'time': 'text_31', 'activity': 'text_95', 'owner': 'text_38'},
    {'time': 'text_23', 'activity': 'text_16', 'owner': 'text_33'},
    {'time': 'text_24', 'activity': 'text_17', 'owner': 'text_34'},
    {'time': 'text_25', 'activity': 'text_18', 'owner': 'text_35'},
]
P9_FIELDS = [
    {'number': 'text_45', 'title': 'text_43', 'english': 'text_44'},
    {'number': 'text_139', 'title': 'text_140', 'english': 'text_141'},
    {'number': 'text_168', 'title': 'text_169', 'english': 'text_170'},
    {'number': 'text_257', 'title': 'text_258', 'english': 'text_259'},
    {'number': 'text_229', 'title': 'text_230', 'english': 'text_231'},
    {'number': 'text_201', 'title': 'text_202', 'english': 'text_203'},
]


def curate(root: Path, update_manifest=True):
    catalog_file = root / 'catalog.json'
    catalog = json.loads(catalog_file.read_text(encoding='utf-8'))
    found = {}
    for page in FIELD_MAP:
        entry = next(e for e in catalog['layouts'] if e.get('style_family') == 'deep-blue-tech' and e['source_page'] == page)
        groups_file = root / entry['item_groups']
        data = json.loads(groups_file.read_text(encoding='utf-8'))
        bindings = json.loads((root / entry['bindings']).read_text(encoding='utf-8'))
        fields = {f['field']: f for f in bindings['fields']}
        if len(data['units']) != 6: raise ValueError(f'P{page:03d} expected 6 units')
        for i, unit in enumerate(data['units']):
            allowed = {f['field'] for f in bindings['fields'] if f['shape_id'] in unit['source_shape_ids']}
            if page == 69: mapped = P69_FIELDS[i]
            elif page == 9: mapped = P9_FIELDS[i]
            else:
                wanted = FIELD_MAP[page][0]
                selected = [f for f in bindings['fields'] if f['field'] in allowed]
                if len(selected) != len(wanted): raise ValueError(f'P{page:03d} unit {i+1} field count')
                mapped = dict(zip(wanted, [f['field'] for f in selected]))
            if set(mapped.values()) != allowed: raise ValueError(f'P{page:03d} unit {i+1} mapping mismatch')
            unit['fields'] = mapped
            unit['semantic_index'] = i + 1
            for role, key in mapped.items():
                fields[key]['semantic_key'] = f'item_{i+1}.{role}'
                fields[key]['semantic_role'] = 'item_field_reviewed'
        data['status'] = 'field_membership_reviewed_geometry_pending'
        data['review_note'] = '字段归属按原生对象组与预览复核；减少项数仍需重排和渲染验证。'
        dump(groups_file, data)
        dump(root / entry['bindings'], bindings)
        entry['item_group_status'] = data['status']
        entry['item_group_field_count'] = sum(len(u['fields']) for u in data['units'])
        if page in (9,49):
            rules_file=root/entry['layout_rules']
            rules=json.loads(rules_file.read_text(encoding='utf-8'))
            rules.update(cardinality_mode='tech_grid_2x3',supported_counts=[2,3,4,5,6],
                         validation_status='prototype_requires_visual_review',
                         reflow_status='internal_prototype',source_count=6,
                         units=[u['source_shape_ids'] for u in data['units']],
                         unit_roots=[u['root_shape_id'] for u in data['units']],
                         row_parent_ids=[193,194] if page==9 else [56,57],
                         row_strip_ids=[] if page==9 else [77,76])
            dump(rules_file,rules)
            entry['cardinality_status']='internal_prototype_requires_visual_review'
            static_ids=[entry['source_logo_shape_id']] if entry.get('source_logo_shape_id') else []
            motion={'layout_id':entry['id'],'source_animation':False,'source_transition':False,
                    'motion_suitability':'A','status':'prototype','preset':'step-reveal',
                    'effect':'fade','duration_seconds':0.35,
                    'groups':[{'step':i+1,'shape_ids':[u['root_shape_id']],
                               'semantic_unit':f'item_{i+1}'} for i,u in enumerate(data['units'])],
                    'static_shape_ids':static_ids,'brand_static':True,
                    'final_state_complete':True,'playback_review':'not_signed_off',
                    'group_generation_rule':'animate retained top-level item groups after reflow'}
            dump(root/entry['motion'],motion)
            entry['motion_support']='prototype_requires_playback_review'
        if page == 51:
            fields['text_280']['semantic_role']='computed_item_count'
            fields['text_280']['semantic_key']='item_count'
            dump(root/entry['bindings'],bindings)
            rules_file=root/entry['layout_rules']
            rules=json.loads(rules_file.read_text(encoding='utf-8'))
            rules.update(cardinality_mode='tech_six_pillars',supported_counts=[2,3,4,5,6],
                         validation_status='prototype_requires_visual_review',
                         reflow_status='internal_prototype',source_count=6,
                         units=[u['source_shape_ids'] for u in data['units']],
                         item_fields=[u['fields'] for u in data['units']],
                         source_indices_by_count={'2':[0,5],'3':[0,2,5],
                                                  '4':[0,1,4,5],'5':[0,1,2,4,5],
                                                  '6':[0,1,2,3,4,5]},
                         spacing_emu_by_count={'2':3017520,'3':2788920,'4':2331720,
                                               '5':2066544,'6':1823280},
                         canvas_width_emu=12192000,
                         anchor_shape_ids=[269,271,273,274,272,270],
                         computed_count_shape_id=280)
            dump(rules_file,rules)
            entry['cardinality_status']='internal_prototype_requires_visual_review'
            motion={'layout_id':entry['id'],'source_animation':False,'source_transition':False,
                    'motion_suitability':'A','status':'prototype','preset':'step-reveal',
                    'effect':'fade','duration_seconds':0.35,
                    'groups':[{'step':i+1,'shape_ids':u['source_shape_ids'],
                               'semantic_unit':f'pillar_{i+1}'} for i,u in enumerate(data['units'])],
                    'static_shape_ids':[280,293,entry['source_logo_shape_id']],
                    'brand_static':True,'final_state_complete':True,
                    'playback_review':'not_signed_off',
                    'group_generation_rule':'animate retained source pillar object sets in logical order'}
            dump(root/entry['motion'],motion)
            entry['motion_support']='prototype_requires_playback_review'
        if page == 69:
            rules_file = root / entry['layout_rules']
            rules = json.loads(rules_file.read_text(encoding='utf-8'))
            rules.update(cardinality_mode='tech_schedule_rows', supported_counts=[2, 3, 4, 5, 6],
                         validation_status='prototype_requires_visual_review',
                         reflow_status='internal_prototype',
                         source_count=6, units=[u['source_shape_ids'] for u in data['units']],
                         shared_connector_shape_id=96,
                         source_row_tops_emu=[2288193, 2997443, 3706693, 4415944, 5125194, 5834445])
            dump(rules_file, rules)
            entry['cardinality_status'] = 'internal_prototype_requires_visual_review'
            motion={'layout_id':entry['id'],'source_animation':False,'source_transition':False,
                    'motion_suitability':'A','status':'prototype','preset':'step-reveal',
                    'effect':'fade','duration_seconds':0.35,
                    'groups':[{'step':i+1,'shape_ids':u['source_shape_ids'],
                               'semantic_unit':f'row_{i+1}'} for i,u in enumerate(data['units'])],
                    'static_shape_ids':[96,entry['source_logo_shape_id']],
                    'brand_static':True,'final_state_complete':True,
                    'playback_review':'not_signed_off'}
            dump(root/entry['motion'],motion)
            entry['motion_support']='prototype_requires_playback_review'
        found[page] = entry['id']
    dump(catalog_file, catalog)
    if update_manifest:
        files = {p.relative_to(root).as_posix(): digest(p) for p in root.rglob('*')
                 if p.is_file() and '.git' not in p.parts and p.name not in
                 ('knowledge-manifest.json', 'audit-report.json', 'blank.pptx', 'blank-red.pptx')
                 and 'source-pages' not in p.relative_to(root).parts}
        dump(root / 'knowledge-manifest.json', {'schema_version': '1.0', 'version': VERSION,
                                               'status': 'draft_pending_review',
                                               'file_count': len(files), 'files': files})
    return found


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--library', type=Path, required=True)
    print(json.dumps(curate(p.parse_args().library), ensure_ascii=False))
