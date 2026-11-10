"""Import the two user supplied supplemental decks into the existing library."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from pptx import Presentation

BASE = Path(r"D:\codex_test\AI实践案例\AI培训课程\企业PPT-Skills-精选")
SOURCE = BASE / "模板" / "新模板"
PREVIEW = BASE / "_验证输出" / "蓝红补充模板评估"

# The first eight records have semantic field maps. Other physical pages are
# indexed and kept provisional until their text, logo and media checks finish.
RECORDS = [
 ("supp-directory-01","directory",1,9,"directory-six-paired-circles",{4:"page.title",3:"items[0].title",12:"items[1].title",16:"items[2].title",18:"items[3].title",20:"items[4].title",22:"items[5].title"},None),
 ("supp-directory-02","directory",2,10,"directory-six-vertical-cards",{4:"page.title",25:"items[0].title",31:"items[1].title",33:"items[2].title",35:"items[3].title",39:"items[4].title",43:"items[5].title"},None),
 ("supp-directory-03","directory",3,12,"directory-six-horizontal",{4:"page.title",3:"items[0].title",28:"items[1].title",32:"items[2].title",34:"items[3].title",38:"items[4].title",42:"items[5].title"},None),
 ("supp-directory-04","directory",4,8,"directory-six-double-cards",{4:"page.title",12:"items[0].title",21:"items[1].title",24:"items[2].title",27:"items[3].title",30:"items[4].title",33:"items[5].title"},None),
 ("supp-section-01","section",5,14,"section-number-side",{4:"section.title",5:"section.subtitle",6:"section.number"},None),
 ("supp-section-02","section",6,15,"section-number-center",{2:"section.number",4:"section.title"},None),
 ("supp-section-03","section",7,16,"section-part-label",{4:"section.title",5:"section.subtitle",6:"section.part"},{4:"section.title",2:"section.subtitle",6:"section.part"}),
 ("supp-closing-01","closing",10,20,"closing-triangle",{4:"closing.title",10:"closing.presenter"},None),
 ("supp-directory-04-red-variant","directory",None,11,"directory-six-double-cards",None,{4:"page.title",12:"items[0].title",21:"items[1].title",24:"items[2].title",27:"items[3].title",30:"items[4].title",33:"items[5].title"}),
 ("supp-section-blue-08","section",8,None,"section-blue-full",None,None),
 ("supp-section-blue-09","section",9,None,"section-hexagon-blue",None,None),
 ("supp-section-red-13","section",None,13,"section-report-red",None,None),
 ("supp-section-red-17","section",None,17,"section-ribbon-red",None,None),
 ("supp-section-red-18","section",None,18,"section-hexagon-red",None,None),
 ("supp-closing-02","closing",11,21,"closing-curve",None,None),
 ("supp-closing-03","closing",12,22,"closing-gradient-ribbon",None,None),
 ("supp-closing-blue-13","closing",13,None,"closing-blue-full",None,None),
 ("supp-closing-blue-14","closing",14,None,"closing-blue-minimal",None,None),
 ("supp-closing-red-19","closing",None,19,"closing-product-red",None,None),
 ("supp-closing-red-23","closing",None,23,"closing-red-full",None,None),
 ("supp-closing-red-24","closing",None,24,"closing-red-minimal",None,None),
 *[(f"supp-cover-red-{n:02d}","cover",None,n,f"cover-red-{n:02d}",None,None) for n in range(1,8)],
]

EXTRA_FIELDS={
 'supp-directory-04-red-variant':{4:'page.title',12:'items[0].title',21:'items[1].title',24:'items[2].title',27:'items[3].title',30:'items[4].title',33:'items[5].title'},
 'supp-section-blue-08':{4:'section.title',5:'section.subtitle',6:'section.number'},
 'supp-section-blue-09':{7:'section.title',9:'section.number',11:'section.subtitle'},
 'supp-section-red-13':{4:'section.title',7:'section.header',15:'section.part'},
 'supp-section-red-17':{4:'section.title',7:'section.header',6:'section.number'},
 'supp-section-red-18':{7:'section.title',9:'section.number'},
 'supp-closing-02':{4:'closing.title',10:'closing.presenter'},
 'supp-closing-03':{4:'closing.title',10:'closing.presenter'},
 'supp-closing-blue-13':{4:'closing.title',5:'closing.subtitle',10:'closing.presenter'},
 'supp-closing-blue-14':{4:'closing.title',5:'closing.subtitle'},
 'supp-closing-red-19':{16:'closing.title',19:'closing.subtitle',8:'closing.note'},
 'supp-closing-red-23':{4:'closing.title',5:'closing.subtitle',7:'closing.date',10:'closing.presenter'},
 'supp-closing-red-24':{4:'closing.title',5:'closing.subtitle',10:'closing.presenter'},
 'supp-cover-red-01':{11:'cover.title',15:'cover.english',14:'cover.subtitle',97:'cover.presenter'},
 'supp-cover-red-02':{5:'cover.title',6:'cover.presenter',7:'cover.kicker'},
 'supp-cover-red-03':{4:'cover.title',5:'cover.kicker',10:'cover.presenter'},
 'supp-cover-red-04':{4:'cover.title',5:'cover.kicker',10:'cover.presenter'},
 'supp-cover-red-05':{4:'cover.title',5:'cover.kicker',10:'cover.presenter'},
 'supp-cover-red-06':{4:'cover.title',10:'cover.presenter'},
 'supp-cover-red-07':{4:'cover.title',10:'cover.presenter'},
}
SOURCE_LOGOS={
 'supp-closing-01':(7,3),'supp-closing-02':(7,5),'supp-closing-03':(18,3),
 'supp-closing-blue-13':(8,None),'supp-closing-blue-14':(7,None),
 'supp-closing-red-19':(None,7),'supp-closing-red-23':(None,12),'supp-closing-red-24':(None,3),
 'supp-cover-red-01':(None,3),'supp-cover-red-02':(None,4),'supp-cover-red-03':(None,3),
 'supp-cover-red-04':(None,7),'supp-cover-red-05':(None,3),'supp-cover-red-06':(None,8),
 'supp-cover-red-07':(None,3),
}
STYLES={
 'supp-cover-red-01':'product-launch','supp-cover-red-02':'white-curve',
 'supp-cover-red-03':'executive-minimal','supp-cover-red-04':'triangle-corporate',
 'supp-cover-red-05':'ribbon-bold','supp-cover-red-06':'full-red',
 'supp-cover-red-07':'diagonal-ribbon','supp-closing-red-19':'product-launch',
 'supp-closing-01':'triangle-corporate','supp-closing-02':'white-curve',
 'supp-closing-03':'diagonal-ribbon','supp-closing-blue-13':'full-blue',
 'supp-closing-blue-14':'executive-minimal','supp-closing-red-23':'full-red',
 'supp-closing-red-24':'executive-minimal',
}

def dump(path: Path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def fields(slide, semantic):
    out=[]
    def walk(shapes):
        for shape in shapes:
            yield shape
            if shape.shape_type==6:yield from walk(shape.shapes)
    for shape in walk(slide.shapes):
        if not shape.has_text_frame or not shape.text.strip(): continue
        sid=shape.shape_id
        text=shape.text.strip()
        if "688232" in text or "成为行业数字化领航者" in text: continue
        role=semantic.get(sid) if semantic is not None else None
        if semantic is not None and role is None: continue
        width=round(shape.width/12700,1)
        wide=50 if width<1 else max(8,min(100,int(width/7)))
        field={"field":f"text_{sid}","shape_id":sid,"shape_name":shape.name,"type":"text",
               "max_chars":max(8,min(120,len(text)*2+6)),"source_sample_chars":len(text),
               "source_text":text,"bounds_pt":[round(v/12700,1) for v in (shape.left,shape.top,shape.width,shape.height)],
               "semantic_role":role.rsplit('.',1)[-1] if role else "provisional"}
        field.update(semantic_path=role or f"source.shape_{sid}")
        if role:
            field.update(max_width_units=wide,max_lines=max(1,text.count('\n')+1))
        out.append(field)
    if semantic is not None and set(semantic)-{x['shape_id'] for x in out}:
        raise ValueError(f"semantic shape missing: {set(semantic)-{x['shape_id'] for x in out}}")
    return out

def find_shape(shapes,target):
    for shape in shapes:
        if shape.shape_id==target:return shape
        if shape.shape_type==6:
            nested=find_shape(shape.shapes,target)
            if nested is not None:return nested
    return None

def image_objects(slide,logo_id):
    output=[]
    def walk(shapes):
        for shape in shapes:
            if shape.shape_type==13:
                output.append({'shape_id':shape.shape_id,'shape_name':shape.name,
                               'semantic_role':'brand_logo_locked' if shape.shape_id==logo_id else 'source_visual_locked',
                               'asset_sha256':hashlib.sha256(shape.image.blob).hexdigest()})
            if shape.shape_type==6:walk(shape.shapes)
    walk(slide.shapes)
    return output

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--library',type=Path,required=True);a=ap.parse_args()
    root=a.library.resolve()
    decks={"blue":Presentation(SOURCE/"01蓝色-补充.pptx"),"red":Presentation(SOURCE/"02红色-补充.pptx")}
    for color,name in (("blue","01蓝色-补充.pptx"),("red","02红色-补充.pptx")):
        shutil.copy2(SOURCE/name,root/"sources"/f"{color}-supplement.pptx")
        dst=root/"source-previews"/f"{color}-supplement";dst.mkdir(parents=True,exist_ok=True)
        for n in range(1,len(decks[color].slides)+1):
            shutil.copy2(PREVIEW/color/f"P{n:02d}.png",dst/f"P{n:03d}.png")
    catalog=json.loads((root/"catalog.json").read_text(encoding="utf-8"))
    catalog['layouts']=[x for x in catalog['layouts'] if not x['id'].startswith('supp-')]
    source_pages=json.loads((root/"source-pages.json").read_text(encoding="utf-8"))
    source_pages=[x for x in source_pages if x['source'] not in ('blue-supplement','red-supplement')]
    pages_seen={"blue":{},"red":{}}
    for ident,role,bp,rp,family,bmap,rmap in RECORDS:
        color='blue' if bp is not None else 'red';page=bp if bp is not None else rp
        common={"id":ident,"version":"1.0.0-draft","collection":"new-template-supplement",
                "role":role,"information_relation":{"directory":"navigation","section":"chapter-divider","cover":"visual-story","closing":"closing-message"}[role],
                "classification_status":"provisional","family_id":family,
                "source":f"sources/{color}-supplement.pptx","example":f"sources/{color}-supplement.pptx",
                "source_page":page,"source_mapping":{},"bindings":f"layouts/{ident}/bindings.json",
                "spec":f"layouts/{ident}/spec.md","layout_rules":f"layouts/{ident}/layout_rules.json",
                "motion":f"layouts/{ident}/motion.json","preview":f"source-previews/{color}-supplement/P{page:03d}.png",
                "themes":["blue","red"] if bp and rp else [color],"status":"draft_pending_review",
                "capacity":{"body_slots":7 if role=='directory' else 3,"item_title_slots":6 if role=='directory' else 0,"cell_max_chars":20},
                "shape_count":len(decks[color].slides[page-1].shapes),"media_status":"source_pending_review",
                "html_support":"not_implemented","motion_support":"source_static",
                "pptx_support":"source_index_only","brand_policy":"default_logo; preserve source brand; no duplicate",
                "cardinality_status":"fixed_source_count_pending_review",
                "composition_tags":[role,family],"color_family":color,
                "style":STYLES.get(ident,'blue-red-minimal'),"visual_impact":"high" if ident in ('supp-cover-red-01','supp-cover-red-05','supp-cover-red-06','supp-cover-red-07') else "medium"}
        if role=='cover':
            common['cover_match_status']='pending_powerpoint_review'
            common['title_area_hint']='left' if ident in ('supp-cover-red-01','supp-cover-red-04','supp-cover-red-05','supp-cover-red-06') else 'center'
            common['subject_tags']=['enterprise-report','minimal-red']
        if role=='closing':
            common['closing_match_status']='pending_powerpoint_review'
            common['subject_tags']=['enterprise-report','closing']
        common['color_binding_status']='native_blue_red_palette; supplemental token audit pending'
        if bp:
            common['source_mapping']['blue-supplement']=bp
            pages_seen['blue'][bp]=ident
        if rp:
            common['source_mapping']['red-supplement']=rp
            pages_seen['red'][rp]=ident
        if bp and rp:
            common['red_source']='sources/red-supplement.pptx';common['red_source_page']=rp
            common['red_bindings']=f"layouts/{ident}/bindings-red.json"
            common['red_preview']=f"source-previews/red-supplement/P{rp:03d}.png"
        if role=='directory':
            common['capacity']['item_title_slots']=6
        if ident in {"supp-directory-01","supp-directory-02","supp-directory-03","supp-directory-04","supp-section-01","supp-section-02","supp-section-03","supp-closing-01"}:
            common['semantic_review_status']='mapped_pending_render'
        if ident in SOURCE_LOGOS:
            blue_logo,red_logo=SOURCE_LOGOS[ident]
            if blue_logo is not None:
                common['source_logo_shape_id']=blue_logo
                logo=find_shape(decks['blue'].slides[bp-1].shapes,blue_logo)
                common['source_logo_asset_sha256']=hashlib.sha256(logo.image.blob).hexdigest()
            if red_logo is not None:
                if bp is not None:common['red_source_logo_shape_id']=red_logo
                else:
                    common['source_logo_shape_id']=red_logo
                    logo=find_shape(decks['red'].slides[rp-1].shapes,red_logo)
                    common['source_logo_asset_sha256']=hashlib.sha256(logo.image.blob).hexdigest()
        catalog['layouts'].append(common)
        semantic=(bmap if color=='blue' else rmap) or EXTRA_FIELDS.get(ident)
        bindings=fields(decks[color].slides[page-1],semantic)
        if ident=='supp-directory-04':
            for field in bindings:
                if field.get('semantic_path')=='page.title':
                    field.update(max_chars=2,max_width_units=4,allowed_values=['目录'])
        for field in bindings:
            path=field.get('semantic_path')
            if ident=='supp-cover-red-05' and path=='cover.title':
                field.update(max_width_units=12,max_lines=2)
            if ident=='supp-cover-red-06' and path=='cover.title':
                field.update(max_chars=6,max_width_units=12,max_lines=1)
            if ident=='supp-section-red-13' and path=='section.part':
                field.update(max_chars=6,max_width_units=6,max_lines=1)
        logo_id=SOURCE_LOGOS.get(ident,(None,None))[0 if color=='blue' else 1]
        dump(root/common['bindings'],{"schema_version":"1.0","fields":bindings,"objects":{"charts":[],"tables":[],"images":image_objects(decks[color].slides[page-1],logo_id)},
                 "review":"semantic mapped, rendering pending" if ident.startswith(('supp-directory-','supp-section-0','supp-closing-01')) else "source index only"})
        if bp and rp:
            rb=fields(decks['red'].slides[rp-1],rmap or bmap or EXTRA_FIELDS.get(ident))
            if [x['semantic_path'] for x in bindings] != [x['semantic_path'] for x in rb]:
                # Use semantic path as stable field name across the two native variants.
                if set(x['semantic_path'] for x in bindings)!=set(x['semantic_path'] for x in rb):
                    raise ValueError(f"paired fields mismatch: {ident}")
                rb.sort(key=lambda x:[b['semantic_path'] for b in bindings].index(x['semantic_path']))
            for field,red_field in zip(bindings,rb):red_field['field']=field['field']
            if ident=='supp-directory-04':
                for field in rb:
                    if field.get('semantic_path')=='page.title':
                        field.update(max_chars=2,max_width_units=4,allowed_values=['目录'])
            red_logo_id=SOURCE_LOGOS.get(ident,(None,None))[1]
            dump(root/common['red_bindings'],{"schema_version":"1.0","fields":rb,"objects":{"charts":[],"tables":[],"images":image_objects(decks['red'].slides[rp-1],red_logo_id)},"review":"red native counterpart"})
        count=6 if role=='directory' else 1
        layout_rules={"cardinality_mode":"fixed","supported_counts":[count],"source_count":count,
                 "reflow_status":"not_applicable","validation_status":"source_index_only",
                 "count_evidence":"native geometry; fixed count pending QA"}
        if ident=='supp-section-red-17':layout_rules['text_box_expand_pt']=[{"shape_id":6,"vertical_extra_pt":12}]
        dump(root/common['layout_rules'],layout_rules)
        dump(root/common['motion'],{"status":"source_static","groups":[],"design_intent":{"directory":"six items reveal in reading order","section":"brief chapter transition","cover":"title and subtitle reveal","closing":"short fade-in"}[role],"playback_review":"not_done"})
        (root/common['spec']).write_text(
            f"# {ident}\n\n来源：蓝色补充 P{bp:02d}" if bp else f"# {ident}\n\n来源：红色补充 P{rp:02d}",encoding="utf-8")
    for color,pages in pages_seen.items():
        expected=len(decks[color].slides)
        if set(pages)!=set(range(1,expected+1)):raise ValueError(f"{color} physical page coverage incomplete: {set(range(1,expected+1))-set(pages)}")
        for page,component_id in sorted(pages.items()):
            source_pages.append({"source":f"{color}-supplement","page":page,"component_id":component_id,
                                 "variant":color,"source_pptx":f"sources/{color}-supplement.pptx","extraction_status":"indexed"})
    dump(root/"catalog.json",catalog);dump(root/"source-pages.json",source_pages)
    sm=json.loads((root/"source-manifest.json").read_text(encoding="utf-8"))
    for color,name in (("blue","01蓝色-补充.pptx"),("red","02红色-补充.pptx")):
        sm['sources'][f"{color}-supplement"]={"filename":name,"sha256":hashlib.sha256((SOURCE/name).read_bytes()).hexdigest(),
                                              "page_count":len(decks[color].slides),"relationship":"extends-existing-minimal-color"}
    dump(root/"source-manifest.json",sm)
    print(json.dumps({"physical_pages":sum(len(x.slides) for x in decks.values()),"layout_records":len(RECORDS),
                      "source_coverage":{k:len(v) for k,v in pages_seen.items()}},ensure_ascii=False))

if __name__=='__main__': main()
