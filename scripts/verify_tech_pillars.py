"""Build and structurally check fictitious P51 samples for 2–6 pillars."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from pptx import Presentation
from audit_logo import audit as audit_logo
from fill_layout import fill,walk

ITEMS=[
    ('目标共识','明确目标与分工，形成共同的工作方向。'),
    ('角色分工','约定责任边界，及时交接关键事项。'),
    ('建立信任','公开进展与风险，保持团队信息透明。'),
    ('有效沟通','记录问题与结论，减少重复沟通成本。'),
    ('协同处理','围绕同一任务清单推进跨组配合。'),
    ('成果复盘','回顾结果和经验，确定下一步改进。'),
]

def run(lib:Path,outdir:Path):
    outdir.mkdir(parents=True,exist_ok=True)
    rules=json.loads((lib/'layouts/content-tech-051/layout_rules.json').read_text(encoding='utf-8'))
    results=[]
    for count in range(2,7):
        content={'theme':'deep-blue-tech','items':[{'title':title,'body':body} for title,body in ITEMS[:count]],
                 'texts':{'text_24':'团队协作关键举措','text_25':'内部结构验证样稿，所有内容均为虚构','text_293':'项关键举措'}}
        data=outdir/f'P051-{count}项-输入.json';data.write_text(json.dumps(content,ensure_ascii=False,indent=2),encoding='utf-8')
        output=outdir/f'P051-{count}项-内部样稿.pptx'
        report=fill(lib,'content-tech-051',data,output,allow_draft=True,internal=True)
        slide=Presentation(output).slides[0]
        shapes={s.shape_id:s for s in slide.shapes}
        all_ids=[s.shape_id for s in walk(slide.shapes)]
        if len(all_ids)!=len(set(all_ids)):raise AssertionError(f'{count} 项对象 ID 重复')
        selected=rules['source_indices_by_count'][str(count)]
        for index,unit in enumerate(rules['units']):
            for sid in unit:
                if (sid in shapes)!=(index in selected):raise AssertionError(f'{count} 项对象归属错误 {sid}')
        if shapes[rules['computed_count_shape_id']].text.strip()!=str(count):
            raise AssertionError(f'{count} 项中心数字未更新')
        lefts=[shapes[rules['anchor_shape_ids'][i]].left for i in selected]
        if lefts!=sorted(lefts) or len(lefts)!=len(set(lefts)):
            raise AssertionError(f'{count} 项立柱横向顺序异常')
        logo=audit_logo(output,True)
        if not logo['passed'] or logo['logos_with_primary_image']!=1:
            raise AssertionError(f'{count} 项 Logo 异常')
        report['structural_qa']={'passed':True,'retained_items':count,'removed_items':6-count,
                                 'source_slots':[i+1 for i in selected],
                                 'pillar_lefts_emu':lefts,'computed_count':count,'logo_count':1}
        results.append(report)
    (outdir/'结构验证.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    return [{'count':x['cardinality']['count'],'passed':x['structural_qa']['passed']} for x in results]

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True)
    p.add_argument('--out-dir',type=Path,required=True);a=p.parse_args()
    print(json.dumps(run(a.library,a.out_dir),ensure_ascii=False))
