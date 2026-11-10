"""Bind four native charts, monthly finance table and three percentage rings."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

MAP={10:'page.title',18:'metrics.visitors.label',19:'metrics.visitors.value',
 25:'metrics.deals.label',26:'metrics.deals.value',35:'metrics.revenue.label',36:'metrics.revenue.value',
 42:'metrics.cost.label',43:'metrics.cost.value',49:'metrics.balance.label',50:'metrics.balance.value',
 99:'metrics.visitors.note',100:'metrics.deals.note',101:'metrics.revenue.note',
 102:'metrics.cost.note',103:'metrics.balance.note',
 7:'chart.callouts[0]',13:'chart.callouts[1]',105:'chart.callouts[2]',108:'chart.callouts[3]',
 121:'shares[0].value',122:'shares[0].label',123:'shares[0].english',
 125:'shares[1].value',126:'shares[1].label',127:'shares[1].english',
 129:'shares[2].value',139:'shares[2].label',133:'shares[2].english'}
INCOME=[400,450,500,520,550,570,600,620,650,680,700,750]
COST=[150,160,180,190,200,210,220,230,240,250,260,280]
FEE=[80,80,90,90,100,100,110,110,120,120,130,130]
BALANCE=[a-b-c for a,b,c in zip(INCOME,COST,FEE)]
SAMPLE={'page.title':'经营数据｜年度指标与月度明细',
 'metrics.visitors.label':'访客量（人）','metrics.visitors.value':'8,920',
 'metrics.deals.label':'成交量（人）','metrics.deals.value':'3,210',
 'metrics.revenue.label':'收入(万)','metrics.revenue.value':'6990',
 'metrics.cost.label':'成本(万)','metrics.cost.value':'2570',
 'metrics.balance.label':'结余(万)','metrics.balance.value':'3160',
 'metrics.visitors.note':'全年访客量持续增长','metrics.deals.note':'成交人数稳步提升',
 'metrics.revenue.note':'年度收入较期初增加','metrics.cost.note':'成本控制按月跟进',
 'metrics.balance.note':'全年结余保持增长',
 'chart.callouts[0]':'A组\n一期达峰','chart.callouts[1]':'B组\n二期达峰',
 'chart.callouts[2]':'C组\n三期达峰','chart.callouts[3]':'D组\n四期达峰'}
for i,(share,name) in enumerate([(32,'服务A'),(42,'服务B'),(26,'服务C')]):
 SAMPLE[f'shares[{i}].value']=f'{share}%';SAMPLE[f'shares[{i}].label']=f'{name}收入占比';
 SAMPLE[f'shares[{i}].english']=f'{share}% share of annual revenue'

def chart(shape_id,categories,series,unit):return {'shape_id':shape_id,'categories':categories,'series':series,
 'unit':unit,'period':'2026年度','source':'虚构演示数据'}
CHARTS=[chart(2,['一期','二期','三期','四期'],[
 {'name':'A','values':[5,3,4,2]},{'name':'B','values':[1,5,2,4]},
 {'name':'C','values':[3,2,5,3]},{'name':'D','values':[2,4,3,5]}],'分')]
for sid,share in [(120,32),(124,42),(128,26)]:
 CHARTS.append(chart(sid,['该服务','其他'],[{'name':'收入占比','values':[share,100-share]}],'%'))
TABLE=[['月份']+[f'{i}月' for i in range(1,13)]]
for name,row in [('收入',INCOME),('成本',COST),('费用',FEE),('结余',BALANCE)]:
 TABLE.append([name]+[str(v) for v in row])

def dump(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
 p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--samples',type=Path,required=True);p.add_argument('--reviewed',action='store_true');a=p.parse_args()
 root=a.library.resolve();base=root/'layouts/content-blue-036';a.samples.mkdir(parents=True,exist_ok=True)
 touched={'catalog.json','layouts/content-blue-036/layout_rules.json','layouts/content-blue-036/spec.md'}
 for name in ('bindings.json','bindings-red.json'):
  path=base/name;b=json.loads(path.read_text(encoding='utf-8-sig'))
  if {f['shape_id'] for f in b['fields']}!=set(MAP):raise ValueError(name+' source text changed')
  for f in b['fields']:
   key=MAP[f['shape_id']];f.update(semantic_path=key,semantic_role=key.split('.')[-1],
     max_chars=min(f['max_chars'],4 if f['shape_id'] in (36,43,50) else 36 if key.endswith('.english') else 28),
     max_lines=2 if key.startswith('chart.callouts') else 1)
  for item in b.get('objects',{}).get('charts',[]):
   item['categories_max']=4 if item['shape_id']==2 else 2
   item['series_max']=4 if item['shape_id']==2 else 1
  dump(path,b);touched.add(path.relative_to(root).as_posix())
 catpath=root/'catalog.json';cat=json.loads(catpath.read_text(encoding='utf-8-sig'));e=next(x for x in cat['layouts'] if x['id']=='content-blue-036')
 e.update(role='data-chart',information_relation='multi-metric-finance-dashboard',family_id='four-charts-monthly-table',
  classification_status='verified' if a.reviewed else 'visual_reviewed',
  pptx_support='verified_static' if a.reviewed else 'pending_render',
  batch_status='fixed_four_charts_one_table_verified' if a.reviewed else 'fields_mapped_pending_render',
  semantic_review_status='verified_blue_red' if a.reviewed else 'fields_mapped_pending_render')
 dump(catpath,cat)
 rulepath=base/'layout_rules.json';rules=json.loads(rulepath.read_text(encoding='utf-8-sig'))
 rules.update(cardinality_mode='fixed',source_count=4,supported_counts=[4],
  verified_counts=[4] if a.reviewed else [],
  validation_status='verified_fixed_count' if a.reviewed else 'pending_render',
  four_chart_table_consistency={'share_chart_ids':[120,124,128],
    'share_text_fields':[f'shares[{i}].value' for i in range(3)],
    'table_shape_id':135,
    'table_total_fields':[['metrics.revenue.value',0],['metrics.cost.value',1],['metrics.balance.value',3]]})
 dump(rulepath,rules)
 (base/'spec.md').write_text('# 四图一表经营看板\n\n来源：蓝红 P036。固定一张四组柱图、三张构成环图和一张 12 月原生表格。'
  '三张环图的占比文字须与数据相等且合计 100%；每月结余等于收入减成本减费用，年度指标须与表格合计一致。'
  +('蓝红虚构数据实填及 PowerPoint 渲染通过。' if a.reviewed else '语义字段与数据约束已登记，渲染待验收。')
  +'不开放图表模块增减；Logo 原位保留。动效、HTML、其他色系未验收。\n',encoding='utf-8')
 for theme in ('blue','red'):
  dump(a.samples/f'content-blue-036-{theme}.json',{'theme':theme,'item_count':4,'texts':SAMPLE,
   'charts':CHARTS,'tables':[{'shape_id':135,'rows':TABLE}]})
 mp=root/'knowledge-manifest.json';m=json.loads(mp.read_text(encoding='utf-8-sig'))
 for rel in touched:m['files'][rel]=hashlib.sha256((root/rel).read_bytes()).hexdigest()
 dump(mp,m)
if __name__=='__main__':main()
