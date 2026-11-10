"""Inventory tech OOXML colors per source object without claiming recolor support."""
from __future__ import annotations
import argparse,json,posixpath,re
from collections import Counter
from pathlib import Path
from zipfile import ZipFile
from lxml import etree

NS={'a':'http://schemas.openxmlformats.org/drawingml/2006/main',
    'p':'http://schemas.openxmlformats.org/presentationml/2006/main',
    'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
COLOR_TAGS={'srgbClr','schemeClr','sysClr','prstClr','scrgbClr','hslClr'}
SHAPE_TAGS={'sp','pic','cxnSp','graphicFrame'}
SVG_COLOR_RE=re.compile(r'(?:fill|stroke)\s*=\s*[\"\']([^\"\']+)[\"\']|#[0-9A-Fa-f]{3,8}')

def local(node):return etree.QName(node).localname
def color_ref(node):
    value=node.get('val') or node.get('lastClr') or node.get('r')
    return {'kind':local(node),'value':value,'context':local(node.getparent())}
def parse_rels(z:ZipFile,page:int):
    name=f'ppt/slides/_rels/slide{page}.xml.rels'
    if name not in z.namelist():return {}
    root=etree.fromstring(z.read(name));ret={}
    for x in root:
        target=x.get('Target','')
        ret[x.get('Id')]=posixpath.normpath(posixpath.join('ppt/slides',target.lstrip('/'))) if not target.startswith('/') else target.lstrip('/')
    return ret

def build(root:Path,update_manifest=True):
    from import_tech_style import VERSION,digest,dump
    root=Path(root)
    source=root/'sources/tech.pptx'
    catalog=json.loads((root/'catalog.json').read_text(encoding='utf-8'))['layouts']
    tech={e['source_page']:e['id'] for e in catalog if e.get('style_family')=='deep-blue-tech'}
    pages={};total=Counter();chart_paths=set();media_paths=set()
    with ZipFile(source) as z:
      names=set(z.namelist())
      for page in sorted(tech):
        slide=etree.fromstring(z.read(f'ppt/slides/slide{page}.xml'))
        rels=parse_rels(z,page);objects=[];sums=Counter();colors=Counter();images=[];page_charts=[]
        media_paths.update(path for path in rels.values() if path.startswith('ppt/media/'))
        for node in slide.iter():
          if local(node) not in SHAPE_TAGS:continue
          props=node.xpath('./p:nvSpPr/p:cNvPr|./p:nvPicPr/p:cNvPr|./p:nvCxnSpPr/p:cNvPr|./p:nvGraphicFramePr/p:cNvPr',namespaces=NS)
          if not props:continue
          sid=int(props[0].get('id'));name=props[0].get('name','')
          refs=[];gradient_count=0;stops=0
          for part in node.iter():
            if part is not node and local(part) in SHAPE_TAGS:continue
            if local(part) in COLOR_TAGS:
              ref=color_ref(part);refs.append(ref);colors[(ref['kind'],str(ref['value']))]+=1
            elif local(part)=='gradFill':gradient_count+=1
            elif local(part)=='gs':stops+=1
          # Shape nodes do not nest other shapes, so descendant counts belong to this object.
          if refs or gradient_count:
            objects.append({'shape_id':sid,'name':name,'color_refs':refs,
                            'gradient_fills':gradient_count,'gradient_stops':stops,
                            'semantic_role':'unmapped_pending_review'})
          sums['color_refs']+=len(refs);sums['gradients']+=gradient_count;sums['gradient_stops']+=stops
          if local(node)=='pic':
            for blip in node.xpath('.//a:blip',namespaces=NS):
              path=rels.get(blip.get('{%s}embed'%NS['r']))
              if path:images.append({'shape_id':sid,'media':path,'kind':Path(path).suffix.lower()});media_paths.add(path)
          if local(node)=='graphicFrame':
            for chart in node.xpath('.//*[local-name()="chart"]'):
              path=rels.get(chart.get('{%s}id'%NS['r']))
              if path:page_charts.append({'shape_id':sid,'chart_part':path});chart_paths.add(path)
        for key,value in sums.items():total[key]+=value
        total['pictures']+=len(images);total['charts']+=len(page_charts)
        pages[str(page)]={'component_id':tech[page],'counts':dict(sums),
          'distinct_colors':[{'kind':kind,'value':val,'occurrences':n} for (kind,val),n in colors.most_common()],
          'objects':objects,'pictures':images,'charts':page_charts,
          'recolor_status':'not_verified'}
      svg=[]
      for path in sorted(path for path in names if path.startswith('ppt/media/') and path.lower().endswith('.svg')):
        if path in names:
          xml=z.read(path).decode('utf-8',errors='replace')
          svg.append({'media':path,'color_tokens':sorted({m.group(1) or m.group(0) for m in SVG_COLOR_RE.finditer(xml)}),
                      'source_slide_refs':[page for page in sorted(tech) if path in parse_rels(z,page).values()],
                      'recolor_status':'not_verified'})
      chart_inventory=[]
      for path in sorted(chart_paths):
        if path not in names:continue
        xml=etree.fromstring(z.read(path));cols=Counter((local(x),str(x.get('val') or x.get('lastClr'))) for x in xml.iter() if local(x) in COLOR_TAGS)
        chart_inventory.append({'part':path,'color_refs':[{'kind':k,'value':v,'count':n} for (k,v),n in cols.most_common()],
          'gradient_fills':sum(local(x)=='gradFill' for x in xml.iter()),'recolor_status':'not_verified'})
    report={'schema_version':'1.0','source':'sources/tech.pptx','status':'inventory_only_no_recolor_claim',
      'page_count':len(pages),'totals':dict(total),'chart_parts':len(chart_inventory),
      'svg_media':svg,'charts':chart_inventory,'pages':pages,
      'next_step':'逐对象赋予语义角色；实测主题、渐变、SVG、图表和背景图的换色，再开放对应组件。'}
    dump(root/'color-inventory-tech.json',report)
    if update_manifest:
      files={p.relative_to(root).as_posix():digest(p) for p in root.rglob('*')
             if p.is_file() and '.git' not in p.parts and p.name not in
             ('knowledge-manifest.json','audit-report.json','blank.pptx','blank-red.pptx')
             and 'source-pages' not in p.relative_to(root).parts}
      dump(root/'knowledge-manifest.json',{'schema_version':'1.0','version':VERSION,
                                          'status':'draft_pending_review','file_count':len(files),'files':files})
    return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True)
    x=build(p.parse_args().library)
    print(json.dumps({k:x[k] for k in ('status','page_count','totals','chart_parts')},ensure_ascii=False))
