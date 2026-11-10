"""Create an offline visual index of covers and reviewed component candidates."""
from __future__ import annotations
import argparse,html,json
from pathlib import Path

def card(entry):
    title=entry['id'];role=entry.get('role','')
    meta=' · '.join(str(x) for x in (entry.get('information_relation'),entry.get('color_family'),entry.get('style'),entry.get('visual_impact')) if x)
    preview=html.escape('../'+entry['preview'],quote=True)
    return (f'<article class="card" data-role="{html.escape(role,quote=True)}" data-color="{html.escape(str(entry.get("color_family","")),quote=True)}">'
            f'<img loading="lazy" src="{preview}" alt="{html.escape(title,quote=True)}">'
            f'<div class="body"><b>{html.escape(title)}</b><small>{html.escape(meta)}</small>'
            f'<span>{html.escape(entry.get("classification_status",""))} · {html.escape(entry.get("status",""))}</span></div></article>')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--library',type=Path,required=True);a=ap.parse_args()
    root=a.library.resolve();cat=json.loads((root/'catalog.json').read_text(encoding='utf-8'))['layouts']
    cover=[e for e in cat if e['role']=='cover'];representative=[e for e in cat if e.get('classification_status')=='visual_reviewed']
    style='''*{box-sizing:border-box}body{margin:0;background:#f4f7fc;color:#1e293b;font:16px system-ui,"Microsoft YaHei",sans-serif}
header{position:sticky;top:0;background:#fff;padding:16px 24px;box-shadow:0 2px 10px #0001;z-index:2}h1{margin:0 0 8px;font-size:22px}p{margin:4px 0;color:#64748b}select{padding:6px 12px;margin-right:8px}main{max-width:1500px;margin:auto;padding:24px}h2{margin:20px 0 14px}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px}.card{background:#fff;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden}.card img{display:block;width:100%;aspect-ratio:16/9;object-fit:contain;background:#e9eef6}.body{padding:12px;display:grid;gap:4px}small{color:#475569}.body span{color:#64748b;font-size:12px}article[hidden]{display:none}'''
    script='''function filter(){const color=document.querySelector('#color').value,role=document.querySelector('#role').value;document.querySelectorAll('article').forEach(x=>x.hidden=(color&&x.dataset.color!==color)||(role&&x.dataset.role!==role));}'''
    choices=''.join(f'<option value="{html.escape(v,quote=True)}">{html.escape(v)}</option>' for v in sorted({e.get('color_family','') for e in cover if e.get('color_family')}))
    roles=''.join(f'<option value="{html.escape(v,quote=True)}">{html.escape(v)}</option>' for v in sorted({e['role'] for e in representative}))
    page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>新模板知识库视觉索引</title><style>{style}</style><header><h1>新模板知识库视觉索引</h1><p>20 张封面及首批视觉初审内容页。标签是候选索引，仍需实填和放映验收。</p><label>封面色系 <select id="color" onchange="filter()"><option value="">全部</option>{choices}</select></label><label>内容角色 <select id="role" onchange="filter()"><option value="">全部</option>{roles}</select></label></header><main><h2>封面（{len(cover)}）</h2><section class="grid">{''.join(card(x) for x in cover)}</section><h2>首批内容组件（{len(representative)}）</h2><section class="grid">{''.join(card(x) for x in representative)}</section></main><script>{script}</script></html>'''
    out=root/'review'/'视觉索引.html';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(page,encoding='utf-8')
    print(out)
if __name__=='__main__':main()
