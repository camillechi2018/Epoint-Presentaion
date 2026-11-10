"""Reproducible source baseline for the 85-page tech template."""
from __future__ import annotations
import argparse,json,re
from collections import Counter
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile
from pptx import Presentation

def build(root:Path,update_manifest=True):
  from import_tech_style import VERSION,digest,dump
  root=Path(root);source=root/'sources/tech.pptx';p=Presentation(source)
  catalog=json.loads((root/'catalog.json').read_text(encoding='utf-8'))['layouts']
  tech=[e for e in catalog if e.get('style_family')=='deep-blue-tech']
  recursive=sum(len(json.loads((root/e['shape_tree']).read_text(encoding='utf-8'))['recursive_shapes']) for e in tech)
  top=sum(len(s.shapes) for s in p.slides)
  tables=sum(1 for slide in p.slides for shape in slide.shapes if shape.has_table)
  media=Counter();notes=0
  with ZipFile(source) as z:
    for name in z.namelist():
      if name.startswith('ppt/media/') and not name.endswith('/'):
        media[Path(name).suffix.lower()]+=1
      if re.fullmatch(r'ppt/notesSlides/notesSlide\d+\.xml',name):notes+=1
  inventory=json.loads((root/'color-inventory-tech.json').read_text(encoding='utf-8'))
  report={'schema_version':'1.0','status':'source_structure_checked','source':'sources/tech.pptx',
    'source_sha256':sha256(source.read_bytes()).hexdigest(),'source_bytes':source.stat().st_size,
    'slide_count':len(p.slides),'canvas_inches':[round(p.slide_width/914400,3),round(p.slide_height/914400,3)],
    'catalog_entries':len(tech),'source_previews':len(list((root/'source-previews/tech').glob('P*.png'))),
    'top_level_shapes':top,'recursive_shape_records':recursive,'source_logo_pages':sum(bool(e.get('source_logo_present')) for e in tech),
    'native_charts':inventory['totals']['charts'],'native_tables':tables,'notes_slides':notes,
    'media_by_extension':dict(media),'color_inventory':'color-inventory-tech.json',
    'limits':['结构和源文件核对不等于 85 页逐页内容、字体、视觉、放映验收。']}
  if len(p.slides)!=85 or len(tech)!=85 or report['source_previews']!=85 or report['native_charts']!=12:
    raise ValueError('科技来源基线数量不符')
  dump(root/'review/tech-source-audit.json',report)
  if update_manifest:
    files={p.relative_to(root).as_posix():digest(p) for p in root.rglob('*')
           if p.is_file() and '.git' not in p.parts and p.name not in
           ('knowledge-manifest.json','audit-report.json','blank.pptx','blank-red.pptx')
           and 'source-pages' not in p.relative_to(root).parts}
    dump(root/'knowledge-manifest.json',{'schema_version':'1.0','version':VERSION,
                                        'status':'draft_pending_review','file_count':len(files),'files':files})
  return report
if __name__=='__main__':
  p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True)
  x=build(p.parse_args().library)
  print(json.dumps({k:x[k] for k in ('status','source_sha256','slide_count','catalog_entries','source_previews','native_charts')},ensure_ascii=False))
