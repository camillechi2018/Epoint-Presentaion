"""Portable, auditable entry for knowledge-base preflight and page planning."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from library_location import SKILL, resolve_library
from plan_deck import resolve
from content_adapters import (adapt_for_layout, classify_trial_failure,
                              structural_mapping_issue, field_source_evidence)
from capacity_preflight import preflight
from fill_layout import fill
from render_offline_brand import render as render_guided_page, resolved_variant, validate_page
from fallback_rules import fallback_type
from audit_deck import audit as audit_deck

STYLES = {
    'blue': 'legacy-blue-red',
    'red': 'legacy-blue-red',
    'deep-blue-tech': 'deep-blue-tech',
}
STRUCTURAL = ('cover', 'directory', 'section', 'closing')


def error_code(exc):
    value = str(exc).casefold()
    if 'hash' in value or '哈希' in value or '清单' in value:
        return 'LIBRARY_HASH_FAILED'
    if 'authentication' in value or 'permission denied' in value or '403' in value or '认证' in value:
        return 'GIT_AUTH_FAILED'
    if 'git' in value or 'fetch' in value or '网络' in value or 'resolve host' in value:
        return 'GIT_UNAVAILABLE'
    return 'LIBRARY_UNAVAILABLE'


def safe_message(exc):
    message = str(exc)
    return re.sub(r'https://[^\s/@]+:[^\s/@]+@', 'https://[REDACTED]@', message)[:400]


def style_assets(theme):
    root = SKILL / 'assets' / 'style-kits' / theme
    manifest = SKILL / 'assets' / 'style-kits' / 'manifest.json'
    if not manifest.is_file():
        return {'ready': False, 'reason': 'STYLE_KIT_MISSING'}
    data = json.loads(manifest.read_text(encoding='utf-8'))
    profile = root / 'style.json'
    if not profile.is_file():
        return {'ready': False, 'reason': 'STYLE_PROFILE_MISSING'}
    images = [(SKILL / rel).resolve() for rel in data.get('styles', {}).get(theme, {}).get('previews', [])]
    records = json.loads(profile.read_text(encoding='utf-8'))['sample_records']
    hashes_ok = all((root / row['preview']).is_file() and
                    hashlib.sha256((root / row['preview']).read_bytes()).hexdigest() == row['sha256'] for row in records)
    return {'ready': bool(images) and all(x.is_file() for x in images) and hashes_ok,
            'version': data.get('version'), 'style_path': str(profile.resolve()),
            'preview_paths': [str(x) for x in images],
            'visual_references_loaded': False,
            'reason': None if hashes_ok else 'STYLE_PREVIEW_HASH_FAILED'}


def capability():
    windows = os.name == 'nt'
    com = importlib.util.find_spec('win32com') is not None if windows else False
    registry = bool(_powerpoint_registry()) if windows else False
    shell = shutil.which('pwsh') or shutil.which('powershell')
    return {
        'python': sys.version.split()[0], 'git': shutil.which('git'),
        'python_pptx': importlib.util.find_spec('pptx') is not None,
        'pillow': importlib.util.find_spec('PIL') is not None,
        'powerpoint_com_module': com,
        'powerpoint_registry': registry, 'powershell': shell,
        'can_plan': True,
        'can_fill_pptx': importlib.util.find_spec('pptx') is not None,
        'can_assemble_pptx': windows and registry and bool(shell),
        'can_render_in_powerpoint': windows and registry and bool(shell),
    }


def _powerpoint_registry():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, 'PowerPoint.Application'):
            return True
    except (ImportError, OSError):
        return False


def candidate_counts(root, theme, family):
    catalog = json.loads((root / 'catalog.json').read_text(encoding='utf-8-sig'))
    counts = {}
    for role in (*STRUCTURAL, 'body'):
        rows = [e for e in catalog['layouts']
                if theme in e.get('themes', [])
                and (e.get('style_family') or 'legacy-blue-red') == family
                and (e.get('role') == role if role != 'body' else e.get('role') not in STRUCTURAL)
                and not str(e.get('pptx_support', '')).startswith('blocked_')
                and e.get('media_status') != 'missing-source-image']
        counts[role] = {'verified_draft': sum(e.get('classification_status') == 'verified' and e.get('status') == 'draft_pending_review' for e in rows),
                        'approved': sum(e.get('classification_status') == 'verified' and e.get('status') == 'approved' for e in rows),
                        'unverified': sum(e.get('classification_status') != 'verified' for e in rows)}
    return counts


def preflight(request, *, library=None, offline=False):
    theme = request.get('theme', 'blue')
    if theme not in STYLES:
        raise ValueError('theme 仅支持 blue、red、deep-blue-tech')
    family = request.get('style_family', STYLES[theme])
    if family != STYLES[theme]:
        raise ValueError('theme 与 style_family 不一致')
    fmt = request.get('format', 'pptx')
    if fmt not in ('pptx', 'html'):
        raise ValueError('format 仅支持 pptx 或 html')
    complete = request.get('complete_deck', True)
    if not isinstance(complete, bool):
        raise ValueError('complete_deck 必须是布尔值')
    policy = request.get('asset_policy', 'verified_draft')
    if policy not in ('verified_draft', 'approved_only', 'provisional_manual'):
        raise ValueError('asset_policy 不受支持')
    result = {'schema_version': '1.0', 'status': 'blocked', 'error_code': None,
              'theme': theme, 'style_family': family, 'format': fmt,
              'complete_deck': complete, 'asset_policy': policy,
              'skill_version': _skill_version(), 'library_connected': False,
              'library_used': False, 'library_source': None, 'library_commit': None,
              'style_kit': style_assets(theme), 'runtime': capability(),
              'candidate_counts': None, 'warnings': []}
    root = None
    try:
        if library:
            root, source, commit, warning = resolve_library(library)
        elif offline:
            root, source, commit, warning = resolve_library(cache_only=True)
        else:
            root, source, commit, warning = resolve_library()
        result.update(library_connected=True, library_source=source, library_commit=commit,
                      library_path=str(root), candidate_counts=candidate_counts(root, theme, family))
        if warning:
            result['warnings'].append('远端更新失败，已使用最后一次校验通过的本地来源：' + safe_message(warning))
    except (RuntimeError, FileNotFoundError, ValueError, OSError) as exc:
        result['error_code'] = error_code(exc)
        result['warnings'].append(safe_message(exc))
    if not result['style_kit']['ready']:
        result['error_code'] = result['style_kit']['reason'] or 'STYLE_KIT_MISSING'
        return result
    if root:
        counts = result['candidate_counts']
        requested_roles = {'cover', 'closing'}
        if isinstance(request.get('pages'), list):
            requested_roles.update(page.get('role') for page in request['pages'] if isinstance(page, dict))
        missing = [role for role in STRUCTURAL if role in requested_roles and counts[role]['verified_draft'] + counts[role]['approved'] == 0]
        if fmt == 'html':
            result['error_code'] = 'HTML_TEMPLATE_UNVERIFIED'
        elif policy == 'approved_only' and any(counts[role]['approved'] == 0 for role in requested_roles if role in STRUCTURAL):
            result['error_code'] = 'APPROVED_TEMPLATE_MISSING'
        elif missing and complete:
            result['error_code'] = 'NO_' + theme.upper().replace('-', '_') + '_' + missing[0].upper() + '_VERIFIED'
        elif complete and not result['runtime']['can_fill_pptx']:
            result['error_code'] = 'PPTX_FILL_BACKEND_UNAVAILABLE'
        elif complete and not result['runtime']['can_assemble_pptx']:
            result['error_code'] = 'PPTX_BACKEND_UNAVAILABLE'
        else:
            result['status'] = 'ready' if complete else 'partial_draft'
            result['error_code'] = None
    if result['status'] == 'blocked' and not complete and result['style_kit']['ready']:
        result['status'] = 'partial_draft'
    result['can_make_complete_deck'] = result['status'] == 'ready'
    return result


def _skill_version():
    text = (SKILL / 'SKILL.md').read_text(encoding='utf-8-sig')
    match = re.search(r'version:\s*["\']?([^"\'\s]+)', text)
    return match.group(1) if match else 'unknown'


def execute_plan(request, plan, report, output: Path):
    """Fill each planned page, assemble it and audit mandatory source pages."""
    if not report['can_make_complete_deck'] or request.get('format', 'pptx') != 'pptx':
        raise ValueError('预检未通过完整 PPTX 出稿门槛')
    if output.exists():
        raise FileExistsError('成稿文件已存在，请另存新文件')
    pages = request.get('pages', [])
    if len(pages) != len(plan['pages']):
        raise ValueError('逐页内容与规划页数不一致')
    output = output.resolve()
    work = output.parent / (output.stem + '-work')
    work.mkdir(parents=True, exist_ok=True)
    slides = []
    audit_pages = []
    used_guided_variants = {}
    locked_section_layout_id = None
    for index, (page, choice) in enumerate(zip(pages, plan['pages']), 1):
        content = page.get('content')
        if not isinstance(content, dict):
            raise ValueError(f'第 {index} 页缺少可填充的 content 对象')
        page_out = work / f'P{index:03d}.pptx'
        if page_out.exists():
            raise FileExistsError(f'中间文件已存在：{page_out}')
        if choice['selection_mode'] == 'source_template':
            data = dict(content)
            data['theme'] = report['theme']
            data['library_commit'] = report['library_commit']
            if 'items' not in data and isinstance(page.get('items'), list):
                data['items'] = page['items']
            content_path = work / f'P{index:03d}-content.json'
            content_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            filled = None
            candidate_ids = choice.get('candidate_ids', [choice['layout_id']])
            if page.get('role') == 'section' and locked_section_layout_id:
                candidate_ids = [locked_section_layout_id]
                choice['candidate_ids'] = candidate_ids
            for candidate_id in candidate_ids:
                catalog = json.loads((Path(report['library_path']) / 'catalog.json').read_text(encoding='utf-8-sig'))
                entry = next(e for e in catalog['layouts'] if e['id'] == candidate_id)
                candidate_data, adapter = adapt_for_layout(candidate_id, data, page.get('title'), entry=entry)
                if not adapter and entry.get('matching_activation') in ('structure_ready', 'pilot_verified'):
                    issue = structural_mapping_issue(entry, data, page.get('title'))
                    if issue:
                        choice['trial_results'].append({
                            'layout_id': candidate_id, 'status': 'rejected',
                            'reason': '结构字段未完成真实内容映射',
                            'reason_code': issue['reason_code'],
                            'unmapped_semantic_paths': issue['paths'],
                            'content_adapter': None})
                        continue
                capacity_check = preflight(Path(report['library_path']), entry, data,
                                            page.get('title'), report['theme'])
                if capacity_check['hard_issues']:
                    choice['trial_results'].append({
                        'layout_id': candidate_id, 'status': 'rejected',
                        'reason': '绑定字段容量预检未通过', 'reason_code': 'TEXT_OVER_CAPACITY',
                        'capacity_preflight': capacity_check, 'content_adapter': adapter})
                    continue
                wrap_applied = capacity_check['wrap_suggestions']
                if wrap_applied and isinstance(candidate_data.get('texts'), dict):
                    candidate_data = dict(candidate_data)
                    candidate_data['texts'] = dict(candidate_data['texts'], **wrap_applied)
                candidate_content_path = content_path
                if adapter or wrap_applied:
                    candidate_content_path = work / f'P{index:03d}-{candidate_id}-content.json'
                    candidate_content_path.write_text(json.dumps(candidate_data, ensure_ascii=False, indent=2), encoding='utf-8')
                try:
                    filled = fill(Path(report['library_path']), candidate_id, candidate_content_path, page_out,
                                  allow_draft=request.get('asset_policy', 'verified_draft') != 'approved_only')
                    choice['layout_id'] = candidate_id
                    choice['trial_results'].append({'layout_id': candidate_id, 'status': 'filled',
                                                    'visual_qa': 'not_run', 'content_adapter': adapter,
                                                    'capacity_preflight': capacity_check,
                                                    'wrap_applied': wrap_applied,
                                                    'field_source_evidence': field_source_evidence(
                                                        dict(content, source_refs=page.get('source_refs', [])),
                                                        candidate_data) if adapter else {}})
                    if page.get('role') == 'section' and locked_section_layout_id is None:
                        locked_section_layout_id = candidate_id
                    break
                except (ValueError, KeyError, FileNotFoundError) as exc:
                    choice['trial_results'].append({'layout_id': candidate_id, 'status': 'rejected',
                                                    'reason': safe_message(exc),
                                                    'reason_code': classify_trial_failure(str(exc)),
                                                    'capacity_preflight': capacity_check,
                                                    'wrap_applied': wrap_applied,
                                                    'content_adapter': adapter})
                    for partial in (page_out, page_out.with_suffix('.qa.json'),
                                    page_out.with_suffix('.colors.json')):
                        partial.unlink(missing_ok=True)
            if filled is None:
                if page.get('role') in STRUCTURAL:
                    raise ValueError(f'第 {index} 页结构模板试填均失败：{choice["trial_results"]}')
                assessment = content.get('layout_assessment') if isinstance(content.get('layout_assessment'), dict) else {}
                use_free = assessment.get('skill_suitable') is False and isinstance(content.get('free_layout'), dict)
                if use_free and not str(assessment.get('reason', '')).strip():
                    raise ValueError(f'第 {index} 页自由编排缺少技能排版不适用的原因')
                choice['selection_mode'] = 'free_composition' if use_free else 'guided_composition'
                choice['selection_label'] = '自由编排' if use_free else '技能排版'
                choice['reason_code'] = 'NO_FIT_AFTER_TRIAL'
                choice['layout_id'] = None
            else:
                stamp = filled['source_stamp']
                if not stamp:
                    raise RuntimeError(f'第 {index} 页来源标记缺失')
                choice['source_stamp'] = stamp
        if choice['selection_mode'] == 'guided_composition':
            if page_out.exists():
                raise RuntimeError('试填失败后遗留单页文件，拒绝覆盖')
            guided = dict(content)
            guided.setdefault('title', page.get('title', page['purpose']))
            guided['type'] = fallback_type(guided)
            guided['_deck_page_number'] = index
            if guided['type'] == 'cards' and guided.get('variant', 'auto') == 'auto':
                count = len(guided.get('items', []))
                if count == 3:
                    guided['variant'] = 'columns'
                elif count == 6:
                    guided['variant'] = 'stat_rows' if not used_guided_variants.get(('cards', 'stat_rows')) else 'grid'
            if guided['type'] in ('cover', 'directory', 'section', 'closing'):
                raise ValueError('结构页不得由离线正文绘制器替代')
            try:
                validate_page(guided, index)
            except ValueError as exc:
                choice['trial_results'].append({'status': 'skill_layout_rejected', 'reason': safe_message(exc)})
                if isinstance(content.get('free_layout'), dict):
                    choice['selection_mode'] = 'free_composition'
                    choice['selection_label'] = '自由编排'
                    choice['reason_code'] = 'SKILL_LAYOUT_VALIDATION_FAILED'
                else:
                    raise ValueError(f'第 {index} 页技能排版不适用，且未提供 free_layout：{exc}') from exc
            if choice['selection_mode'] == 'guided_composition':
                render_guided_page({'theme': report['theme'], 'complete_deck': False,
                                    'pages': [guided]}, page_out)
                stamp = None
                choice['fallback_layout_id'] = guided['type']
                choice['variant'] = resolved_variant(guided, guided['type']) if guided['type'] in ('bullets', 'cards', 'process', 'priority_grid', 'milestone_timeline', 'metrics', 'comparison', 'data_table', 'image_case') else None
                used_guided_variants[(guided['type'], choice['variant'])] = used_guided_variants.get((guided['type'], choice['variant']), 0) + 1
                choice['trial_results'].append({'status': 'guided_drawn', 'library_used': False,
                                                'fallback_layout_id': guided['type'],
                                                'variant': choice['variant']})
        if choice['selection_mode'] == 'free_composition':
            if page.get('role') in STRUCTURAL:
                raise ValueError('结构页不得自由编排')
            free = dict(content)
            free['title'] = free.get('title') or page.get('title', page['purpose'])
            free['type'] = 'free_composition'
            free['_deck_page_number'] = index
            render_guided_page({'theme': report['theme'], 'complete_deck': False,
                                'pages': [free]}, page_out)
            stamp = None
            choice['fallback_layout_id'] = None
            choice['variant'] = None
            choice['trial_results'].append({'status': 'free_drawn', 'library_used': False,
                                            'rationale': free['free_layout']['rationale']})
        if choice['selection_mode'] == 'source_template':
            stamp = choice['source_stamp']
        slides.append({'path': str(page_out), 'role': page.get('role', 'body'),
                       'layout_id': choice.get('layout_id'), 'source_stamp': stamp})
        free_images = [element['source_path'] for element in content.get('free_layout', {}).get('elements', [])
                       if isinstance(element, dict) and element.get('kind') == 'image' and element.get('source_path')] \
            if isinstance(content.get('free_layout'), dict) else []
        audit_pages.append({'role': page.get('role', 'body'), 'layout_id': choice.get('layout_id'),
                            'selection_mode': choice['selection_mode'], 'selection_label': choice['selection_label'],
                            'source_stamp': stamp,
                            'data_source': page.get('data_source') or content.get('data_source'),
                            'image_sources': page.get('image_sources') or free_images or ([content['image_path']] if content.get('image_path') else None)})
    assembly = {'theme': report['theme'], 'library_commit': report['library_commit'],
                'library_source': report['library_source'], 'complete_deck': True,
                'require_template_source': all(x['selection_mode'] == 'source_template' for x in plan['pages']),
                'slides': slides, 'pages': audit_pages}
    manifest_path = work / 'assembly-plan.json'
    manifest_path.write_text(json.dumps(assembly, ensure_ascii=False, indent=2), encoding='utf-8')
    render_dir = work / 'rendered'
    command = [report['runtime']['powershell'], '-NoProfile', '-File',
               str(SKILL / 'scripts' / 'assemble_deck.ps1'), '-Manifest', str(manifest_path),
               '-OutputPath', str(output), '-RenderDirectory', str(render_dir),
               '-PythonExe', sys.executable]
    completed = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if completed.returncode:
        raise RuntimeError('PowerPoint 组装失败：' + (completed.stderr or completed.stdout)[-1000:])
    audit = audit_deck(manifest_path, output)
    audit_path = work / 'deck-audit.json'
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    if not audit['p0_passed']:
        raise RuntimeError('成稿来源或内容验收失败：' + str(audit['issues'][:5]))
    plan['selection_summary'] = {label: sum(row['selection_label'] == label for row in plan['pages'])
                                 for label in ('知识库模板', '技能排版', '自由编排')}
    return {'output': str(output.resolve()), 'slides': len(slides),
            'library_used': any(x['selection_mode'] == 'source_template' for x in plan['pages']),
            'source_template_pages': sum(x['selection_mode'] == 'source_template' for x in plan['pages']),
            'guided_pages': sum(x['selection_mode'] == 'guided_composition' for x in plan['pages']),
            'free_pages': sum(x['selection_mode'] == 'free_composition' for x in plan['pages']),
            'selection_summary': plan['selection_summary'],
            'manifest': str(manifest_path), 'audit': str(audit_path), 'render_directory': str(render_dir)}


def main():
    ap = argparse.ArgumentParser(description='知识库预检与逐页规划的统一入口')
    ap.add_argument('--request', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--plan-out', type=Path)
    ap.add_argument('--execute-out', type=Path, help='所有页面均有 content 时填充并组装完整 PPTX')
    ap.add_argument('--library', type=Path, help='测试或固定版本时指定已下载知识库')
    ap.add_argument('--offline', action='store_true')
    args = ap.parse_args()
    if args.out.exists() or args.plan_out and args.plan_out.exists() or args.execute_out and args.execute_out.exists():
        ap.error('输出文件已存在')
    request = json.loads(args.request.read_text(encoding='utf-8-sig'))
    report = preflight(request, library=args.library, offline=args.offline)
    if report['status'] == 'ready' and (args.plan_out or args.execute_out) and request.get('pages'):
        stage = 'planning'
        try:
            plan_request = dict(request)
            plan_request['allow_draft'] = request.get('asset_policy', 'verified_draft') != 'approved_only'
            plan_request['allow_provisional'] = request.get('asset_policy') == 'provisional_manual'
            plan = resolve(Path(report['library_path']), plan_request)
            plan['library_commit'] = report['library_commit']
            plan['library_source'] = report['library_source']
            plan['complete_deck'] = request.get('complete_deck', True)
            if args.execute_out:
                stage = 'execution'
                report['execution'] = execute_plan(request, plan, report, args.execute_out)
                report['library_used'] = report['execution']['library_used']
            report['selection_summary'] = plan['selection_summary']
            if args.plan_out:
                args.plan_out.parent.mkdir(parents=True, exist_ok=True)
                args.plan_out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
                report['plan_path'] = str(args.plan_out.resolve())
        except (ValueError, KeyError, FileNotFoundError, RuntimeError, OSError) as exc:
            report['status'] = 'blocked'
            report['can_make_complete_deck'] = False
            report['error_code'] = 'PAGE_LAYOUT_UNAVAILABLE' if stage == 'planning' else 'PPTX_EXECUTION_FAILED'
            report['warnings'].append(safe_message(exc))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': report['status'], 'error_code': report['error_code'],
                      'library_source': report['library_source'], 'report': str(args.out)}, ensure_ascii=False))
    return 0 if report['status'] in ('ready', 'partial_draft') else 2


if __name__ == '__main__':
    raise SystemExit(main())
