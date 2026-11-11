"""Render known PPTX fixtures before judging a new host or font profile.

This creates task copies and a traceable report. Image inspection remains a
separate human check; a successful export is not visual acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from zipfile import ZipFile

from audit_fonts import audit
from font_profile import probe
from normalize_fonts import normalize


def _run(command: list[str], timeout=180) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True,
                          encoding='utf-8', errors='replace', timeout=timeout)


def _render_windows(source: Path, target: Path) -> tuple[str, str]:
    shell = shutil.which('pwsh') or shutil.which('powershell')
    if not shell:
        raise RuntimeError('RENDERER_NOT_FOUND: PowerShell')
    script = Path(__file__).with_name('export_source_previews.ps1')
    result = _run([shell, '-NoProfile', '-File', str(script),
                   '-InputPath', str(source), '-OutputDir', str(target)], 180)
    if result.returncode:
        raise RuntimeError('POWERPOINT_RENDER_FAILED: ' + result.stderr[-500:])
    version = _run([shell, '-NoProfile', '-Command',
                    '$p=New-Object -ComObject PowerPoint.Application;'
                    'try{$p.Version}finally{$p.Quit()}'], 30)
    return 'Microsoft PowerPoint', version.stdout.strip() or 'unknown'


def _render_linux(source: Path, target: Path) -> tuple[str, str]:
    soffice = shutil.which('soffice')
    pdf_to_png = shutil.which('pdftoppm')
    if not soffice or not pdf_to_png:
        raise RuntimeError('RENDERER_NOT_FOUND: soffice and pdftoppm required')
    with tempfile.TemporaryDirectory(prefix='epoint-lo-profile-') as profile:
        result = _run([soffice, '-env:UserInstallation=file://' + profile,
                       '--headless', '--convert-to', 'pdf', '--outdir', str(target),
                       str(source)], 180)
    pdf = target / (source.stem + '.pdf')
    if result.returncode or not pdf.is_file():
        raise RuntimeError('LIBREOFFICE_RENDER_FAILED: ' +
                           (result.stderr or result.stdout)[-500:])
    result = _run([pdf_to_png, '-png', '-r', '120', str(pdf),
                   str(target / 'page')], 180)
    if result.returncode:
        raise RuntimeError('PDF_RASTER_FAILED: ' + result.stderr[-500:])
    for number, image in enumerate(sorted(target.glob('page-*.png'),
                                          key=lambda p: int(p.stem.split('-')[-1])), 1):
        image.rename(target / f'P{number:03d}.png')
    version = _run([soffice, '--version'], 20)
    return 'LibreOffice Impress', version.stdout.strip() or 'unknown'


def calibrate(fixtures: list[Path], out_dir: Path, profile_name: str) -> dict:
    started = time.time()
    fonts = probe(profile_name)
    report = {'schema_version': '1.0', 'host': platform.platform(),
              'font_profile': fonts, 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ',
                                                                  time.gmtime(started)),
              'fixtures': [], 'visual_status': 'pending_manual_review'}
    out_dir.mkdir(parents=True, exist_ok=True)
    if fonts['status'] != 'available':
        report['status'] = 'blocked'
        report['error_code'] = fonts['error_code']
        return report
    system = platform.system()
    renderer = (_render_windows if system == 'Windows' else
                _render_linux if system == 'Linux' else None)
    for index, fixture in enumerate(fixtures, 1):
        item = {'source': str(fixture), 'source_sha256': None,
                'status': 'failed', 'images': []}
        report['fixtures'].append(item)
        try:
            item['source_sha256'] = hashlib.sha256(fixture.read_bytes()).hexdigest()
            target = out_dir / f'{index:02d}-{fixture.stem}'
            target.mkdir(parents=True, exist_ok=True)
            prepared = target / 'calibration.pptx'
            item['font_normalization'] = normalize(fixture, prepared, profile=profile_name)
            font_audit = audit(prepared, profile_name)
            if not font_audit['passed']:
                raise RuntimeError('FONT_AUDIT_FAILED: ' + str(font_audit['violations'][:3]))
            with ZipFile(prepared) as archive:
                item['slide_count'] = sum(name.startswith('ppt/slides/slide') and
                                          name.endswith('.xml') and
                                          name.rsplit('/', 1)[-1][5:-4].isdigit()
                                          for name in archive.namelist())
            item['prepared_sha256'] = hashlib.sha256(prepared.read_bytes()).hexdigest()
            if renderer is None:
                item['status'] = 'prepared_pending_mac_powerpoint'
                item['manual_action'] = 'Open calibration.pptx in Mac PowerPoint; export every slide as PNG and record version and visual findings.'
                continue
            app, version = renderer(prepared, target)
            item['renderer'] = app
            item['renderer_version'] = version
            item['images'] = [str(p) for p in sorted(target.glob('P*.png'))]
            if len(item['images']) != item['slide_count']:
                raise RuntimeError('RENDERED_PAGE_COUNT_MISMATCH')
            item['status'] = 'rendered_pending_visual_review'
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
            item['error'] = str(exc)[:700]
    statuses = {item['status'] for item in report['fixtures']}
    report['status'] = ('rendered_pending_visual_review' if statuses == {'rendered_pending_visual_review'}
                        else 'prepared_pending_mac_powerpoint' if statuses == {'prepared_pending_mac_powerpoint'}
                        else 'failed')
    report['duration_seconds'] = round(time.time() - started, 2)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, action='append', required=True)
    parser.add_argument('--profile', choices=('windows', 'macos', 'linux'), required=True)
    parser.add_argument('--out-dir', type=Path, required=True)
    args = parser.parse_args()
    report = calibrate(args.fixture, args.out_dir, args.profile)
    path = args.out_dir / 'calibration-report.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': report['status'], 'report': str(path)}, ensure_ascii=True))
    return 0 if report['status'] in ('rendered_pending_visual_review',
                                     'prepared_pending_mac_powerpoint') else 2


if __name__ == '__main__':
    raise SystemExit(main())
