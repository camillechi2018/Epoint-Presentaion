"""Bind the native two-pair issue/action page and four-step follow-up strip."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

MAP={5:'page.title',30:'issues[0].title',31:'issues[1].title',
     50:'actions[0].title',51:'actions[1].title',
     100:'issues[0].body',101:'issues[1].body',
     102:'actions[0].body',103:'actions[1].body',
     81:'center.issue_label',90:'center.action_label',
     12:'center.team_label',13:'center.personal_label',119:'plan.label'}
for prefix,groups in [('issues',[[24,25,26],[78,79,80]]),
                      ('actions',[[87,88,89],[96,97,98]])]:
 for i,ids in enumerate(groups):
  for j,sid in enumerate(ids):MAP[sid]=f'{prefix}[{i}].tags[{j}]'
for i,sid in enumerate([120,121,122,123]):MAP[sid]=f'plan.steps[{i}]'
LOCKED={2,66,67,68}
SAMPLE={'page.title':'问题复盘｜改进措施与后续计划',
        'center.issue_label':'现存问题','center.action_label':'改进举措',
        'center.team_label':'团队层面','center.personal_label':'个人层面',
        'plan.label':'后续\n计划'}
for i,(title,body,tags) in enumerate([
 ('协作问题 01','信息同步不及时，影响任务衔接。\n责任分工尚需进一步明确。',['沟通滞后','分工模糊','进度失准']),
 ('排期问题 02','多项任务集中到期，资源安排紧张。\n优先级判断还需统一。',['任务积压','资源紧张','优先级弱'])]):
 SAMPLE[f'issues[{i}].title']=title;SAMPLE[f'issues[{i}].body']=body
 for j,tag in enumerate(tags):SAMPLE[f'issues[{i}].tags[{j}]']=tag
for i,(title,body,tags) in enumerate([
 ('协作改进 01','每周同步进度与风险，及时共享记录。\n明确责任人和交付时间。',['周会同步','责任到人','共享记录']),
 ('排期改进 02','按影响程度排序，预留关键任务资源。\n每月复核排期与完成质量。',['分级排序','资源预留','月度复核'])]):
 SAMPLE[f'actions[{i}].title']=title;SAMPLE[f'actions[{i}].body']=body
 for j,tag in enumerate(tags):SAMPLE[f'actions[{i}].tags[{j}]']=tag
for i,value in enumerate(['统一协作机制','明确交付责任','优化任务排期','持续复盘改进']):SAMPLE[f'plan.steps[{i}]']=value

def dump(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
 p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--samples',type=Path,required=True);p.add_argument('--reviewed',action='store_true');a=p.parse_args()
 root=a.library.resolve();base=root/'layouts/content-blue-135';a.samples.mkdir(parents=True,exist_ok=True)
 touched={'catalog.json','layouts/content-blue-135/layout_rules.json','layouts/content-blue-135/spec.md'}
 for name in ('bindings.json','bindings-red.json'):
  path=base/name;b=json.loads(path.read_text(encoding='utf-8-sig'))
  if {x['shape_id'] for x in b['fields']}!=set(MAP)|LOCKED:raise ValueError(name+' text IDs changed')
  for f in b['fields']:
   sid=f['shape_id']
   if sid in LOCKED:f.update(semantic_role='decoration_locked')
   else:
    key=MAP[sid];is_body=key.endswith('.body')
    f.update(semantic_path=key,semantic_role='body' if is_body else 'label',
             max_chars=min(f['max_chars'],72 if is_body else 22),
             max_lines=2 if is_body or key=='plan.label' else 1)
  dump(path,b);touched.add(path.relative_to(root).as_posix())
 catpath=root/'catalog.json';cat=json.loads(catpath.read_text(encoding='utf-8-sig'));e=next(x for x in cat['layouts'] if x['id']=='content-blue-135')
 e.update(role='comparison',information_relation='issue-action-two-pairs',family_id='issue-action-rings',
          classification_status='verified' if a.reviewed else 'visual_reviewed',
          pptx_support='verified_static' if a.reviewed else 'pending_render',
          batch_status='fixed_two_pairs_verified' if a.reviewed else 'fields_mapped_pending_render',
          semantic_review_status='verified_blue_red' if a.reviewed else 'fields_mapped_pending_render')
 dump(catpath,cat)
 rulepath=base/'layout_rules.json';rules=json.loads(rulepath.read_text(encoding='utf-8-sig'))
 rules.update(cardinality_mode='fixed',source_count=2,supported_counts=[2],
              verified_counts=[2] if a.reviewed else [],
              validation_status='verified_fixed_count' if a.reviewed else 'pending_render',
              count_evidence='two issue/action pairs surround shared center rings and four-step plan')
 dump(rulepath,rules)
 (base/'spec.md').write_text('# 两组问题与改进措施\n\n来源：蓝红 P135。固定两组问题、两组对应措施，底部另有四步后续计划。'
   +'中心双环及顶部层面横幅与四块信息卡形成整体构图，当前不开放增减组数。'
   +('蓝红短文案实填和 PowerPoint 渲染通过。' if a.reviewed else '语义字段已登记，实填渲染待验收。')
   +'Logo 原位保留；动效、HTML 和其他色系未验收。\n',encoding='utf-8')
 for theme in ('blue','red'):dump(a.samples/f'content-blue-135-{theme}.json',{'theme':theme,'item_count':2,'texts':SAMPLE})
 mp=root/'knowledge-manifest.json';m=json.loads(mp.read_text(encoding='utf-8-sig'))
 for rel in touched:m['files'][rel]=hashlib.sha256((root/rel).read_bytes()).hexdigest()
 dump(mp,m)
if __name__=='__main__':main()
