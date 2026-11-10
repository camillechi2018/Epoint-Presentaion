"""Publish eight fixed-count, short-copy technology layouts after PPTX review."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from extend_tech_static_pool import DECOR_SHA

CONFIG={
  7:(5,'navigation',{'text_5':'item_1.number','text_6':'heading','text_7':'english_heading','text_14':'item_1.title','text_15':'item_1.english','text_21':'item_2.title','text_23':'item_2.english','text_25':'item_3.title','text_26':'item_3.english','text_28':'item_4.title','text_29':'item_4.english','text_30':'item_5.title','text_31':'item_5.english','text_34':'item_5.number','text_41':'item_4.number','text_42':'item_3.number','text_43':'item_2.number'}),
  8:(5,'navigation',{'text_16':'item_1.title','text_17':'item_1.english','text_22':'item_2.title','text_24':'item_2.english','text_35':'item_3.title','text_36':'item_3.english','text_40':'item_4.title','text_44':'item_4.english','text_48':'item_5.title','text_49':'item_5.english','text_10':'english_heading','text_54':'heading','text_124':'item_1.number','text_138':'item_2.number','text_151':'item_3.number','text_164':'item_4.number','text_177':'item_5.number'}),
  13:(1,'section',{'text_10':'heading','text_13':'subtitle','text_9':'part_label'}),
  15:(1,'section',{'text_5':'heading','text_6':'english_heading','text_3':'section_number'}),
  18:(3,'hierarchy',{'text_121':'tier_1.body','text_122':'tier_2.body','text_120':'tier_3.body','text_128':'heading','text_129':'summary','text_112':'left_support','text_169':'right_support'}),
  20:(6,'parallel-points',{'text_1086':'heading','text_1087':'summary','text_23':'left_1.title','text_1037':'left_2.title','text_1041':'left_3.title','text_1075':'right_1.title','text_1072':'right_2.title','text_1069':'right_3.title','text_1103':'center.topic'}),
  23:(2,'parallel-points',{'text_22':'heading','text_23':'summary','text_48':'left.body','text_49':'right.body','text_47':'right.title','text_46':'left.title'}),
  37:(3,'parallel-points',{'text_819':'item_1.body','text_820':'item_1.title','text_821':'item_2.body','text_822':'item_2.title','text_823':'item_3.body','text_824':'item_3.title','text_1919':'heading','text_1920':'summary'}),
}
FONT_OVERRIDES={8:{'54':57},13:{'10':116},15:{'3':220}}

def extend(root:Path,update_manifest=True):
  from import_tech_style import VERSION,digest,dump
  root=Path(root);catalog_path=root/'catalog.json'
  catalog=json.loads(catalog_path.read_text(encoding='utf-8'))
  for page,(count,relation,paths) in CONFIG.items():
    e=next(x for x in catalog['layouts'] if x.get('style_family')=='deep-blue-tech' and x['source_page']==page)
    folder=root/'layouts'/e['id']
    bindings=json.loads((folder/'bindings.json').read_text(encoding='utf-8'))
    if set(paths)!={f['field'] for f in bindings['fields']} or len(set(paths.values()))!=len(paths):
      raise ValueError(f'P{page:03d} field/path mismatch')
    for field in bindings['fields']:
      semantic=paths[field['field']]
      if field.get('semantic_path') and field['semantic_path']!=semantic:raise ValueError(f'P{page:03d} semantic conflict')
      field['semantic_path']=semantic;field['semantic_role']='reviewed_text'
    for obj in bindings.get('objects',{}).get('images',[]):
      if obj.get('semantic_role')!='source_media_unclassified':continue
      if obj['sha256'] not in DECOR_SHA:raise ValueError(f'P{page:03d} unknown source image')
      obj['semantic_role']='source_decorative_locked'
      obj['review_note']='与科技内容页同 SHA 的页眉光效，固定装饰。'
    dump(folder/'bindings.json',bindings)
    rules=json.loads((folder/'layout_rules.json').read_text(encoding='utf-8'))
    rules.update({'cardinality_mode':'fixed_verified','source_count':count,
                  'supported_counts':[count],'verified_counts':[count],
                  'static_pptx_status':'verified_short_copy_draft','reflow_status':'fixed_count_only'})
    if page in FONT_OVERRIDES:rules['font_size_overrides_pt']=FONT_OVERRIDES[page]
    dump(folder/'layout_rules.json',rules)
    review={'source_page':page,'component_id':e['id'],'information_relation':relation,
            'source_item_count':count,'content_fit_limit':'仅原生项数与短文案；长文和变项数另测。',
            'review_status':'static_pptx_verified','field_binding_status':'reviewed',
            'normal_use_status':'static_pptx_verified_draft',
            'source_text_policy':'源稿示例文字与数字只作版式参考，不作项目事实。',
            'verification_note':'虚构内容全字段实填、PowerPoint 渲染、文字边界、单 Logo 和媒体引用核对。'}
    dump(folder/'semantic-review.json',review)
    e['classification_status']='verified';e['pptx_support']='verified_static_draft'
    e['visual_review_status']='powerpoint_render_checked'
    e['semantic_review']=(folder/'semantic-review.json').relative_to(root).as_posix()
    e['semantic_review_status']='static_pptx_verified'
  dump(catalog_path,catalog)
  report_path=root/'review/tech-static-pptx-pool.json'
  report=json.loads(report_path.read_text(encoding='utf-8'))
  report['batch3_pages']=list(CONFIG)
  report['static_pptx_total']=len(report['representative_pages'])+len(report['covers'])+len(report['closings'])+len(report.get('additional_pages',[]))+len(CONFIG)
  report['tested_sample_count']=report['static_pptx_total']
  report['evidence']['batch3_gallery']='review/tech-8-static-pptx-batch3.jpg'
  dump(report_path,report)
  if update_manifest:
    files={p.relative_to(root).as_posix():digest(p) for p in root.rglob('*')
           if p.is_file() and '.git' not in p.parts and p.name not in
           ('knowledge-manifest.json','audit-report.json','blank.pptx','blank-red.pptx')
           and 'source-pages' not in p.relative_to(root).parts}
    dump(root/'knowledge-manifest.json',{'schema_version':'1.0','version':VERSION,
         'status':'draft_pending_review','file_count':len(files),'files':files})

if __name__=='__main__':
  ap=argparse.ArgumentParser();ap.add_argument('--library',type=Path,required=True)
  extend(ap.parse_args().library)
