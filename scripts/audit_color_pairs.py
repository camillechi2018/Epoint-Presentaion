"""Compare blue/red OOXML color nodes without guessing semantic RGB replacements."""
from __future__ import annotations
import argparse,json
from collections import Counter
from pathlib import Path

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--library',type=Path,required=True);a=ap.parse_args()
    root=a.library.resolve();catalog=json.loads((root/'catalog.json').read_text(encoding='utf8'))['layouts']
    pages=json.loads((root/'color-inventory.json').read_text(encoding='utf8'))['pages']
    records=[];summary=Counter()
    for e in catalog:
        if not e.get('red_source_page'):continue
        blue=pages['blue'][str(e['source_page'])]['color_refs']
        red=pages['red'][str(e['red_source_page'])]['color_refs']
        aligned=len(blue)==len(red) and all(x['kind']==y['kind'] for x,y in zip(blue,red))
        different_explicit=sum(x['kind']==y['kind']=='srgbClr' and x['value']!=y['value'] for x,y in zip(blue,red)) if aligned else None
        explicit=sum(x['kind']=='srgbClr' for x in blue)
        record={'id':e['id'],'blue_page':e['source_page'],'red_page':e['red_source_page'],
                'blue_color_refs':len(blue),'red_color_refs':len(red),'blue_explicit_refs':explicit,
                'order_and_kind_aligned':aligned,'explicit_differences':different_explicit,
                'status':'paired_color_structure_candidate' if aligned else 'requires_object_level_review'}
        records.append(record)
        summary['pairs']+=1
        summary['aligned' if aligned else 'needs_review']+=1
        summary['explicit_refs_blue']+=explicit
        if different_explicit is not None:summary['different_explicit']+=different_explicit
    out=root/'color-pair-audit.json'
    out.write_text(json.dumps({'status':'provisional','summary':dict(summary),'records':records,
                               'limits':['颜色节点顺序一致不等于语义角色已批准','嵌套图表和表格的独立 XML 颜色仍需审计','图片是主题专属素材或锁定品牌资产']},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(summary),ensure_ascii=False))
if __name__=='__main__':main()
