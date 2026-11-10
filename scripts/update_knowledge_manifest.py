"""Rebuild hashes for every distributed knowledge-base file."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);a=p.parse_args()
 root=a.library.resolve();manifest_path=root/'knowledge-manifest.json'
 manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
 files={}
 for path in sorted(root.rglob('*')):
  if not path.is_file() or '.git' in path.relative_to(root).parts or path.name in ('knowledge-manifest.json','audit-report.json'):
   continue
  files[path.relative_to(root).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
 manifest['files']=files;manifest['file_count']=len(files)
 manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'file_count':len(files)},ensure_ascii=False))
if __name__=='__main__':main()
