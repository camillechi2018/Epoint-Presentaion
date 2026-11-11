"""Rebuild hashes for every distributed knowledge-base file."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import subprocess
from distribution import normalize_files, write_json

def main():
 p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);a=p.parse_args()
 root=a.library.resolve();manifest_path=root/'knowledge-manifest.json'
 manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
 files={}
 tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode('utf-8').split('\0')
 tracked = [rel for rel in tracked if rel and (root / rel).is_file()]
 normalize_files(root, tracked)
 for relative in sorted(tracked):
  path = root / relative
  if path.name in ('knowledge-manifest.json','audit-report.json'):
   continue
  files[path.relative_to(root).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
 manifest['files']=files;manifest['file_count']=len(files)
 write_json(manifest_path, manifest)
 print(json.dumps({'file_count':len(files)},ensure_ascii=False))
if __name__=='__main__':main()
