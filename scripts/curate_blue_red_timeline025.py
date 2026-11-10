"""Bind the four-quarter, sixteen-milestone P025 page for static QA."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

HEADINGS = [[40, 97, 99, 101], [127, 129, 131, 133],
            [135, 137, 139, 141], [143, 145, 147, 149]]
BODIES = [[43, 98, 109, 110], [80, 81, 82, 83],
          [84, 85, 96, 103], [104, 105, 106, 107]]
QUARTERS = [[7, 8, 112], [115, 116, 117], [119, 120, 121], [123, 124, 125]]
MAP = {10: 'page.title'}
for quarter in range(4):
    for key, sid in zip(('label', 'focus', 'period'), QUARTERS[quarter]):
        MAP[sid] = f'quarters[{quarter}].{key}'
    for item in range(4):
        MAP[HEADINGS[quarter][item]] = f'quarters[{quarter}].milestones[{item}].title'
        MAP[BODIES[quarter][item]] = f'quarters[{quarter}].milestones[{item}].body'

FOCI = ['需求与方案', '建设与联调', '试点与优化', '交付与复盘']
ACTION = [['需求访谈', '范围确认', '数据盘点', '计划评审'],
          ['原型设计', '功能开发', '接口联调', '内部测试'],
          ['试点部署', '用户培训', '反馈收集', '问题修复'],
          ['验收准备', '成果交付', '运行观察', '经验复盘']]
SAMPLE = {'page.title': '项目进展｜年度四季度里程碑'}
for quarter in range(4):
    SAMPLE.update({f'quarters[{quarter}].label': f'Q{quarter+1}：工作重点',
                   f'quarters[{quarter}].focus': FOCI[quarter],
                   f'quarters[{quarter}].period': f'（2026.{quarter*3+1}-2026.{quarter*3+3}）'})
    for item, action in enumerate(ACTION[quarter]):
        base = f'quarters[{quarter}].milestones[{item}]'
        SAMPLE[base+'.title'] = f'{item+1:02d}.{action}'
        SAMPLE[base+'.body'] = f'完成{action}。\n形成阶段记录。'

def dump(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--library', type=Path, required=True)
    p.add_argument('--samples', type=Path, required=True)
    p.add_argument('--reviewed', action='store_true')
    a = p.parse_args()
    root = a.library.resolve(); base = root/'layouts/content-blue-025'
    a.samples.mkdir(parents=True, exist_ok=True)
    touched = {'catalog.json', 'layouts/content-blue-025/layout_rules.json',
               'layouts/content-blue-025/spec.md'}
    for name in ('bindings.json', 'bindings-red.json'):
        path = base/name; binding = json.loads(path.read_text(encoding='utf-8-sig'))
        if {f['shape_id'] for f in binding['fields']} != set(MAP):
            raise ValueError(f'{name}: source text fields changed')
        for field in binding['fields']:
            sid = field['shape_id']; semantic = MAP[sid]
            is_body = semantic.endswith('.body')
            field.update(semantic_path=semantic, semantic_role='body' if is_body else 'heading',
                         max_chars=min(field['max_chars'], 32 if is_body else 24),
                         max_lines=2 if is_body else 1)
        dump(path, binding); touched.add(path.relative_to(root).as_posix())
    catpath = root/'catalog.json'; cat = json.loads(catpath.read_text(encoding='utf-8-sig'))
    entry = next(e for e in cat['layouts'] if e['id']=='content-blue-025')
    entry.update(role='timeline', information_relation='quarter-milestone-matrix',
                 family_id='four-quarter-sixteen-milestones',
                 classification_status='verified' if a.reviewed else 'visual_reviewed',
                 pptx_support='verified_static' if a.reviewed else 'pending_render',
                 batch_status='fixed_four_by_four_verified' if a.reviewed else 'fields_mapped_pending_render',
                 semantic_review_status='verified_blue_red' if a.reviewed else 'fields_mapped_pending_render')
    dump(catpath, cat)
    rulepath = base/'layout_rules.json'; rules = json.loads(rulepath.read_text(encoding='utf-8-sig'))
    rules.update(cardinality_mode='fixed', source_count=4, supported_counts=[4],
                 verified_counts=[4] if a.reviewed else [],
                 matrix_columns=4, matrix_items_per_row=4,
                 validation_status='verified_fixed_count' if a.reviewed else 'pending_render',
                 count_evidence='native_4x4_quarter_matrix; item removal would require row and milestone reflow')
    rules['render_overrides'] = {
        'blue': {'text_color_by_shape_id': {'107': '202020'}},
        'red': {'text_color_by_shape_id': {'107': '202020'}},
    }
    dump(rulepath, rules)
    (base/'spec.md').write_text(
        '# 四季度里程碑矩阵\n\n来源：蓝红 P025。固定四季度，每季度四个里程碑，共 16 项。'
        '季度标签、阶段重点、周期及每项标题和正文均为独立可编辑文本。'
        + ('蓝红短文案实填及 PowerPoint 渲染通过。' if a.reviewed else '语义字段已登记，蓝红实填与渲染待验收。')
        + '季度行与横向四列共用节点和连接线；变更季度或里程碑数量须整体重排，当前不开放。'
        'Logo 原位保留；动效、HTML 和其他色系未验收。\n', encoding='utf-8')
    for theme in ('blue', 'red'):
        dump(a.samples/f'content-blue-025-{theme}.json',
             {'theme': theme, 'item_count': 4, 'texts': SAMPLE})
    import hashlib
    mp = root/'knowledge-manifest.json'; manifest = json.loads(mp.read_text(encoding='utf-8-sig'))
    for rel in touched:
        manifest['files'][rel] = hashlib.sha256((root/rel).read_bytes()).hexdigest()
    dump(mp, manifest)

if __name__ == '__main__':
    main()
