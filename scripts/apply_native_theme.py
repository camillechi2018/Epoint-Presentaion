"""Apply verified theme slots to an editable copy; report unresolved explicit colors."""
from __future__ import annotations
import argparse,json,re
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from lxml import etree
from pptx import Presentation
from library_location import get_library

ANS='http://schemas.openxmlformats.org/drawingml/2006/main'

def apply(library:Path,layout_id:str,theme_file:Path,output:Path,input_file:Path|None=None):
    library=library.resolve();output=output.resolve()
    cat=json.loads((library/'catalog.json').read_text(encoding='utf-8-sig'))
    layout=next((e for e in cat['layouts'] if e['id']==layout_id),None)
    if not layout:raise ValueError('未知组件：'+layout_id)
    theme=json.loads(theme_file.read_text(encoding='utf-8-sig'))
    if layout.get('role')=='cover':raise ValueError('封面背景是图片，必须按色系选择图库图片，不能仅改主题槽换色')
    target=theme_file.stem.removeprefix('new-template-')
    if target not in ('blue','red') and 'blue' not in layout.get('themes',[]):
        raise ValueError('扩展色目前只以蓝色原稿为基线，当前组件缺少蓝色来源')
    source_rel=layout.get('red_source') if target=='red' and layout.get('red_source') else layout['source']
    source=(library/source_rel).resolve()
    if not source.is_relative_to(library) or output==source or output.is_relative_to(library):raise ValueError('输出必须在知识库外')
    if input_file is not None:
        source=input_file.resolve()
        if output==source:raise ValueError('换色不能覆盖输入')
    slots={k:v.lstrip('#').upper() for k,v in theme['color_slots'].items()}
    counts={'theme_slots_changed':0,'explicit_unmapped':0,'source_color_variant':source_rel}
    page=layout.get('red_source_page') if target=='red' and layout.get('red_source_page') else layout['source_page']
    presentation=Presentation(source)
    if input_file is None:
        ids=list(presentation.slides._sldIdLst);keep=ids[page-1]
        for item in ids:
            if item is keep:continue
            presentation.part.drop_rel(item.rId);presentation.slides._sldIdLst.remove(item)
    elif len(presentation.slides)!=1:
        raise ValueError('已填充输入必须是单页组件')
    selected=BytesIO();presentation.save(selected);selected.seek(0)
    output.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(selected) as inp,ZipFile(output,'w') as out:
        for member in inp.infolist():
            data=inp.read(member.filename);name=member.filename
            if re.fullmatch(r'ppt/theme/theme\d+\.xml',name):
                root=etree.fromstring(data)
                for node in root.xpath('.//a:clrScheme/*',namespaces={'a':ANS}):
                    role=etree.QName(node).localname
                    if role not in slots:continue
                    for child in node:
                        if etree.QName(child).localname=='srgbClr' and child.get('val','').upper()!=slots[role]:
                            child.set('val',slots[role]);counts['theme_slots_changed']+=1
                data=etree.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True)
            elif re.fullmatch(r'ppt/slides/slide\d+\.xml',name):
                root=etree.fromstring(data)
                counts['explicit_unmapped']+=len(root.xpath('.//a:srgbClr',namespaces={'a':ANS}))
            out.writestr(member,data)
    with ZipFile(output) as z:
        if z.testzip():raise ValueError('生成的 PPTX ZIP 校验失败')
    report={'layout_id':layout_id,'theme':theme['id'],'source':str(source) if input_file else source_rel,'output':str(output),
            'counts':counts,'object_binding_status':'pending_review','visual_qa':'not_run',
            'warning':'显式色与渐变节点仅完成清点，未批准的对象映射不执行猜测替换'}
    output.with_suffix('.theme-qa.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--library',type=Path);ap.add_argument('--layout',required=True);ap.add_argument('--theme',type=Path,required=True);ap.add_argument('--input',type=Path);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    try:print(json.dumps(apply(a.library or get_library(),a.layout,a.theme,a.out,a.input),ensure_ascii=False))
    except (ValueError,KeyError,FileNotFoundError) as e:ap.exit(2,str(e)+'\n')
if __name__=='__main__':main()
