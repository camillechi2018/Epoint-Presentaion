"""Bind six task rows, month bars and native progress arcs for P191."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

MAP={3:'page.title',57:'summary[0].label',59:'summary[0].rate',
     61:'summary[1].label',63:'summary[1].rate',
     53:'summary[2].label',75:'summary[2].rate'}
BAR_IDS=[45,43,48,44,46,47]
NOTE_IDS=[39,40,41,42,49,50]
for i in range(6):
 MAP[BAR_IDS[i]]=f'tasks[{i}].period'
 MAP[NOTE_IDS[i]]=f'tasks[{i}].note'
SAMPLE={'page.title':'年度计划｜六项任务排期',
 'summary[0].label':'计划推进','summary[0].rate':'85%',
 'summary[1].label':'报告完成','summary[1].rate':'50%',
 'summary[2].label':'任务完成','summary[2].rate':'75%'}
TASKS=[
 {'name':'需求梳理','start_month':1,'end_month':3,'note':'完成调研'},
 {'name':'方案设计','start_month':3,'end_month':5,'note':'完成评审'},
 {'name':'功能开发','start_month':5,'end_month':7,'note':'形成版本'},
 {'name':'试点运行','start_month':6,'end_month':8,'note':'收集反馈'},
 {'name':'流程优化','start_month':8,'end_month':10,'note':'修复问题'},
 {'name':'验收复盘','start_month':10,'end_month':12,'note':'完成交付'},
]
def dump(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
 p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--samples',type=Path,required=True);p.add_argument('--reviewed',action='store_true');a=p.parse_args()
 root=a.library.resolve();base=root/'layouts/content-blue-191';a.samples.mkdir(parents=True,exist_ok=True)
 touched={'catalog.json','layouts/content-blue-191/layout_rules.json','layouts/content-blue-191/spec.md'}
 for name in ('bindings.json','bindings-red.json'):
  path=base/name;b=json.loads(path.read_text(encoding='utf-8-sig'))
  if {f['shape_id'] for f in b['fields']}!=set(MAP):raise ValueError(name+' source text changed')
  for f in b['fields']:
   sid=f['shape_id'];key=MAP[sid]
   f.update(semantic_path=key,semantic_role=key.rsplit('.',1)[-1],
            max_chars=min(f['max_chars'],24 if sid in NOTE_IDS else 26),max_lines=1)
  dump(path,b);touched.add(path.relative_to(root).as_posix())
 catpath=root/'catalog.json';cat=json.loads(catpath.read_text(encoding='utf-8-sig'));e=next(x for x in cat['layouts'] if x['id']=='content-blue-191')
 e.update(role='data-table',information_relation='six-task-gantt',family_id='six-row-month-gantt',
  classification_status='verified' if a.reviewed else 'visual_reviewed',
  pptx_support='verified_static' if a.reviewed else 'pending_geometry_render',
  batch_status='fixed_six_tasks_geometry_bound_verified' if a.reviewed else 'geometry_binding_pending_render',
  semantic_review_status='verified_blue_red' if a.reviewed else 'geometry_binding_pending_render')
 dump(catpath,cat)
 rulepath=base/'layout_rules.json';rules=json.loads(rulepath.read_text(encoding='utf-8-sig'))
 rules.update(cardinality_mode='gantt_six_tasks',source_count=6,supported_counts=[6],
  verified_counts=[6] if a.reviewed else [],
  validation_status='verified_fixed_count' if a.reviewed else 'pending_render',
  gantt_table_shape_id=35,gantt_bar_shape_ids=BAR_IDS,gantt_note_shape_ids=NOTE_IDS,
  month_start_emu=2432304,month_width_emu=767520,note_gap_emu=109728,
  gantt_note_icon_shape_ids={'1':51,'4':78},
  summary_arc_shape_ids=[['summary[1].rate',65],['summary[2].rate',77]],
  summary_bar_rate_field='summary[0].rate',summary_bar_track_shape_id=55,
  summary_bar_shape_id=58,summary_bar_rate_shape_id=59,summary_bar_label_gap_emu=73152)
 dump(rulepath,rules)
 (base/'spec.md').write_text('# 六任务甘特排期\n\n来源：蓝红 P191。固定六行任务和十二个月坐标。'
  '调用时每行提供任务名、起止月份和备注；原生表格、日期条及备注位置联动，底部三项进度率驱动横条和两段原生弧形。'
  +('蓝红虚构数据实填与 PowerPoint 渲染通过。' if a.reviewed else '几何绑定规则已登记，蓝红渲染待验收。')
  +'暂不开放增减任务行数；Logo 原位保留。动效、HTML 和其他色系未验收。\n',encoding='utf-8')
 for theme in ('blue','red'):dump(a.samples/f'content-blue-191-{theme}.json',
  {'theme':theme,'item_count':6,'texts':SAMPLE,'tasks':TASKS})
 mp=root/'knowledge-manifest.json';m=json.loads(mp.read_text(encoding='utf-8-sig'))
 for rel in touched:m['files'][rel]=hashlib.sha256((root/rel).read_bytes()).hexdigest()
 dump(mp,m)
if __name__=='__main__':main()
