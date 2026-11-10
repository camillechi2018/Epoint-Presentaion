"""Curate the native five-stage process page; shorter variants remain pending."""
import argparse, json
from hashlib import sha256
from pathlib import Path

IDS = [139,143,144,145,146]
GOALS = [16,23,25,27,29]
ACTS = [39,42,44,46,48]
OUTPUTS = [41,43,45,47,49]
GOAL_LABELS = [14,22,24,26,28]
ACT_LABELS = [30,32,34,36,50]
OUT_LABELS = [31,33,35,37,51]
MAP = {40:'page.title'}
for i in range(5):
    for sid,key in ((IDS[i],'heading'),(GOALS[i],'goal'),(ACTS[i],'activity'),(OUTPUTS[i],'output'),
                    (GOAL_LABELS[i],'goal_label'),(ACT_LABELS[i],'activity_label'),(OUT_LABELS[i],'output_label')):
        MAP[sid] = f'steps[{i}].{key}'

def dump(path,obj): path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--library',type=Path,required=True);ap.add_argument('--reviewed',action='store_true');a=ap.parse_args()
    root=a.library.resolve();base=root/'layouts/content-blue-230';touched={'catalog.json'}
    for fname in ('bindings.json','bindings-red.json'):
        path=base/fname;data=json.loads(path.read_text(encoding='utf-8-sig'))
        if {int(f['field'].split('_')[1]) for f in data['fields']} != set(MAP): raise ValueError(fname+' fields changed')
        for f in data['fields']:
            sid=int(f['field'].split('_')[1]);key=MAP[sid]
            f.update(semantic_path=key,semantic_role=key.rsplit('.',1)[-1],
                     max_chars=min(f['max_chars'],36 if sid in ACTS else 25 if sid in OUTPUTS else 18),
                     max_lines=4 if sid in ACTS else 2 if sid in IDS else 1)
        dump(path,data);touched.add(path.relative_to(root).as_posix())
    catpath=root/'catalog.json';cat=json.loads(catpath.read_text(encoding='utf-8-sig'))
    e=next(x for x in cat['layouts'] if x['id']=='content-blue-230')
    e.update(role='process',information_relation='five-stage-process',family_id='process-five-chevron',
             classification_status='verified' if a.reviewed else 'visual_reviewed',
             semantic_review_status='verified_blue_red' if a.reviewed else 'fields_mapped_pending_render',
             batch_status='native_five_verified_shorter_variants_pending' if a.reviewed else 'pending_render',
             composition_tags=['five-steps','chevron','terminal-stage'])
    if a.reviewed:e.update(pptx_support='verified_static',media_status='verified_brand_logo_only')
    dump(catpath,cat)
    rules=base/'layout_rules.json';v=json.loads(rules.read_text(encoding='utf-8-sig'))
    v.update(cardinality_mode='fixed',source_count=5,supported_counts=[5],
             verified_counts=[5] if a.reviewed else [],
             planned_variant_counts=[3,4],validation_status='verified_fixed_count' if a.reviewed else 'pending_render',
             reflow_status='shorter_terminal_variants_not_implemented',
             terminal_stage_shape_id=111,connector_shape_ids=[117,118,119,120])
    dump(rules,v);touched.add(rules.relative_to(root).as_posix())
    spec=base/'spec.md';spec.write_text('# 五阶段流程\n\n来源：蓝红 P230。五项均含阶段、目标、活动、输出；终点第五项造型独立。原生五步完成语义字段及蓝红短文实填验收；三、四步仍须重新设计终点与连接线，未开放。Logo 保持原位；动效、HTML 和扩展色系另行验收。\n',encoding='utf-8');touched.add(spec.relative_to(root).as_posix())
    if a.reviewed:
        rp=root/'review/content-blue-230.json';dump(rp,{'date':'2026-11-05','layout_id':'content-blue-230','status':'verified_static_pptx_draft_pending_review','verified_counts':[5],'pending_counts':[3,4],'preview_paths':['review/content-blue-230-blue-filled.png','review/content-blue-230-red-filled.png']});touched.add(rp.relative_to(root).as_posix());touched.update({'review/content-blue-230-blue-filled.png','review/content-blue-230-red-filled.png'})
    manifest=root/'knowledge-manifest.json';m=json.loads(manifest.read_text(encoding='utf-8-sig'))
    for rel in touched:m['files'][rel]=sha256((root/rel).read_bytes()).hexdigest()
    dump(manifest,m)
if __name__=='__main__':main()
