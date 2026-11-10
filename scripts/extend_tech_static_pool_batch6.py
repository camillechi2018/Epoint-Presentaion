"""Register the sixth batch of source-count technology draft layouts."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from extend_tech_static_pool import DECOR_SHA

# P066 adds two fixed blue glow arcs above the milestone wave.
FIXED_DECOR_SHA=DECOR_SHA|{
  'c31a78caf416ad63296b42cce92f0e28517e2d66ec610289505036f48769dc43',
  '033b30d473a6d57f425cdb03e9f24bb4fab33418289c57343357ee82f6a7eec5',
}

CONFIG = {
  17:(4,'metrics',['center.topic','metric_1.label','metric_2.label','metric_3.label','metric_4.label','foundation.topic','metric_1.value','metric_1.name','metric_2.value','metric_2.name','metric_3.value','metric_3.name','metric_4.value','metric_4.name','heading','summary']),
  58:(6,'cycle',['heading','summary','center.topic','decorative.ring_ticks','center.subtitle','partner_1','partner_2','partner_3','partner_4','partner_5','partner_6']),
  59:(5,'hierarchy',['heading','summary','center.topic','capability_1.title','capability_1.body','capability_2.title','capability_2.body','capability_3.title','capability_3.body','capability_4.title','capability_4.body','capability_5.title','capability_5.body']),
  60:(4,'hierarchy',['heading','pillar_1.title','pillar_2.title','pillar_2.body','pillar_3.title','pillar_4.title','pillar_4.body','pillar_3.body','pillar_1.body','center.topic','summary']),
  61:(3,'hierarchy',['heading','pillar_1.body','pillar_1.title','pillar_2.title','pillar_2.body','pillar_3.title','pillar_3.body','pillar_3.detail','pillar_1.detail','center.topic']),
  63:(5,'timeline',['heading','summary','milestone_1.body','milestone_1.year','milestone_2.body','milestone_2.year','milestone_4.body','milestone_4.year','milestone_5.body','milestone_5.year','milestone_3.body','milestone_3.year']),
  65:(5,'timeline',['heading','summary','milestone_2.date','milestone_2.body','milestone_4.date','milestone_4.body','milestone_3.body','milestone_3.date','milestone_5.date','milestone_5.body','milestone_1.body','milestone_1.date']),
  66:(7,'timeline',['heading','milestone_1','milestone_2','milestone_3','milestone_4','milestone_5','milestone_6','milestone_7']),
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
            field['semantic_path']=semantic;field['semantic_role']='source_decorative_locked' if semantic.startswith('decorative.') else 'reviewed_text'
        for obj in bindings.get('objects',{}).get('images',[]):
            if obj.get('semantic_role')!='source_media_unclassified':continue
            if obj['sha256'] not in FIXED_DECOR_SHA:raise ValueError(f'P{page:03d} unknown media {obj["sha256"]}')
            obj['semantic_role']='source_decorative_locked';obj['review_note']='固定科技背景与装饰，不作业务事实。'
        dump(folder/'bindings.json',bindings)
        rules=json.loads((folder/'layout_rules.json').read_text(encoding='utf-8'))
        rules.update({'cardinality_mode':'fixed_verified','source_count':count,'supported_counts':[count],
                      'verified_counts':[count],'static_pptx_status':'verified_short_copy_draft','reflow_status':'fixed_count_only'})
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
    report_path=root/'review/tech-static-pptx-pool.json';report=json.loads(report_path.read_text(encoding='utf-8'))
    report['batch6_pages']=list(CONFIG)
    report['static_pptx_total']=len(report['representative_pages'])+len(report['covers'])+len(report['closings'])+sum(len(report.get(key,[])) for key in ('additional_pages','batch3_pages','batch4_pages','batch5_pages'))+len(CONFIG)
    report['tested_sample_count']=report['static_pptx_total']
    report['visual_review']='63 个科技风固定项数短文案样张已经 PowerPoint 导出并逐批目视复核；第五、六批总览见对应证据。'
    report['brand_status']='63 个科技风常规实填样张逐页通过单 Logo 检查。'
    report['evidence']['batch6_gallery']='review/tech-8-static-pptx-batch6.jpg'
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
