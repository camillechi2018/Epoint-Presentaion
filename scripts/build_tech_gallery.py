"""Create a compact visual review index for the 85-page tech source."""
from __future__ import annotations
import argparse, html, json
from pathlib import Path


def build(root: Path) -> Path:
    entries = [x for x in json.loads((root / 'catalog.json').read_text(encoding='utf-8'))['layouts']
               if x.get('style_family') == 'deep-blue-tech']
    entries.sort(key=lambda x: x['source_page'])
    groups = [('封面', 'cover'), ('目录', 'directory'), ('大标题页', 'section'),
              ('内容页', 'content'), ('图表', 'data-chart'), ('时间与计划', 'schedule'), ('封底', 'closing')]
    css = '''body{font:15px Microsoft YaHei,Arial,sans-serif;margin:0;background:#0b1730;color:#eaf2ff}
    header{position:sticky;top:0;background:#102146;padding:16px 24px;z-index:2;border-bottom:1px solid #345}
    h1{margin:0 0 8px;font-size:24px}nav a{color:#8edaff;margin-right:18px}main{padding:20px}
    h2{border-left:4px solid #39ceee;padding-left:12px;margin-top:34px}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:18px}
    article{background:#14284d;border:1px solid #2b4c76;border-radius:10px;overflow:hidden}article img{width:100%;aspect-ratio:16/9;object-fit:contain;background:#060b18}
    .meta{padding:10px 14px}.name{font-weight:bold}.sub{font-size:12px;color:#a4bad7;margin-top:4px;line-height:1.6}
    .flag{color:#ffcb78}'''
    nav = ''.join(f'<a href="#{role}">{label}</a>' for label, role in groups)
    sections = []
    for label, role in groups:
        selected = [e for e in entries if e['role'] == role]
        if not selected: continue
        cards = []
        for e in selected:
            preview = '../' + e['preview']
            bits = [f'来源 P{e["source_page"]:03d}', f'对象 {e["shape_count"]}',
                    f'关系 {e.get("information_relation", "-")}',
                    f'项数 {e.get("cardinality_status", "待验收")}',
                    f'动效 {e.get("motion_support", "待验收")}']
            if role in ('cover', 'closing'):
                bits += [f'风格 {e.get("style", "待验收")}', f'视觉冲击 {e.get("visual_impact", "待验收")}']
            cards.append(f'<article><img loading="lazy" src="{html.escape(preview)}" alt="P{e["source_page"]:03d}">'
                         f'<div class="meta"><div class="name">{html.escape(e["id"])} · P{e["source_page"]:03d}</div>'
                         f'<div class="sub">{html.escape(" · ".join(bits))}</div></div></article>')
        sections.append(f'<section id="{role}"><h2>{label} · {len(selected)} 页</h2><div class="grid">{"".join(cards)}</div></section>')
    page = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>深蓝科技风 · 85 页拆解索引</title><style>{css}</style><header><h1>深蓝科技风 · 85 页拆解索引</h1><div class="flag">来源与结构初拆；封面匹配、项数、动效、换色与 HTML 尚需逐页验收</div><nav>{nav}</nav></header><main>{''.join(sections)}</main></html>'''
    out = root / 'review' / '深蓝科技风85页索引.html'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding='utf-8')
    return out


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--library', type=Path, required=True)
    print(build(p.parse_args().library))
