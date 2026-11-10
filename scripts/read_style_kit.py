"""Expose a portable style brief and absolute visual-reference paths."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from library_location import SKILL
from run_presentation import style_assets


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--theme', required=True, choices=['blue','red','deep-blue-tech'])
    p.add_argument('--out', type=Path)
    args = p.parse_args()
    state = style_assets(args.theme)
    if not state['ready']:
        raise SystemExit(json.dumps(state, ensure_ascii=False))
    profile = json.loads(Path(state['style_path']).read_text(encoding='utf-8'))
    composition = json.loads((Path(state['style_path']).parent.parent / 'composition-rules.json').read_text(encoding='utf-8'))
    result = {'theme': args.theme, 'style_family': profile['style_family'],
              'visual_rules': profile['visual_rules'],
              'layout_principles': profile['layout_principles'],
              'composition_recipes': profile['composition_recipes'],
              'composition_rules': {**composition['relationship_recipes'],
                                    'card_grid': composition['card_grid'],
                                    'density_thresholds': composition['density_thresholds'],
                                    'style_specific': composition['style_specific'][args.theme],
                                    'source_examples': composition['examples'][args.theme]},
              'colors': profile['colors'], 'typography': profile['typography'],
              'prohibitions': profile['prohibitions'],
              'samples': [{**row, 'absolute_path': str((Path(state['style_path']).parent / row['preview']).resolve())}
                          for row in profile['sample_records']],
              'visual_references_loaded': False,
              'note': '预览路径仅说明可读取；Agent 实际打开图像后才可将 visual_references_loaded 标为 true。'}
    serialized = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        if args.out.exists():
            p.error('输出文件已存在')
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(serialized, encoding='utf-8')
    print(serialized)


if __name__ == '__main__':
    main()
