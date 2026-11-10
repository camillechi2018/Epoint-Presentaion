"""Curate native-count P015 and P191, and create fictional QA content."""
import argparse,json
from pathlib import Path
from hashlib import sha256

RATE=[36,37,38,39,40];CARD=[7,8,9,10,11];BODY=[58,60,62,64,66];LABEL=[52,53,54,55,56]
MAP15={2:'page.title',5:'page.section',6:'page.summary',42:'quarters[0]',45:'quarters[1]',43:'quarters[2]',44:'quarters[3]'}
for i in range(5):
    for sid,key in ((RATE[i],'rate'),(CARD[i],'title'),(BODY[i],'body'),(LABEL[i],'rate_label')):MAP15[sid]=f'items[{i}].{key}'
MAP191={3:'page.title',57:'summary[0].label',59:'summary[0].rate',61:'summary[1].label',63:'summary[1].rate',53:'summary[2].label',75:'summary[2].rate'}
for i,sid in enumerate((45,43,48,44,46,47)):MAP191[sid]=f'tasks[{i}].period'
for i,sid in enumerate((39,40,41,42,49,50)):MAP191[sid]=f'tasks[{i}].note'
SAMPLE15={'page.title':'项目复盘｜五项工作进展','page.section':'项目完成情况','page.summary':'本页以虚构项目展示五项任务的进度与阶段成果；百分比仅用于版式验收。'}
names=['需求梳理','方案设计','系统建设','试点运行','推广复盘']
for i,name in enumerate(names):
    SAMPLE15.update({f'items[{i}].rate':f'{92-i*7}%',f'items[{i}].title':f'{i+1}.{name}',
                     f'items[{i}].rate_label':'任务完成进度',f'items[{i}].body':f'任务概述：推进{name}。\n阶段成果：形成可检查的交付记录。'})
for i,q in enumerate(('第一季度','第二季度','第三季度','第四季度')):SAMPLE15[f'quarters[{i}]']=q
SAMPLE191={'page.title':'年度计划｜六项任务排期','summary[0].label':'计划推进','summary[0].rate':'85%',
           'summary[1].label':'材料准备','summary[1].rate':'50%','summary[2].label':'任务完成','summary[2].rate':'75%'}
periods=['1月-3月','3月-5月','5月-7月','6月-8月','8月-10月','10月-12月']
notes=['完成调研与立项','完成方案评估','实施核心功能','组织试点反馈','优化交付流程','完成验收与复盘']
for i in range(6):SAMPLE191.update({f'tasks[{i}].period':periods[i],f'tasks[{i}].note':notes[i]})
TASKS=['调研立项','方案评估','功能实施','试点反馈','流程优化','验收复盘']
TABLE=[['工作任务']+[f'{n}月' for n in range(1,13)]]+[[name]+['' for _ in range(12)] for name in TASKS]

def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--reviewed',action='store_true');a=p.parse_args();root=a.library.resolve();a.out.mkdir(parents=True,exist_ok=True)
    catpath=root/'catalog.json';cat=json.loads(catpath.read_text(encoding='utf-8-sig'));touched={'catalog.json'}
    for page,mapping,count,sample,relation,family in ((15,MAP15,5,SAMPLE15,'five-project-progress','five-progress-cards'),(191,MAP191,6,SAMPLE191,'six-task-gantt','six-task-gantt')):
        name=f'content-blue-{page:03d}';base=root/'layouts'/name;entry=next(x for x in cat['layouts'] if x['id']==name)
        approved=a.reviewed and page==15
        for fn in ('bindings.json','bindings-red.json'):
            path=base/fn;b=json.loads(path.read_text(encoding='utf-8-sig'))
            if {int(f['field'].split('_')[1]) for f in b['fields']}!=set(mapping):raise ValueError(name+' fields changed')
            for f in b['fields']:
                sid=int(f['field'].split('_')[1]);key=mapping[sid]
                f.update(semantic_path=key,semantic_role=key.rsplit('.',1)[-1],
                         max_chars=min(f['max_chars'],70 if key=='page.summary' else 55 if key.endswith('.body') else 24),
                         max_lines=2 if key=='page.summary' or key.endswith('.body') else 1)
            dump(path,b);touched.add(path.relative_to(root).as_posix())
        entry.update(information_relation=relation,family_id=family,
                     classification_status='verified' if approved else 'visual_reviewed',
                     semantic_review_status='verified_blue_red' if approved else 'rendered_demo_data_geometry_pending',
                     pptx_support='verified_static' if approved else 'pending_data_geometry_binding')
        rules=base/'layout_rules.json';v=json.loads(rules.read_text(encoding='utf-8-sig'))
        v.update(cardinality_mode='fixed',source_count=count,supported_counts=[count],verified_counts=[count] if approved else [],
                 validation_status='verified_fixed_count' if approved else 'pending_data_geometry_binding')
        if page==15:
            v['render_overrides']={'red':{'text_color_by_shape_id':{str(sid):'000000' for sid in BODY}}}
        dump(rules,v);touched.add(rules.relative_to(root).as_posix())
        spec=base/'spec.md'
        detail=('原生五张进度卡与四段季度条；只验收固定五项。3／4 项须同时重排卡片、圆形进度值与季度条。'
                if page==15 else '原生 7×13 表格，含一行表头和六行任务；日期及条形进度按六行对应。只验收固定六行。')
        conclusion=('原生数量的蓝红静态 PPTX 草稿已验收。' if approved else '蓝红示例已渲染，但日期与百分比图形尚未随业务数据联动，暂不进入选稿池。')
        spec.write_text(f'# {name}\n\n来源：蓝红 P{page:03d}。{detail}{conclusion}Logo 保持原位；动效、HTML 和其他色系未验收。\n',encoding='utf-8')
        touched.add(spec.relative_to(root).as_posix())
        for theme in ('blue','red'):
            data={'theme':theme,'item_count':count,'texts':sample}
            if page==191:data['tables']=[{'shape_id':35,'rows':TABLE}]
            dump(a.out/f'{name}-{theme}.json',data)
        if a.reviewed:
            rp=root/'review'/f'{name}.json';dump(rp,{'date':'2026-11-05','layout_id':name,'status':'verified_static_pptx_draft_pending_review' if approved else 'rendered_demo_data_geometry_pending','verified_counts':[count] if approved else [],'preview_paths':[f'review/{name}-blue-filled.png',f'review/{name}-red-filled.png'],'limits':['other counts pending reflow','HTML and motion not verified'] if approved else ['date labels and progress graphics not bound to changed business data']});touched.add(rp.relative_to(root).as_posix());touched.update({f'review/{name}-{t}-filled.png' for t in ('blue','red')})
    dump(catpath,cat);mp=root/'knowledge-manifest.json';m=json.loads(mp.read_text(encoding='utf-8-sig'))
    for rel in touched:m['files'][rel]=sha256((root/rel).read_bytes()).hexdigest()
    dump(mp,m)
if __name__=='__main__':main()
