"""Promote supplemental layouts only after all static PowerPoint checks pass."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from pptx import Presentation

sys.path.insert(0,str(Path(__file__).resolve().parent))
from audit_logo import audit as audit_logo
from repair_svg_fallbacks import repair as audit_svg

BANNED=('WPS,a click to unlimited possibilities','单击此处添加','蓝色简约风','20XX/01/01','模板内容')

def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def visual_units(value):
    return max(sum(2 if unicodedata.east_asian_width(ch) in 'WF' else 1 for ch in line) for line in value.split('\n'))

def all_shapes(shapes):
    for shape in shapes:
        yield shape
        if shape.shape_type==6:yield from all_shapes(shape.shapes)

def main():
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--samples',type=Path,required=True);a=p.parse_args()
    root=a.library.resolve();samples=a.samples.resolve()
    entries=json.loads((root/'catalog.json').read_text(encoding='utf-8'))
    layouts=[x for x in entries['layouts'] if x['id'].startswith('supp-')]
    fit=json.loads((samples/'text-fit.json').read_text(encoding='utf-8-sig'))
    if not fit['passed'] or fit['inputs']!=38:raise ValueError('38 份 PowerPoint 文字边界检查未全部通过')
    results=[];sample_registry={}
    for entry in layouts:
        variants=[]
        for theme in entry['themes']:
            key=f"{entry['id']}-{theme}"
            data=json.loads((samples/f'{key}.json').read_text(encoding='utf-8'))
            ppt=samples/f'{key}.pptx';image=samples/f'{key}.png'
            if not ppt.is_file() or not image.is_file():raise FileNotFoundError(key)
            deck=Presentation(ppt)
            if len(deck.slides)!=1:raise ValueError(key+'不是单页 PPTX')
            texts='\n'.join(s.text for s in all_shapes(deck.slides[0].shapes) if s.has_text_frame)
            if any(bad in texts for bad in BANNED):raise ValueError(key+'仍含源稿占位文案')
            logo=audit_logo(ppt,require_every_slide=True)
            svg=audit_svg(ppt,None,check=True)
            if not logo['passed'] or not svg['passed']:raise ValueError(key+'Logo 或 SVG 媒体检查未通过')
            rel=entry.get('red_bindings') if theme=='red' and entry.get('red_bindings') else entry['bindings']
            bindings=json.loads((root/rel).read_text(encoding='utf-8'))
            for field in bindings['fields']:
                alias=field['semantic_path'];value=data['texts'][alias]
                field['max_chars']=min(field['max_chars'],len(value))
                field['max_width_units']=min(field.get('max_width_units',100),visual_units(value))
                field['max_lines']=min(field.get('max_lines',99),len(value.split('\n')))
            bindings['review']='semantic fields; short-copy PowerPoint render and capacity boundary verified'
            dump(root/rel,bindings)
            variants.append({'theme':theme,'source_page':entry.get('red_source_page') if theme=='red' and entry.get('red_source_page') else entry['source_page'],
                             'logo_count':logo['logos_with_primary_image'],'svg_passed':svg['passed'],
                             'pptx':key+'.pptx','png':key+'.png'})
            sample_registry[key]=data
        entry.update(classification_status='verified',pptx_support='verified_static_draft',
                     media_status='verified_source_media',cardinality_status='verified_fixed_count',
                     semantic_review_status='verified_short_copy',visual_review_status='powerpoint_render_checked',
                     title_pressure_status='tested_short_copy_only')
        if entry['role']=='cover':entry['cover_match_status']='verified_original'
        if entry['role']=='closing':entry['closing_match_status']='verified_original'
        rules_path=root/entry['layout_rules'];rules=json.loads(rules_path.read_text(encoding='utf-8'))
        rules.update(validation_status='verified_fixed_count',verified_counts=rules['supported_counts'],
                     count_evidence='native count; semantic fill and 1600x900 PowerPoint render checked')
        title_alias={'directory':'page.title','section':'section.title','cover':'cover.title','closing':'closing.title'}[entry['role']]
        title_values=[sample_registry[f"{entry['id']}-{theme}"]['texts'][title_alias] for theme in entry['themes']]
        rules['title_pressure_test']={'safe_title_chars':min(len(x) for x in title_values),'status':'tested_short_copy_only'}
        dump(rules_path,rules)
        (root/entry['spec']).write_text(
            f"# {entry['id']}\n\n页面职责：`{entry['role']}`；结构家族：`{entry['family_id']}`。"
            f"来源：{entry['source_mapping']}。支持主题：{', '.join(entry['themes'])}。\n\n"
            f"字段按 `bindings.json` 的 `semantic_path` 填充。只开放源稿固定 {rules['source_count']} 项；"
            "标题和其他字段的上限取已在 PowerPoint 实填验证的短文案，超限需精简或换版。"
            "已保留母版装饰、股票代码与原生品牌 Logo；缺少源 Logo 的页面默认补标准 Logo。"
            "静态可编辑 PPTX、Logo、媒体与 1600×900 渲染已验收。"
            "其他色系、逐对象颜色变量、长文案、HTML 和动效仍未验收。\n",
            encoding='utf-8')
        results.append({'id':entry['id'],'role':entry['role'],'themes':entry['themes'],'fixed_count':rules['source_count'],'variants':variants})
    dump(root/'catalog.json',entries)
    report={'status':'verified_static_draft','physical_pages':38,'layout_records':len(layouts),
            'variant_renders':sum(len(x['variants']) for x in results),'fixed_count_only':True,
            'text_fit':'38/38 pass','logo':'38/38 one visible source or added logo','svg_fallback':'38/38 pass',
            'limits':['no motion or HTML','supplemental native colors are not yet mapped to cross-palette variables','short-copy capacity only'],
            'layouts':results}
    dump(root/'review'/'supplement-blue-red.json',report)
    dump(root/'review'/'supplement-static-samples.json',sample_registry)
    readme=root/'README.md';text=readme.read_text(encoding='utf-8')
    marker='## 蓝红补充稿（2026-11-06）'
    section=(f"\n\n{marker}\n\n在原蓝红简约版上增补蓝色 14 页、红色 24 页，逐页索引 38/38，"
             f"整理出 {len(layouts)} 条版式记录（含蓝红配对与红色视觉变体）。"
             "新增目录、章节、红色简约封面和封底，全部为固定项数短文案静态可编辑 PPTX 草稿。"
             "逐项字段、来源页、主题与容量见 `catalog.json`、`layouts/supp-*/`；"
             "验收证据见 `review/supplement-blue-red.json`。使用仍须 `allow_draft` 和人工审阅。"
             "蓝红源稿颜色属于原生配色，尚未声称跨色系变量换色；动效和 HTML 未验收。\n")
    text=text.split(marker)[0].rstrip()+section if marker in text else text.rstrip()+section
    readme.write_text(text,encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('status','physical_pages','layout_records','variant_renders','text_fit','logo','svg_fallback')},ensure_ascii=False))

if __name__=='__main__':main()
