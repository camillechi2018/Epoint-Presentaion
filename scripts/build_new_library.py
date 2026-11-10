"""Build the isolated, traceable library with an optional fourth tech source.

This deliberately records unreviewed classifications as provisional. Source
slides remain editable OOXML; business example text is removed from blank PPTX.
"""
from __future__ import annotations

import argparse
from collections import Counter
from difflib import SequenceMatcher
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
from shutil import copy2
import subprocess,sys
from zipfile import ZipFile, ZIP_DEFLATED

from lxml import etree
from pptx import Presentation

VERSION = "1.0.0-draft"
NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
SLOGAN = "成为行业数字化领航者"
CODE = "688232"
COLORS = {
    "blue": {"dk2":"041D4B","lt2":"F6F9FF","accent1":"0154DD","accent2":"00BDDE","accent3":"24D3BA","accent4":"13A6E5","accent5":"79A6FF","accent6":"3277F4"},
    "red": {"dk2":"3E0000","lt2":"FFFFFF","accent1":"930000","accent2":"AC2C00","accent3":"A64C0A","accent4":"D18755","accent5":"DAB67F","accent6":"FF9E73"},
}
COVER_LABELS = [
    ("blue","technology-future","high","left"),("blue","technology-minimal","medium","left"),
    ("blue","technology-future","high","left"),("blue","stage-launch","high","right"),
    ("warm-gold","ceremony","medium-high","upper-center"),("warm-gold","modern-business","medium","upper-center"),
    ("blue","nature-vista","medium","right"),("warm-gold","city-architecture","medium","right"),
    ("blue","city-technology","high","left"),("blue","technology-future","high","left"),
    ("blue","technology-speed","high","center"),("blue","technology-speed","high","right"),
    ("light-blue","bright-future","medium","left"),("light-blue","city-architecture","medium","left"),
    ("neutral","minimal-business","medium","center"),("warm-gold","ceremony","high","center"),
    ("blue","nature-vista","medium","upper-center"),("blue","digital-city","high","center"),
    ("blue","digital-city","high","upper-center"),("blue","technology-future","high","right"),
]

def dump(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def digest(path: Path):
    h=sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def walk(shapes):
    for s in shapes:
        yield s
        if s.shape_type == 6: yield from walk(s.shapes)

def signature(slide):
    return tuple((int(s.shape_type),round(s.left/914400,3),round(s.top/914400,3),
                  round(s.width/914400,3),round(s.height/914400,3),
                  s.text.strip() if s.has_text_frame else "") for s in slide.shapes)

def inspect(slide):
    shapes=list(walk(slide.shapes)); texts=[]; objects={"charts":[],"tables":[],"images":[]}
    for s in shapes:
        if s.has_text_frame and s.text.strip():
            v=s.text.strip(); field=f"text_{s.shape_id}"
            texts.append({"field":field,"shape_id":s.shape_id,"shape_name":s.name,
                          "type":"text","max_chars":max(len(v)*2,24),
                          "source_sample_chars":len(v),"source_text":v,
                          "bounds_pt":[round(x/12700,1) for x in (s.left,s.top,s.width,s.height)],
                          "semantic_role":"brand_locked" if CODE in v or SLOGAN in v else "provisional"})
        if s.has_chart: objects["charts"].append({"shape_id":s.shape_id,"shape_name":s.name,"categories_max":8,"series_max":4})
        if s.has_table: objects["tables"].append({"shape_id":s.shape_id,"shape_name":s.name,"rows":len(s.table.rows),"columns":len(s.table.columns)})
        if s.shape_type==13:
            try: image_hash=sha256(s.image.blob).hexdigest()
            except Exception: image_hash=None
            objects["images"].append({"shape_id":s.shape_id,"shape_name":s.name,"sha256":image_hash,
                                      "bounds_pt":[round(x/12700,1) for x in (s.left,s.top,s.width,s.height)]})
    return texts,objects,len(shapes)

def single_slide(src: bytes, number: int, out: Path):
    p=Presentation(BytesIO(src)); ids=list(p.slides._sldIdLst); keep=ids[number-1]
    for item in ids:
        if item is keep: continue
        p.part.drop_rel(item.rId);p.slides._sldIdLst.remove(item)
    out.parent.mkdir(parents=True,exist_ok=True);p.save(out)

def blank_slide(example:Path, out:Path):
    out.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(example) as zin, ZipFile(out,"w",ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data=zin.read(info.filename)
            if re.fullmatch(r"ppt/slides/slide\d+\.xml",info.filename):
                root=etree.fromstring(data)
                for node in root.xpath(".//a:t",namespaces=NS):
                    if node.text and CODE not in node.text and SLOGAN not in node.text and '股票代码' not in node.text:
                        node.text=""
                data=etree.tostring(root,encoding="UTF-8",xml_declaration=True,standalone=True)
            zout.writestr(info,data)

def make_entry(slide, kind, number, entry_id, source, themes, pair=None, logo_hashes=None):
    fields,objects,shape_count=inspect(slide)
    if kind=='cover':
        for field in fields:
            if field['semantic_role']!='brand_locked':field['max_chars']=field['source_sample_chars']
    capacity={"body_slots":sum(x["semantic_role"]!="brand_locked" for x in fields),
              "item_title_slots":0,"cell_max_chars":20}
    role="cover" if kind=="cover" else ("data-chart" if objects["charts"] else "data-table" if objects["tables"] else "content")
    rel="visual-story" if kind=="cover" else "unclassified"
    entry={"id":entry_id,"version":VERSION,"collection":"new-template-covers" if kind=="cover" else "new-template-content",
           "role":role,"information_relation":rel,"classification_status":"provisional",
           "family_id":f"{role}-{number:03d}","source":source,"example":source,
           "bindings":f"layouts/{entry_id}/bindings.json","spec":f"layouts/{entry_id}/spec.md",
           "layout_rules":f"layouts/{entry_id}/layout_rules.json","motion":f"layouts/{entry_id}/motion.json",
           "preview":f"source-previews/{kind}/P{number:03d}.png","themes":themes,"status":"draft_pending_review",
           "capacity":capacity,"source_page":number,"shape_count":shape_count,
           "media_status":"missing-source-image" if kind=="blue" and number==277 or kind=="red" and number==278 else "unreviewed",
           "html_support":"not_implemented","motion_support":"source_static",
           "source_mapping":pair or {kind:number}}
    if kind!='cover' and logo_hashes:
        matches=[s for s in slide.shapes if s.shape_type==13 and sha256(s.image.blob).hexdigest() in logo_hashes
                 and s.left>10*914400 and s.top<1*914400]
        if len(matches)>1:raise ValueError(f'多张源稿Logo：{kind} P{number:03d}')
        if matches:
            entry['source_logo_present']=True
            entry['source_logo_shape_id']=matches[0].shape_id
            entry['source_logo_asset_sha256']=sha256(matches[0].image.blob).hexdigest()
            for image in objects['images']:
                if image['shape_id']==matches[0].shape_id:image['semantic_role']='brand_logo_locked'
    return entry,fields,objects

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--templates",type=Path,required=True);ap.add_argument("--logo",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True);ap.add_argument("--limit",type=int,default=0)
    a=ap.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    paths={"blue":a.templates/"01蓝色系.pptx","red":a.templates/"02红色系.pptx","cover":a.templates/"20页封面（比例16-9）.pptx"}
    raw={k:v.read_bytes() for k,v in paths.items()}; decks={k:Presentation(BytesIO(v)) for k,v in raw.items()}
    logo_frequency=Counter()
    for kind in ('blue','red'):
        for slide in decks[kind].slides:
            for s in slide.shapes:
                if s.shape_type==13 and s.left>10*914400 and s.top<1*914400:
                    logo_frequency[sha256(s.image.blob).hexdigest()]+=1
    logo_hashes={h for h,count in logo_frequency.items() if count>=5}
    originals=out/'sources';originals.mkdir(parents=True,exist_ok=True)
    for kind,path in paths.items():copy2(path,originals/(kind+'.pptx'))
    assert (len(decks["blue"].slides),len(decks["red"].slides),len(decks["cover"].slides))==(295,296,20)
    blue_sig=[signature(s) for s in decks["blue"].slides];red_sig=[signature(s) for s in decks["red"].slides]
    matcher=SequenceMatcher(None,blue_sig,red_sig,autojunk=False);pairs={};paired_red=set()
    for block in matcher.get_matching_blocks():
        for offset in range(block.size):pairs[block.a+offset+1]=block.b+offset+1;paired_red.add(block.b+offset+1)
    if len(pairs)!=287: print("WARNING: exact shape pair count changed",len(pairs),flush=True)
    dump(out/"source-manifest.json",{"schema_version":"1.0","sources":{k:{"filename":v.name,"sha256":digest(v),"page_count":len(decks[k].slides)} for k,v in paths.items()},"exact_top_level_pairs":len(pairs),"pair_status":"provisional; media and deep group review pending"})
    for theme,tokens in COLORS.items():
        dump(out/"themes"/f"new-template-{theme}.json",{"id":f"new-template-{theme}","status":"provisional","color_slots":tokens,
            "semantic_roles":{"primary":"accent1","secondary":"accent2","text_dark":"dk2","surface_light":"lt2"},
            "logo_color_policy":"locked; never recolor logo","object_binding_status":"pending per-object audit"})
    logo_out=out/"brand"/"logo";logo_out.mkdir(parents=True,exist_ok=True)
    for p in a.logo.iterdir():
        if p.is_file() and p.suffix.lower()==".svg":copy2(p,logo_out/p.name)
    catalog=[];source_pages=[]
    jobs=[("blue",i) for i in range(1,296)]+[("red",i) for i in range(1,297)]+[("cover",i) for i in range(1,21)]
    for idx,(kind,n) in enumerate(jobs,1):
        paired=kind=="red" and n in paired_red
        eid=f"content-blue-{n:03d}" if kind=="blue" else f"content-red-{n:03d}" if kind=="red" and not paired else f"cover-{n:02d}" if kind=="cover" else None
        source=f"sources/{kind}.pptx"
        source_pages.append({"source":kind,"page":n,"component_id":eid if eid else next(f"content-blue-{b:03d}" for b,r in pairs.items() if r==n),
                             "variant":"paired-red" if paired else kind,"source_pptx":source,
                             "extraction_status":"indexed"})
        if a.limit and idx>a.limit:continue
        if eid:
            slide=decks[kind].slides[n-1];entry,fields,objects=make_entry(slide,kind,n,eid,source,
                ["blue","red"] if kind=="blue" and n in pairs else ["blue"] if kind=="blue" else ["red"] if kind=="red" else [COVER_LABELS[n-1][0]],
                {"blue":n,"red":pairs[n]} if kind=="blue" and n in pairs else None,logo_hashes)
            component=out/"layouts"/eid;component.mkdir(parents=True,exist_ok=True)
            dump(component/"bindings.json",{"schema_version":"1.0","fields":fields,"objects":objects,"review":"field semantics provisional; template data not project facts"})
            if kind=='blue' and n in pairs:
                red_fields,red_objects,_=inspect(decks['red'].slides[pairs[n]-1])
                red_logo=[s for s in decks['red'].slides[pairs[n]-1].shapes if s.shape_type==13
                          and sha256(s.image.blob).hexdigest() in logo_hashes and s.left>10*914400 and s.top<1*914400]
                if len(red_logo)>1:raise ValueError(f'多张红版源Logo：P{pairs[n]:03d}')
                if red_logo:
                    entry['red_source_logo_shape_id']=red_logo[0].shape_id
                    for image in red_objects['images']:
                        if image['shape_id']==red_logo[0].shape_id:image['semantic_role']='brand_logo_locked'
                if len(red_fields)!=len(fields) or any(len(red_objects[k])!=len(objects[k]) for k in objects):
                    raise ValueError(f'蓝红字段结构不一致：蓝 P{n:03d} / 红 P{pairs[n]:03d}')
                for original,variant in zip(fields,red_fields):
                    variant['field']=original['field'];variant['semantic_role']=original['semantic_role'];variant['max_chars']=original['max_chars']
                dump(component/"bindings-red.json",{"schema_version":"1.0","fields":red_fields,"objects":red_objects,
                                                    "review":"paired by flattened object order; shape IDs are theme-specific; provisional"})
                entry['red_bindings']=f"layouts/{eid}/bindings-red.json"
            dump(component/"layout_rules.json",{"cardinality_mode":"fixed_until_validated","supported_counts":[],"source_count":None,"reflow_status":"not_implemented"})
            dump(component/"motion.json",{"source_animation":False,"source_transition":False,"status":"static","eligible_groups":[],"brand_static":True,"final_state_complete":True})
            (component/"spec.md").write_text(f"# {eid}\n\n来源：{kind} P{n:03d}。原生结构保留，可编辑。\n\n角色：{entry['role']}；信息关系及重复项数待人工复核。源稿文字、图表和图片不构成项目事实。\n",encoding="utf-8")
            if kind=="cover":
                color,style,impact,safe=COVER_LABELS[n-1]
                entry.update({"color_family":color,"style":style,"visual_impact":impact,"title_area_hint":safe,
                              "cover_match_status":"original_only_pending_review","stock_code_default":CODE,
                              "slogan_locked":SLOGAN if n in (3,4,14,15,16,20) else None,
                              "source_logo_present":True})
                pics=[s for s in walk(slide.shapes) if s.shape_type==13]
                if pics:
                    pic=max(pics,key=lambda s:s.width*s.height)
                    try:
                        blob=pic.image.blob;ext=pic.image.ext
                        imgpath=out/"cover-images"/f"P{n:02d}.{ext}";imgpath.parent.mkdir(parents=True,exist_ok=True);imgpath.write_bytes(blob)
                        entry["background_image"]=imgpath.relative_to(out).as_posix()
                    except Exception as e:entry["background_extraction_error"]=str(e)
            catalog.append(entry)
        if idx%25==0:print(f"extracted {idx}/{len(jobs)}",flush=True)
    # Red source variants are kept independently even when top-level shape signatures match.
    for b,r in pairs.items():
        for e in catalog:
            if e["id"]==f"content-blue-{b:03d}":e["red_source"]="sources/red.pptx";e["red_source_page"]=r;break
    curation_file=out/'curation'/'representatives.json'
    if curation_file.is_file():
        curated=json.loads(curation_file.read_text(encoding='utf-8'))['entries']
        for entry in catalog:
            update=curated.get(entry['id'])
            if not update:continue
            entry.update({k:v for k,v in update.items() if k!='source_count'})
            entry['classification_status']='visual_reviewed'
            component=out/'layouts'/entry['id']
            rules_file=component/'layout_rules.json'
            rules=json.loads(rules_file.read_text(encoding='utf-8'))
            rules['source_count']=update.get('source_count')
            rules['count_evidence']='source_preview_only; not a validated reflow range'
            dump(rules_file,rules)
            with (component/'spec.md').open('a',encoding='utf-8') as f:
                f.write(f"\n预览初审：{update['information_relation']}；结构家族 {update['family_id']}；密度 {update['density']}。数量变化尚未验证。\n")
    motion_file=out/'curation'/'motion-prototypes.json'
    if motion_file.is_file():
        profiles=json.loads(motion_file.read_text(encoding='utf-8'))['profiles']
        for entry in catalog:
            if entry['id'] not in profiles:continue
            profile=profiles[entry['id']]
            dump(out/entry['motion'],profile)
            entry['motion_support']='prototype_requires_playback_review'
    count_file=out/'curation'/'count-prototypes.json'
    if count_file.is_file():
        profiles=json.loads(count_file.read_text(encoding='utf-8'))['profiles']
        for entry in catalog:
            if entry['id'] not in profiles:continue
            rules_path=out/entry['layout_rules']
            rules=json.loads(rules_path.read_text(encoding='utf-8'))
            rules.update(profiles[entry['id']])
            dump(rules_path,rules)
            entry['cardinality_status']=rules['validation_status']
    cover_overrides=out/'curation'/'cover-overrides.json'
    if cover_overrides.is_file():
        overrides=json.loads(cover_overrides.read_text(encoding='utf-8'))['overrides']
        for entry in catalog:
            if entry['id'] not in overrides:continue
            spec=overrides[entry['id']]
            if entry['role']!='cover':raise ValueError('背景覆盖仅适用于封面')
            asset=out/spec['image']
            if not asset.is_file():raise FileNotFoundError(asset)
            entry['background_override']=spec['image']
            entry['background_image']=spec['image']
            entry['preview']=spec['image']
            entry['subject_tags']=spec['subject_tags']
            entry['style']=spec['style']
            entry['visual_impact']=spec['visual_impact']
            entry['color_family']=spec['color_family']
            entry['title_area_hint']=spec['title_area_hint']
            entry['background_source_note']=spec['source_note']
            with (out/entry['spec']).open('a',encoding='utf-8') as f:
                f.write(f"\n背景替换：{spec['image']}。主题标签：{'、'.join(spec['subject_tags'])}。{spec['source_note']}\n")
    tag_overrides=out/'curation'/'cover-tag-overrides.json'
    if tag_overrides.is_file():
        overrides=json.loads(tag_overrides.read_text(encoding='utf-8'))['overrides']
        for entry in catalog:
            if entry['id'] not in overrides:continue
            if entry['role']!='cover':raise ValueError('封面标签覆盖仅适用于封面')
            spec=overrides[entry['id']]
            entry['color_family']=spec['color_family']
            entry['themes']=[spec['color_family']]
            entry['cover_match_status']=spec['cover_match_status']
            entry['color_match_note']=spec['note']
            if spec.get('brand_contrast_variant'):entry['brand_contrast_variant']=spec['brand_contrast_variant']
            with (out/entry['spec']).open('a',encoding='utf-8') as f:
                f.write(f"\n色系标签：{spec['color_family']}。{spec['note']}\n")
    html_file=out/'curation'/'html-prototypes.json'
    if html_file.is_file():
        profiles=json.loads(html_file.read_text(encoding='utf-8'))['profiles']
        for entry in catalog:
            if entry['id'] not in profiles:continue
            entry['html_support']='prototype_requires_cross_format_review'
            entry['html_profile']=profiles[entry['id']]
    dump(out/"source-pages.json",source_pages)
    dump(out/"catalog.json",{"schema_version":"1.0","version":VERSION,"status":"draft_pending_review","layouts":catalog,
                             "pairing_method":"exact top-level shape signatures; provisional",
                             "physical_pages":611,"component_entries":len(catalog)})
    (out/"README.md").write_text("# 新模板独立知识库\n\n只来自 01蓝色系、02红色系、20页封面（比例16-9）及提供的 Logo。现有仓库主分支 `main`，当前状态 `draft_pending_review`。\n\n`source-pages.json` 保留 611 个物理页位；`catalog.json` 是首轮候选组件，蓝红配对仅按顶层形状签名，需复核媒体与嵌套对象。`sources/` 保留三份可编辑原稿；调用时从选中的来源页按需生成空版，避免重复存储整套母版。`review/视觉索引.html` 展示 20 个封面和 14 个首批人工观察的内容页。P060 的 2／3／4 步重排及动效、P01 和 P060 的 HTML 均为内部原型；未审核的字段语义、换色、HTML 和动效不得宣称已全面支持。\n",encoding="utf-8")
    subprocess.run([sys.executable,str(Path(__file__).with_name('build_review_gallery.py')),'--library',str(out)],check=True)
    subprocess.run([sys.executable,str(Path(__file__).with_name('audit_color_pairs.py')),'--library',str(out)],check=True)
    tech_source=a.templates/'03深蓝-科技风.pptx'
    if tech_source.is_file():
        from import_tech_style import integrate
        tech=integrate(out,tech_source)
        print(json.dumps({"tech_import":tech},ensure_ascii=False),flush=True)
    else:
        files={p.relative_to(out).as_posix():digest(p) for p in out.rglob("*")
               if p.is_file() and ".git" not in p.parts and p.name not in ("knowledge-manifest.json","audit-report.json")
               and "source-pages" not in p.relative_to(out).parts
               and p.name not in ("blank.pptx","blank-red.pptx")}
        dump(out/"knowledge-manifest.json",{"schema_version":"1.0","version":VERSION,"status":"draft_pending_review","file_count":len(files),"files":files})
    print(json.dumps({"physical_pages":len(source_pages)+(85 if tech_source.is_file() else 0),"indexed":sum(x["extraction_status"]=="indexed" for x in source_pages)+(85 if tech_source.is_file() else 0),"components":len(catalog)+(85 if tech_source.is_file() else 0),"pairs":len(pairs)},ensure_ascii=False),flush=True)

if __name__=="__main__":main()
