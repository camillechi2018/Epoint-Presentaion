"""Publish the reviewed static PPTX pool without upgrading motion or HTML."""
from __future__ import annotations
import argparse,json
from pathlib import Path

PAGES=[6,11,16,22,26,32,38,42,45,53,64,69,71,75,77,81]
BOOKENDS=[1,2,3,4,5,82,83,84,85]
SEMANTIC_PATHS={
  6:['english_heading','chapter_1.title','chapter_2.title','chapter_3.title','chapter_4.title','chapter_5.title',
     'chapter_1.number','chapter_2.number','chapter_3.number','chapter_4.number','chapter_5.number','heading',
     'chapter_1.english','chapter_2.english','chapter_3.english','chapter_4.english','chapter_5.english'],
  11:['section_number','heading','english_subtitle'],
  16:['item_3.label','item_4.label','item_5.label','item_1.body','item_2.body','item_3.body','item_4.body',
      'item_1.label','item_2.label','item_5.body','center.count','center.unit','heading','summary'],
  22:['heading','layer_3.pyramid','layer_2.pyramid','layer_1.pyramid','native_hatch_1','layer_3.badge',
      'layer_1.description','layer_2.description','layer_3.description','native_hatch_2',
      'layer_2.badge','native_hatch_3','layer_1.badge','summary'],
  26:['heading','summary','issue_1.title','issue_1.body','issue_2.title','issue_2.body','issue_3.title',
      'issue_3.body','issue_4.title','issue_4.body','issue_1.number','issue_3.number','issue_4.number','issue_2.number'],
  32:['item_1.title','item_1.number','item_1.body_a','item_1.body_b','item_2.title','item_2.number',
      'item_2.body_a','item_2.body_b','item_3.title','item_3.number','item_3.body_a','item_3.body_b',
      'item_4.title','item_4.number','item_4.body_a','item_4.body_b','heading','summary'],
  38:['heading','summary','item_1.number','item_1.title','item_2.title','item_3.title','item_4.title',
      'item_4.number','item_3.number','item_2.number','item_4.body','item_3.body','item_2.body','item_1.body'],
  42:['heading','item_4.title','item_3.title','item_1.title','item_2.title','item_1.body',
      'item_2.body','item_4.body','item_3.body','center.conclusion'],
  45:['item_2.body','item_1.body','heading','summary','item_3.body','item_4.body','item_4.step',
      'item_4.title','item_2.step','item_2.title','item_1.step','item_1.title','item_3.step','item_3.title'],
  53:['heading','metric_3.label','metric_1.value','metric_2.value','metric_3.value','metric_1.label',
      'metric_1.body','metric_2.label','metric_2.body','metric_3.body'],
  64:['heading','summary','item_1.event','item_1.year','item_2.event','item_2.year','item_3.event',
      'item_3.year','item_4.event','item_4.year','item_5.event','item_5.year'],
  69:['table.time_heading','table.activity_heading','table.owner_heading','row_1.activity','row_4.activity',
      'row_5.activity','row_6.activity','row_2.activity','row_1.time','row_4.time','row_5.time',
      'row_6.time','row_2.time','row_3.time','row_1.owner','row_4.owner','row_5.owner','row_6.owner',
      'row_2.owner','row_3.owner','row_3.activity','heading','summary'],
  71:['heading','summary','conclusion','chart_caption'],
  75:['kpi_1.label','kpi_1.value','kpi_2.label','kpi_2.value','kpi_3.label','kpi_3.value',
      'heading','chart_label','trend_note'],
  77:['tier_1.label','tier_2.label','tier_3.label','tier_4.label','tier_1.description','tier_2.description',
      'tier_3.description','tier_4.description','pyramid_caption','pyramid_summary','heading',
      'tier_1.ratio_label','tier_1.ratio','tier_2.ratio_label','tier_2.ratio',
      'tier_3.ratio_label','tier_3.ratio','tier_4.ratio_label','tier_4.ratio'],
  81:['heading','stage_1.title','stage_2.title','stage_3.title',
      'stage_1.body','stage_2.body','stage_3.body'],
}
BOOKEND_PATHS={
  1:['english_title','title','presenter','date'],
  2:['main_title','title','date','presenter'],
  3:['title','subtitle'],4:['title','place_date'],5:['title','speaker'],
  82:['thanks_title','english_label'],83:['english_label','thanks_title'],
  84:['thanks_title','english_label'],85:['project_subtitle','thanks_title'],
}

def finalize(root:Path,update_manifest=True):
  from import_tech_style import VERSION,digest,dump
  from curate_tech_pptx_pool import COVER_LIMITS
  root=Path(root);catalog_path=root/'catalog.json'
  catalog=json.loads(catalog_path.read_text(encoding='utf-8'))
  for page in PAGES+BOOKENDS:
    entry=next(x for x in catalog['layouts'] if x.get('style_family')=='deep-blue-tech' and x['source_page']==page)
    folder=root/'layouts'/entry['id'];binding_path=folder/'bindings.json'
    bindings=json.loads(binding_path.read_text(encoding='utf-8'))
    paths=(SEMANTIC_PATHS if page in PAGES else BOOKEND_PATHS)[page]
    if len(paths)!=len(bindings['fields']) or len(set(paths))!=len(paths):
      raise ValueError(f'P{page:03d} semantic path count/uniqueness')
    for field,path in zip(bindings['fields'],paths):
      if field.get('semantic_path') and field['semantic_path']!=path:
        raise ValueError(f'P{page:03d} semantic path conflict: {field["field"]}')
      field['semantic_path']=path
      if field.get('semantic_role') not in ('decoration_locked','computed_item_count','computed_item_number'):
        field['semantic_role']='reviewed_text'
    tree=json.loads((folder/'shape-tree.json').read_text(encoding='utf-8'))['recursive_shapes']
    tree_by_id={x['shape_id']:x for x in tree}
    for image in bindings.get('objects',{}).get('images',[]):
      if image.get('semantic_role')!='source_media_unclassified':continue
      sid=image['shape_id'];bounds=tree_by_id[sid]['local_bounds_emu']
      if page==81 and sid==12:
        image['semantic_role']='source_visual_locked'
        image['review_note']='源稿漏斗主体图形，固定结构使用；不得当成可替换业务图片。'
      else:
        image['semantic_role']='source_decorative_locked'
        image['review_note']='来源页眉、光效或指标底纹装饰；保留原件，内容不从图片读取。'
      image['source_bounds_emu']=bounds
    dump(binding_path,bindings)
    rules_path=folder/'layout_rules.json'
    rules=json.loads(rules_path.read_text(encoding='utf-8'))
    rules['static_pptx_status']='verified_short_copy_draft'
    rules['static_pptx_source_count']=rules.get('source_count')
    if page==38:rules['verified_counts']=[4]
    if page==69:rules['verified_counts']=[6]
    dump(rules_path,rules)
    entry['classification_status']='verified'
    entry['pptx_support']='verified_static_draft'
    entry['visual_review_status']='powerpoint_render_checked'
    if page in PAGES:
      review_path=folder/'semantic-review.json'
      review=json.loads(review_path.read_text(encoding='utf-8'))
      review['field_binding_status']='reviewed'
      review['normal_use_status']='static_pptx_verified_draft'
      review['review_status']='static_pptx_verified'
      review['verification_note']='虚构内容实填、PowerPoint 渲染、文字边界、单 Logo 与图片 fallback 已核对；HTML、动效和扩展色分别验收。'
      dump(review_path,review)
      entry['semantic_review_status']='static_pptx_verified'
  dump(catalog_path,catalog)
  report={'schema_version':'1.0','status':'static_pptx_verified_draft',
          'representative_pages':PAGES,'covers':[1,2,3,4,5],'closings':[82,83,84,85],
          'sample_policy':'fictitious_data_only',
          'tested_sample_count':25,
          'title_pressure_cases':27,
          'title_limits':{str(page):limits for page,limits in COVER_LIMITS.items()},
          'source_fixed_counts_only':{'38':4,'69':6},
          'checks':['PowerPoint open/export','actual_text_bounds','one_logo_per_page','svg_primary_fallback',
                    'native_editable_chart_71_75','source_image_semantics','short_title_pressure'],
          'excluded_capabilities':['html','motion','theme_recolor','unverified_item_counts','long_titles'],
          'chart_verification':{'71':'one native line chart, 5 categories and one replaced series',
                                '75':'one native combo chart, 7 categories and two replaced series'},
          'visual_review':'16 representative and 9 short-copy bookend slides inspected in contact sheets',
          'brand_status':'one valid logo on each of 25 normal-filled samples',
          'evidence':{'representative_gallery':'review/tech-16-static-pptx.jpg',
                      'safe_bookends_gallery':'review/tech-9-short-title.jpg'}}
  dump(root/'review/tech-static-pptx-pool.json',report)
  if update_manifest:
    files={p.relative_to(root).as_posix():digest(p) for p in root.rglob('*')
           if p.is_file() and '.git' not in p.parts and p.name not in
           ('knowledge-manifest.json','audit-report.json','blank.pptx','blank-red.pptx')
           and 'source-pages' not in p.relative_to(root).parts}
    dump(root/'knowledge-manifest.json',{'schema_version':'1.0','version':VERSION,
                                        'status':'draft_pending_review','file_count':len(files),'files':files})

if __name__=='__main__':
  parser=argparse.ArgumentParser();parser.add_argument('--library',type=Path,required=True)
  finalize(parser.parse_args().library)
