"""Fill one editable template; fail before writing on missing facts or capacity errors."""
from library_location import get_library
from normalize_fonts import normalize
from pathlib import Path
from copy import deepcopy
import argparse,json,math,unicodedata,re,subprocess
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.oxml.xmlchemy import OxmlElement
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.dml.color import RGBColor
from pptx.util import Pt
from PIL import Image
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from layout_safety import apply_constraints
from logo_brand import add_logo, load_config, settings as logo_settings
from materialize_component_colors import freeze as materialize_component_colors
NS={'a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
def walk(ss):
    for s in ss:
        yield s
        if s.shape_type==6:yield from walk(s.shapes)
def visual_width_units(text):
    return sum(2 if unicodedata.east_asian_width(char) in ('W','F') else 1 for char in text)
def set_text(sh,text):
    tf=sh.text_frame;p0=deepcopy(tf.paragraphs[0]._p)
    for c in list(tf._txBody):
        if c.tag.endswith('}p'):tf._txBody.remove(c)
    for line in text.split('\n'):
        p=deepcopy(p0);first=p.find('a:r',NS);props=deepcopy(first.find('a:rPr',NS)) if first is not None and first.find('a:rPr',NS) is not None else None
        pp=p.find('a:pPr',NS)
        if pp is None:pp=OxmlElement('a:pPr');p.insert(0,pp)
        pp.set('hangingPunct','0');pp.set('eaLnBrk','1')
        # Source paragraphs often use full justification for long demo copy.
        # Short replacement facts otherwise acquire large gaps between Chinese characters.
        if pp.get('algn') in {'just','dist','justLow','thaiDist'}:pp.set('algn','l')
        for c in list(p):
            if c.tag.rsplit('}',1)[-1] not in ['pPr','endParaRPr']:p.remove(c)
        r=OxmlElement('a:r')
        if props is not None:r.append(props)
        t=OxmlElement('a:t');t.text=line;r.append(t);end=p.find('a:endParaRPr',NS)
        if end is None:p.append(r)
        else:p.insert(list(p).index(end),r)
        tf._txBody.append(p)
def select_source_page(presentation,page_number):
    ids=list(presentation.slides._sldIdLst)
    if page_number<1 or page_number>len(ids):raise ValueError('来源页号越界')
    keep=ids[page_number-1]
    for item in ids:
        if item is keep:continue
        presentation.part.drop_rel(item.rId);presentation.slides._sldIdLst.remove(item)
    return presentation.slides[0]

def clear_source_motion(slide):
    """Remove source slide timing/transition settings before applying new motion."""
    root=slide._element
    for node in list(root):
        kind=node.tag.rsplit('}',1)[-1]
        if kind in ('transition','timing'):
            root.remove(node)
        elif kind=='AlternateContent':
            for descendant in list(node.iter()):
                if descendant is node:continue
                if descendant.tag.rsplit('}',1)[-1] in ('transition','timing'):
                    descendant.getparent().remove(descendant)
            if not any(child.tag.rsplit('}',1)[-1] not in ('Choice','Fallback') or len(child) for child in node):
                root.remove(node)
def apply_tech_grid(slide,rules,count):
    if count is None:count=6
    if type(count) is not int or count not in rules['supported_counts']:raise ValueError('网格项数不在支持范围')
    parents={shape.shape_id:shape for shape in slide.shapes if shape.shape_id in rules['row_parent_ids']}
    if len(parents)!=2:raise ValueError('网格来源排组不完整')
    parent_order=[parents[sid] for sid in rules['row_parent_ids']]
    roots=[]
    for root_id in rules['unit_roots']:
        parent=next((g for g in parent_order if any(x.shape_id==root_id for x in g.shapes)),None)
        if parent is None:raise ValueError(f'网格单项对象缺失 {root_id}')
        child=next(x for x in parent.shapes if x.shape_id==root_id)
        tx=parent._element.grpSpPr.xfrm
        scale_x=parent.width/tx.chExt.cx;scale_y=parent.height/tx.chExt.cy
        box=(round(parent.left+(child.left-tx.chOff.x)*scale_x),
             round(parent.top+(child.top-tx.chOff.y)*scale_y),
             round(child.width*scale_x),round(child.height*scale_y))
        child._element.getparent().remove(child._element)
        slide.shapes._spTree.append(child._element)
        child.left,child.top,child.width,child.height=box
        roots.append(child)
    for parent in parent_order:
        parent._element.getparent().remove(parent._element)
    x0=roots[0].left;spacing=roots[1].left-roots[0].left
    upper=roots[0].top;lower=roots[3].top
    top_count=count if count<=3 else (2 if count==4 else 3)
    bottom_count=count-top_count
    for i,shape in enumerate(roots):
        if i>=count:
            shape._element.getparent().remove(shape._element)
            continue
        row=0 if i<top_count else 1
        row_count=top_count if row==0 else bottom_count
        col=i if row==0 else i-top_count
        shape.left=round(x0+(3-row_count)*spacing/2+col*spacing)
        shape.top=round((upper+lower)/2) if bottom_count==0 else (upper if row==0 else lower)
    strip_ids=rules.get('row_strip_ids',[])
    if strip_ids:
        strips={s.shape_id:s for s in slide.shapes if s.shape_id in strip_ids}
        if len(strips)!=2:raise ValueError('网格公共底光带缺失')
        for row,sid in enumerate(strip_ids):
            strip=strips[sid]
            row_count=top_count if row==0 else bottom_count
            if not row_count:
                strip._element.getparent().remove(strip._element)
                continue
            shift=round((3-row_count)*spacing/2)
            strip.left+=shift
            strip.width-=round((3-row_count)*spacing)
            if bottom_count==0:strip.top+=round((lower-upper)/2)
    return {'mode':'tech_grid_2x3','count':count,'source_count':6,
            'top_count':top_count,'bottom_count':bottom_count,
            'status':rules['validation_status']}
def apply_directory_reflow(slide,rules,count,items,theme):
    """Move or clone native directory units, keeping source styling editable."""
    if type(count) is not int or count not in rules['supported_counts']:
        raise ValueError('目录项数不在已验证范围')
    units=rules['directory_units'];source_count=rules['source_count']
    if len(units)!=source_count or not isinstance(items,list) or len(items)!=count:
        raise ValueError('目录单元与输入项数不一致')
    shapes={s.shape_id:s for s in walk(slide.shapes)}
    if any(sid not in shapes for unit in units for sid in unit['shape_ids']):
        raise ValueError('目录来源对象缺失')
    original=[{sid:shapes[sid] for sid in unit['shape_ids']} for unit in units]
    original_geometry={sid:(sh.left,sh.top,sh.width,sh.height) for unit in original for sid,sh in unit.items()}
    anchors=[(shapes[u['anchor_shape_id']].left,shapes[u['anchor_shape_id']].top) for u in units]
    inch=914400;kind=rules['directory_layout']
    def grid(cols,first_x,step_x,first_y,step_y):
        row_counts=([2,2] if cols==3 and count==4 else [3,2] if cols==3 and count==5 else
                    [cols]*(count//cols)+([count%cols] if count%cols else []))
        rows=len(row_counts);result=[]
        for i in range(count):
            row=next(r for r in range(rows) if i<sum(row_counts[:r+1]))
            in_row=row_counts[row];col=i-sum(row_counts[:row])
            x=first_x+(cols-in_row)*step_x/2+col*step_x
            result.append((round(x*inch),round((first_y+row*step_y)*inch)))
        return result
    if kind=='primary_grid':
        targets=grid(3,1.69,4.11,3.36 if count<=3 else 2.22,2.29) if count<=6 else grid(4,.75,3.15,2.22,2.29)
        sx=sy=1.0
    elif kind=='plain_two_column':
        first_y=3.75 if count<=2 else 3.1 if count<=4 else 2.52
        targets=grid(2,1.89,5.5,first_y,1.31) if count<=6 else grid(2,1.89,5.5,2.16,1.08)
        sx=sy=1.0
    elif kind=='tall_cards':
        targets=grid(count,0.93+(6-count)*.97,1.94,2.93,0) if count<=6 else grid(4,.93,2.9,2.35,2.23)
        sx=1.0 if count<=6 else 1.5;sy=1.0 if count<=6 else .48
    elif kind=='line_numbers':
        targets=grid(count,.77+(6-count)*1.005,2.01,3.81,0) if count<=6 else grid(4,1.25,2.9,2.5,2.15)
        sx=1.0 if count<=6 else 1.16;sy=1.0 if count<=6 else .82
    elif kind=='two_column_cards':
        first_y=3.9 if count<=2 else 3.25 if count<=4 else 2.56
        targets=grid(2,1.79,5.5,first_y,1.405) if count<=6 else grid(2,1.79,5.5,2.27,1.06)
        sx=1.0;sy=1.0 if count<=6 else .82
    elif kind=='tech_five_cards':
        targets=grid(count,.72+(5-count)*1.2,2.4,3.04,0) if count<=5 else grid(3,1.0,4.13,2.82,1.94)
        sx=1.0 if count<=5 else 1.12;sy=1.0 if count<=5 else .66
    elif kind=='tech_diagonal':
        targets=[(round((5.55-i*.63)*inch),round((1.05+i*1.17+(5-count)*.585)*inch)) for i in range(count)] if count<=5 else [(round((5.7-i*.57)*inch),round((.72+i*1.02)*inch)) for i in range(count)]
        sx=sy=1.0
    elif kind=='tech_arc':
        x=[6.03,5.29,5.09,5.29,6.05,6.45]
        step=1.25 if count<=5 else 1.03;first=.81+(5-count)*.625 if count<=5 else .7
        targets=[(round(x[i]*inch),round((first+i*step)*inch)) for i in range(count)]
        sx=sy=1.0
    elif kind=='tech_four_cards':
        targets=grid(2,1.59,5.31,3.08 if count<=2 else 1.98,2.2) if count<=4 else grid(2,1.59,5.31,1.75,1.72)
        sx=1.0;sy=1.0 if count<=4 else .78
    else:raise ValueError('未知目录重排模式')
    next_id=max(s.shape_id for s in walk(slide.shapes))+1
    def clone(src):
        nonlocal next_id
        node=deepcopy(src._element);mapping={}
        for item in list(node.iter()):
            if item.tag.rsplit('}',1)[-1]=='tags':
                item.getparent().remove(item)
                continue
            if item.tag.rsplit('}',1)[-1]=='cNvPr' and item.get('id'):
                old=int(item.get('id'));mapping[old]=next_id;item.set('id',str(next_id));next_id+=1
        slide.shapes._spTree.append(node)
        new=next(s for s in slide.shapes if s.shape_id==mapping[src.shape_id])
        return new,mapping
    extras={}
    for i in range(source_count,count):
        source_index=source_count-1;unit=units[source_index];shape_map={};id_map={}
        for sid in unit['shape_ids']:
            new,mapping=clone(original[source_index][sid]);shape_map[sid]=new;id_map.update(mapping)
        extras[i]=(shape_map,id_map)
    for i in range(count):
        source_index=i if i<source_count else source_count-1
        unit=units[source_index];source_anchor=anchors[source_index]
        shape_map={};id_map={}
        if i<source_count:
            shape_map=original[source_index]
        else:
            shape_map,id_map=extras[i]
        dx,dy=targets[i]
        for sid,shape in shape_map.items():
            left,top,width,height=original_geometry[sid]
            shape.left=round(dx+(left-source_anchor[0])*sx)
            shape.top=round(dy+(top-source_anchor[1])*sy)
            shape.width=round(width*sx);shape.height=round(height*sy)
            if (sx<1 or sy<1) and shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    for run in para.runs:
                        if run.font.size:run.font.size=round(run.font.size*(.82 if kind=='tall_cards' else min(sx,sy)))
            if kind=='tech_four_cards' and count>4 and shape.shape_type==6:
                for child in walk(shape.shapes):
                    if child.has_text_frame:
                        for para in child.text_frame.paragraphs:
                            for run in para.runs:
                                if run.font.size:run.font.size=round(run.font.size*sy)
        if i>=source_count:
            nested={s.shape_id:s for s in walk(slide.shapes)}
            for key,old in unit.get('text_shape_ids',{}).items():
                new_id=id_map.get(old)
                if new_id and new_id in nested:set_text(nested[new_id],f'{i+1:02d}' if key=='number' else items[i][key])
        if kind=='primary_grid' and len(items[i].get('subtitle',''))>12:
            subtitle_id=unit['text_shape_ids'].get('subtitle')
            subtitle=shape_map.get(subtitle_id)
            if subtitle is not None:subtitle.height=max(subtitle.height,Pt(30))
        number_id=unit.get('number_shape_id')
        if number_id and i<source_count and number_id in shapes:
            set_text(shapes[number_id],f'{i+1:02d}')
        if kind=='tall_cards' and count>6:
            for key,size in (('number',24),('title',16)):
                sid=unit['text_shape_ids'][key]
                target=shape_map.get(sid)
                if target and target.has_text_frame:
                    for para in target.text_frame.paragraphs:
                        for run in para.runs:run.font.size=Pt(size)
        if kind=='tech_five_cards' and count==6:
            sid=unit['number_shape_id'];target=shape_map.get(sid)
            if target:
                target.top=dy+round(1.19*inch);target.height=round(.48*inch)
                for para in target.text_frame.paragraphs:
                    for run in para.runs:
                        run.font.size=Pt(25);run.font.color.rgb=RGBColor(255,255,255)
        if kind=='primary_grid' and i>=source_count:
            number_group=shape_map[unit['anchor_shape_id']]
            number_group._element.getparent().remove(number_group._element)
            title=shape_map[unit['text_shape_ids']['title']]
            color=RGBColor.from_string(rules['directory_primary_rgb_by_theme'][theme])
            box=slide.shapes.add_textbox(dx-round(.06*inch),dy-round(.32*inch),round(1.86*inch),round(1.1*inch))
            box.text=f'{i+1:02d}'
            para=box.text_frame.paragraphs[0];para.alignment=PP_ALIGN.CENTER
            for run in para.runs:
                run.font.name='Arial';run.font.size=Pt(64);run.font.bold=False
                if color:run.font.color.rgb=color
            line=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,dx-round(.05*inch),dy+round(.66*inch),round(1.84*inch),round(.018*inch))
            line.line.fill.background()
            if color:line.fill.solid();line.fill.fore_color.rgb=color
    for unit in units[count:]:
        for sid in unit['shape_ids']:
            node=shapes[sid]._element
            if node.getparent() is not None:node.getparent().remove(node)
    return {'mode':'directory_reflow','count':count,'source_count':source_count,
            'status':rules['validation_status'],'layout':kind}
def apply_tech_pillars(slide,rules,count):
    if count is None:count=6
    if type(count) is not int or count not in rules['supported_counts']:raise ValueError('立柱项数不在支持范围')
    selected=rules['source_indices_by_count'][str(count)]
    if len(selected)!=count or len(set(selected))!=count:raise ValueError('立柱来源槽位规则不完整')
    shapes={s.shape_id:s for s in slide.shapes}
    groups=rules['units'];anchors=rules['anchor_shape_ids']
    if len(groups)!=6 or len(anchors)!=6:raise ValueError('立柱来源结构不完整')
    if any(sid not in shapes for group in groups for sid in group):raise ValueError('立柱对象缺失')
    source_lefts=[shapes[sid].left for sid in anchors]
    spacing=rules['spacing_emu_by_count'][str(count)]
    width=shapes[anchors[0]].width
    first=round((rules['canvas_width_emu']-(count-1)*spacing-width)/2)
    for index,group in enumerate(groups):
        if index not in selected:
            for sid in group:
                node=shapes[sid]._element;node.getparent().remove(node)
            continue
        logical=selected.index(index)
        delta=first+logical*spacing-source_lefts[index]
        for sid in group:shapes[sid].left+=delta
    set_text(shapes[rules['computed_count_shape_id']],str(count))
    return {'mode':'tech_six_pillars','count':count,'source_count':6,
            'source_slots':[i+1 for i in selected],'status':rules['validation_status']}
def apply_cardinality(slide,rules,count,items=None,theme=None):
    if rules.get('cardinality_mode')=='directory_reflow':
        return apply_directory_reflow(slide,rules,count,items,theme)
    if rules.get('cardinality_mode')=='directory_grid_3x2':
        if count is None:count=6
        if type(count) is not int or count not in rules['supported_counts']:
            raise ValueError('目录项数须在已验证的 2–6 项内')
        shapes={s.shape_id:s for s in slide.shapes}
        units=rules['units'];anchors=rules['anchor_shape_ids']
        if len(units)!=6 or len(anchors)!=6 or any(sid not in shapes for unit in units for sid in unit):
            raise ValueError('目录来源对象不完整')
        source=[(shapes[sid].left,shapes[sid].top) for sid in anchors]
        lefts=[source[i][0] for i in (0,1,2)]
        top,bottom=source[0][1],source[3][1]
        center=(top+bottom)//2
        two=[(lefts[0]+lefts[1])//2,(lefts[1]+lefts[2])//2]
        if count==2: targets=[(two[0],center),(two[1],center)]
        elif count==3: targets=[(x,center) for x in lefts]
        elif count==4: targets=[(x,y) for y in (top,bottom) for x in two]
        elif count==5: targets=[(x,top) for x in lefts]+[(x,bottom) for x in two]
        else: targets=[(x,y) for y in (top,bottom) for x in lefts]
        for unit in units[count:]:
            for sid in unit:
                node=shapes[sid]._element;node.getparent().remove(node)
        for i,unit in enumerate(units[:count]):
            dx=targets[i][0]-source[i][0];dy=targets[i][1]-source[i][1]
            for sid in unit:shapes[sid].left+=dx;shapes[sid].top+=dy
        return {'mode':'directory_grid_3x2','count':count,'source_count':6,
                'status':rules['validation_status'],'rows':1 if count<=3 else 2}
    if rules.get('cardinality_mode')=='process_terminal':
        if count is None:count=rules['source_count']
        if type(count) is not int or count not in rules['supported_counts']:
            raise ValueError('流程项数不在已验证范围')
        shapes={s.shape_id:s for s in slide.shapes}
        units=rules['units'];connectors=rules['connector_shape_ids']
        selected=rules['source_indices_by_count'][str(count)]
        if len(units)!=5 or len(selected)!=count or selected[-1]!=4 or len(connectors)!=4:
            raise ValueError('流程终点规则不完整')
        if any(sid not in shapes for unit in units for sid in unit) or any(sid not in shapes for sid in connectors):
            raise ValueError('流程来源对象缺失')
        if count==5:
            return {'mode':'process_terminal','count':5,'source_count':5,
                    'source_slots':[1,2,3,4,5],'status':rules['validation_status']}
        base=rules['source_lefts_emu'];spacing=rules['spacing_emu']
        first=base[0]+(5-count)*spacing//2
        for index,unit in enumerate(units):
            if index not in selected:
                for sid in unit:shapes[sid]._element.getparent().remove(shapes[sid]._element)
                continue
            delta=first+selected.index(index)*spacing-base[index]
            for sid in unit:shapes[sid].left+=delta
        for index,sid in enumerate(connectors):
            if index>=count-1:shapes[sid]._element.getparent().remove(shapes[sid]._element)
            else:shapes[sid].left=first+index*spacing+rules['connector_offset_emu']
        return {'mode':'process_terminal','count':count,'source_count':5,
                'source_slots':[i+1 for i in selected],'status':rules['validation_status']}
    if rules.get('cardinality_mode')=='tech_process_columns':
        if count is None:count=rules['source_count']
        if type(count) is not int or count not in rules['supported_counts']:
            raise ValueError('四步路径项数不在支持范围')
        shapes={s.shape_id:s for s in slide.shapes}
        units=rules['units'];anchors=rules['anchor_shape_ids']
        if len(units)!=4 or len(anchors)!=4 or any(sid not in shapes for unit in units for sid in unit):
            raise ValueError('四步路径来源对象不完整')
        source_lefts=[shapes[sid].left for sid in anchors]
        width=shapes[anchors[0]].width
        spacing=rules['spacing_emu']
        first=round((rules['canvas_width_emu']-(count-1)*spacing-width)/2)
        for i,unit in enumerate(units):
            if i>=count:
                for sid in unit:
                    node=shapes[sid]._element;node.getparent().remove(node)
                continue
            delta=first+i*spacing-source_lefts[i]
            for sid in unit:shapes[sid].left+=delta
        return {'mode':'tech_process_columns','count':count,'source_count':4,
                'status':rules['validation_status'],'spacing_emu':spacing}
    if rules.get('cardinality_mode')=='tech_six_pillars':
        return apply_tech_pillars(slide,rules,count)
    if rules.get('cardinality_mode')=='tech_grid_2x3':
        return apply_tech_grid(slide,rules,count)
    if rules.get('cardinality_mode')=='tech_schedule_rows':
        if count is None:count=rules['source_count']
        if type(count) is not int or count not in rules['supported_counts']:raise ValueError('排期行数不在支持范围')
        all_shapes={s.shape_id:s for s in slide.shapes}
        units=rules['units'];source_tops=rules['source_row_tops_emu']
        if len(units)!=6 or len(source_tops)!=6:raise ValueError('排期来源行组不完整')
        for unit in units:
            if any(sid not in all_shapes for sid in unit):raise ValueError('排期行对象缺失')
        for unit in units[count:]:
            for sid in unit:
                node=all_shapes[sid]._element;node.getparent().remove(node)
        emu=914400;center=(source_tops[0]+source_tops[-1])//2
        spacing=min(int(1.45*emu),(source_tops[-1]-source_tops[0])//(count-1))
        first=center-spacing*(count-1)//2
        for i,unit in enumerate(units[:count]):
            delta=first+i*spacing-source_tops[i]
            for sid in unit:all_shapes[sid].top+=delta
        connector=all_shapes[rules['shared_connector_shape_id']]
        connector.top=first+int(.25*emu)
        connector.height=spacing*(count-1)
        return {'mode':'tech_schedule_rows','count':count,'source_count':6,
                'status':rules['validation_status'],'spacing_emu':spacing}
    if rules.get('cardinality_mode')!='repeatable':
        if count is not None and count!=rules.get('source_count'):raise ValueError('此组件未开放数量变化')
        return {'mode':'fixed','count':rules.get('source_count')}
    if count is None:count=rules['source_count']
    if type(count) is not int or count not in rules['supported_counts']:raise ValueError('项数未在该组件支持范围内')
    groups=rules['units'];source_count=rules['source_count']
    if len(groups)!=source_count:raise ValueError('数量规则与来源结构不一致')
    all_shapes={s.shape_id:s for s in slide.shapes};spacing=rules['spacing_emu']
    for group in groups[count:]:
        for sid in group:
            if sid not in all_shapes:raise ValueError(f'数量规则缺失形状 {sid}')
            node=all_shapes[sid]._element;node.getparent().remove(node)
    delta=(source_count-count)*spacing//2
    for group in groups[:count]:
        for sid in group:all_shapes[sid].left+=delta
    arrow=all_shapes[rules['arrow_shape_id']]
    arrow.left+=delta;arrow.width-=(source_count-count)*spacing
    return {'mode':'repeatable','count':count,'source_count':source_count,'status':rules['validation_status']}
def apply_project_schedule(slide,rules,tasks):
    shapes={s.shape_id:s for s in slide.shapes}
    rows=rules['schedule_rows']
    if len(rows)!=6 or len(tasks)!=6:raise ValueError('年度排期必须为六个项目')
    for index,(shape_ids,task) in enumerate(zip(rows,tasks)):
        bars=[shapes.get(sid) for sid in shape_ids['bars']]
        labels=[shapes.get(sid) for sid in shape_ids['labels']]
        if any(shape is None for shape in bars+labels):raise ValueError('年度排期条或标签对象缺失')
        durations=task['durations']
        if not isinstance(durations,list) or len(durations)!=3 or any(type(d) is not int or d<2 for d in durations) or sum(durations)!=12:
            raise ValueError(f'第{index+1}个项目的三段时长须为至少两个月且总计十二个月')
        left=bars[0].left;right=bars[-1].left+bars[-1].width
        width=right-left;gap=rules['bar_gap_emu'];offset=rules['label_offset_emu']
        passed=0
        for stage,(bar,label,months) in enumerate(zip(bars,labels,durations)):
            start=left+round(passed*width/12)
            end=left+round((passed+months)*width/12)
            bar.left=start+(gap//2 if stage else 0)
            bar.width=end-start-(gap if stage==1 else gap//2)
            label.left=bar.left+offset
            passed+=months
    return {'rows':6,'phases_per_row':3,'geometry_bound_to_durations':True}
def apply_tech_font_roles(path,binding_data):
    role_fonts={'chinese_display':'Microsoft YaHei','chinese_heading':'Microsoft YaHei',
                'chinese_body':'Microsoft YaHei','latin_numeric':'Arial'}
    roles={x['shape_id']:x.get('typography_role') for x in binding_data.get('fields',[])}
    p=Presentation(path);changed=0
    for shape in walk(p.slides[0].shapes):
        font=role_fonts.get(roles.get(shape.shape_id))
        if not font or not shape.has_text_frame:continue
        for paragraph in shape.text_frame.paragraphs:
            for run in paragraph.runs:
                run.font.name=font
                props=run._r.get_or_add_rPr()
                for tag in ('latin','ea','cs'):
                    child=props.find('a:'+tag,NS)
                    if child is None:child=OxmlElement('a:'+tag);props.append(child)
                    child.set('typeface',font)
                changed+=1
    p.save(path)
    return {'role_bound_runs':changed,'fonts':role_fonts}
def apply_tech_size_overrides(path,rules):
    overrides={int(k):float(v) for k,v in rules.get('font_size_overrides_pt',{}).items()}
    if not overrides:return {'size_adjusted_runs':0}
    p=Presentation(path);changed=0
    for shape in walk(p.slides[0].shapes):
        size=overrides.get(shape.shape_id)
        if size is None or not shape.has_text_frame:continue
        for para in shape.text_frame.paragraphs:
            for run in para.runs:
                run.font.size=int(size*12700);changed+=1
    p.save(path)
    return {'size_adjusted_runs':changed}
def apply_body_text_presentation(slide,rules,bindings):
    """Apply reviewed text geometry for a source component without editing its PPTX."""
    cfg=rules.get('body_text_presentation')
    if not cfg:return None
    shapes={shape.shape_id:shape for shape in walk(slide.shapes)}
    fields={field['semantic_path']:field for field in bindings if field.get('semantic_path')}
    size=float(cfg['font_size_pt'])
    if not 10<=size<=24:raise ValueError('正文说明字号超出组件安全范围')
    box_height=cfg.get('body_box_height_pt')
    if box_height is not None:
        box_height=float(box_height)
        if not 20<=box_height<=70:raise ValueError('正文说明框高度超出组件安全范围')
    remove_bullets=cfg.get('remove_bullets',False)
    normal_weight=cfg.get('normal_weight',False)
    if not isinstance(remove_bullets,bool) or not isinstance(normal_weight,bool):
        raise ValueError('正文说明项目符号和字重配置必须为布尔值')
    adjusted=[]
    for item in cfg['rows']:
        body_field=fields[item['body']]
        heading_field=fields[item['heading']]
        body=shapes.get(body_field['shape_id'])
        heading=shapes.get(heading_field['shape_id'])
        if body is None or heading is None or not body.has_text_frame or not heading.has_text_frame:
            raise ValueError('正文说明与标题对象缺失')
        if box_height is not None:body.height=Pt(box_height)
        body.top=heading.top+(heading.height-body.height)//2
        body.text_frame.vertical_anchor=MSO_ANCHOR.MIDDLE
        body.text_frame.word_wrap=True
        for paragraph in body.text_frame.paragraphs:
            paragraph.space_before=Pt(0)
            paragraph.space_after=Pt(0)
            if remove_bullets:
                p_pr=paragraph._p.get_or_add_pPr()
                for child in list(p_pr):
                    if child.tag.rsplit('}',1)[-1].startswith('bu'):
                        p_pr.remove(child)
                p_pr.set('marL','0')
                p_pr.set('indent','0')
                p_pr.append(OxmlElement('a:buNone'))
            for run in paragraph.runs:
                run.font.size=Pt(size)
                if normal_weight:run.font.bold=False
        adjusted.append({'body':item['body'],'heading':item['heading'],'font_size_pt':size})
    return {'rows':adjusted,'vertical_alignment':'middle','word_wrap':True,'remove_bullets':remove_bullets,'normal_weight':normal_weight}
def apply_normal_body_weight(slide,rules,bindings):
    cfg=rules.get('normal_body_weight')
    if not cfg:return None
    if cfg.get('weight')!='regular':raise ValueError('普通正文只支持 regular 字重')
    roles=set(cfg.get('semantic_roles',[]))
    if not roles or not roles.issubset({'body','step_body','item_detail'}):
        raise ValueError('普通正文语义角色配置不合法')
    shapes={shape.shape_id:shape for shape in walk(slide.shapes)}
    changed=[]
    for field in bindings:
        if field.get('semantic_role') not in roles:continue
        shape=shapes.get(field['shape_id'])
        if shape is None or not shape.has_text_frame:raise ValueError('普通正文对象缺失')
        for paragraph in shape.text_frame.paragraphs:
            for run in paragraph.runs:run.font.bold=False
        changed.append(field['shape_id'])
    if not changed:raise ValueError('普通正文配置没有匹配到字段')
    return {'weight':'regular','shape_ids':changed}
def apply_page_background_role(slide,rules,theme,slide_width,slide_height,allow_source_scheme=False):
    """Override only a reviewed component's canvas using a locked theme role."""
    role=rules.get('page_background_role_by_theme',{}).get(theme)
    if role is None:return None
    palette_path=Path(__file__).resolve().parent.parent/'assets'/'brand'/'brand-palette-lock.json'
    palette=json.loads(palette_path.read_text(encoding='utf-8'))
    color=palette['themes'][theme]['roles'].get(role)
    if not color or not re.fullmatch(r'[0-9A-Fa-f]{6}',color):
        raise ValueError('组件背景角色未登记在锁定色系中：'+str(role))
    expected=rules.get('page_background_expected_rgb_by_theme',{}).get(theme)
    if expected and expected.upper()!=color.upper():
        raise ValueError('组件背景颜色与锁定色板不一致：'+theme)
    backing=rules.get('backing_shapes_by_theme',{}).get(theme)
    if backing:
        shapes={shape.shape_id:shape for shape in walk(slide.shapes)}
        expected_backing=backing['expected_rgb'].upper()
        for sid in backing['shape_ids']:
            shape=shapes.get(sid)
            if shape is None or shape.fill.type is None or (shape.fill.fore_color.type == 2 and allow_source_scheme):
                if shape is None or shape.fill.type is None:raise ValueError('组件衬底形状缺失：'+str(sid))
                continue
            if shape.fill.fore_color.type != 1 or str(shape.fill.fore_color.rgb).upper()!=expected_backing:
                raise ValueError('组件衬底形状缺失或色值漂移：'+str(sid))
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb=RGBColor.from_string(color)
    # A PowerPoint design clone can drop p:bg during deck assembly. Mirror the
    # reviewed canvas as a native rectangle behind every slide object so the
    # visible result and editability survive InsertFromFile.
    canvas_name='brand:canvas:'+role
    existing=[shape for shape in slide.shapes if shape.name==canvas_name]
    if len(existing)>1:raise ValueError('组件底层画布重复')
    canvas=existing[0] if existing else slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,0,0,slide_width,slide_height)
    canvas.name=canvas_name
    canvas.left=0;canvas.top=0;canvas.width=slide_width;canvas.height=slide_height
    canvas.fill.solid();canvas.fill.fore_color.rgb=RGBColor.from_string(color)
    canvas.line.fill.background()
    tree=slide.shapes._spTree
    tree.remove(canvas._element);tree.insert(2,canvas._element)
    return {'theme':theme,'role':role,'rgb':color,'native_canvas_shape':canvas.name,'reused_native_canvas':bool(existing)}
def fill(lib,layout,content,out,allow_draft=False,internal=False,logo_config=None,no_logo=False):
    lib=Path(lib).resolve();out=Path(out).resolve();content=Path(content).resolve()
    cat=json.loads((lib/'catalog.json').read_text(encoding='utf-8-sig'));m=next((x for x in cat['layouts'] if x['id']==layout),None)
    if m is None:raise ValueError('未知组件 '+layout)
    if m['status']!='approved' and not allow_draft:raise ValueError('组件尚未批准；内部使用必须显式 --allow-draft')
    data=json.loads(content.read_text(encoding='utf-8-sig'))
    theme=data.get('theme','blue')
    if theme not in m.get('themes',[]):raise ValueError('该组件不支持所选主题：'+str(theme))
    source_rel=m.get('red_source') if theme=='red' and m.get('red_source') else m['source']
    source_page=m.get('red_source_page') if theme=='red' and m.get('red_source_page') else m['source_page']
    ready_source=m.get('ready_source_by_theme',{}).get(theme)
    if ready_source:
        source_rel=ready_source
        source_page=1
    commit=data.get('library_commit')
    source_stamp=None
    if commit is not None:
        if not isinstance(commit,str) or not re.fullmatch(r'[0-9a-f]{40}',commit):
            raise ValueError('library_commit 须为完整 Git 提交号')
        if (lib/'.git').exists():
            actual=subprocess.check_output(['git','-C',str(lib),'rev-parse','HEAD'],text=True).strip()
        else:
            manifest=json.loads((lib/'knowledge-manifest.json').read_text(encoding='utf-8'))
            actual=manifest.get('source_commit')
        if actual!=commit:
            raise ValueError('知识库提交号与填充计划不一致')
        source_stamp=f'epoint:{layout}:{theme}:{source_rel}:{source_page}:{commit}'
    source=(lib/source_rel).resolve()
    if not source.is_relative_to(lib):raise ValueError('源文件越出库根目录')
    if out==source or out.is_relative_to(lib/'layouts') or out.is_relative_to(lib/'diagrams') or out.is_relative_to(lib/'master'):raise ValueError('输出不能覆盖模板库资产')
    binding_rel=m.get('red_bindings') if theme=='red' and m.get('red_bindings') else m['bindings']
    binding_data=json.loads((lib/binding_rel).read_text(encoding='utf-8-sig'))
    if m.get('collection')=='new-template-content' and not internal:
        safe_media={'brand_logo_locked','source_decorative_locked','source_visual_locked','cover_visual_layer'}
        unreviewed=[x for x in binding_data.get('objects',{}).get('images',[]) if x.get('semantic_role') not in safe_media]
        if unreviewed:raise ValueError('该页含未分类的源稿图片，需先确认装饰用途或替换内容图片；内部结构测试可传 --internal-draft')
    rules=json.loads((lib/m['layout_rules']).read_text(encoding='utf-8-sig'))
    item_count=data.get('item_count')
    if item_count is not None and rules.get('cardinality_mode')=='fixed' and item_count not in rules.get('supported_counts',[]):
        raise ValueError('固定项数组件不支持该项数；请重新选版')
    if item_count is not None and rules.get('cardinality_mode') in ('repeatable','tech_schedule_rows','tech_grid_2x3','tech_six_pillars','tech_process_columns','process_terminal','directory_grid_3x2','directory_reflow') and rules.get('validation_status')!='verified' and item_count not in rules.get('verified_counts',[]) and not internal:
        raise ValueError('该数量变化尚处原型；内部结构测试需传 --internal-draft')
    bindings=binding_data['fields'];texts=dict(data.get('texts',{}));known={x['field'] for x in bindings}
    semantic_aliases={x['semantic_path']:x['field'] for x in bindings if x.get('semantic_path')}
    for alias,field in semantic_aliases.items():
        if alias in texts:
            if field in texts:raise ValueError('同一字段不能同时提供语义路径和旧字段名：'+field)
            texts[field]=texts.pop(alias)
    if m.get('role') in ('cover','section','closing'):
        for b in bindings:
            path=b.get('semantic_path')
            if path and (b['field'] not in texts or not isinstance(texts[b['field']],str) or not texts[b['field']].strip()):
                raise ValueError('结构页可编辑文字字段必须提供真实非空内容；不适用时请改选版式：'+path)
    if rules.get('cardinality_mode') in ('directory_reflow','tech_grid_2x3') and m.get('role')=='directory':
        items=data.get('items')
        if not isinstance(items,list) or len(items) not in rules['supported_counts']:
            raise ValueError('目录 items 项数不在支持范围')
        if item_count is not None and item_count!=len(items):raise ValueError('目录 item_count 与 items 数量不一致')
        item_count=len(items)
        item_fields=rules['directory_item_fields']
        for i,item in enumerate(items[:rules['source_count']]):
            needed={key for key in item_fields[i] if key!='number'}
            if not isinstance(item,dict) or any(not isinstance(item.get(k),str) or not item[k].strip() for k in needed):
                raise ValueError('目录项缺少必需标题或副标题')
            for key,field in item_fields[i].items():
                value=f'{i+1:02d}' if key=='number' else item[key]
                if field in texts:raise ValueError('目录 items 与 texts 重复指定字段 '+field)
                texts[field]=value
        extra_needed={key for key in item_fields[-1] if key!='number'}
        field_limits={b['field']:b for b in bindings}
        for item in items[rules['source_count']:]:
            if not isinstance(item,dict) or any(not isinstance(item.get(k),str) or not item[k].strip() for k in extra_needed):
                raise ValueError('目录项缺少必需标题或副标题')
            for key in extra_needed:
                limit=field_limits[item_fields[-1][key]];value=item[key];lines=value.split('\n')
                if len(value)>limit.get('max_chars',9999) or len(lines)>limit.get('max_lines',9999) or any(visual_width_units(line)>limit.get('max_width_units',9999) for line in lines):
                    raise ValueError('新增目录项超出来源组件容量：'+key)
        for field,value in rules.get('directory_heading_fields',{}).items():
            texts.setdefault(field,value)
    if rules.get('cardinality_mode')=='directory_grid_3x2':
        items=data.get('items')
        if not isinstance(items,list) or len(items) not in rules['supported_counts']:
            raise ValueError('目录须提供 2–6 个 items')
        if item_count is not None and item_count!=len(items):
            raise ValueError('目录 item_count 与 items 数量不一致')
        item_count=len(items)
        for i,item in enumerate(items):
            if not isinstance(item,dict) or any(not isinstance(item.get(k),str) or not item[k].strip() for k in ('title','subtitle')):
                raise ValueError('目录每项须提供 title 和 subtitle')
            for key in ('title','subtitle'):
                field=semantic_aliases[f'items[{i}].{key}']
                if field in texts:raise ValueError('目录 items 与 texts 重复指定字段 '+field)
                texts[field]=item[key]
    if rules.get('cardinality_mode')=='process_terminal' and data.get('items') is not None:
        items=data['items']
        if not isinstance(items,list) or len(items) not in rules['supported_counts']:
            raise ValueError('流程 items 必须是 3–5 项数组')
        if item_count is not None and item_count!=len(items):raise ValueError('item_count 与 items 数量不一致')
        item_count=len(items)
        selected=rules['source_indices_by_count'][str(item_count)]
        names=('heading','goal_label','goal','activity_label','activity','output_label','output')
        for logical,source_index in enumerate(selected):
            item=items[logical]
            if not isinstance(item,dict) or any(not isinstance(item.get(k),str) or not item[k].strip() for k in names):
                raise ValueError('每个流程项须完整提供标题、目标、活动和输出')
            for name in names:
                alias=f'steps[{source_index}].{name}'
                field=semantic_aliases[alias]
                if field in texts:raise ValueError('items 与 texts 重复指定同一字段 '+field)
                texts[field]=item[name]
    elif rules.get('cardinality_mode')=='process_terminal' and item_count in (3,4):
        raise ValueError('3/4 步流程必须提供 items，避免终点槽位沿用原稿内容')
    if rules.get('cardinality_mode')=='project_schedule':
        tasks=data.get('tasks')
        if not isinstance(tasks,list) or len(tasks)!=6:raise ValueError('年度项目排期须提供六个 tasks')
        if item_count is not None and item_count!=6:raise ValueError('年度项目排期固定六项')
        item_count=6
        for i,task in enumerate(tasks):
            if not isinstance(task,dict) or any(not isinstance(task.get(k),str) or not task[k].strip() for k in ('code','name','level')):
                raise ValueError('每个项目须提供 code、name、level')
            if not isinstance(task.get('stages'),list) or len(task['stages'])!=3 or any(not isinstance(x,str) or not x.strip() for x in task['stages']):
                raise ValueError('每个项目须提供三个阶段名称')
            for name,value in [('code',task['code']),('name',task['name']),('level',task['level'])]:
                alias=f'tasks[{i}].{name}';field=semantic_aliases[alias]
                if field in texts:raise ValueError('tasks 与 texts 重复指定同一字段 '+field)
                texts[field]=value
            for j,value in enumerate(task['stages']):
                alias=f'tasks[{i}].stages[{j}]';field=semantic_aliases[alias]
                if field in texts:raise ValueError('tasks 与 texts 重复指定同一字段 '+field)
                texts[field]=value
    if rules.get('cardinality_mode')=='gantt_six_tasks':
        tasks=data.get('tasks')
        if not isinstance(tasks,list) or len(tasks)!=6:raise ValueError('甘特图须提供六个 tasks')
        if item_count is not None and item_count!=6:raise ValueError('甘特图固定六行')
        item_count=6
        for i,task in enumerate(tasks):
            if not isinstance(task,dict) or any(not isinstance(task.get(k),str) or not task[k].strip() for k in ('name','note')):
                raise ValueError('每项任务须有 name 和 note')
            start,end=task.get('start_month'),task.get('end_month')
            if type(start) is not int or type(end) is not int or not (1<=start<=end<=12):
                raise ValueError('甘特图月份必须在 1–12 且起始不晚于结束')
            for key,value in [('period',f'{start}月-{end}月'),('note',task['note'])]:
                field=semantic_aliases[f'tasks[{i}].{key}']
                if field in texts:raise ValueError('tasks 与 texts 重复指定同一字段 '+field)
                texts[field]=value
    if rules.get('cardinality_mode')=='tech_six_pillars' and data.get('items') is not None:
        items=data['items']
        if not isinstance(items,list) or len(items) not in rules['supported_counts']:
            raise ValueError('立柱 items 必须为 2–6 项数组')
        if item_count is not None and item_count!=len(items):raise ValueError('item_count 与 items 数量不一致')
        if not internal:raise ValueError('立柱数量变化尚处内部原型；需传 --internal-draft')
        item_count=len(items)
        for logical,source_index in enumerate(rules['source_indices_by_count'][str(item_count)]):
            item=items[logical]
            if not isinstance(item,dict) or not isinstance(item.get('title'),str) or not isinstance(item.get('body'),str):
                raise ValueError('每项须有 title 和 body 文字')
            fields=rules['item_fields'][source_index]
            for key,value in ((fields['title'],item['title']),(fields['description'],item['body'])):
                if key in texts:raise ValueError('items 与 texts 重复指定同一字段 '+key)
                texts[key]=value
    if rules.get('cardinality_mode')=='tech_process_columns' and data.get('items') is not None:
        items=data['items']
        if not isinstance(items,list) or len(items) not in rules['supported_counts']:
            raise ValueError('四步路径 items 必须为 2–4 项数组')
        if item_count is not None and item_count!=len(items):raise ValueError('item_count 与 items 数量不一致')
        if not internal:raise ValueError('四步路径仍是内部原型；需传 --internal-draft')
        item_count=len(items)
        for i,item in enumerate(items):
            if not isinstance(item,dict) or not isinstance(item.get('title'),str) or not isinstance(item.get('body'),str):
                raise ValueError('每项须有 title 和 body 文字')
            fields=rules['item_fields'][i]
            for key,value in ((fields['title'],item['title']),(fields['body'],item['body']),
                              (fields['number'],f'{i+1:02d}')):
                if key in texts:raise ValueError('items 与 texts 重复指定同一字段 '+key)
                texts[key]=value
    logo_override=False if no_logo else data.get('logo')
    logo_options=logo_settings(load_config(logo_config)[0],logo_override)
    logo_enabled=logo_options['enabled']
    if theme=='red' and logo_options['appearance']=='color':
        raise ValueError('红色风格只允许黑、白单色 Logo；不能指定彩色 Logo')
    removed_ids=set()
    if rules.get('cardinality_mode') in ('repeatable','tech_schedule_rows','tech_grid_2x3','tech_six_pillars','tech_process_columns','process_terminal','directory_grid_3x2','directory_reflow') and item_count is not None:
        if type(item_count) is not int or item_count not in rules['supported_counts']:raise ValueError('项数不在支持范围')
        if rules.get('cardinality_mode') in ('tech_six_pillars','process_terminal'):
            selected=set(rules['source_indices_by_count'][str(item_count)])
            removed_ids={sid for index,unit in enumerate(rules['units']) if index not in selected for sid in unit}
        elif rules.get('cardinality_mode')=='directory_reflow':
            removed_ids={sid for unit in rules['directory_units'][item_count:] for sid in unit['shape_ids']}
        else:removed_ids={sid for unit in rules['units'][item_count:] for sid in unit}
    removed_fields=set()
    if rules.get('cardinality_mode')=='directory_reflow' and item_count is not None:
        removed_fields={field for item in rules['directory_item_fields'][item_count:] for field in item.values()}
    required_fields={x['field'] for x in bindings if x.get('semantic_role') not in ('brand_locked','decoration_locked','source_decorative_locked','computed_item_count') and x['shape_id'] not in removed_ids and x['field'] not in removed_fields}-{'brand'}
    if set(texts)-known:raise ValueError('未知字段 '+str(set(texts)-known))
    if any(b['field'] in texts for b in bindings if b.get('semantic_role') in ('decoration_locked','source_decorative_locked','computed_item_count') and not (b.get('semantic_role')=='computed_item_number' and rules.get('cardinality_mode')=='tech_process_columns')):
        raise ValueError('原生装饰字段不可替换')
    if any(b['field'] in texts for b in bindings if b['shape_id'] in removed_ids):raise ValueError('输入包含已删除分项的字段')
    if required_fields-set(texts) and not internal:raise ValueError('缺少字段 '+str(required_fields-set(texts)))
    for b in bindings:
        if logo_enabled and b['field']=='brand':continue
        if b['field'] in texts:
            v=texts[b['field']]
            if not isinstance(v,str) or not v.strip():raise ValueError('字段必须为非空文字 '+b['field'])
            if len(v)>b['max_chars']:raise ValueError('超出容量，请拆页或精简：'+b['field'])
            if b.get('allowed_values') is not None and v not in b['allowed_values']:
                raise ValueError('字段当前仅支持指定值：'+b['field'])
            lines=v.split('\n')
            if b.get('max_lines') is not None and len(lines)>b['max_lines']:
                raise ValueError('字段超过允许行数：'+b['field'])
            if b.get('max_width_units') is not None and any(visual_width_units(line)>b['max_width_units'] for line in lines):
                raise ValueError('字段超出视觉宽度，请精简或换版：'+b['field'])
    ordered_dates=rules.get('ordered_date_fields')
    if ordered_dates:
        def month_value(alias):
            value=texts[semantic_aliases.get(alias,alias)].strip()
            match=re.fullmatch(r'(\d{4})(?:[.\-/]|年)(\d{1,2})月?',value)
            if not match or not 1<=int(match.group(2))<=12:
                raise ValueError('时间线日期格式须为 YYYY.M 或 YYYY年M月：'+alias)
            return int(match.group(1))*12+int(match.group(2))
        start=month_value(ordered_dates['start']);end=month_value(ordered_dates['end'])
        sequence=[month_value(alias) for alias in ordered_dates['milestones']]
        if not sequence or not (start<=sequence[0] and sequence[-1]<=end and all(a<b for a,b in zip(sequence,sequence[1:]))):
            raise ValueError('时间线节点日期须递增且处于起止区间内')
    goal_kpis=rules.get('goal_kpi_consistency')
    if goal_kpis:
        def item_value(alias):
            value=texts[semantic_aliases.get(alias,alias)].strip()
            if not re.fullmatch(r'\d+项',value):raise ValueError('目标统计须为整数加“项”：'+alias)
            return int(value[:-1])
        total=item_value(goal_kpis['total']);done=item_value(goal_kpis['done']);pending=item_value(goal_kpis['pending'])
        rate=texts[semantic_aliases.get(goal_kpis['rate'],goal_kpis['rate'])].strip()
        if not re.fullmatch(r'\d+%',rate):raise ValueError('目标完成率须为整数百分比')
        if total!=goal_kpis['goal_count'] or done+pending!=total or int(rate[:-1])!=round(done/total*100):
            raise ValueError('目标数量、完成数和完成率不一致')
    quarter_periods=rules.get('quarter_task_periods')
    if quarter_periods:
        period_years=[]
        for alias,quarter in zip(quarter_periods['fields'],quarter_periods['quarters']):
            value=texts[semantic_aliases.get(alias,alias)].strip()
            match=re.fullmatch(r'(\d{4})年(\d{1,2})月\s*[-—–]\s*(?:(\d{4})年)?(\d{1,2})月',value)
            if not match:raise ValueError('季度任务日期格式须为 YYYY年M月-M月：'+alias)
            year,start,other_year,end=int(match.group(1)),int(match.group(2)),match.group(3),int(match.group(4))
            period_years.append(year)
            allowed=range(7,10) if quarter==3 else range(10,13)
            if other_year and int(other_year)!=year or start not in allowed or end not in allowed or start>end:
                raise ValueError('任务日期必须位于对应季度且起止月递增：'+alias)
        if len(set(period_years))!=1:raise ValueError('同一季度任务计划须使用同一年份')
    consecutive_years=rules.get('consecutive_year_fields')
    if consecutive_years:
        years=[]
        for alias in consecutive_years:
            value=texts[semantic_aliases.get(alias,alias)].strip()
            match=re.fullmatch(r'(\d{4})年(?:规划)?',value)
            if not match:raise ValueError('时间轴年份须使用 YYYY年 或 YYYY年规划：'+alias)
            years.append(int(match.group(1)))
        if years!=list(range(years[0],years[0]+len(years))):raise ValueError('时间轴年份须连续递增')
    for alias in rules.get('percentage_fields',[]):
        value=texts[semantic_aliases.get(alias,alias)].strip()
        match=re.fullmatch(r'(\d{1,3})%',value)
        if not match or int(match.group(1))>100:raise ValueError('百分比指标须在 0–100%：'+alias)
    quarter_plan=rules.get('quarter_plan_fields')
    if quarter_plan:
        center=texts[semantic_aliases.get(quarter_plan['center'],quarter_plan['center'])].strip()
        generic_quarters=quarter_plan.get('mode')=='generic_quarters'
        if not generic_quarters and not re.fullmatch(r'\d{4}年季度工作计划',center):
            raise ValueError('季度计划中心标题须为 YYYY年季度工作计划')
        expected=(['第一季度','第二季度','第三季度','第四季度'] if generic_quarters else
                  ['第一季度工作计划','第二季度工作计划','第三季度工作计划','第四季度工作计划'])
        for alias,label in zip(quarter_plan['labels'],expected):
            if texts[semantic_aliases.get(alias,alias)].strip()!=label:
                raise ValueError('季度标签与图形位置不一致：'+alias)
    for item in rules.get('numbered_heading_suffix',[]):
        alias=item['field'];value=texts[semantic_aliases.get(alias,alias)].strip()
        if not value.endswith(item['suffix']):
            raise ValueError('步骤编号与图形位置不一致：'+alias)
    for alias in rules.get('year_fields',[]):
        value=texts[semantic_aliases.get(alias,alias)].strip()
        if not re.fullmatch(r'\d{4}',value):
            raise ValueError('年份须使用四位数字：'+alias)
    year_ranges=rules.get('consecutive_year_ranges')
    if year_ranges:
        spans=[]
        for alias in year_ranges:
            value=texts[semantic_aliases.get(alias,alias)].strip()
            match=re.fullmatch(r'(\d{4})年[-—–](\d{4})年',value)
            if not match:raise ValueError('阶段年份格式须为 YYYY年-YYYY年：'+alias)
            start,end=map(int,match.groups())
            if end!=start+1:raise ValueError('每阶段须覆盖连续两年：'+alias)
            spans.append((start,end))
        if any(b[0]!=a[1]+1 for a,b in zip(spans,spans[1:])):
            raise ValueError('阶段年份须连续且不重叠')
    month_labels=rules.get('consecutive_month_labels')
    if month_labels:
        months=[]
        for alias in month_labels:
            value=texts[semantic_aliases.get(alias,alias)].strip()
            match=re.fullmatch(r'(\d{4})年(\d{1,2})月',value)
            if not match or not 1<=int(match.group(2))<=12:
                raise ValueError('月份须为 YYYY年M月：'+alias)
            months.append(int(match.group(1))*12+int(match.group(2)))
        if any(b!=a+1 for a,b in zip(months,months[1:])):
            raise ValueError('时间线月份须连续递增')
    annual_chart=rules.get('annual_two_series_consistency')
    if annual_chart:
        supplied_charts=data.get('charts',[])
        if len(supplied_charts)!=1 or supplied_charts[0].get('shape_id')!=annual_chart['chart_shape_id']:
            raise ValueError('年度分析须提供登记的原生图表数据')
        chart_data=supplied_charts[0]
        if chart_data.get('categories')!=['Q1','Q2','Q3','Q4'] or len(chart_data.get('series',[]))!=2:
            raise ValueError('年度图表须为四季度营收和成本双系列')
        revenue_series,cost_series=chart_data['series']
        revenue_name=texts[semantic_aliases.get('chart.legend_revenue','chart.legend_revenue')].strip()
        cost_name=texts[semantic_aliases.get('chart.legend_cost','chart.legend_cost')].strip()
        if revenue_series.get('name')!=revenue_name or cost_series.get('name')!=cost_name:
            raise ValueError('图例文字须与图表系列一致')
        if chart_data.get('unit')!=annual_chart['unit']:
            raise ValueError('图表单位与指标单位不一致')
        period=chart_data.get('period','')
        if period not in texts[semantic_aliases.get('chart.heading','chart.heading')] or period not in texts[semantic_aliases.get('analysis.heading','analysis.heading')]:
            raise ValueError('图表周期与分析标题不一致')
        def metric(alias):
            value=texts[semantic_aliases.get(alias,alias)].strip()
            match=re.fullmatch(r'(\d+(?:\.\d+)?)'+re.escape(annual_chart['unit']),value)
            if not match:raise ValueError('年度指标格式不正确：'+alias)
            return float(match.group(1))
        revenue=metric(annual_chart['revenue_field'])
        cost=metric(annual_chart['cost_field'])
        growth=metric(annual_chart['growth_field'])
        previous=data.get(annual_chart['previous_year_key'])
        if type(previous) not in (int,float) or not math.isfinite(previous) or previous<0:
            raise ValueError('须提供非负的上年营收')
        if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for series in (revenue_series,cost_series) for v in series.get('values',[])):
            raise ValueError('季度数据须为非负有限数值')
        if len(revenue_series.get('values',[]))!=4 or len(cost_series.get('values',[]))!=4:
            raise ValueError('季度数据必须为四项')
        if abs(sum(revenue_series['values'])-revenue)>0.001 or abs(sum(cost_series['values'])-cost)>0.001 or abs(revenue-previous-growth)>0.001:
            raise ValueError('图表合计、年度指标或同比增量不一致')
        summary=texts[semantic_aliases.get('analysis.summary','analysis.summary')]
        if texts[semantic_aliases.get(annual_chart['revenue_field'],annual_chart['revenue_field'])] not in summary or texts[semantic_aliases.get(annual_chart['cost_field'],annual_chart['cost_field'])] not in summary:
            raise ValueError('分析摘要须与营收和成本指标一致')
    p=Presentation(source);s=select_source_page(p,source_page)
    clear_source_motion(s)
    for shape_id in rules.get('drop_shape_ids',[]):
        target=next((shape for shape in walk(s.shapes) if shape.shape_id==shape_id),None)
        if target is None:raise ValueError('需清理的源稿对象不存在：'+str(shape_id))
        target._element.getparent().remove(target._element)
    if data.get('generic_visual'):
        contract=m.get('matching_contract') or {}
        if (m.get('matching_activation')!='pilot_verified'
                or contract.get('policy')!='structural'):
            raise ValueError('该组件未验收通用视觉适配')
        ids=contract.get('generic_drop_shape_ids')
        if not isinstance(ids,list) or not ids:
            raise ValueError('通用视觉适配缺少固定图标清理清单')
        direct={shape.shape_id:shape for shape in s.shapes}
        if len(set(ids))!=len(ids) or any(sid not in direct for sid in ids):
            raise ValueError('通用视觉适配的固定图标对象不完整')
        for sid in ids:
            shape=direct[sid]
            shape._element.getparent().remove(shape._element)
        number_ids=contract.get('generic_number_container_ids',[])
        if number_ids:
            if (not isinstance(number_ids,list) or len(number_ids)!=4
                    or len(set(number_ids))!=4 or set(number_ids)&set(ids)
                    or any(sid not in direct or not direct[sid].has_text_frame for sid in number_ids)):
                raise ValueError('通用流程序号容器对象不完整')
            brand=json.loads((Path(__file__).resolve().parents[1]/'assets/brand/brand-baseline.json').read_text(encoding='utf-8'))
            color_role=contract.get('generic_number_color_role','primary')
            if color_role=='neutral.white':
                color_value=brand['themes'][theme]['neutral']['white']
            elif color_role=='primary':
                color_value=brand['themes'][theme]['primary']
            else:
                raise ValueError('通用流程序号颜色角色不合法')
            number_color=RGBColor.from_string(color_value.lstrip('#'))
            number_size=contract.get('generic_number_font_pt',24)
            if not isinstance(number_size,(int,float)) or not 12<=number_size<=28:
                raise ValueError('通用流程序号字号不合法')
            for index,sid in enumerate(number_ids,1):
                shape=direct[sid]
                set_text(shape,f'{index:02d}')
                shape.text_frame.vertical_anchor=MSO_ANCHOR.MIDDLE
                shape.text_frame.margin_left=shape.text_frame.margin_right=0
                shape.text_frame.margin_top=shape.text_frame.margin_bottom=0
                shape.text_frame.word_wrap=False
                for paragraph in shape.text_frame.paragraphs:
                    paragraph.alignment=PP_ALIGN.CENTER
                    for run in paragraph.runs:
                        run.font.size=Pt(number_size)
                        run.font.bold=True
                        run.font.color.rgb=number_color
    if m.get('background_override'):
        override=(lib/m['background_override']).resolve()
        if not override.is_relative_to(lib) or not override.is_file():raise ValueError('封面替换图缺失或越出知识库')
        pictures=[x for x in s.shapes if x.shape_type==13 and x.width>=p.slide_width*0.95 and x.height>=p.slide_height*0.95]
        if m.get('role')!='cover' or len(pictures)!=1:raise ValueError('封面背景图未能唯一定位')
        _,rid=s.part.get_or_add_image_part(str(override))
        pictures[0]._element.xpath('.//a:blip')[0].set('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed',rid)
        pictures[0].crop_left=pictures[0].crop_right=pictures[0].crop_top=pictures[0].crop_bottom=0
    source_logo_shape_id=(m.get('red_source_logo_shape_id') if theme=='red' and m.get('red_source_page') else m.get('source_logo_shape_id'))
    source_logo_present=bool(source_logo_shape_id) or (m.get('role')=='cover' and m.get('source_logo_present'))
    if m.get('role')=='cover' and source_logo_present and not source_logo_shape_id:
        brand_groups=[g for g in s.shapes if g.shape_type==6 and any(x.has_text_frame and '688232' in x.text for x in walk(g.shapes))]
        if len(brand_groups)!=1:raise ValueError('源封面的品牌组未能唯一定位，停止填充')
        brand_groups[0].name='brand:logo:source'
        if m.get('brand_contrast_variant')=='dark':
            pictures=[x for x in walk(brand_groups[0].shapes) if x.shape_type==13]
            if len(pictures)!=1:raise ValueError('深色品牌 Logo 未能唯一定位')
            dark_logo=lib/'brand/logo/logo-black.png'
            if not dark_logo.is_file():raise FileNotFoundError(dark_logo)
            _,rid=s.part.get_or_add_image_part(str(dark_logo))
            pictures[0]._element.xpath('.//a:blip')[0].set('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed',rid)
            # The source also has an Office SVG reference; remove it so PowerPoint
            # displays the updated dark PNG rather than the old white SVG.
            for node in list(pictures[0]._element.iter()):
                if node.tag.endswith('}svgBlip'):
                    ext=node.getparent();ext_list=ext.getparent();ext_list.remove(ext)
                    if len(ext_list)==0:ext_list.getparent().remove(ext_list)
            for sh in walk(brand_groups[0].shapes):
                if sh.has_text_frame:
                    neutral=json.loads((Path(__file__).resolve().parents[1]/'assets/brand/brand-baseline.json').read_text(encoding='utf-8'))['themes'][theme]['neutral']
                    for para in sh.text_frame.paragraphs:
                        for run in para.runs:run.font.color.rgb=RGBColor.from_string(neutral['dark_gray'])
    elif source_logo_shape_id:
        logo_shape=next((x for x in walk(s.shapes) if x.shape_id==source_logo_shape_id),None)
        if logo_shape is None or logo_shape.shape_type!=13:raise ValueError('来源 Logo 图片未找到，停止填充')
        if logo_enabled:logo_shape.name='brand:logo:source'
        else:logo_shape._element.getparent().remove(logo_shape._element)
    lookup={x.shape_id:x for x in walk(s.shapes)}
    for b in bindings:
        if b.get('semantic_role') not in ('brand_locked','decoration_locked','source_decorative_locked') and b['shape_id'] in lookup:set_text(lookup[b['shape_id']],'')
    for b in bindings:
        if b['field'] in texts and not (logo_enabled and b['field']=='brand'):set_text(lookup[b['shape_id']],texts[b['field']])
    for fit in rules.get('text_box_expand_pt',[]):
        shape=lookup.get(fit['shape_id'])
        if shape is None or not shape.has_text_frame:raise ValueError('文字框扩展对象缺失')
        delta=Pt(float(fit['vertical_extra_pt']))
        shape.top-=delta//2;shape.height+=delta
    for fit in rules.get('percentage_text_fit',[]):
        alias=fit['field'];value=texts[semantic_aliases.get(alias,alias)].strip()
        if len(value)==4:
            shape=lookup.get(fit['shape_id'])
            if shape is None or not shape.has_text_frame:raise ValueError('百分比文字对象缺失：'+alias)
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:run.font.size=Pt(fit['four_char_font_pt'])
    if not logo_enabled and 'brand' not in texts:
        for b in bindings:
            if b['field']=='brand':
                old=lookup[b['shape_id']]
                old._element.getparent().remove(old._element)
    chart_shapes={x.shape_id:x for x in walk(s.shapes) if x.has_chart};supplied=data.get('charts',[])
    if {x['shape_id'] for x in supplied}!=set(chart_shapes):raise ValueError('必须显式提供本页所有原生图表数据，禁止使用占位值')
    for c in supplied:
        if m.get('collection')=='new-template-content' and any(not isinstance(c.get(k),str) or not c[k].strip() for k in ['unit','period','source']):raise ValueError('原稿图表组件必须提供unit、period、source')
        categories=c['categories'];series=c['series'];chart=chart_shapes[c['shape_id']].chart
        registered=next((x for x in binding_data.get('objects',{}).get('charts',[]) if x['shape_id']==c['shape_id']),{})
        max_categories=registered.get('categories_max',8);max_series=registered.get('series_max',4)
        if not 1<=len(categories)<=max_categories or not 1<=len(series)<=max_series:raise ValueError(f'图表超容量：本组件最多{max_categories}类、{max_series}系列')
        cd=CategoryChartData();cd.categories=categories
        for ss in series:
            if len(ss['values'])!=len(categories):raise ValueError('图表系列与分类数量不一致')
            if any(isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) for v in ss['values']):raise ValueError('图表必须为有限数值')
            if 'DOUGHNUT' in str(chart.chart_type) and (any(v<0 for v in ss['values']) or sum(ss['values'])<=0):raise ValueError('构成图需非负值且总数大于0')
            cd.add_series(ss['name'],ss['values'])
        chart.replace_data(cd)
        if 'DOUGHNUT' not in str(chart.chart_type) and 'PIE' not in str(chart.chart_type):
            ax=chart.value_axis;ax.major_unit=None;ax.maximum_scale=None;ax.minimum_scale=None
        # Never carry the template's fictitious chart title into a filled report.
        if c.get('title'):
            chart.has_title=True;chart.chart_title.text_frame.text=c['title']
        else:chart.has_title=False
    paired=rules.get('paired_chart_consistency')
    if paired:
        chart_by_id={c['shape_id']:c for c in supplied}
        matched=[chart_by_id[i] for i in paired['chart_shape_ids']]
        if len({tuple(c['categories']) for c in matched})!=1 or len({c['period'] for c in matched})!=1:
            raise ValueError('配对趋势图的分类和周期必须一致')
        for item in paired['metrics']:
            c=chart_by_id[item['chart_shape_id']]
            if len(c['series'])!=1:raise ValueError('该趋势组件每张图只支持一个系列')
            actual=texts[semantic_aliases.get(item['value_field'],item['value_field'])].strip()
            suffix=item['display_unit']
            if not actual.endswith(suffix):raise ValueError('指标值缺少单位：'+item['value_field'])
            try:value=float(actual[:-len(suffix)].replace(',',''))
            except ValueError:raise ValueError('指标值必须是数值加单位：'+item['value_field'])
            if abs(value-sum(c['series'][0]['values']))>0.001:
                raise ValueError('指标值与图表数据合计不一致：'+item['value_field'])
    annual=rules.get('annual_finance_consistency')
    if annual:
        if len(supplied)!=1 or supplied[0]['shape_id']!=annual['chart_shape_id'] or len(supplied[0]['series'])!=1:
            raise ValueError('年度财务页必须提供一张单系列月度图')
        values=supplied[0]['series'][0]['values']
        if len(values)!=12 or len(supplied[0]['categories'])!=12:
            raise ValueError('年度财务页须提供十二个月数据')
        if any(value<0 or value>450 for value in values):
            raise ValueError('年度财务页月度数据超出该图已验证的 0–450 范围')
        axis=chart_shapes[annual['chart_shape_id']].chart.value_axis
        axis.minimum_scale=0;axis.maximum_scale=450;axis.major_unit=50
        def finance_number(alias):
            value=texts[semantic_aliases.get(alias,alias)].strip()
            if not value.upper().endswith('W'):raise ValueError('年度财务指标须用 W 单位：'+alias)
            try:return float(value[:-1].replace(',',''))
            except ValueError:raise ValueError('年度财务指标不是数值：'+alias)
        revenue=finance_number(annual['revenue_field'])
        cost=finance_number(annual['cost_field'])
        profit=finance_number(annual['profit_field'])
        if abs(revenue-sum(values))>0.001 or abs(revenue-cost-profit)>0.001:
            raise ValueError('年度营收、成本、利润与月度图数据不一致')
        for callout in annual['callouts']:
            alias,index=callout[:2]
            if abs(finance_number(alias)-values[index])>0.001:
                raise ValueError('图表标注值与对应月份数据不一致：'+alias)
            if len(callout)>2:
                shape=lookup.get(callout[2])
                if shape is None:raise ValueError('图表标注对象缺失：'+alias)
                shape.top=(annual['callout_plot_baseline_emu']
                           -round(values[index]*annual['callout_y_scale_emu_per_unit'])
                           -shape.height)
    dashboard=rules.get('four_chart_table_consistency')
    if dashboard:
        by_id={c['shape_id']:c for c in supplied}
        share_values=[]
        for index,chart_id in enumerate(dashboard['share_chart_ids']):
            chart_data=by_id[chart_id]
            values=chart_data['series'][0]['values']
            if len(values)!=2 or abs(sum(values)-100)>0.001 or any(v<0 for v in values):
                raise ValueError('产品占比环图必须由占比和补足值组成 100%')
            label=texts[semantic_aliases[dashboard['share_text_fields'][index]]]
            if label!=f'{values[0]:g}%':raise ValueError('产品占比文字与环图不一致')
            share_values.append(values[0])
        if abs(sum(share_values)-100)>0.001:raise ValueError('三种产品占比合计必须为 100%')
    tables={x.shape_id:x.table for x in walk(s.shapes) if x.has_table};supplied_tables=data.get('tables',[])
    if rules.get('cardinality_mode')=='gantt_six_tasks':
        if supplied_tables:raise ValueError('甘特图表格由 tasks 自动生成，不可重复提供')
        supplied_tables=[{'shape_id':rules['gantt_table_shape_id'],'rows':
            [['工作任务']+[f'{i}月' for i in range(1,13)]]+
            [[task['name']]+['' for _ in range(12)] for task in data['tasks']]}]
    if set(tables)!={x['shape_id'] for x in supplied_tables} and not internal:raise ValueError('必须填充本页表格')
    for item in supplied_tables:
        t=tables[item['shape_id']];rows=item['rows'];limit=m['capacity'].get('cell_max_chars',20)
        if not rows or len(rows)>len(t.rows) or any(len(row)>len(t.columns) for row in rows):raise ValueError('表格超容量，请拆页')
        if any(not isinstance(v,str) or len(v)>limit for row in rows for v in row):raise ValueError('表格单元格超字数或类型错误')
        for ri,row in enumerate(t.rows):
            for ci,cell in enumerate(row.cells):set_text(cell,rows[ri][ci] if ri<len(rows) and ci<len(rows[ri]) else '')
        for tr in list(t._tbl.tr_lst)[len(rows):]:t._tbl.remove(tr)
    if dashboard:
        table_item=next((x for x in supplied_tables if x['shape_id']==dashboard['table_shape_id']),None)
        if table_item is None or len(table_item['rows'])!=5 or any(len(row)!=13 for row in table_item['rows']):
            raise ValueError('年度明细表须为表头加四行、十二个月')
        rows=table_item['rows']
        try:finance_rows=[[float(value.replace(',','')) for value in row[1:]] for row in rows[1:]]
        except ValueError:raise ValueError('年度明细表月份数据必须是数值')
        if any(abs(finance_rows[0][i]-finance_rows[1][i]-finance_rows[2][i]-finance_rows[3][i])>0.001 for i in range(12)):
            raise ValueError('年度明细表每月结余与收入、成本、费用不一致')
        for alias,row in dashboard['table_total_fields']:
            value=texts[semantic_aliases[alias]].replace(',','')
            try:metric=float(value)
            except ValueError:raise ValueError('年度指标值必须是数值：'+alias)
            if abs(metric-sum(finance_rows[row]))>0.001:
                raise ValueError('年度指标与明细表合计不一致：'+alias)
    if rules.get('cardinality_mode')=='gantt_six_tasks':
        shapes={x.shape_id:x for x in walk(s.shapes)}
        origin=rules['month_start_emu'];month_width=rules['month_width_emu']
        for i,task in enumerate(data['tasks']):
            bar=shapes[rules['gantt_bar_shape_ids'][i]]
            note=shapes[rules['gantt_note_shape_ids'][i]]
            start,end=task['start_month'],task['end_month']
            bar.left=origin+(start-1)*month_width
            bar.width=(end-start+1)*month_width
            if end<=9:note.left=bar.left+bar.width+rules['note_gap_emu']
            else:note.left=bar.left-note.width-rules['note_gap_emu']
            if note.left<origin or note.left+note.width>origin+12*month_width:
                raise ValueError('甘特备注无安全空间，请换用短备注或其他排期组件')
            icon_id=rules['gantt_note_icon_shape_ids'].get(str(i))
            if icon_id:
                icon=shapes[icon_id]
                if end<=9:
                    icon.left=note.left
                    note.left=icon.left+icon.width+rules['note_gap_emu']
                else:icon.left=note.left-icon.width-rules['note_gap_emu']
                if note.left<origin or note.left+note.width>origin+12*month_width:
                    raise ValueError('甘特备注与图标没有安全空间')
        for rate_field,arc_id in rules['summary_arc_shape_ids']:
            raw=texts[semantic_aliases[rate_field]].strip()
            if not raw.endswith('%'):raise ValueError('甘特进度率必须为百分数')
            try:rate=float(raw[:-1])
            except ValueError:raise ValueError('甘特进度率不是数值')
            if not 0<=rate<=100:raise ValueError('甘特进度率超出 0–100%')
            arc=shapes[arc_id]
            gd=next(x for x in arc._element.xpath('.//a:gd') if x.get('name')=='adj2')
            gd.set('fmla',f'val {round((16200000+21600000*rate/100)%21600000)}')
        raw=texts[semantic_aliases[rules['summary_bar_rate_field']]].strip()
        rate=float(raw[:-1])
        track=shapes[rules['summary_bar_track_shape_id']];bar=shapes[rules['summary_bar_shape_id']]
        label=shapes[rules['summary_bar_rate_shape_id']]
        usable=label.left-bar.left-rules['summary_bar_label_gap_emu']
        if usable<=0:raise ValueError('甘特进度条与百分比文字区域冲突')
        bar.width=round(usable*rate/100)
    images=data.get('images',[]);image_slots=[x for x in walk(s.shapes) if x.name=='field:image' or x.name.startswith('field:image:')]
    required_image_names={x.name for x in image_slots};supplied_image_names={x.get('shape_name') for x in images}
    if required_image_names-supplied_image_names and not internal:raise ValueError('图片区域尚未全部替换；内部结构稿可用 --internal-draft')
    if len(supplied_image_names)!=len(images):raise ValueError('图片占位重复提供')
    for img in images:
        targets=[x for x in walk(s.shapes) if x.name==img['shape_name']]
        if len(targets)!=1:raise ValueError('图片占位区不唯一或不存在')
        old=targets[0]
        if old.name not in required_image_names:raise ValueError('只能替换登记的图片槽，不能猜测覆盖装饰或背景')
        if m.get('collection')=='new-template-content' and not str(img.get('source','')).strip():raise ValueError('新增内容组件配图需填写source来源')
        fp=Path(img['path']);fp=fp if fp.is_absolute() else content.parent/fp
        with Image.open(fp) as im:w,h=im.size
        if old.shape_type==13:
            # Replace the native picture reference in place, retaining group transforms,
            # masking geometry, drawing order and independently editable picture object.
            _,rid=s.part.get_or_add_image_part(str(fp));old._element.xpath('.//a:blip')[0].set('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed',rid)
            target=old.width/old.height;actual=w/h
            old.crop_left=old.crop_right=(1-target/actual)/2 if actual>target else 0
            old.crop_top=old.crop_bottom=(1-actual/target)/2 if actual<target else 0
        else:
            if old._element.getparent().tag.endswith('}grpSp'):raise ValueError('组合内非图片占位需要在副本中原位改造')
            scale=min(old.width/w,old.height/h);ww=int(w*scale);hh=int(h*scale)
            pic=s.shapes.add_picture(str(fp),old.left+(old.width-ww)//2,old.top+(old.height-hh)//2,ww,hh)
            par=old._element.getparent();idx=list(par).index(old._element);par.remove(pic._element);par.insert(idx,pic._element);par.remove(old._element)
    render_override=rules.get('render_overrides',{}).get(theme,{})
    if render_override:
        current={x.shape_id:x for x in walk(s.shapes)}
        for key,height in render_override.get('shape_height_pt_by_shape_id',{}).items():
            shape=current.get(int(key))
            if shape is None or not shape.has_text_frame:raise ValueError('渲染高度目标不存在：'+key)
            shape.height=Pt(height)
        for key,color in render_override.get('text_color_by_shape_id',{}).items():
            shape=current.get(int(key))
            if shape is None or not shape.has_text_frame:raise ValueError('渲染文字颜色目标不存在：'+key)
            rgb=RGBColor.from_string(color)
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:run.font.color.rgb=rgb
        if render_override.get('table_body_text_color_rgb'):
            rgb=RGBColor.from_string(render_override['table_body_text_color_rgb'])
            for table in tables.values():
                for row_index in range(1,len(table.rows)):
                    for cell in table.rows[row_index].cells:
                        for paragraph in cell.text_frame.paragraphs:
                            for run in paragraph.runs:run.font.color.rgb=rgb
    for item in rules.get('rate_bars',[]):
        value=texts[semantic_aliases.get(item['value_field'],item['value_field'])].strip()
        if not value.endswith('%'):raise ValueError('达标率必须用百分号：'+item['value_field'])
        try:rate=float(value[:-1])
        except ValueError:raise ValueError('达标率必须是数值：'+item['value_field'])
        if not 0<=rate<=100:raise ValueError('达标率超出 0–100%：'+item['value_field'])
        shapes={x.shape_id:x for x in walk(s.shapes)}
        track=shapes.get(item['track_shape_id']);bar=shapes.get(item['bar_shape_id'])
        if track is None or bar is None:raise ValueError('达标率进度条形状缺失')
        bar.width=round(track.width*rate/100)
    constraint_file=source.parent/'constraints.json'
    layout_changes=apply_constraints(p,json.loads(constraint_file.read_text(encoding='utf-8'))) if constraint_file.is_file() else []
    body_text_result=apply_body_text_presentation(s,rules,bindings)
    normal_body_weight_result=apply_normal_body_weight(s,rules,bindings)
    page_background_result=apply_page_background_role(s,rules,theme,p.slide_width,p.slide_height)
    brand_slot=next((lookup[b['shape_id']] for b in bindings if b['field']=='brand'),None) if logo_enabled else None
    cardinality_result=apply_cardinality(s,rules,item_count,data.get('items'),theme)
    schedule_result=apply_project_schedule(s,rules,data['tasks']) if rules.get('cardinality_mode')=='project_schedule' else None
    if source_logo_present and m.get('role')=='cover' and not source_logo_shape_id:
        if not logo_enabled:raise ValueError('该源封面内置 Logo；关闭 Logo 需先完成品牌对象拆分验收')
        logo_result={'added':False,'reason':'source_logo_preserved','visual_qa':'not_run'}
    elif source_logo_present and logo_enabled and m.get('replace_source_logo'):
        logo_layout=dict(m)
        if theme=='red' and m.get('red_source_page'):
            logo_layout['preview']=m.get('red_preview',f"source-previews/red/P{m['red_source_page']:03d}.png")
        logo_result=add_logo(p,s,logo_layout,lib,logo_config,logo_override,logo_shape,replace_existing=True,theme=theme)
    elif source_logo_present:
        logo_result={'added':False,'reason':'source_logo_preserved' if logo_enabled else 'source_logo_removed','visual_qa':'not_run'}
    else:
        logo_layout=dict(m)
        if theme=='red' and m.get('red_source_page'):
            logo_layout['preview']=m.get('red_preview',f"source-previews/red/P{m['red_source_page']:03d}.png")
        logo_result=add_logo(p,s,logo_layout,lib,logo_config,logo_override,brand_slot,theme=theme)
    if source_stamp:
        s._element.cSld.set('name',source_stamp)
    out.parent.mkdir(parents=True,exist_ok=True);p.save(out);normalize(out,out)
    font_result=apply_tech_font_roles(out,binding_data) if m.get('style_family')=='deep-blue-tech' else None
    if m.get('style_family')=='deep-blue-tech':
        font_result.update(apply_tech_size_overrides(out,rules))
    color_result=materialize_component_colors(out,out,out.with_suffix('.colors.json'),source,source_page)
    if theme=='red' and logo_enabled:
        from audit_logo import audit as audit_logo
        logo_audit=audit_logo(out,require_every_slide=True,theme='red')
        if not logo_audit['passed']:
            raise ValueError('红色风格 Logo 必须是黑白灰单色：'+str(logo_audit['issues']))
    report=dict(layout_id=layout,source_stamp=source_stamp,asset_version=m['version'],asset_status=m['status'],internal_draft=internal,output=str(out),structure_filled=True,layout_constraints=layout_changes,normal_body_weight=normal_body_weight_result,page_background=page_background_result,cardinality=cardinality_result,schedule=schedule_result,logo=logo_result,fonts=font_result,colors={'materialized_references':sum(color_result['materialized_by_part'].values()),'remaining_chart_style_placeholders':sum(color_result['remaining_chart_style_placeholders'].values()),'rendering_depends_on_master_theme_slots':color_result['rendering_depends_on_master_theme_slots'],'chart_visual_review_required':color_result['chart_visual_review_required']},visual_qa='not_run',powerpoint_open='not_run',collision_qa='not_run')
    out.with_suffix('.qa.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');return report
def main():
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path);p.add_argument('--layout',required=True);p.add_argument('--content',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--allow-draft',action='store_true');p.add_argument('--internal-draft',action='store_true');p.add_argument('--logo-config',type=Path);p.add_argument('--no-logo',action='store_true');a=p.parse_args()
    try:print(json.dumps(fill(a.library or get_library(),a.layout,a.content,a.out,a.allow_draft,a.internal_draft,a.logo_config,a.no_logo),ensure_ascii=False,indent=2))
    except (ValueError,KeyError,FileNotFoundError) as e:p.exit(2,str(e)+'\n')
if __name__=='__main__':main()
