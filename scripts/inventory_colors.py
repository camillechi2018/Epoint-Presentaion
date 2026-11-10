"""Record OOXML color references by source page and object; no unsafe global recolor."""
from __future__ import annotations
import argparse,json,re
from collections import Counter
from pathlib import Path
from zipfile import ZipFile
from lxml import etree

PNS='http://schemas.openxmlformats.org/presentationml/2006/main'
ANS='http://schemas.openxmlformats.org/drawingml/2006/main'
COLOR={'srgbClr','schemeClr','sysClr','prstClr','scrgbClr','hslClr'}

def scan(path):
    pages={};totals=Counter()
    with ZipFile(path) as z:
        names=[n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml',n)]
        for name in sorted(names,key=lambda x:int(re.search(r'(\d+)\.xml$',x).group(1))):
            n=int(re.search(r'(\d+)\.xml$',name).group(1));root=etree.fromstring(z.read(name));refs=[]
            for node in root.iter():
                if etree.QName(node).namespace!=ANS or etree.QName(node).localname not in COLOR:continue
                parent=node.getparent();shape=None
                for ancestor in node.iterancestors():
                    if etree.QName(ancestor).namespace==PNS and etree.QName(ancestor).localname in ('sp','pic','graphicFrame','cxnSp','grpSp'):
                        shape=ancestor;break
                if shape is not None:
                    ids=shape.xpath('.//p:cNvPr',namespaces={'p':PNS})
                    shape_id=int(ids[0].get('id')) if ids else None
                else:shape_id=None
                owner=etree.QName(parent).localname if parent is not None else None
                kind=etree.QName(node).localname;value=node.get('val') or node.get('lastClr') or ''
                refs.append({'shape_id':shape_id,'kind':kind,'value':value,'context':owner,
                             'xpath':root.getroottree().getpath(node),'role':'unmapped_pending_review'})
                totals[(kind,value)]+=1
            pages[str(n)]={'color_refs':refs,'count':len(refs)}
    return pages,totals

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--templates',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    files={'blue':'01蓝色系.pptx','red':'02红色系.pptx','cover':'20页封面（比例16-9）.pptx'}
    all_pages={};summary={}
    for kind,filename in files.items():
        pages,counts=scan(a.templates/filename);all_pages[kind]=pages
        summary[kind]={'pages':len(pages),'references':sum(x['count'] for x in pages.values()),
                       'top_colors':[{'kind':k[0],'value':k[1],'count':v} for k,v in counts.most_common(50)]}
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/'color-inventory.json').write_text(json.dumps({'schema_version':'1.0','status':'unmapped_pending_review','pages':all_pages},ensure_ascii=False),encoding='utf-8')
    (a.out/'color-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:{'pages':v['pages'],'references':v['references']} for k,v in summary.items()},ensure_ascii=False))
if __name__=='__main__':main()
