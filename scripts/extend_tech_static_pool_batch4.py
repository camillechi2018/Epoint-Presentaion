"""Register eight additional fixed-count technology PPTX layouts."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from extend_tech_static_pool import DECOR_SHA

CONFIG={
  14:(1,'section',['part_label','heading','subtitle']),
  19:(5,'hierarchy',['center.topic','center.body','item_1.title','item_2.body','item_3.body','item_3.title','item_1.subtitle','item_4.body','item_5.body','item_5.title','item_4.title','heading','summary']),
  24:(5,'parallel-points',['tool_1.body','tool_2.body','step_1.title','step_1.body','step_2.title','step_2.body','step_3.title','step_3.body','tool_2.title','heading','summary','tool_1.title']),
  28:(2,'process',['heading','summary','left.issue_1','left.issue_2','left.issue_3','left.issue_4','left.issue_5','right.issue_1','right.issue_2','right.issue_3','right.issue_4','right.issue_5','phase_1.title','phase_2.title']),
  29:(2,'comparison',['right.title','left.title','heading','right.body','left.body','bottom.conclusion','summary']),
  30:(2,'cycle',['heading','left.title','left.body','right.title','right.body','goal','metric_3','metric_2','metric_1','summary']),
  31:(3,'parallel-points',['item_1.title','item_2.title','item_3.title','item_1.body','item_2.body','item_3.body','top_summary','heading','summary']),
  34:(5,'parallel-points',['item_1.body','item_1.title','item_2.body','item_2.title','item_3.body','item_3.title','item_4.body','item_4.title','item_5.body','item_5.title','heading','summary']),
}

def extend(root:Path,update_manifest=True):
    from import_tech_style import VERSION,digest,dump
    root=Path(root);catalog_path=root/'catalog.json'
    catalog=json.loads(catalog_path.read_text(encoding='utf-8'))
    for page,(count,relation,paths) in CONFIG.items():
        entry=next(e for e in catalog['layouts'] if e.get('style_family')=='deep-blue-tech' and e['source_page']==page)
        folder=root/'layouts'/entry['id']
        bindings=json.loads((folder/'bindings.json').read_text(encoding='utf-8'))
        if len(bindings['fields'])!=len(paths) or len(set(paths))!=len(paths):
            raise ValueError(f'P{page:03d} field mapping mismatch')
        for field,semantic in zip(bindings['fields'],paths):
            if field.get('semantic_path') and field['semantic_path']!=semantic:
                raise ValueError(f'P{page:03d} conflicting semantic path')
            field['semantic_path']=semantic;field['semantic_role']='reviewed_text'
        for obj in bindings.get('objects',{}).get('images',[]):
            if obj.get('semantic_role') not in ('source_media_unclassified','source_illustrative_locked'):continue
            if obj['sha256'] in DECOR_SHA or page==14:
                obj['semantic_role']='source_decorative_locked'
                obj['review_note']='固定科技装饰，不读作项目事实。'
            elif page==30 and obj['sha256'] in {
                'c35c4704b8bd8cb00c9b2a4655f3e1c3b84831fd27e879a177e7b435f0fc38a7',
                '1a62735faee9642e3d87b283ff9c21ae718d13f5db351eb8eac5b8cf8e893d5a'}:
                obj['semantic_role']='source_visual_locked'
                obj['review_note']='来源环内装饰图标，随当前科技风保留。'
            else:raise ValueError(f'P{page:03d} unknown source image {obj["sha256"]}')
        dump(folder/'bindings.json',bindings)
        rules=json.loads((folder/'layout_rules.json').read_text(encoding='utf-8'))
        rules.update({'cardinality_mode':'fixed_verified','source_count':count,
                      'supported_counts':[count],'verified_counts':[count],
                      'static_pptx_status':'verified_short_copy_draft','reflow_status':'fixed_count_only'})
        dump(folder/'layout_rules.json',rules)
        review={'source_page':page,'component_id':entry['id'],'information_relation':relation,
                'source_item_count':count,'content_fit_limit':'原生项数和短文案；长文及变项数另测。',
                'review_status':'static_pptx_verified','field_binding_status':'reviewed',
                'normal_use_status':'static_pptx_verified_draft',
                'source_text_policy':'源稿示例文字、数字不作为业务事实。',
                'verification_note':'虚构内容全字段实填、PowerPoint 渲染、文字边界、单 Logo 与媒体引用核对。'}
        dump(folder/'semantic-review.json',review)
        entry['information_relation']=relation
        entry['classification_status']='verified';entry['pptx_support']='verified_static_draft'
        entry['visual_review_status']='powerpoint_render_checked'
        entry['semantic_review']=(folder/'semantic-review.json').relative_to(root).as_posix()
        entry['semantic_review_status']='static_pptx_verified'
    dump(catalog_path,catalog)
    report_path=root/'review/tech-static-pptx-pool.json'
    report=json.loads(report_path.read_text(encoding='utf-8'))
    report['batch4_pages']=list(CONFIG)
    report['static_pptx_total']=len(report['representative_pages'])+len(report['covers'])+len(report['closings'])+len(report.get('additional_pages',[]))+len(report.get('batch3_pages',[]))+len(CONFIG)
    report['tested_sample_count']=report['static_pptx_total']
    report['evidence']['batch4_gallery']='review/tech-8-static-pptx-batch4.jpg'
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
