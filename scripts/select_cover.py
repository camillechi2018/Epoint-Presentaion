"""Rank original cover combinations; preserve color and review boundaries."""
from __future__ import annotations
import argparse,json,unicodedata
from pathlib import Path
from library_location import get_library

IMPACT={'high':3,'medium-high':2,'medium':1}

def select(library:Path,request:dict):
    catalog=json.loads((library/'catalog.json').read_text(encoding='utf-8-sig'))
    covers=[x for x in catalog['layouts'] if x['role']=='cover']
    theme=request.get('theme','blue');purpose=request.get('purpose','cover');style=request.get('style');subject_tag=request.get('subject_tag')
    requested_family=request.get('style_family')
    title=request.get('title','');exclude=set(request.get('exclude_ids',[]))
    evaluated=[];ranked=[]
    for c in covers:
        reasons=[]
        if requested_family:
            if (c.get('style_family') or 'legacy-blue-red')!=requested_family:reasons.append('style_family_mismatch')
        elif c.get('style_family')=='deep-blue-tech':reasons.append('style_family_not_selected')
        if c['id'] in exclude:reasons.append('excluded')
        if c.get('color_family')!=theme and theme not in c.get('themes',[]):reasons.append('color_family_mismatch')
        if subject_tag and subject_tag not in c.get('subject_tags',[]):reasons.append('subject_tag_mismatch')
        if c.get('cover_match_status')!='verified_original' and not request.get('allow_draft'):reasons.append('not_visually_verified')
        if c.get('title_pressure_status')=='tested_short_copy_only':
            rules=json.loads((library/c['layout_rules']).read_text(encoding='utf-8'))
            safe=rules.get('title_pressure_test',{}).get('safe_title_chars',0)
            if title and len(title)>safe:reasons.append('title_over_verified_capacity')
            bindings=json.loads((library/c['bindings']).read_text(encoding='utf-8'))['fields']
            title_field=next((x for x in bindings if x.get('semantic_path')=='cover.title'),None)
            if title and title_field:
                units=lambda line:sum(2 if unicodedata.east_asian_width(ch) in 'WF' else 1 for ch in line)
                if any(units(line)>title_field.get('max_width_units',100) for line in title.split('\n')) or len(title.split('\n'))>title_field.get('max_lines',1):
                    reasons.append('title_over_verified_width')
        elif len(title)>28:reasons.append('long_title_needs_manual_fit_check')
        if reasons:evaluated.append({'id':c['id'],'excluded_reasons':reasons});continue
        score=IMPACT.get(c.get('visual_impact'),0)*10
        if style and c.get('style')==style:score+=8
        if purpose=='back' and c.get('style') in ('technology-future','digital-city'):score+=2
        ranked.append((score,c));evaluated.append({'id':c['id'],'score':score,'style':c.get('style'),'subject_tags':c.get('subject_tags',[])})
    ranked.sort(key=lambda x:(-x[0],x[1]['id']))
    best=ranked[0][1] if ranked else None
    return {'status':'candidate_requires_visual_review' if best else 'no_verified_match',
            'theme':theme,'selected_id':best['id'] if best else None,
            'source_page':best.get('source_page') if best else None,
            'background_image':best.get('background_image') if best else None,
            'decision_log':evaluated,'warning':'颜色和安全区是初标，填入真实标题后需要 PPTX/HTML 分别复核' if best else '当前色系没有合格候选；不得把暖金冒充红色'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--library',type=Path);ap.add_argument('--request',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    report=select(a.library or get_library(),json.loads(a.request.read_text(encoding='utf-8-sig')))
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'selected_id':report['selected_id'],'status':report['status']},ensure_ascii=False))
if __name__=='__main__':main()
