"""Offline, selectable-text HTML prototypes for a cover and a variable-count flow."""
from __future__ import annotations
import argparse,base64,html,json,re
from pathlib import Path
from library_location import get_library
from audit_brand_palette_source import source_xml_colors
from PIL import Image

def uri(path:Path,mime:str):
    return f'data:{mime};base64,'+base64.b64encode(path.read_bytes()).decode('ascii')

SHELL='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>*{{box-sizing:border-box}}html,body{{margin:0;min-height:100%;background:#000000;font-family:Arial,"Microsoft YaHei",sans-serif}}body{{min-height:100vh;display:grid;place-items:center}}#viewport{{position:relative;margin:0 auto;overflow:hidden}}#stage{{position:relative;width:1280px;height:720px;transform-origin:0 0;overflow:hidden}}#stage *{{user-select:text}}{css}</style>
<div id="viewport"><main id="stage" aria-label="{title}">{body}</main></div><script>
function fit(){{const scale=Math.min(window.innerWidth/1280,window.innerHeight/720);const v=document.querySelector('#viewport');v.style.width=(1280*scale)+'px';v.style.height=(720*scale)+'px';document.querySelector('#stage').style.transform='scale('+scale+')';}}
window.addEventListener('resize',fit);fit();{script}</script></html>'''

def esc(value):return html.escape(str(value),quote=True)


def assert_source_colors(root:Path,layout:str,data:dict,output:str):
    if layout=='cover-01':
        source='cover.pptx';preview='source-previews/cover/P001.png'
    elif layout=='cover-tech-001':
        source='tech.pptx';preview='source-previews/tech/P001.png'
    else:
        palette=data.get('theme','blue')
        source=f'{palette}.pptx';preview=None
    allowed=source_xml_colors(root/'sources'/source)
    if preview:
        with Image.open(root/preview) as image:
            allowed.update('%02X%02X%02X'%pixel for pixel in image.convert('RGB').get_flattened_data())
    colors={value[1:].upper() for value in re.findall(r'#[0-9A-Fa-f]{6}(?![0-9A-Fa-f])|#[0-9A-Fa-f]{3}(?![0-9A-Fa-f])',output)}
    colors={color if len(color)==6 else ''.join(channel*2 for channel in color) for color in colors}
    unsupported=colors-allowed
    if unsupported:raise ValueError('HTML 原型含来源模板之外的颜色：'+str(sorted(unsupported)))

def render_cover(root:Path,entry:dict,data:dict):
    if entry['id']!='cover-01':raise ValueError('HTML 封面原型目前仅支持 cover-01')
    fields=json.loads((root/entry['bindings']).read_text(encoding='utf-8'))['fields']
    caps={x['field']:x['max_chars'] for x in fields}
    values=data.get('texts',{})
    required=('text_3','text_4','text_5','text_16','text_21')
    for key in required:
        if not isinstance(values.get(key),str) or not values[key].strip():raise ValueError('缺少封面字段 '+key)
        if len(values[key])>caps[key]:raise ValueError('封面字段超过已测长度 '+key)
    bg=uri(root/entry['background_image'],'image/png')
    logo=uri(root/'brand/logo/logo-epoint-white.svg','image/svg+xml')
    css='''#stage{background:#00021b url("'''+bg+'''") center/cover no-repeat;color:#f0f5fe}.logo{position:absolute;left:40px;top:38px;width:120px;height:auto}.stock{position:absolute;right:42px;top:40px;letter-spacing:4px;font-size:12px;color:#fff}.eyebrow{position:absolute;left:130px;top:216px;font-size:46px;line-height:1;color:#cadefb;letter-spacing:3px}.english{position:absolute;left:130px;top:270px;font-size:40px;line-height:1;color:#cadefb;letter-spacing:2px}.rule{position:absolute;left:132px;top:360px;width:39px;border-top:2px solid #fff}.headline{position:absolute;left:130px;top:394px;width:540px;font-size:42px;font-weight:700;line-height:1.25;color:#dbe8fc}.subtitle{position:absolute;left:132px;top:490px;font-size:19px}.presenter{position:absolute;left:132px;top:527px;font-size:19px}.ticks{position:absolute;right:46px;top:189px;height:251px;border-right:2px dashed #7bd5fe;opacity:.75}.ticks:after{content:"";position:absolute;bottom:-5px;right:-4px;width:7px;height:7px;border:1px solid #7bd5fe;border-radius:50%}'''
    body=(f'<img class="logo" src="{logo}" alt="新点 Logo"><div class="stock">股票代码 688232</div>'
          f'<div class="eyebrow">{esc(values["text_5"])}</div><div class="english">{esc(values["text_16"])}</div>'
          f'<div class="rule"></div><div class="headline">{esc(values["text_3"])}</div>'
          f'<div class="subtitle">{esc(values["text_4"])}</div><div class="presenter">{esc(values["text_21"])}</div><div class="ticks"></div>')
    return SHELL.format(title=esc(values['text_3']),css=css,body=body,script='')

def render_tech_cover(root:Path,entry:dict,data:dict):
    if entry['id']!='cover-tech-001':raise ValueError('科技风 HTML 封面原型目前仅支持 P001')
    fields=json.loads((root/entry['bindings']).read_text(encoding='utf-8'))['fields']
    caps={item['field']:item['max_chars'] for item in fields}
    values=data.get('texts',{})
    for key in ('text_6','text_4','text_15','text_16'):
        if not isinstance(values.get(key),str) or not values[key].strip():raise ValueError('缺少封面字段 '+key)
        if len(values[key])>caps[key]:raise ValueError('封面字段超过已测长度 '+key)
    background=uri(root/'cover-assets/tech/P001-layer01.jpg','image/jpeg')
    visual=uri(root/'cover-assets/tech/P001-layer02.jpg','image/jpeg')
    logo=uri(root/'brand/logo/logo-white.svg','image/svg+xml')
    css='''#stage{background:#04142b;color:#edf8ff}.background{position:absolute;inset:0;width:1280px;height:720px}.visual{position:absolute;left:0;top:202px;width:477px;height:280px;object-fit:cover}.slash{position:absolute;background:linear-gradient(115deg,#0f96ff,#0764b6);transform:skewX(-30deg)}.slash.one{left:394px;top:129px;width:41px;height:187px}.slash.two{left:240px;top:448px;width:42px;height:107px}.slash.three{left:24px;top:364px;width:38px;height:118px}.logo{position:absolute;left:1150px;top:19px;width:94px;height:22px;object-fit:contain}.title{position:absolute;left:458px;top:268px;width:800px;margin:0;font-family:"Microsoft YaHei",Arial,sans-serif;font-size:64px;font-weight:400;line-height:1;white-space:nowrap;background:linear-gradient(#fff 65%,#8accff);color:transparent;background-clip:text}.english{position:absolute;left:467px;top:354px;width:740px;color:#a6bbce;font:21px/1.25 Arial,sans-serif;white-space:nowrap}.metadata{position:absolute;top:404px;color:#d3ecff;font:22px/1.4 "Microsoft YaHei",Arial,sans-serif;white-space:nowrap}.presenter{left:480px}.date{left:752px}.icon{display:inline-grid;place-items:center;vertical-align:middle;width:32px;height:32px;margin-right:12px;border:1px solid #0f96ff;border-radius:5px;color:#0f96ff;font-size:19px}'''
    body=(f'<img class="background" src="{background}" alt=""><img class="visual" src="{visual}" alt="AI 科技视觉图">'
          '<i class="slash one" aria-hidden="true"></i><i class="slash two" aria-hidden="true"></i><i class="slash three" aria-hidden="true"></i>'
          f'<img class="logo" src="{logo}" alt="新点 Logo"><h1 class="title">{esc(values["text_6"])}</h1>'
          f'<div class="english">{esc(values["text_4"])}</div>'
          f'<div class="metadata presenter"><span class="icon" aria-hidden="true">♙</span>{esc(values["text_15"])}</div>'
          f'<div class="metadata date"><span class="icon" aria-hidden="true">▦</span>{esc(values["text_16"])}</div>')
    return SHELL.format(title=esc(values['text_6']),css=css,body=body,script='')

def render_flow(root:Path,entry:dict,data:dict):
    if entry['id']!='content-blue-060':raise ValueError('HTML 流程原型目前仅支持 content-blue-060')
    count=data.get('item_count',4)
    if type(count) is not int or count not in (2,3,4):raise ValueError('流程 HTML 仅支持 2、3、4 步')
    palette=data.get('theme','blue')
    if palette not in ('blue','red'):raise ValueError('HTML 流程只支持来源蓝色或红色模板')
    theme=json.loads((root/'themes'/f'new-template-{palette}.json').read_text(encoding='utf-8'))['color_slots']
    values=data.get('texts',{})
    for key in ('text_29','text_30'):
        if not values.get(key):raise ValueError('缺少标题 '+key)
    accents=[theme['accent1'],theme['accent2'],theme['accent3'],theme['accent4']]
    logo_name='logo-epoint-black.svg' if palette=='red' else 'logo-epoint.svg'
    logo=uri(root/'brand/logo'/logo_name,'image/svg+xml')
    items=[]
    for idx in range(count):
        n=idx+1
        number=values.get(f'text_{9+idx}',f'{n:02d}')
        title=values.get(f'text_{21+idx}','')
        body=values.get(f'text_{25+idx}','')
        footer=values.get(f'text_{13+idx}','')
        if not title or not body or not footer:raise ValueError(f'第{n}步字段不完整')
        color='#'+accents[idx]
        items.append(f'<section class="item" style="--item-color:{color}"><div class="node">{esc(number)}</div><div class="down">◆</div><div class="card"><div class="pill">{esc(title)}</div><p>{esc(body)}</p></div><div class="footer">{esc(footer)}</div></section>')
    # Original PPTX flow keeps the source Epoint logo in the top-right corner.
    width=count*280+(count-1)*16
    left=(1280-width)//2
    base=theme['lt2'];primary=theme['accent1'];text=theme['dk2']
    css=f'''#stage{{background:#{base};color:#{text}}}.top{{position:absolute;top:40px;left:56px;font-size:28px;font-weight:700;color:#{primary}}}.toprule{{position:absolute;left:56px;right:55px;top:83px;border-top:1px solid #{primary}}}.logo{{position:absolute;right:56px;top:36px;width:130px;height:29px}}.headline{{position:absolute;top:121px;left:68px;font-size:30px;font-weight:700;color:#{primary}}}.arrow{{position:absolute;left:{left}px;top:180px;width:{width}px;height:66px;background:#{primary};clip-path:polygon(0 0,calc(100% - 52px) 0,100% 50%,calc(100% - 52px) 100%,0 100%)}}.row{{position:absolute;left:{left}px;top:205px;display:flex;gap:16px}}.item{{position:relative;width:280px;height:475px;text-align:center;transition:opacity .35s ease}}.node{{height:80px;width:80px;margin:0 auto;border:2px solid var(--item-color);border-radius:50%;background:#fff;color:var(--item-color);display:grid;place-items:center;font-size:27px;font-weight:bold}}.down{{height:52px;padding-top:4px;color:var(--item-color);font-size:26px}}.card{{width:280px;height:255px;background:#fff;border-radius:15px;padding:12px 14px;text-align:left}}.pill{{border-radius:16px;background:var(--item-color);color:#fff;text-align:center;font-size:17px;font-weight:bold;line-height:31px;height:31px}}.card p{{font-size:17px;line-height:1.45;margin:13px 4px 0;white-space:pre-wrap}}.footer{{margin-top:20px;height:54px;background:var(--item-color);color:#fff;display:grid;place-items:center;font-size:17px;font-weight:bold}}#stage.motion-ready .item:not(.shown){{opacity:0}}@media(prefers-reduced-motion:reduce){{.item{{transition:none!important}}}}'''
    body=f'<div class="top">{esc(values["text_30"])}</div><div class="toprule"></div><img class="logo" src="{logo}" alt="新点 Logo"><div class="headline">{esc(values["text_29"])}</div><div class="arrow"></div><div class="row">{"".join(items)}</div>'
    animate=bool(data.get('motion'))
    script=('''const stage=document.querySelector('#stage');const items=[...stage.querySelectorAll('.item')];if(!matchMedia('(prefers-reduced-motion:reduce)').matches){stage.classList.add('motion-ready');let at=0;const next=()=>{if(at<items.length)items[at++].classList.add('shown')};stage.addEventListener('click',next);addEventListener('keydown',e=>{if(e.key===' '||e.key==='ArrowRight'){e.preventDefault();next()}});}''') if animate else ''
    return SHELL.format(title=esc(values['text_29']),css=css,body=body,script=script)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--library',type=Path);ap.add_argument('--layout',required=True);ap.add_argument('--content',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    root=(a.library or get_library()).resolve();catalog=json.loads((root/'catalog.json').read_text(encoding='utf-8'))
    entry=next((x for x in catalog['layouts'] if x['id']==a.layout),None)
    if entry is None:raise ValueError('未知组件')
    data=json.loads(a.content.read_text(encoding='utf-8-sig'))
    if a.layout=='cover-01':output=render_cover(root,entry,data)
    elif a.layout=='cover-tech-001':output=render_tech_cover(root,entry,data)
    elif a.layout=='content-blue-060':output=render_flow(root,entry,data)
    else:raise ValueError('该组件尚无 HTML 渲染实现')
    assert_source_colors(root,a.layout,data,output)
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(output,encoding='utf-8')
    print(json.dumps({'layout':a.layout,'out':str(a.out),'status':'html_prototype_requires_browser_review'},ensure_ascii=False))
if __name__=='__main__':main()
