"""Bind the native five-column SMART page; preserve acronym labels."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

LABELS=[61,62,63,64,65]
DESCRIPTIONS=[97,98,99,100,101]
BULLETS=[[66,67,68],[81,82,83],[85,86,87],[89,90,91],[93,94,95]]
LOCKED=set([16,17,18,19,20,21,25,26,27,28]+LABELS)
MAP={47:'page.title'}
for i in range(5):
 MAP[DESCRIPTIONS[i]]=f'dimensions[{i}].description'
 for j,sid in enumerate(BULLETS[i]):MAP[sid]=f'dimensions[{i}].evidence[{j}]'
SAMPLE={'page.title':'项目目标｜SMART原则验证'}
DESCS=['明确试点服务的办理范围与交付物。','以办理时长和用户评分衡量结果。',
       '沿用现有平台与团队，分阶段实现。','与年度服务效率目标保持一致。','三季度完成试点并提交验收材料。']
EVIDENCE=[['明确服务范围','列出交付事项','落实责任人员'],
          ['记录办理时长','统计用户评分','按月公布进度'],
          ['复用现有平台','安排专职小组','分批开展试点'],
          ['对应年度目标','聚焦高频事项','形成改进依据'],
          ['六月完成方案','八月完成试点','九月完成验收']]
for i in range(5):
 SAMPLE[f'dimensions[{i}].description']=DESCS[i]
 for j in range(3):SAMPLE[f'dimensions[{i}].evidence[{j}]']=EVIDENCE[i][j]

def dump(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
 p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--samples',type=Path,required=True);p.add_argument('--reviewed',action='store_true');a=p.parse_args()
 root=a.library.resolve();base=root/'layouts/content-blue-125';a.samples.mkdir(parents=True,exist_ok=True)
 touched={'catalog.json','layouts/content-blue-125/layout_rules.json','layouts/content-blue-125/spec.md'}
 for name in ('bindings.json','bindings-red.json'):
  path=base/name;b=json.loads(path.read_text(encoding='utf-8-sig'))
  if {x['shape_id'] for x in b['fields']}!=set(MAP)|LOCKED:raise ValueError(name+' text IDs changed')
  for f in b['fields']:
   sid=f['shape_id']
   if sid in LOCKED:f.update(semantic_role='decoration_locked')
   else:
    semantic=MAP[sid];description=semantic.endswith('.description')
    f.update(semantic_path=semantic,semantic_role='description' if description else 'evidence',
             max_chars=min(f['max_chars'],42 if description else 18),max_lines=3 if description else 1)
  dump(path,b);touched.add(path.relative_to(root).as_posix())
 catpath=root/'catalog.json';cat=json.loads(catpath.read_text(encoding='utf-8-sig'));e=next(x for x in cat['layouts'] if x['id']=='content-blue-125')
 e.update(role='framework',information_relation='smart-goal-framework',family_id='smart-five-columns',
          classification_status='verified' if a.reviewed else 'visual_reviewed',
          pptx_support='verified_static' if a.reviewed else 'pending_render',
          batch_status='fixed_five_smart_verified' if a.reviewed else 'fields_mapped_pending_render',
          semantic_review_status='verified_blue_red' if a.reviewed else 'fields_mapped_pending_render')
 dump(catpath,cat)
 rulespath=base/'layout_rules.json';rules=json.loads(rulespath.read_text(encoding='utf-8-sig'))
 rules.update(cardinality_mode='fixed',source_count=5,supported_counts=[5],
              verified_counts=[5] if a.reviewed else [],
              validation_status='verified_fixed_count' if a.reviewed else 'pending_render',
              count_evidence='SMART acronym and five vertical columns are semantic constants')
 dump(rulespath,rules)
 (base/'spec.md').write_text('# SMART 五维目标框架\n\n来源：蓝红 P125。S/M/A/R/T、英文和中文含义为固定框架标签；每维的解释与三条行动证据为可编辑字段。'
  +('蓝红短文案实填和 PowerPoint 渲染通过。' if a.reviewed else '语义字段已登记，实填与渲染待验收。')
  +'框架固定五列，不开放增减项数。Logo 原位保留；动效、HTML 和其他色系未验收。\n',encoding='utf-8')
 for theme in ('blue','red'):dump(a.samples/f'content-blue-125-{theme}.json',{'theme':theme,'item_count':5,'texts':SAMPLE})
 mp=root/'knowledge-manifest.json';m=json.loads(mp.read_text(encoding='utf-8-sig'))
 for rel in touched:m['files'][rel]=hashlib.sha256((root/rel).read_bytes()).hexdigest()
 dump(mp,m)
if __name__=='__main__':main()
