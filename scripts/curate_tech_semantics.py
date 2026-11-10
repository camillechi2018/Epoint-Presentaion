"""Record first-pass, machine-readable content fit for 16 representative pages."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from import_tech_style import dump, digest, VERSION

PROFILES = {
  6: ('navigation', 5, '五个章节入口，中文短标题、英文辅助行与编号一一对应', '章节数量变化仍需目录卡及底部光纹重排'),
  11: ('section', 1, '章节序号、中文标题、英文副题三层', '只适合章节过渡，不能承载正文'),
  16: ('hierarchy', 5, '中心指标、环形五类能力与外侧解释', '五类位置与连线关系不得打乱'),
  22: ('hierarchy', 3, '三层三角、三条解释与图标对应', '竖线装饰文字不可作为内容字段'),
  26: ('comparison', 4, '四类风险的标题、说明和编号', '四项是并列诊断，不代表时间先后'),
  32: ('process', 4, '四个立柱，每项标题、编号与双段说明', '长正文须拆页，图标须保持原位'),
  38: ('process', 4, '四步 OKR，每步编号、目标与证据', '曲线及图标随项数变化时须重排'),
  42: ('cycle', 4, '四角需求卡与中央循环结论', '中心环保持完整，四角文字限短'),
  45: ('process', 4, '曲线路径四节点，每项标题和解释', '节点与曲线路径必须同步移动'),
  53: ('metrics', 3, '三项指标数值、名称和解释成组', '数字、单位、口径与期别必须由项目输入提供'),
  64: ('timeline', 5, '五个时间节点的年份与事件说明', '时间顺序单调，预测标识不得混入历史事实'),
  69: ('schedule', 6, '六行时间、活动、负责人形状表格', '数据必须逐行对应；当前 2 至 6 行仅内部静态原型'),
  71: ('data-chart', 1, '结论卡与一张原生折线图', '结论必须从替换后的图表数据推导'),
  75: ('data-chart', 3, '一张原生趋势图与三项 KPI 卡', '三项 KPI 的数值口径需与图表一致'),
  77: ('hierarchy', 4, '四层人群金字塔、占比与特征说明', '原稿示例占比合计 132%，禁止复用为真实数据'),
  81: ('cycle', 3, '三层教育服务漏斗与右侧三段解释', '层级顺序固定，文本必须逐层对应'),
}


def curate(root: Path, update_manifest=True):
    path = root/'catalog.json'; cat=json.loads(path.read_text(encoding='utf-8'))
    for page,(relation,count,parts,risk) in PROFILES.items():
        entry=next(e for e in cat['layouts'] if e.get('style_family')=='deep-blue-tech' and e['source_page']==page)
        review=root/'layouts'/entry['id']/'semantic-review.json'
        record={'source_page':page,'component_id':entry['id'],'information_relation':relation,
                'source_item_count':count,'component_parts':parts,'content_fit_limit':risk,
                'review_status':'first_pass_visual_and_structure',
                'field_binding_status':'provisional_except_explicitly_reviewed_groups',
                'normal_use_status':'not_verified',
                'source_text_policy':'源稿中的业务、数字、人名均为示例，不得作为输出事实'}
        dump(review,record)
        entry['semantic_review']=review.relative_to(root).as_posix()
        entry['semantic_review_status']=record['review_status']
        if page==22:
            bindings=json.loads((root/entry['bindings']).read_text(encoding='utf-8'))
            byfield={f['field']:f for f in bindings['fields']}
            layer_fields=[('text_16','text_66','text_24'),
                          ('text_15','text_59','text_25'),
                          ('text_14','text_54','text_26')]
            record['layer_field_mapping']=[{'level':i+1,'pyramid':row[0],
                                            'badge':row[1],'description':row[2]}
                                           for i,row in enumerate(layer_fields)]
            for i,row in enumerate(layer_fields,1):
                for role,key in zip(('pyramid','badge','description'),row):
                    byfield[key]['semantic_key']=f'layer_{i}.{role}'
                    byfield[key]['semantic_role']='layer_field_reviewed'
            for key in ('text_37','text_57','text_67'):
                if not set(byfield[key]['source_text']) <= {'|',' ','\n'}:raise ValueError('P22 装饰字段原稿发生变化')
                byfield[key]['semantic_role']='decoration_locked'
                byfield[key]['semantic_key']='native_hatch'
            dump(root/entry['bindings'],bindings)
            dump(review,record)
    dump(path,cat)
    if update_manifest:
        files={p.relative_to(root).as_posix():digest(p) for p in root.rglob('*')
               if p.is_file() and '.git' not in p.parts and p.name not in
               ('knowledge-manifest.json','audit-report.json','blank.pptx','blank-red.pptx')
               and 'source-pages' not in p.relative_to(root).parts}
        dump(root/'knowledge-manifest.json',{'schema_version':'1.0','version':VERSION,
                                            'status':'draft_pending_review','file_count':len(files),'files':files})
    return len(PROFILES)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True)
    print(curate(p.parse_args().library))
