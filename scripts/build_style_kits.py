"""Package traceable source previews and concise offline style rules."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
ASSETS = SKILL / 'assets' / 'style-kits'

SAMPLES = {
    'blue': [
        ('cover', 'cover-02', 'source-previews/cover/P002.png', 'reference_only'),
        ('directory', 'content-blue-001', 'source-previews/blue/P001.png', 'verified_draft'),
        ('section', 'content-blue-002', 'source-previews/blue/P002.png', 'verified_draft'),
        ('process', 'content-blue-060', 'source-previews/blue/P060.png', 'verified_draft'),
        ('data', 'content-blue-036', 'source-previews/blue/P036.png', 'verified_draft'),
        ('comparison', 'content-blue-133', 'source-previews/blue/P133.png', 'verified_draft'),
        ('closing', 'supp-closing-01', 'source-previews/blue-supplement/P010.png', 'verified_draft'),
    ],
    'red': [
        ('cover', 'supp-cover-red-06', 'source-previews/red-supplement/P006.png', 'verified_draft'),
        ('directory', 'supp-directory-04-red-variant', 'source-previews/red-supplement/P011.png', 'verified_draft'),
        ('section', 'supp-section-red-13', 'source-previews/red-supplement/P013.png', 'verified_draft'),
        ('process', 'content-blue-060', 'source-previews/red/P060.png', 'verified_draft'),
        ('data', 'content-blue-036', 'source-previews/red/P036.png', 'verified_draft'),
        ('comparison', 'content-blue-133', 'source-previews/red/P133.png', 'verified_draft'),
        ('closing', 'supp-closing-red-19', 'source-previews/red-supplement/P019.png', 'verified_draft'),
    ],
    'deep-blue-tech': [
        ('cover', 'cover-tech-001', 'source-previews/tech/P001.png', 'verified_draft'),
        ('directory', 'directory-tech-006', 'source-previews/tech/P006.png', 'verified_draft'),
        ('section', 'section-tech-011', 'source-previews/tech/P011.png', 'verified_draft'),
        ('parallel', 'content-tech-021', 'source-previews/tech/P021.png', 'verified_draft'),
        ('process', 'content-tech-028', 'source-previews/tech/P028.png', 'verified_draft'),
        ('data', 'data-chart-tech-071', 'source-previews/tech/P071.png', 'verified_draft'),
        ('closing', 'closing-tech-082', 'source-previews/tech/P082.png', 'verified_draft'),
    ],
}

RULES = {
    'blue': {
        'name': '蓝白简约', 'background': '浅蓝白底与大面积留白；新绘正文底层使用两枚锁定主题色的低透明度柔边椭圆',
        'title': '正文页左上角 24 pt 主题蓝标题，右上角同款彩色 Logo，标题下方使用同知识库正文页的蓝色细分隔线',
        'structure': '优先平面矩形、轻边框、箭头与分栏；图表坐标和文字留足呼吸空间',
        'visual_rhythm': '正文以浅底为主，重点页可加蓝色大数字或蓝色结构图，但不连续堆叠密集图表',
        'image': '图片只选蓝色系来源资产；保留标题安全区，不从图片临时抽色',
    },
    'red': {
        'name': '红白简约', 'background': '白底、深红主强调与少量浅红信息面；新绘正文底层使用两枚锁定主题色的低透明度柔边椭圆',
        'title': '正文页左上角 24 pt 主题红标题，右上角同款彩色 Logo，标题下方使用同知识库正文页的红色细分隔线',
        'structure': '沿用蓝红简约系列的平面流程、并列、对比和图表结构，图形主色取红色主题变量',
        'visual_rhythm': '重点结论使用深红，正文保持白底留白，避免红色模块连续满屏',
        'image': '只使用红色系标签及已验证的来源图片，不把暖金或蓝色素材当作红色背景',
    },
    'deep-blue-tech': {
        'name': '深蓝科技', 'background': '新绘正文固定使用 #05193A 画布；顶部使用本地知识库提取的科技标题栏图形组，不叠加弥散椭圆',
        'title': '正文页采用 content-tech-021 原稿顶部标题栏，28 pt 白色可编辑标题居中，右上角白色 Logo；不绘制简约版横线',
        'structure': '用原稿中的发光线、几何网格、科技感层级作为参考；新绘正文使用可编辑矢量图形',
        'visual_rhythm': '深底保持连贯，以蓝青强调关键数据和路径；避免简约版白卡直接混入',
        'image': '图片与光效必须来自已登记科技风素材；不得自行生成锁外霓虹色',
    },
}


def build(library: Path):
    catalog = json.loads((library / 'catalog.json').read_text(encoding='utf-8-sig'))
    entries = {e['id']: e for e in catalog['layouts']}
    baseline = json.loads((SKILL / 'assets/brand/brand-baseline.json').read_text(encoding='utf-8-sig'))
    payload = {'schema_version': '1.0', 'version': '1.0.0-draft', 'status': 'draft_pending_review', 'styles': {}}
    for theme, samples in SAMPLES.items():
        folder = ASSETS / theme
        folder.mkdir(parents=True, exist_ok=True)
        records = []
        for role, entry_id, relative, status in samples:
            entry = entries[entry_id]
            source = library / relative
            if not source.is_file():
                raise FileNotFoundError(source)
            name = f'{role}-{entry_id}.png'
            target = folder / name
            shutil.copyfile(source, target)
            records.append({'role': role, 'layout_id': entry_id, 'preview': name,
                            'source_preview': relative, 'status': status,
                            'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                            'theme': theme})
        rules = {
            'schema_version': '1.0', 'theme': theme,
            'style_family': 'deep-blue-tech' if theme == 'deep-blue-tech' else 'legacy-blue-red',
            'brand_profile': '../../brand/brand-baseline.json',
            'palette_lock': '../../brand/brand-palette-lock.json',
            'typography': {**baseline['typography'], 'title_pt': 28 if theme == 'deep-blue-tech' else 24}, 'colors': baseline['themes'][theme],
            'visual_rules': RULES[theme],
            'layout_principles': {
                'canvas': ('16:9；科技风新绘正文使用 #05193A 画布及 offline-core.json.tech_content_header 原稿图形组，正文关系排版沿用现有规则' if theme == 'deep-blue-tech' else '16:9；正文标题、分隔线和 Logo 固定读取 offline-core.json.content_header，仅横线下方的内容按信息关系弹性排布'),
                'logo': '浅底彩色、深底白色；避开标题和图形，不改变 Logo 内部色',
                'shadows': 'none',
                'background_effect': ('科技风新绘正文不叠加弥散椭圆；顶部图形组来自技能本地已提取的知识库原稿' if theme == 'deep-blue-tech' else '蓝红新绘正文读取 offline-core.json.content_atmosphere；可编辑椭圆、主题锁色、预设透明度、220 pt 柔边，知识库来源页不叠加'),
                'editable': '正文文本与图形保持可编辑；预览图只作参考，不得整张贴为成稿',
                'counts': '依据真实信息量调整分栏和间距，不通过清空旧图形模拟减项',
                'text': '正文优先短句，字体低于 16pt 时重排或拆页',
            },
            'composition_recipes': {
                'parallel': '按真实条目数分栏；项数过多时换两行或拆页，标题和正文保持对齐',
                'process': '步骤与连接线同步增减；每步只保留阶段、动作和结果的必要信息',
                'comparison': '同维度左右对齐；不对称材料改用上下叙事，不强塞双列',
                'timeline': '日期顺序严格递增，节点与对应文字一起移动',
                'data': '图表注明单位、周期和来源；系列与摘要数值一致',
            },
            'prohibitions': ['锁外 RGB 或从图片抽取新主题色', '默认阴影', '混入其他风格背景或组件',
                             '复制预览里的示例文字或数字', 'Logo 与标题/图形重叠'],
            'sample_records': records,
        }
        (folder / 'style.json').write_text(json.dumps(rules, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        payload['styles'][theme] = {'profile': f'{theme}/style.json',
                                    'previews': [f'assets/style-kits/{theme}/{row["preview"]}' for row in records]}
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / 'manifest.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {k: len(v) for k, v in SAMPLES.items()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--library', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.library), ensure_ascii=False))
