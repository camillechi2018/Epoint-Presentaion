"""Normalize editable PPTX text to the locked task font profile."""
from pathlib import Path
from zipfile import ZipFile
from io import BytesIO
from lxml import etree
import argparse,json
import re
import copy
from font_profile import resolve
from embedded_fonts import clean_metadata, font_parts
A='http://schemas.openxmlformats.org/drawingml/2006/main'
P='http://schemas.openxmlformats.org/presentationml/2006/main'
NS={'a':A,'p':P}
PRIVATE_USE=re.compile(r'^[\ue000-\uf8ff\U000f0000-\U0010ffff]+$')

def preserve_font(node):
    names=node.xpath('ancestor::p:sp[1]/p:nvSpPr/p:cNvPr/@name',namespaces=NS)
    if names and names[0].startswith('brand:logo:'):
        return True
    runs=node.xpath('ancestor-or-self::a:r[1]',namespaces=NS)
    if runs:
        value=''.join(runs[0].xpath('./a:t/text()',namespaces=NS)).strip()
        return bool(value and PRIVATE_USE.fullmatch(value))
    return False
def normalize(src,out=None,check=False,profile=None):
    selected=resolve(profile)
    fonts={'latin':selected['latin'],'ea':selected['east_asian'],'cs':selected['latin']}
    issues=[];changed=0;gradient_fallbacks=0;buffer=BytesIO()
    with ZipFile(src) as zin, ZipFile(buffer,'w') as zout:
        embedded = font_parts(zin.namelist()) if not check else set()
        for info in zin.infolist():
            if info.filename in embedded:
                continue
            data=zin.read(info.filename)
            if info.filename.startswith('ppt/') and info.filename.endswith('.xml'):
                root=etree.fromstring(data)
                # python-pptx may omit a:rPr on a new run. It must be created
                # explicitly; theme defaults alone do not satisfy run audit.
                for run in root.xpath('//a:r|//a:fld',namespaces=NS):
                    if not preserve_font(run) and run.find(f'{{{A}}}rPr') is None:
                        run.insert(0,etree.Element(f'{{{A}}}rPr'))
                nodes=root.xpath('//a:rPr|//a:defRPr|//a:endParaRPr|//a:majorFont|//a:minorFont',namespaces=NS)
                for node in nodes:
                    if preserve_font(node):continue
                    for tag,font in fonts.items():
                        child=node.find(f'{{{A}}}{tag}')
                        if child is None or child.get('typeface')!=font:
                            issues.append({'part':info.filename,'script':tag})
                            if child is None:child=etree.SubElement(node,f'{{{A}}}{tag}')
                            child.set('typeface',font);changed+=1
                    for child in node.findall(f'{{{A}}}font'):
                        if child.get('script') in ('Hans','Hant') and child.get('typeface')!=selected['east_asian']:
                            issues.append({'part':info.filename,'script':child.get('script')})
                            child.set('typeface',selected['east_asian']);changed+=1
                if selected['id']=='linux':
                    # LibreOffice 7.x can render gradient-filled text black or
                    # invisible. A task copy uses the brightest visible stop;
                    # the source template and Windows/Mac variants stay intact.
                    inherited_shapes=root.xpath('//p:sp[p:txBody/a:lstStyle//a:defRPr/a:gradFill]',namespaces=NS)
                    for properties in root.xpath('//a:rPr[a:gradFill]|//a:defRPr[a:gradFill]',namespaces=NS):
                        if preserve_font(properties):continue
                        gradient=properties.find(f'{{{A}}}gradFill')
                        candidates=[]
                        for stop in gradient.findall(f'.//{{{A}}}gs'):
                            color=stop.find(f'{{{A}}}srgbClr')
                            if color is None or not color.get('val'):continue
                            alpha=color.find(f'{{{A}}}alpha')
                            opacity=int(alpha.get('val')) if alpha is not None else 100000
                            value=color.get('val')
                            brightness=sum(int(value[i:i+2],16) for i in (0,2,4))
                            candidates.append((opacity,brightness,value))
                        if not candidates:continue
                        opacity,_,value=max(candidates)
                        solid=etree.Element(f'{{{A}}}solidFill')
                        rgb=etree.SubElement(solid,f'{{{A}}}srgbClr')
                        rgb.set('val',value)
                        if opacity<100000:
                            etree.SubElement(rgb,f'{{{A}}}alpha').set('val',str(opacity))
                        properties.replace(gradient,solid)
                        gradient_fallbacks+=1
                    # LibreOffice does not reliably inherit a converted
                    # lstStyle fill, so materialize it on the actual run.
                    for shape in inherited_shapes:
                        defaults=shape.xpath('./p:txBody/a:lstStyle//a:defRPr/a:solidFill',namespaces=NS)
                        if not defaults:continue
                        for run in shape.xpath('./p:txBody/a:p/a:r',namespaces=NS):
                            props=run.find(f'{{{A}}}rPr')
                            if props is not None and not any(props.find(f'{{{A}}}{kind}') is not None
                                                         for kind in ('solidFill','gradFill','noFill','pattFill')):
                                props.insert(0,copy.deepcopy(defaults[0]))
                                gradient_fallbacks+=1
                data=etree.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
            if embedded:
                data=clean_metadata(info.filename,data)
            zout.writestr(info,data)
    if not check:
        if out is None:raise ValueError('Output path required')
        Path(out).write_bytes(buffer.getvalue())
    return {'passed':not issues if check else True,'font_assignments_changed':changed,
            'issues':len(issues),'font_profile':selected,
            'gradient_text_fallbacks':gradient_fallbacks,
            'embedded_font_parts_removed':len(embedded)}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',required=True,type=Path);p.add_argument('--out',type=Path);p.add_argument('--check',action='store_true');p.add_argument('--profile');a=p.parse_args()
    result=normalize(a.input,a.out,a.check,a.profile);print(json.dumps(result))
    if not result['passed']:raise SystemExit(2)
