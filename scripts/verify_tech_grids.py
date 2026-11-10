"""Create fictitious editable 2-6 item samples for P09 and P49."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from pptx import Presentation
from audit_logo import audit as audit_logo
from fill_layout import fill
from fill_layout import walk

NAMES=['项目背景','现状分析','方案设计','实施路径','成效评估','后续计划']
ENGLISH=['Background','Analysis','Design','Roadmap','Evaluation','Next Steps']
CAPABILITIES=['信息整合','规则校验','智能检索','协同处理','过程追踪','结果复盘']
DESCRIPTIONS=['汇集多源信息，形成统一的工作视图。','按明确的规则检查输入与输出。',
              '快速定位所需材料和相关记录。','让各环节在同一流程中完成协作。',
              '记录关键节点，便于追溯处理过程。','依据结果总结经验并调整下一步。']

def main():
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True)
    p.add_argument('--out-dir',type=Path,required=True);a=p.parse_args()
    a.out_dir.mkdir(parents=True,exist_ok=True)
    results=[]
    for page,layout in ((9,'directory-tech-009'),(49,'content-tech-049')):
        groups=json.loads((a.library/'layouts'/layout/'item-groups.json').read_text(encoding='utf-8'))
        for count in range(2,7):
            texts={'text_2':'CONTENTS','text_3':'目录'} if page==9 else {
                'text_6':'方案能力概览','text_7':'以下为虚构内容，仅用于版式与项数验证'}
            for i,unit in enumerate(groups['units'][:count]):
                f=unit['fields']
                if page==9:
                    texts[f['number']]=f'{i+1:02d}';texts[f['title']]=NAMES[i]
                    texts[f['english']]=ENGLISH[i]
                else:
                    texts[f['title']]=CAPABILITIES[i]
                    texts[f['description']]=DESCRIPTIONS[i]
            content=a.out_dir/f'P{page:03d}-{count}项-输入.json'
            content.write_text(json.dumps({'theme':'deep-blue-tech','item_count':count,'texts':texts},
                                          ensure_ascii=False,indent=2),encoding='utf-8')
            out=a.out_dir/f'P{page:03d}-{count}项-内部样稿.pptx'
            report=fill(a.library,layout,content,out,allow_draft=True,internal=True)
            deck=Presentation(out);slide=deck.slides[0]
            top={sh.shape_id:sh for sh in slide.shapes}
            recursive_ids=[sh.shape_id for sh in walk(slide.shapes)]
            if len(recursive_ids)!=len(set(recursive_ids)):
                raise AssertionError(f'P{page:03d} {count} 项对象 ID 重复')
            roots=[u['root_shape_id'] for u in groups['units']]
            if any(sid not in top for sid in roots[:count]) or any(sid in top for sid in roots[count:]):
                raise AssertionError(f'P{page:03d} {count} 项组残留或丢失')
            item_shapes=[top[sid] for sid in roots[:count]]
            if any(sh.left<0 or sh.top<0 or sh.left+sh.width>deck.slide_width or sh.top+sh.height>deck.slide_height for sh in item_shapes):
                raise AssertionError(f'P{page:03d} {count} 项越界')
            for i,a_item in enumerate(item_shapes):
                for b_item in item_shapes[i+1:]:
                    if min(a_item.left+a_item.width,b_item.left+b_item.width)>max(a_item.left,b_item.left) and min(a_item.top+a_item.height,b_item.top+b_item.height)>max(a_item.top,b_item.top):
                        raise AssertionError(f'P{page:03d} {count} 项相互重叠')
            logo=audit_logo(out,True)
            if not logo['passed'] or logo['logos_with_primary_image']!=1:
                raise AssertionError(f'P{page:03d} {count} 项 Logo 异常')
            report['structural_qa']={'retained_items':count,'removed_items':6-count,
                                     'top_level_item_groups':roots[:count],
                                     'row_positions_emu':[(top[sid].left,top[sid].top) for sid in roots[:count]],
                                     'logo_count':1,'passed':True}
            results.append(report)
    (a.out_dir/'结构验证.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([{'layout':r['layout_id'],'count':r['cardinality']['count'],
                       'passed':r['structural_qa']['passed']} for r in results],ensure_ascii=False))

if __name__=='__main__':main()
