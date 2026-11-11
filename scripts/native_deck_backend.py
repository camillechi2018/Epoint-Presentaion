"""Experimental native assembly for a fully prefilled, source-gated deck."""
from __future__ import annotations

import json
import posixpath
import shutil
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZipFile

from lxml import etree

from assemble_native import assemble_many
from audit_component_color_independence import audit as audit_colors
from audit_fonts import audit as audit_fonts
from audit_logo import audit as audit_logo
from delivery_gate import check_finished
from normalize_fonts import normalize
from repair_svg_fallbacks import repair as repair_svg

P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


def stamp_source_pages(path: Path, slides: list[dict]) -> None:
    """Use the same final slide-name contract as the PowerPoint assembler."""
    with ZipFile(path) as src:
        presentation = etree.fromstring(src.read('ppt/presentation.xml'))
        relations = etree.fromstring(src.read('ppt/_rels/presentation.xml.rels'))
        targets = {item.get('Id'): posixpath.normpath('ppt/' + item.get('Target'))
                   for item in relations}
        slide_parts = {targets[item.get(f'{{{R}}}id')]: number
                       for number, item in enumerate(presentation.findall(f'.//{{{P}}}sldId'), 1)}
        records = [(item, src.read(item.filename)) for item in src.infolist()]
    with ZipFile(path, 'w') as dst:
        for info, data in records:
            number = slide_parts.get(info.filename)
            if number and slides[number - 1].get('source_stamp'):
                root = etree.fromstring(data)
                root.find(f'{{{P}}}cSld').set('name', slides[number - 1]['source_stamp'] + ':' + str(number))
                data = etree.tostring(root, encoding='UTF-8', xml_declaration=True, standalone=True)
            dst.writestr(info, data)


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def _basic_package_audit(path: Path) -> dict:
    with ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('DUPLICATE_PACKAGE_PART')
        required = {'[Content_Types].xml', '_rels/.rels', 'ppt/presentation.xml'}
        if not required.issubset(names):
            raise ValueError('PACKAGE_ROOT_MISSING')
        xml_count = 0
        for name in names:
            if name.startswith('/') or '\\' in name or '..' in name.split('/'):
                raise ValueError('UNSAFE_PACKAGE_PART')
            if name.endswith(('.xml', '.rels')):
                etree.fromstring(archive.read(name))
                xml_count += 1
    return {'passed': True, 'parts': len(names), 'xml_parts': xml_count}


def _render(path: Path, directory: Path) -> bool:
    office = shutil.which('libreoffice') or shutil.which('soffice')
    ppm = shutil.which('pdftoppm')
    if not office or not ppm:
        return False
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='epoint-lo-') as profile:
        command = [office, '-env:UserInstallation=' + Path(profile).as_uri(), '--headless',
                   '--convert-to', 'pdf', '--outdir', str(directory), str(path)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
        pdf = directory / (path.stem + '.pdf')
        if result.returncode or not pdf.is_file():
            raise RuntimeError('LIBREOFFICE_RENDER_FAILED: ' + (result.stderr or result.stdout)[-400:])
    result = subprocess.run([ppm, '-png', '-r', '120', str(pdf), str(directory / 'page')],
                            capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise RuntimeError('PDF_RENDER_FAILED: ' + result.stderr[-400:])
    images = sorted(directory.glob('page-*.png'), key=lambda p: int(p.stem.split('-')[-1]))
    if not images:
        raise RuntimeError('PDF_RENDER_EMPTY')
    for number, image in enumerate(images, 1):
        image.rename(directory / f'P{number:03d}.png')
    return True


def assemble_and_check(assembly: dict, manifest: Path, output: Path,
                       prefilled: dict, render_directory: Path) -> dict:
    inputs = [Path(item['path']) for item in assembly['slides']]
    if len(inputs) < 2:
        raise ValueError('AT_LEAST_TWO_SOURCE_SLIDES_REQUIRED')
    result = assemble_many(inputs, output)
    stamp_source_pages(output, assembly['slides'])
    normalize(output, output, profile=assembly['font_profile'])
    package = _basic_package_audit(output)
    _write(output.with_suffix('.package.json'), package)
    colors = audit_colors(output)
    _write(output.with_suffix('.colors.json'), colors)
    if not colors['passed']:
        raise ValueError('COMPONENT_COLOR_INDEPENDENCE_FAILED')
    media = repair_svg(output, manifest, check=True)
    _write(output.with_suffix('.media.json'), media)
    if not media['passed']:
        raise ValueError('MEDIA_AUDIT_FAILED')
    fonts = audit_fonts(output, assembly['font_profile'])
    _write(output.with_suffix('.fonts.json'), fonts)
    if not fonts['passed']:
        raise ValueError('FONT_AUDIT_FAILED')
    logos = audit_logo(output, require_every_slide=True, theme=assembly['theme'])
    _write(output.with_suffix('.logo.json'), logos)
    if not logos['passed']:
        raise ValueError('LOGO_AUDIT_FAILED')
    finished = check_finished(output, assembly, prefilled)
    rendered = _render(output, render_directory)
    return dict(result, finished=finished, rendered=rendered)
