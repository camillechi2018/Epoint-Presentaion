"""Register eight short-copy technology layouts at their source item counts."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from extend_tech_static_pool import DECOR_SHA

CONFIG={
  43:(3,'parallel-points',['heading','item_1.body','item_1.title','item_2.body','item_2.title','item_3.body','item_3.title','summary']),
  46:(3,'cycle',['heading','item_1.body','item_1.title','item_2.body','item_2.title','item_3.body','item_3.title','center.topic','summary']),
  47:(5,'process',['heading','step_1.body','step_2.body','step_3.body','step_4.body','step_5.body','center.topic','center.subtitle','step_1.symbol','step_2.symbol','step_3.symbol','step_4.symbol','step_5.symbol','summary']),
  48:(4,'parallel-points',['heading','summary','top_conclusion','item_1.body','item_2.body','item_3.body','item_4.body','item_4.title','item_3.title','item_2.title','item_1.title']),
  52:(6,'hierarchy',['scene_1','scene_2','scene_3','scene_4','scene_5','scene_6','scope_1','scope_2','scope_3','scope_4','top_conclusion','heading','summary']),
  55:(1,'single-focus',['heading','body']),
  56:(5,'process',['item_1.title','item_1.body','item_2.body','item_2.title','item_3.body','item_3.title','item_4.body','item_4.title','item_5.body','item_5.title','center.count','heading','summary']),
  57:(6,'hierarchy',['case_1.title','case_1.subtitle','case_2.title','case_2.subtitle','case_3.title','case_3.subtitle','case_4.title','case_4.subtitle','case_5.title','case_5.subtitle','case_6.title','case_6.subtitle','heading','summary']),
}

def extend(root:Path,update_manifest=True):
    from import_tech_style import VERSION,digest,dump
    root=Path(root);catalog_path=root/'catalog.json'
    catalog=json.loads(catalog_path.read_text(encoding='utf-8'))
    for page,(count,relation,paths) in CONFIG.items():
        entry=next(e for e in catalog['layouts'] if e.get('style_family')=='deep-blue-tech' and e['source_page']==page)
        folder=root/'layouts'/entry['id'];bindings=json.loads((folder/'bindings.json').read_text(encoding='utf-8'))
        if len(bindings['fields'])!=len(paths) or len(set(paths))!=len(paths):raise ValueError(f'P{page:03d} mapping mismatch')
        for field,semantic in zip(bindings['fields'],paths):
            if field.get('semantic_path') and field['semantic_path']!=semantic:raise ValueError(f'P{page:03d} semantic conflict')
            field['semantic_path']=semantic;field['semantic_role']='reviewed_text'
        for obj in bindings.get('objects',{}).get('images',[]):
            if obj.get('semantic_role')!='source_media_unclassified':continue
            if obj['sha256'] not in DECOR_SHA:raise ValueError(f'P{page:03d} unknown media')
            obj['semantic_role']='source_decorative_locked';obj['review_note']='固定科技页眉光效，不作业务事实。'
        dump(folder/'bindings.json',bindings)
        rules=json.loads((folder/'layout_rules.json').read_text(encoding='utf-8'))
        rules.update({'cardinality_mode':'fixed_verified','source_count':count,'supported_counts':[count],
                      'verified_counts':[count],'static_pptx_status':'verified_short_copy_draft','reflow_status':'fixed_count_only'})
        if page==56:rules['font_size_overrides_pt']={'53':26}
        dump(folder/'layout_rules.json',rules)
        review={'source_page':page,'component_id':entry['id'],'information_relation':relation,
                'source_item_count':count,'content_fit_limit':'原生项数和短文案；长文及变项数另测。',
                'review_status':'static_pptx_verified','field_binding_status':'reviewed',
                'normal_use_status':'static_pptx_verified_draft',
                'source_text_policy':'来源示例文字、数字不作项目事实。',
                'verification_note':'虚构内容全字段实填、PowerPoint 渲染、文字边界、单 Logo 和媒体引用核对。'}
        dump(folder/'semantic-review.json',review)
        entry['information_relation']=relation;entry['classification_status']='verified'
        entry['pptx_support']='verified_static_draft';entry['visual_review_status']='powerpoint_render_checked'
        entry['semantic_review']=(folder/'semantic-review.json').relative_to(root).as_posix()
        entry['semantic_review_status']='static_pptx_verified'
    dump(catalog_path,catalog)
    report_path=root/'review/tech-static-pptx-pool.json'
    report=json.loads(report_path.read_text(encoding='utf-8'))
    report['batch5_pages']=list(CONFIG)
    report['static_pptx_total']=len(report['representative_pages'])+len(report['covers'])+len(report['closings'])+sum(len(report.get(key,[])) for key in ('additional_pages','batch3_pages','batch4_pages'))+len(CONFIG)
    report['tested_sample_count']=report['static_pptx_total']
    report['evidence']['batch5_gallery']='review/tech-8-static-pptx-batch5.jpg'
    dump(report_path,report)
    if update_manifest:
        files={p.relative_to(root).as_posix():digest(p) for p in root.rglob('*')
               if p.is_file() and '.git' not in p.parts and p.name not in
               ('knowledge-manifest.json','audit-report.json','blank.pptx','blank-red.pptx')
               and 'source-pages' not in p.relative_to(root).parts}
        dump(root/'knowledge-manifest.json',{'schema_version':'1.0','version':VERSION,
             'status':'draft_pending_review','file_count':len(files),'files':files})

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--library',type=Path,required=True)
    extend(parser.parse_args().library)
