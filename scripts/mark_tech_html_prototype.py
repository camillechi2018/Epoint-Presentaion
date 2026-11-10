"""Register the reviewed browser prototype without opening HTML for normal planning."""
from __future__ import annotations
import argparse,json
from pathlib import Path

def mark(root:Path,update_manifest=True):
    from import_tech_style import VERSION,digest,dump
    root=Path(root)
    catalog_path=root/'catalog.json'
    catalog=json.loads(catalog_path.read_text(encoding='utf-8'))
    entry=next(x for x in catalog['layouts'] if x['id']=='cover-tech-001')
    entry['html_support']='prototype_requires_cross_format_review'
    entry['html_prototype']='review/tech-cover-001-html-prototype.png'
    dump(catalog_path,catalog)
    if update_manifest:
        files={p.relative_to(root).as_posix():digest(p) for p in root.rglob('*')
               if p.is_file() and '.git' not in p.parts and p.name not in
               ('knowledge-manifest.json','audit-report.json','blank.pptx','blank-red.pptx')
               and 'source-pages' not in p.relative_to(root).parts}
        dump(root/'knowledge-manifest.json',{'schema_version':'1.0','version':VERSION,
            'status':'draft_pending_review','file_count':len(files),'files':files})

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--library',type=Path,required=True)
    mark(ap.parse_args().library)
