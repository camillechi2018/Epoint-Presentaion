"""The S2 package gate rejects broken relations and tampered slide sources."""
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree as ET

from pptx import Presentation

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from assemble_native import P, assemble
from audit_native_package import inspect


class NativePackageAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sources = []
        for number in (1, 2):
            deck = Presentation()
            slide = deck.slides.add_slide(deck.slide_layouts[6])
            slide.shapes.add_textbox(0, 0, 1000000, 300000).text = str(number)
            slide._element.cSld.set('name', f'epoint:fixture:blue:source:{number}:' + 'a' * 40)
            path = self.root / f'source{number}.pptx'
            deck.save(path)
            self.sources.append(path)
        self.deck = self.root / 'joined.pptx'
        assemble(*self.sources, self.deck)

    def rewrite(self, remove=None, tamper=None):
        with ZipFile(self.deck) as archive:
            files = {name: archive.read(name) for name in archive.namelist() if not name.endswith('/')}
        if remove:
            del files[remove]
        if tamper:
            files[tamper] = files[tamper].replace(b'epoint:fixture', b'epoint:forged!')
        bad = self.root / 'bad.pptx'
        with ZipFile(bad, 'w', ZIP_DEFLATED) as archive:
            for name, data in files.items():
                archive.writestr(name, data)
        return bad

    def test_good_package_and_source_are_verified(self):
        report = inspect(self.deck, self.sources)
        self.assertEqual(report['slide_count'], 2)
        self.assertEqual(report['registered_masters'], 2)
        self.assertEqual(len(report['source_file_sha256']), 2)

    def test_missing_layout_relation_target_is_rejected(self):
        with ZipFile(self.deck) as archive:
            layout = next(name for name in archive.namelist() if name.startswith('ppt/slideLayouts/slideLayout') and name.endswith('.xml'))
        with self.assertRaisesRegex(ValueError, 'RELATION_TARGET_MISSING'):
            inspect(self.rewrite(remove=layout), self.sources)

    def test_tampered_source_stamp_is_rejected(self):
        with ZipFile(self.deck) as archive:
            slide = next(name for name in archive.namelist() if name.startswith('ppt/slides/slide') and name.endswith('.xml'))
        with self.assertRaisesRegex(ValueError, 'SOURCE_SLIDE_XML_MISMATCH'):
            inspect(self.rewrite(tamper=slide), self.sources)

    def test_repeated_layout_id_is_rejected(self):
        with ZipFile(self.deck) as archive:
            files = {name: archive.read(name) for name in archive.namelist() if not name.endswith('/')}
        first = ET.fromstring(files['ppt/slideMasters/slideMaster1.xml'])
        second = ET.fromstring(files['ppt/slideMasters/slideMaster999.xml'])
        first_id = next(first.iter('{' + P + '}sldLayoutId')).attrib['id']
        next(second.iter('{' + P + '}sldLayoutId')).attrib['id'] = first_id
        files['ppt/slideMasters/slideMaster999.xml'] = ET.tostring(second)
        bad = self.root / 'duplicate-ids.pptx'
        with ZipFile(bad, 'w', ZIP_DEFLATED) as archive:
            for name, data in files.items():
                archive.writestr(name, data)
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_MASTER_OR_LAYOUT_ID'):
            inspect(bad, self.sources)


if __name__ == '__main__':
    unittest.main()
