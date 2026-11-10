"""Structural audit of the isolated knowledge base and source coverage."""
from __future__ import annotations
import argparse,json,re
from collections import Counter
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile
from lxml import etree
from pptx import Presentation

ANS='http://schemas.openxmlformats.org/drawingml/2006/main'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--library',type=Path,required=True);ap.add_argument('--out',type=Path);a=ap.parse_args()
    root=a.library.resolve();issues=[]
    source=json.loads((root/'source-pages.json').read_text(encoding='utf-8'))
    catalog=json.loads((root/'catalog.json').read_text(encoding='utf-8'))
    manifest=json.loads((root/'knowledge-manifest.json').read_text(encoding='utf-8'))
    tech_inventory_path=root/'color-inventory-tech.json'
    if (root/'sources'/'tech.pptx').is_file():
        if not tech_inventory_path.is_file():issues.append('科技风颜色对象清单缺失')
        else:
            inventory=json.loads(tech_inventory_path.read_text(encoding='utf-8'))
            if inventory.get('page_count')!=85 or inventory.get('chart_parts')!=12 or inventory.get('status')!='inventory_only_no_recolor_claim':
                issues.append('科技风颜色对象清单状态或来源页数错误')
    expected_counts={'blue':295,'red':296,'cover':20}
    if (root/'sources'/'tech.pptx').is_file():expected_counts['tech']=85
    if (root/'sources'/'blue-supplement.pptx').is_file():expected_counts['blue-supplement']=14
    if (root/'sources'/'red-supplement.pptx').is_file():expected_counts['red-supplement']=24
    if len(source)!=sum(expected_counts.values()):issues.append(f'物理页位不是{sum(expected_counts.values())}：{len(source)}')
    by_kind=Counter(x['source'] for x in source)
    if dict(by_kind)!=expected_counts:issues.append('来源页数不匹配：'+str(dict(by_kind)))
    ids={e['id'] for e in catalog['layouts']}
    decks={kind:Presentation(root/'sources'/f'{kind}.pptx') for kind in expected_counts}
    deck_by_path={str((root/'sources'/f'{kind}.pptx').resolve()):deck for kind,deck in decks.items()}
    def all_shapes(shapes):
        for shape in shapes:
            yield shape
            if shape.shape_type==6:yield from all_shapes(shape.shapes)
    if len(ids)!=len(catalog['layouts']):issues.append('组件ID重复')
    checked_sources={}
    for record in source:
        if record['component_id'] not in ids:issues.append('来源映射无组件：'+str(record))
        path=root/record['source_pptx']
        if not path.is_file():issues.append('缺失单页：'+str(path));continue
        if path not in checked_sources:
            try:
                with ZipFile(path) as z:
                    if z.testzip():issues.append('损坏ZIP：'+str(path))
                    xml=z.read('ppt/presentation.xml');node=etree.fromstring(xml)
                    checked_sources[path]=len(node.xpath('.//*[local-name()="sldId"]'))
            except Exception as exc:issues.append('无法读取PPTX：'+str(path)+' '+str(exc))
        if record['page']>checked_sources.get(path,0):issues.append('来源页号超出源稿：'+str(record))
    for e in catalog['layouts']:
        for key in ('source','bindings','spec','layout_rules','motion','preview'):
            if key in e and not (root/e[key]).is_file():issues.append(f"{e['id']} 缺失 {key}: {e[key]}")
        if e.get('red_source_page'):
            if not e.get('red_bindings') or not (root/e['red_bindings']).is_file():
                issues.append(e['id']+'缺少红版专属绑定')
            else:
                blue_fields=json.loads((root/e['bindings']).read_text(encoding='utf-8'))['fields']
                red_fields=json.loads((root/e['red_bindings']).read_text(encoding='utf-8'))['fields']
                if [x['field'] for x in blue_fields]!=[x['field'] for x in red_fields]:issues.append(e['id']+'蓝红字段名未对齐')
        base_kind='tech' if e.get('style_family')=='deep-blue-tech' else 'cover' if e['role']=='cover' else 'red' if e['id'].startswith('content-red-') else 'blue'
        base_deck=deck_by_path.get(str((root/e['source']).resolve()))
        if base_deck is None:issues.append(e['id']+'来源未纳入审计');continue
        base_shapes={s.shape_id:s for s in all_shapes(base_deck.slides[e['source_page']-1].shapes)}
        if e.get('source_logo_shape_id'):
            logo=base_shapes.get(e['source_logo_shape_id'])
            if logo is None or logo.shape_type!=13 or sha256(logo.image.blob).hexdigest()!=e.get('source_logo_asset_sha256'):
                issues.append(e['id']+'来源Logo形状或图片哈希不符')
        if e.get('red_source_logo_shape_id'):
            red_deck=deck_by_path.get(str((root/e['red_source']).resolve()))
            red_shapes={s.shape_id:s for s in all_shapes(red_deck.slides[e['red_source_page']-1].shapes)} if red_deck else {}
            if e['red_source_logo_shape_id'] not in red_shapes:issues.append(e['id']+'红版Logo形状不存在')
        rules=json.loads((root/e['layout_rules']).read_text(encoding='utf-8'))
        ready_sources=e.get('ready_source_by_theme',{})
        ready_previews=e.get('ready_preview_by_theme',{})
        for theme,rel in ready_sources.items():
            ready_path=root/rel
            preview_path=root/ready_previews.get(theme,'')
            if not ready_path.is_file() or not preview_path.is_file():
                issues.append(e['id']+' '+theme+'已修整组件或预览缺失')
                continue
            try:
                ready=Presentation(ready_path)
                if len(ready.slides)!=1:raise ValueError('必须恰好一页')
                slide=ready.slides[0]
                shapes={shape.shape_id:shape for shape in all_shapes(slide.shapes)}
                binding_rel=e.get('red_bindings') if theme=='red' else e['bindings']
                fields=json.loads((root/binding_rel).read_text(encoding='utf-8'))['fields']
                for row in rules.get('body_text_presentation',{}).get('rows',[]):
                    field=next((f for f in fields if f.get('semantic_path')==row['body']),None)
                    body=shapes.get(field['shape_id']) if field else None
                    if body is None or not body.has_text_frame:raise ValueError('正文对象缺失')
                    for paragraph in body.text_frame.paragraphs:
                        if rules['body_text_presentation'].get('remove_bullets'):
                            if paragraph._p.xpath('./a:pPr/a:buAutoNum') or not paragraph._p.xpath('./a:pPr/a:buNone'):
                                raise ValueError('正文仍含自动序号')
                        if rules['body_text_presentation'].get('normal_weight') and any(run.font.bold is not False for run in paragraph.runs):
                            raise ValueError('正文仍为粗体')
                normal_cfg=rules.get('normal_body_weight',{})
                if normal_cfg:
                    roles=set(normal_cfg.get('semantic_roles',[]))
                    matched=[f for f in fields if f.get('semantic_role') in roles]
                    if not matched:raise ValueError('普通正文配置没有匹配到字段')
                    for field in matched:
                        body=shapes.get(field['shape_id'])
                        if body is None or not body.has_text_frame or any(run.font.bold is not False for paragraph in body.text_frame.paragraphs for run in paragraph.runs):
                            raise ValueError('普通正文仍为粗体或对象缺失')
                role=rules.get('page_background_role_by_theme',{}).get(theme)
                if role:
                    expected=rules['page_background_expected_rgb_by_theme'][theme].upper()
                    canvas=next((shape for shape in slide.shapes if shape.name=='brand:canvas:'+role),None)
                    if canvas is None or canvas.left!=0 or canvas.top!=0 or canvas.width!=ready.slide_width or canvas.height!=ready.slide_height or str(canvas.fill.fore_color.rgb).upper()!=expected:
                        raise ValueError('底层画布缺失或颜色漂移')
                    backing=rules.get('backing_shapes_by_theme',{}).get(theme,{})
                    for sid in backing.get('shape_ids',[]):
                        if sid not in shapes or str(shapes[sid].fill.fore_color.rgb).upper()!=backing['expected_rgb'].upper():
                            raise ValueError('五块衬底缺失或颜色漂移')
            except Exception as exc:
                issues.append(e['id']+' '+theme+'已修整组件不合规：'+str(exc))
        if rules.get('cardinality_mode')=='repeatable':
            units=rules['units'];known=set(base_shapes)
            if len(units)!=rules['source_count'] or any(sid not in known for unit in units for sid in unit):
                issues.append(e['id']+'数量原型目标形状与源页不符')
        motion=json.loads((root/e['motion']).read_text(encoding='utf-8'))
        if motion.get('status')=='prototype':
            known=set(base_shapes)
            if rules.get('cardinality_mode')=='tech_grid_2x3':
                tree=json.loads((root/e['shape_tree']).read_text(encoding='utf-8'))
                known={x['shape_id'] for x in tree['recursive_shapes']}
            if any(sid not in known for group in motion['groups'] for sid in group['shape_ids']):
                issues.append(e['id']+'动效原型目标形状与源页不符')
        if e.get('style_family')=='deep-blue-tech':
            if e.get('semantic_review'):
                review_path=root/e['semantic_review']
                if not review_path.is_file():issues.append(e['id']+'语义审查文件缺失')
                else:
                    review=json.loads(review_path.read_text(encoding='utf-8'))
                    expected_status=('static_pptx_verified_draft' if e.get('pptx_support')=='verified_static_draft' else 'not_verified')
                    if review.get('source_page')!=e['source_page'] or review.get('normal_use_status')!=expected_status:
                        issues.append(e['id']+'语义审查状态错误')
            if e['source_page']==22:
                bindings=json.loads((root/e['bindings']).read_text(encoding='utf-8'))
                locked={f['field'] for f in bindings['fields'] if f.get('semantic_role')=='decoration_locked'}
                if locked!={'text_37','text_57','text_67'}:issues.append(e['id']+'装饰字形锁定错误')
            for key in ('shape_tree','item_groups'):
                if not e.get(key) or not (root/e[key]).is_file():issues.append(e['id']+'缺少'+key)
            if e.get('item_groups') and (root/e['item_groups']).is_file():
                groups=json.loads((root/e['item_groups']).read_text(encoding='utf-8'))
                units=groups.get('units',[]);targets=[sid for u in units for sid in u['source_shape_ids']]
                if len(targets)!=len(set(targets)):issues.append(e['id']+'重复项对象归属冲突')
                if e['source_page'] in (9,49,51,69) and len(units)!=6:issues.append(e['id']+'六项分组不完整')
                if e['source_page'] in (9,49,51,69):
                    bindings=json.loads((root/e['bindings']).read_text(encoding='utf-8'))
                    field_ids={f['field']:f['shape_id'] for f in bindings['fields']}
                    for number,unit in enumerate(units,1):
                        named=unit.get('fields',{})
                        if not named or any(field_ids.get(key) not in unit['source_shape_ids'] for key in named.values()):
                            issues.append(e['id']+f'第{number}项字段归属错误')
                    if e['source_page'] in (9,49):
                        rules=json.loads((root/e['layout_rules']).read_text(encoding='utf-8'))
                        if rules.get('cardinality_mode')!='tech_grid_2x3' or rules.get('supported_counts')!=[2,3,4,5,6]:
                            issues.append(e['id']+'网格项数原型规则缺失')
                        if rules.get('unit_roots')!=[u['root_shape_id'] for u in units] or len(rules.get('row_parent_ids',[]))!=2:
                            issues.append(e['id']+'网格项数对象映射错误')
                        if any(sid not in base_shapes for sid in rules.get('row_parent_ids',[])+rules.get('row_strip_ids',[])):
                            issues.append(e['id']+'网格公共排组或底光带缺失')
                    if e['source_page']==69:
                        rules=json.loads((root/e['layout_rules']).read_text(encoding='utf-8'))
                        if rules.get('cardinality_mode')!='tech_schedule_rows' or rules.get('supported_counts')!=[2,3,4,5,6]:
                            issues.append(e['id']+'排期项数原型规则缺失')
                    if e['source_page']==51:
                        rules=json.loads((root/e['layout_rules']).read_text(encoding='utf-8'))
                        variants=rules.get('source_indices_by_count',{})
                        if rules.get('cardinality_mode')!='tech_six_pillars' or any(len(variants.get(str(n),[]))!=n for n in range(2,7)):
                            issues.append(e['id']+'立柱项数原型规则缺失')
                        bindings=json.loads((root/e['bindings']).read_text(encoding='utf-8'))
                        count_field=next((x for x in bindings['fields'] if x['field']=='text_280'),None)
                        if not count_field or count_field.get('semantic_role')!='computed_item_count':
                            issues.append(e['id']+'立柱中心数字未绑定项数')
            if e['role']=='cover':
                layers=e.get('background_layers',[])
                if not layers or any(not (root/layer['image']).is_file() for layer in layers):issues.append(e['id']+'封面图层缺失')
            if e['role']=='closing' and e.get('source_logo_present'):issues.append(e['id']+'封底来源Logo意外出现')
        if e['role']=='cover' and e['source']=='sources/cover.pptx':
            if not e.get('background_image') or not (root/e['background_image']).is_file():issues.append(e['id']+'缺少背景')
            try:
                with ZipFile(root/e['source']) as z:slide=etree.fromstring(z.read(f"ppt/slides/slide{e['source_page']}.xml"))
                text=''.join(slide.xpath('.//a:t/text()',namespaces={'a':ANS}))
                if '688232' not in text:issues.append(e['id']+'空版股票代码未保留')
                if e.get('slogan_locked') and e['slogan_locked'] not in text:issues.append(e['id']+'空版Slogan未保留')
            except Exception as exc:issues.append(e['id']+'品牌检查失败 '+str(exc))
    for rel,expected in manifest.get('files',{}).items():
        p=(root/rel).resolve()
        if not p.is_relative_to(root) or not p.is_file():issues.append('manifest缺失：'+rel)
        elif sha256(p.read_bytes()).hexdigest()!=expected:issues.append('manifest哈希错误：'+rel)
    report={'status':'pass' if not issues else 'fail','physical_pages':len(source),
            'component_entries':len(catalog['layouts']),'exact_pair_candidates':sum('red_source' in e for e in catalog['layouts']),
            'source_logo_entries':sum(bool(e.get('source_logo_shape_id')) for e in catalog['layouts']),
            'visual_reviewed_entries':sum(e.get('classification_status')=='visual_reviewed' for e in catalog['layouts']),
            'motion_prototype_entries':sum(e.get('motion_support')=='prototype_requires_playback_review' for e in catalog['layouts']),
            'source_counts':dict(by_kind),'manifest_files':len(manifest.get('files',{})),
            'issues':issues[:100],'issue_count':len(issues),
            'limits':['顶层配对未完成人工语义复核','旧三源 P01 封面及 P060 流程有 HTML 内部原型；科技风 P001 封面也有离线 HTML 内部原型','旧三源 P060 项数和动效原型放映未签收','科技风已验收 63 个固定项数短文静态 PPTX 草稿组件；其余 22 页仍为来源与结构初拆，P09/P49/P51/P69 的 2–6 项及 P38 的 2–4 步与逐项淡入是内部原型，整套 HTML 和换色未开放','科技风颜色对象清单仅完成来源盘点，未逐对象审核换色','预览未逐页视觉验收','显式色对象映射待审核']}
    if a.out:a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if issues:raise SystemExit(2)
if __name__=='__main__':main()

