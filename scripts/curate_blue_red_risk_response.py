"""Map the blue/red P050 risk-response page for semantic filling."""
import argparse
import json
from hashlib import sha256
from pathlib import Path

PATHS = {
    10: 'page.title', 17: 'page.risk_heading', 18: 'page.response_heading',
    19: 'risks[0].detail', 20: 'risks[1].detail',
    23: 'risks[2].detail', 24: 'risks[3].detail',
    21: 'responses[0].detail', 22: 'responses[1].detail',
    25: 'responses[2].detail', 26: 'responses[3].detail',
    28: 'responses[1].detail_2', 29: 'responses[3].detail_2',
    33: 'principles[0]', 34: 'principles[1]', 35: 'principles[2]',
    36: 'risks[0].title', 37: 'risks[1].title',
    38: 'risks[2].title', 39: 'risks[3].title',
    40: 'responses[0].title', 41: 'responses[1].title',
    42: 'responses[2].title', 43: 'responses[3].title',
}

def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--library', type=Path, required=True)
    p.add_argument('--reviewed', action='store_true')
    args = p.parse_args()
    root = args.library.resolve()
    touched = {'catalog.json'}
    base = root / 'layouts/content-blue-050'
    for filename in ('bindings.json', 'bindings-red.json'):
        path = base / filename
        obj = json.loads(path.read_text(encoding='utf-8'))
        assert {int(f['field'].split('_')[1]) for f in obj['fields']} == set(PATHS)
        for f in obj['fields']:
            sid = int(f['field'].split('_')[1])
            f['semantic_path'] = PATHS[sid]
            f['semantic_role'] = PATHS[sid].split('.')[0]
            f['max_chars'] = min(f['max_chars'], 34 if '.detail' in PATHS[sid] else 18)
            f['max_lines'] = 2 if '.detail' in PATHS[sid] or sid in (17, 18) else 1
        dump(path, obj)
        touched.add(path.relative_to(root).as_posix())
    catpath = root / 'catalog.json'
    cat = json.loads(catpath.read_text(encoding='utf-8'))
    item = next(x for x in cat['layouts'] if x['id'] == 'content-blue-050')
    item.update(information_relation='risk-response', family_id='risk-response-triangles',
                classification_status='verified' if args.reviewed else 'visual_reviewed',
                semantic_review_status='verified_blue_red' if args.reviewed else 'fields_mapped_pending_render',
                composition_tags=['four-risks', 'four-responses', 'two-sided'])
    if args.reviewed:
        item['pptx_support'] = 'verified_static'
        item['media_status'] = 'verified_brand_logo_only'
    dump(catpath, cat)
    rules = base / 'layout_rules.json'
    obj = json.loads(rules.read_text(encoding='utf-8'))
    obj.update(cardinality_mode='fixed', source_count=4, supported_counts=[4],
               validation_status='verified_fixed_count' if args.reviewed else 'pending_render')
    dump(rules, obj)
    touched.add(rules.relative_to(root).as_posix())
    spec = base / 'spec.md'
    spec.write_text('# 风险与应对\n\n蓝红 P050：四项风险分别对应四项措施；上下两个三角分别表示风险管理与应对策略。中间三条原则单独填充。固定四组，第二及第四项措施各有补充说明。所有业务文字由本次材料提供。蓝红静态 PPTX 实填渲染已复核；动效、HTML、扩展色系未验收。\n', encoding='utf-8')
    touched.add(spec.relative_to(root).as_posix())
    if args.reviewed:
        review = root / 'review/content-blue-050.json'
        dump(review, {'date':'2026-11-05', 'layout_id':'content-blue-050',
                      'status':'verified_static_pptx_draft_pending_review',
                      'supported_counts':[4], 'themes':['blue','red'],
                      'preview_paths':['review/content-blue-050-blue-filled.png','review/content-blue-050-red-filled.png'],
                      'limits':['motion not verified','HTML not implemented','other colors not verified']})
        touched.add(review.relative_to(root).as_posix())
        touched.update({'review/content-blue-050-blue-filled.png','review/content-blue-050-red-filled.png'})
    manifest = root / 'knowledge-manifest.json'
    m = json.loads(manifest.read_text(encoding='utf-8'))
    for rel in touched:
        m['files'][rel] = sha256((root / rel).read_bytes()).hexdigest()
    dump(manifest, m)

if __name__ == '__main__':
    main()
