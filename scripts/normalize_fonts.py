"""Normalize editable PPTX text to Windows fonts; retain symbol fonts and media."""
from pathlib import Path
from zipfile import ZipFile
from io import BytesIO
from lxml import etree
import argparse,json
A='http://schemas.openxmlformats.org/drawingml/2006/main'
NS={'a':A}
FONTS={'latin':'Arial','ea':'Microsoft YaHei','cs':'Arial'}

def normalize(src,out=None,check=False):
    issues=[];changed=0;buffer=BytesIO()
    with ZipFile(src) as zin, ZipFile(buffer,'w') as zout:
        for info in zin.infolist():
            data=zin.read(info.filename)
            if info.filename.startswith('ppt/') and info.filename.endswith('.xml'):
                root=etree.fromstring(data)
                nodes=root.xpath('//a:rPr|//a:defRPr|//a:endParaRPr|//a:majorFont|//a:minorFont',namespaces=NS)
                for node in nodes:
                    for tag,font in FONTS.items():
                        child=node.find(f'{{{A}}}{tag}')
                        if child is None or child.get('typeface')!=font:
                            issues.append({'part':info.filename,'script':tag})
                            if child is None:child=etree.SubElement(node,f'{{{A}}}{tag}')
                            child.set('typeface',font);changed+=1
                    for child in node.findall(f'{{{A}}}font'):
                        if child.get('script') in ('Hans','Hant') and child.get('typeface')!='Microsoft YaHei':
                            issues.append({'part':info.filename,'script':child.get('script')})
                            child.set('typeface','Microsoft YaHei');changed+=1
                data=etree.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
            zout.writestr(info,data)
    if not check:
        if out is None:raise ValueError('Output path required')
        Path(out).write_bytes(buffer.getvalue())
    return {'passed':not issues if check else True,'font_assignments_changed':changed,'issues':len(issues),'east_asian':'Microsoft YaHei','latin':'Arial'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',required=True,type=Path);p.add_argument('--out',type=Path);p.add_argument('--check',action='store_true');a=p.parse_args()
    result=normalize(a.input,a.out,a.check);print(json.dumps(result))
    if not result['passed']:raise SystemExit(2)
