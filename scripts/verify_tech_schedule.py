"""Create fictitious 2-6 row samples for the native-shape P69 schedule."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from fill_layout import fill
from pptx import Presentation
from audit_logo import audit as audit_logo

ACTIVITIES = ['主题说明', '方案讨论', '分组展示', '交流反馈', '行动计划', '总结回顾']
OWNERS = ['甲组', '乙组', '丙组', '丁组', '戊组', '己组']
FIELDS = [
    ('text_22','text_15','text_32'), ('text_29','text_19','text_36'),
    ('text_31','text_95','text_38'), ('text_23','text_16','text_33'),
    ('text_24','text_17','text_34'), ('text_25','text_18','text_35'),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--out-dir', type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    reports = []
    group_data=json.loads((args.library/'layouts/schedule-tech-069/item-groups.json').read_text(encoding='utf-8'))
    row_units=[set(u['source_shape_ids']) for u in group_data['units']]
    for count in range(2, 7):
        texts = {'text_12':'时间', 'text_13':'活动安排', 'text_14':'负责人',
                 'text_20':'项目日程演示', 'text_21':'内部结构验证 · 所有内容均为虚构'}
        for i, (time_field, activity_field, owner_field) in enumerate(FIELDS[:count]):
            texts[time_field] = f'{9+i:02d}:00-{9+i:02d}:30'
            texts[activity_field] = ACTIVITIES[i]
            texts[owner_field] = OWNERS[i]
        content = args.out_dir / f'P069-{count}行-输入.json'
        content.write_text(json.dumps({'theme':'deep-blue-tech', 'item_count':count, 'texts':texts},
                                      ensure_ascii=False,indent=2),encoding='utf-8')
        out = args.out_dir / f'P069-{count}行-内部样稿.pptx'
        report=fill(args.library,'schedule-tech-069',content,out,allow_draft=True,internal=True)
        slide=Presentation(out).slides[0]
        by_id={shape.shape_id:shape for shape in slide.shapes}
        if any(sid not in by_id for unit in row_units[:count] for sid in unit):
            raise AssertionError(f'{count} 行存在缺失对象')
        if any(sid in by_id for unit in row_units[count:] for sid in unit):
            raise AssertionError(f'{count} 行仍包含已删除对象')
        row_tops=[by_id[u['root_shape_id']].top for u in group_data['units'][:count]]
        if row_tops!=sorted(row_tops) or len(set(row_tops))!=count:
            raise AssertionError(f'{count} 行位置冲突')
        logo=audit_logo(out,True)
        if not logo['passed'] or logo['logos_with_primary_image']!=1:
            raise AssertionError(f'{count} 行 Logo 验证失败')
        report['structural_qa']={'retained_rows':count,'removed_rows':6-count,
                                 'row_tops_emu':row_tops,'logo_count':1,'passed':True}
        reports.append(report)
    (args.out_dir/'结构验证.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([{'count':r['cardinality']['count'],'output':r['output'],
                       'logo':r['logo']['reason']} for r in reports],ensure_ascii=False,indent=2))


if __name__=='__main__': main()
