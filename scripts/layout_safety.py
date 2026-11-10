"""Apply explicit layout contracts in slide coordinates, including nested groups.

Only named/identified decorations in a supplied contract may move. Semantic flow
arrows are never guessed or moved automatically. Rendering QA is still required.
"""
from pathlib import Path
import argparse,json
from pptx import Presentation
from pptx.enum.text import MSO_AUTO_SIZE

EMU_PER_PT=12700
def world_shapes(shapes,transform=(1.,1.,0.,0.)):
    sx,sy,tx,ty=transform
    for sh in shapes:
        yield sh,transform
        if sh.shape_type==6:
            xf=sh._element.grpSpPr.xfrm
            if xf is None:raise ValueError('组合缺少坐标变换')
            if sh.rotation or xf.get('flipH') in ['1','true'] or xf.get('flipV') in ['1','true']:
                # Reject instead of pretending an axis-aligned transform is exact.
                continue
            off=xf.find('{http://schemas.openxmlformats.org/drawingml/2006/main}off')
            ext=xf.find('{http://schemas.openxmlformats.org/drawingml/2006/main}ext')
            child_off=xf.find('{http://schemas.openxmlformats.org/drawingml/2006/main}chOff')
            child_ext=xf.find('{http://schemas.openxmlformats.org/drawingml/2006/main}chExt')
            gx=int(ext.get('cx'))/int(child_ext.get('cx'));gy=int(ext.get('cy'))/int(child_ext.get('cy'))
            yield from world_shapes(sh.shapes,(sx*gx,sy*gy,tx+sx*(int(off.get('x'))-gx*int(child_off.get('x'))),ty+sy*(int(off.get('y'))-gy*int(child_off.get('y')))))
def box(sh,tr):
    sx,sy,tx,ty=tr
    return ((tx+sx*sh.left)/EMU_PER_PT,(ty+sy*sh.top)/EMU_PER_PT,sx*sh.width/EMU_PER_PT,sy*sh.height/EMU_PER_PT)
def find(items,rule,prefix=''):
    name=rule.get(prefix+'shape_name');sid=rule.get(prefix+'shape_id')
    found=[(s,t) for s,t in items if (name and s.name==name) or (sid is not None and s.shape_id==sid)]
    if len(found)!=1:raise ValueError('布局锚点缺失、不唯一或处于不支持的旋转组合：'+str(name or sid))
    return found[0]
def apply_constraints(p,rules):
    changes=[]
    for page in p.slides:
        items=list(world_shapes(page.shapes))
        required=rules.get('match_shape_names',[])
        if required and not set(required).issubset({s.name for s,t in items}):continue
        for r in rules['rules']:
            sh,tr=find(items,r);sx,sy,tx,ty=tr
            if r['type']=='text_region':
                sh.width=round(r['width_pt']*EMU_PER_PT/sx)
                if r.get('single_line'):
                    sh.text_frame.word_wrap=False;sh.text_frame.auto_size=MSO_AUTO_SIZE.NONE
                changes.append(dict(shape_id=sh.shape_id,type='text_region',box_pt=box(sh,tr)))
            elif r['type']=='decoration_after_text':
                anchor,at=find(items,r,'anchor_');x,y,w,h=box(anchor,at)
                left=x+w+r['gap_pt'];aw=box(sh,tr)[2]
                if left+aw>p.slide_width/EMU_PER_PT-r['right_margin_pt']:raise ValueError('装饰超出安全区，需要更换布局或精简标题')
                sh.left=round((left*EMU_PER_PT-tx)/sx)
                sh.name='decoration:after:'+anchor.name
                changes.append(dict(shape_id=sh.shape_id,type='decoration_after_text',reserved_left_pt=left))
            else:raise ValueError('未知布局约束 '+r['type'])
    if not changes:raise ValueError('演示稿中没有匹配布局约束的页面')
    return changes
def main():
    a=argparse.ArgumentParser();a.add_argument('--input',type=Path,required=True);a.add_argument('--out',type=Path,required=True);a.add_argument('--constraints',type=Path,required=True);args=a.parse_args()
    if args.input.resolve()==args.out.resolve():a.error('输出必须是新文件，保留原稿')
    p=Presentation(args.input);changes=apply_constraints(p,json.loads(args.constraints.read_text(encoding='utf-8')));args.out.parent.mkdir(parents=True,exist_ok=True);p.save(args.out)
    print(json.dumps(changes,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
