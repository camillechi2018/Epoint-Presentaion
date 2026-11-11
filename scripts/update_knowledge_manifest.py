"""Normalize tracked release files then hash final bytes; stage intended new files first."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from distribution import normalize_files, refresh_manifest
from prepare_distribution import tracked_files

def main():
 p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);a=p.parse_args()
 root=a.library.resolve(); paths=tracked_files(root)
 changed=normalize_files(root,paths)
 manifest=refresh_manifest(root,paths)
 print(json.dumps({'file_count':manifest['file_count'],'normalized_files':len(changed)}))
if __name__=='__main__':main()
