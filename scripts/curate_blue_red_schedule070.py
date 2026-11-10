"""Bind six native project rows and their month-proportional phase bars."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

LABEL_IDS=[[94,96,98],[100,102,104],[106,108,110],
           [112,114,116],[118,120,122],[124,126,128]]
BAR_IDS=[[93,95,97],[99,101,103],[105,107,109],
         [111,113,115],[117,119,121],[123,125,127]]
LOCKED=set([2,3,4,5,6,7,13,14,15,16,17,18,19,20,21])
MAP={10:'page.title'}
for i in range(6):
 MAP[22+i]=f'tasks[{i}].level';MAP[29+i]=f'tasks[{i}].code';MAP[36+i]=f'tasks[{i}].name'
 for j,sid in enumerate(LABEL_IDS[i]):MAP[sid]=f'tasks[{i}].stages[{j}]'
TASKS=[
 ('项目01','服务事项梳理','1',[5,3,4]),
 ('项目02','统一入口建设','2',[3,5,4]),
 ('项目03','数据治理试点','1',[4,4,4]),
 ('项目04','质量监测改进','3',[2,4,6]),
 ('项目05','知识库上线','2',[6,3,3]),
 ('项目06','培训推广实施','1',[4,5,3]),
]
SAMPLE=[{'code':code,'name':name,'level':level,'durations':durations,'stages':['规划','实施','验收']}
        for code,name,level,durations in TASKS]
def dump(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
 p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--samples',type=Path,required=True);p.add_argument('--reviewed',action='store_true');a=p.parse_args()
 root=a.library.resolve();base=root/'layouts/content-blue-070';a.samples.mkdir(parents=True,exist_ok=True)
 touched={'catalog.json','layouts/content-blue-070/layout_rules.json','layouts/content-blue-070/spec.md'}
 for name in ('bindings.json','bindings-red.json'):
  path=base/name;b=json.loads(path.read_text(encoding='utf-8-sig'))
  if {x['shape_id'] for x in b['fields']}!=set(MAP)|LOCKED:raise ValueError(name+' text IDs changed')
  for f in b['fields']:
   sid=f['shape_id']
   if sid in LOCKED:f.update(semantic_role='decoration_locked')
   else:
    key=MAP[sid];f.update(semantic_path=key,semantic_role=key.rsplit('.',1)[-1],
                         max_chars=min(f['max_chars'],25 if sid==10 else 16),max_lines=1)
  dump(path,b);touched.add(path.relative_to(root).as_posix())
 catpath=root/'catalog.json';cat=json.loads(catpath.read_text(encoding='utf-8-sig'));e=next(x for x in cat['layouts'] if x['id']=='content-blue-070')
 e.update(role='schedule',information_relation='six-project-year-schedule',family_id='six-row-three-phase-schedule',
          classification_status='verified' if a.reviewed else 'visual_reviewed',
          pptx_support='verified_static' if a.reviewed else 'pending_render',
          batch_status='fixed_six_rows_dynamic_phase_widths_verified' if a.reviewed else 'fields_mapped_pending_render',
          semantic_review_status='verified_blue_red' if a.reviewed else 'fields_mapped_pending_render')
 dump(catpath,cat)
 rulepath=base/'layout_rules.json';rules=json.loads(rulepath.read_text(encoding='utf-8-sig'))
 rules.update(cardinality_mode='project_schedule',source_count=6,supported_counts=[6],
              verified_counts=[6] if a.reviewed else [],
              validation_status='verified_fixed_count' if a.reviewed else 'pending_render',
              count_evidence='six native project rows; phase bar lengths driven by twelve-month durations',
              schedule_rows=[{'bars':bars,'labels':labels} for bars,labels in zip(BAR_IDS,LABEL_IDS)],
              bar_gap_emu=54864,label_offset_emu=118872)
 rules['render_overrides']={'red':{'text_color_by_shape_id':{str(sid):'202020' for sid in [*range(29,35),*range(36,42)]}}}
 dump(rulepath,rules)
 (base/'spec.md').write_text('# 六项目年度三阶段排期\n\n来源：蓝红 P070。固定六个项目行、十二个月坐标与每行三个原生阶段条。'
    '每个项目提供名称、等级、三阶段名称和三段月数；月数均至少为 2，合计必须为 12，条形长度随月数重新计算。'
    +('蓝红短文案实填、阶段条重排和 PowerPoint 渲染通过。' if a.reviewed else '字段与条形重排规则已登记，蓝红渲染待验收。')
    +'不开放项目行数增减；Logo 原位保留。动效、HTML 和其他色系未验收。\n',encoding='utf-8')
 for theme in ('blue','red'):dump(a.samples/f'content-blue-070-{theme}.json',
   {'theme':theme,'item_count':6,'texts':{'page.title':'项目规划｜六项年度工作排期'},'tasks':SAMPLE})
 mp=root/'knowledge-manifest.json';m=json.loads(mp.read_text(encoding='utf-8-sig'))
 for rel in touched:m['files'][rel]=hashlib.sha256((root/rel).read_bytes()).hexdigest()
 dump(mp,m)
if __name__=='__main__':main()
