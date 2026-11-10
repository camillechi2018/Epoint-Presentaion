"""Publish six reviewed fixed-count PPTX tech layouts; keep HTML/motion closed."""
from __future__ import annotations
import argparse,json
from pathlib import Path

CONFIG={
  10:{'count':4,'relation':'navigation','parts':'4 个目录卡，编号、中文标题、英文说明一一对应',
      'paths':['english_heading','heading','item_1.number','item_1.title','item_1.english',
               'item_2.number','item_2.title','item_2.english','item_3.number','item_3.title','item_3.english',
               'item_4.number','item_4.title','item_4.english']},
  12:{'count':1,'relation':'section','parts':'章节数字、部分标识、中文标题与短副题',
      'paths':['section_number','part_label','heading','subtitle']},
  21:{'count':3,'relation':'key-points','parts':'顶部一项、下方两项，共三项重点；编号 3 固定',
      'paths':['heading','summary','item_1.title','item_1.subtitle','item_1.body',
               'item_2.title','item_2.subtitle','item_2.body','item_3.title','item_3.body',
               'item_3.subtitle','center.count','center.unit']},
  33:{'count':5,'relation':'parallel-points','parts':'五张等权竖卡：标题与正文一一对应，底部结论单独绑定',
      'paths':['heading','item_1.body','item_2.body','item_3.body','item_4.body','item_5.body',
               'item_1.title','item_2.title','item_3.title','item_4.title','item_5.title',
               'bottom_conclusion','summary']},
  40:{'count':2,'relation':'comparison','parts':'左右两主题及各自正文、两枚补充标签',
      'paths':['heading','left.title','right.title','right.tag_1','right.tag_2',
               'left.tag_1','left.tag_2','right.body','left.body','summary']},
  54:{'count':4,'relation':'process','parts':'四张等权卡；每张编号、标题、正文保持一组',
      'paths':['item_1.title','item_1.body','item_1.number',
               'item_4.title','item_4.body','item_4.number',
               'item_2.title','item_2.body','item_2.number',
               'item_3.title','item_3.body','item_3.number','heading','summary']},
}
DECOR_SHA={
  'a7987ab3608e616831f14be500efbe757d215402eda293657a9f92cf8af0ffdb',
  'b24518bfdd7d063a341220ad003884adaecb201e50c3c7e5e39b90948b34ca51',
}

def extend(root:Path,update_manifest=True):
  from import_tech_style import VERSION,digest,dump
  root=Path(root);catalog_path=root/'catalog.json'
  catalog=json.loads(catalog_path.read_text(encoding='utf-8'))
  for page,cfg in CONFIG.items():
    e=next(x for x in catalog['layouts'] if x.get('style_family')=='deep-blue-tech' and x['source_page']==page)
    folder=root/'layouts'/e['id']
    path=folder/'bindings.json';bindings=json.loads(path.read_text(encoding='utf-8'))
    if len(bindings['fields'])!=len(cfg['paths']) or len(set(cfg['paths']))!=len(cfg['paths']):
      raise ValueError(f'P{page:03d} field path count/uniqueness mismatch')
    for field,semantic in zip(bindings['fields'],cfg['paths']):
      if field.get('semantic_path') and field['semantic_path']!=semantic:raise ValueError(f'P{page:03d} semantic conflict')
      field['semantic_path']=semantic
      field['semantic_role']='reviewed_text'
    for obj in bindings.get('objects',{}).get('images',[]):
      if obj.get('semantic_role')!='source_media_unclassified':continue
      if obj['sha256'] not in DECOR_SHA:raise ValueError(f'P{page:03d} unknown source image')
      obj['semantic_role']='source_decorative_locked'
      obj['review_note']='与其他科技内容页同 SHA 的页眉光效，固定装饰；不读作业务内容。'
    dump(path,bindings)
    path=folder/'layout_rules.json';rules=json.loads(path.read_text(encoding='utf-8'))
    rules.update({'cardinality_mode':'fixed_verified','source_count':cfg['count'],
                  'supported_counts':[cfg['count']],'verified_counts':[cfg['count']],
                  'static_pptx_status':'verified_short_copy_draft',
                  'reflow_status':'fixed_count_only'})
    if page==12:rules['font_size_overrides_pt']={'10':68}
    dump(path,rules)
    review={'source_page':page,'component_id':e['id'],'information_relation':cfg['relation'],
            'source_item_count':cfg['count'],'component_parts':cfg['parts'],
            'content_fit_limit':'仅原生项数与短文案；长文需另测，其他项数须重新排版验收。',
            'review_status':'static_pptx_verified','field_binding_status':'reviewed',
            'normal_use_status':'static_pptx_verified_draft',
            'source_text_policy':'源稿文字、数字和图片中的案例只作版式来源，不作业务事实。',
            'verification_note':'虚构内容全字段实填、PowerPoint 渲染、文字边界、单 Logo 和媒体引用已核对；HTML、动效和扩展色分别验收。'}
    dump(folder/'semantic-review.json',review)
    e['classification_status']='verified';e['pptx_support']='verified_static_draft'
    e['visual_review_status']='powerpoint_render_checked'
    e['semantic_review']=(folder/'semantic-review.json').relative_to(root).as_posix()
    e['semantic_review_status']='static_pptx_verified'
  dump(catalog_path,catalog)
  report_path=root/'review/tech-static-pptx-pool.json'
  report=json.loads(report_path.read_text(encoding='utf-8'))
  report['additional_pages']=list(CONFIG)
  report['static_pptx_total']=len(report['representative_pages'])+len(report['covers'])+len(report['closings'])+len(CONFIG)
  report['tested_sample_count']=report['static_pptx_total']
  report['evidence']['additional_gallery']='review/tech-6-static-pptx-batch2.jpg'
  report['additional_family_coverage']=['four-card-directory','section','three-key-points',
      'five-parallel-cards','two-way-comparison','four-step-guide']
  dump(report_path,report)
  if update_manifest:
    files={p.relative_to(root).as_posix():digest(p) for p in root.rglob('*')
           if p.is_file() and '.git' not in p.parts and p.name not in
           ('knowledge-manifest.json','audit-report.json','blank.pptx','blank-red.pptx')
           and 'source-pages' not in p.relative_to(root).parts}
    dump(root/'knowledge-manifest.json',{'schema_version':'1.0','version':VERSION,
                                        'status':'draft_pending_review','file_count':len(files),'files':files})
if __name__=='__main__':
  p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True)
  extend(p.parse_args().library)
