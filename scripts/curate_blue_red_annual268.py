"""Bind the annual revenue chart, KPI equations and chart callouts."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

MAP={4:'page.title',27:'chart.callouts[0]',30:'chart.callouts[1]',32:'chart.callouts[2]',38:'chart.callouts[3]',
     39:'metrics.revenue.label',40:'metrics.revenue.value',55:'metrics.revenue.english',
     61:'metrics.cost.label',62:'metrics.cost.value',63:'metrics.cost.english',
     68:'metrics.profit.label',69:'metrics.profit.value',70:'metrics.profit.english',
     7:'analysis.title',13:'analysis.paragraphs[0]',16:'analysis.paragraphs[1]'}
VALUES=[220,240,250,260,280,300,330,340,350,360,370,400]
SAMPLE={'page.title':'年度数据｜项目经营分析',
        'chart.callouts[0]':'220W','chart.callouts[1]':'260W',
        'chart.callouts[2]':'300W','chart.callouts[3]':'400W',
        'metrics.revenue.label':'年度营收总额','metrics.revenue.value':'3700W',
        'metrics.revenue.english':'Total annual revenue',
        'metrics.cost.label':'年度成本支出','metrics.cost.value':'800W',
        'metrics.cost.english':'Annual cost expenditure',
        'metrics.profit.label':'年度利润总额','metrics.profit.value':'2900W',
        'metrics.profit.english':'Total annual profit',
        'analysis.title':'年度经营分析',
        'analysis.paragraphs[0]':'收入逐月增加，四季度形成稳定增长。项目按月跟踪交付与回款。',
        'analysis.paragraphs[1]':'年度成本为800万元，利润为2900万元。后续重点控制交付成本。'}

def dump(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
 p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--samples',type=Path,required=True);p.add_argument('--reviewed',action='store_true');a=p.parse_args()
 root=a.library.resolve();base=root/'layouts/content-blue-268';a.samples.mkdir(parents=True,exist_ok=True)
 touched={'catalog.json','layouts/content-blue-268/layout_rules.json','layouts/content-blue-268/spec.md'}
 for name in ('bindings.json','bindings-red.json'):
  path=base/name;b=json.loads(path.read_text(encoding='utf-8-sig'))
  if {x['shape_id'] for x in b['fields']}!=set(MAP):raise ValueError(name+' source text changed')
  for f in b['fields']:
   semantic=MAP[f['shape_id']];analysis=semantic.startswith('analysis.paragraphs')
   f.update(semantic_path=semantic,semantic_role=semantic.split('.')[-1],
            max_chars=min(f['max_chars'],65 if analysis else 32),
            max_lines=4 if analysis else 1)
  charts=b.get('objects',{}).get('charts',[])
  if len(charts)!=1 or charts[0]['shape_id']!=26:raise ValueError(name+' chart changed')
  charts[0]['categories_max']=12;charts[0]['series_max']=1
  dump(path,b);touched.add(path.relative_to(root).as_posix())
 catpath=root/'catalog.json';cat=json.loads(catpath.read_text(encoding='utf-8-sig'));e=next(x for x in cat['layouts'] if x['id']=='content-blue-268')
 e.update(role='data-chart',information_relation='annual-revenue-cost-profit',family_id='annual-finance-area-chart',
          classification_status='verified' if a.reviewed else 'visual_reviewed',
          pptx_support='verified_static' if a.reviewed else 'pending_render',
          batch_status='fixed_three_metrics_twelve_months_verified' if a.reviewed else 'fields_mapped_pending_render',
          semantic_review_status='verified_blue_red' if a.reviewed else 'fields_mapped_pending_render')
 dump(catpath,cat)
 rulepath=base/'layout_rules.json';rules=json.loads(rulepath.read_text(encoding='utf-8-sig'))
 rules.update(cardinality_mode='fixed',source_count=3,supported_counts=[3],
              verified_counts=[3] if a.reviewed else [],
              validation_status='verified_fixed_count' if a.reviewed else 'pending_render',
              count_evidence='three native KPI cards and one twelve-month area chart',
              annual_finance_consistency={'chart_shape_id':26,'revenue_field':'metrics.revenue.value',
                 'cost_field':'metrics.cost.value','profit_field':'metrics.profit.value',
                 'callouts':[['chart.callouts[0]',0,27],['chart.callouts[1]',3,30],
                             ['chart.callouts[2]',5,32],['chart.callouts[3]',11,38]],
                 'callout_plot_baseline_emu':6096000,
                 'callout_y_scale_emu_per_unit':6096})
 dump(rulepath,rules)
 (base/'spec.md').write_text('# 年度营收成本利润分析\n\n来源：蓝 P268／红 P269。固定三指标与十二个月面积图。'
    '营收必须等于月度数据之和，利润必须等于营收减成本，四个图表标注须等于所指月份。'
    +('蓝红短文案和虚构数据实填、PowerPoint 渲染通过。' if a.reviewed else '语义字段及公式已登记，实填渲染待验收。')
    +'指标卡和图表共用数据，不开放增减指标；Logo 保留原位。动效、HTML 与其他色系未验收。\n',encoding='utf-8')
 for theme in ('blue','red'):
  dump(a.samples/f'content-blue-268-{theme}.json',{'theme':theme,'item_count':3,'texts':SAMPLE,
     'charts':[{'shape_id':26,'categories':[f'{i}月' for i in range(1,13)],
                'series':[{'name':'月度营收','values':VALUES}],
                'unit':'万元','period':'2026年度','source':'虚构演示数据'}]})
 mp=root/'knowledge-manifest.json';m=json.loads(mp.read_text(encoding='utf-8-sig'))
 for rel in touched:m['files'][rel]=hashlib.sha256((root/rel).read_bytes()).hexdigest()
 dump(mp,m)
if __name__=='__main__':main()
