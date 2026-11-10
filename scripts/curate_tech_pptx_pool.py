"""Conservative text capacities found by PowerPoint render stress tests."""
from __future__ import annotations
import argparse,json
from pathlib import Path

COVER_LIMITS={
  1:{'text_6':8,'text_4':30},
  2:{'text_7':4,'text_6':8},
  3:{'text_9':8},
  4:{'text_7':8},
  5:{'text_23':6},
  82:{'text_22':4,'text_25':6},
  83:{'text_339':4,'text_338':6},
  84:{'text_29':4},
  85:{'text_5':8},
}
FONT_SIZE_OVERRIDES={
  16:{6:22,7:22,8:22,20:22,21:22},
  75:{94:17},
  83:{339:78},
}

def curate(root:Path,update_manifest=True):
  from import_tech_style import VERSION,digest,dump
  root=Path(root)
  catalog_path=root/'catalog.json'
  cat=json.loads(catalog_path.read_text(encoding='utf-8'))
  for page,limits in COVER_LIMITS.items():
    entry=next(x for x in cat['layouts'] if x.get('style_family')=='deep-blue-tech' and x['source_page']==page)
    path=root/entry['bindings']; data=json.loads(path.read_text(encoding='utf-8'))
    fields={f['field']:f for f in data['fields']}
    for field,limit in limits.items():
      if field not in fields:raise ValueError(f'P{page:03d} field missing: {field}')
      fields[field]['max_chars']=limit
      fields[field]['max_lines']=1
      fields[field]['capacity_status']='powerpoint_short_title_tested'
    dump(path,data)
    rules_path=root/entry['layout_rules']
    rules=json.loads(rules_path.read_text(encoding='utf-8'))
    rules['title_pressure_test']={
      'tested_cjk_lengths':[8,16,24],
      'safe_title_chars':limits[next(iter(limits))],
      'status':'conservative_short_copy_only',
      'overflow_policy':'reject_and_select_another_layout_or_split_title',
    }
    if page in FONT_SIZE_OVERRIDES:rules['font_size_overrides_pt']={str(k):v for k,v in FONT_SIZE_OVERRIDES[page].items()}
    dump(rules_path,rules)
    entry['title_pressure_status']='tested_short_copy_only'
  for page,overrides in FONT_SIZE_OVERRIDES.items():
    if page in COVER_LIMITS:continue
    entry=next(x for x in cat['layouts'] if x.get('style_family')=='deep-blue-tech' and x['source_page']==page)
    path=root/entry['layout_rules'];rules=json.loads(path.read_text(encoding='utf-8'))
    rules['font_size_overrides_pt']={str(k):v for k,v in overrides.items()}
    dump(path,rules)
  dump(catalog_path,cat)
  if update_manifest:
    files={p.relative_to(root).as_posix():digest(p) for p in root.rglob('*')
           if p.is_file() and '.git' not in p.parts and p.name not in
           ('knowledge-manifest.json','audit-report.json','blank.pptx','blank-red.pptx')
           and 'source-pages' not in p.relative_to(root).parts}
    dump(root/'knowledge-manifest.json',{'schema_version':'1.0','version':VERSION,
                                         'status':'draft_pending_review','file_count':len(files),'files':files})

if __name__=='__main__':
  parser=argparse.ArgumentParser();parser.add_argument('--library',type=Path,required=True)
  curate(parser.parse_args().library)
