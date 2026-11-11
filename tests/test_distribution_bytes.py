import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from distribution import canonical_bytes, refresh_manifest, verify_manifest

class DistributionTests(unittest.TestCase):
    def test_text_is_stable_across_checkout_line_endings(self):
        self.assertEqual(canonical_bytes('catalog.json', b'{\r\n}\r\n'), b'{\n}\n')
        self.assertEqual(canonical_bytes('catalog.json', b'{\n}\n'), b'{\n}\n')

    def test_binary_template_is_preserved(self):
        data = b'PK\x03\x04\r\n\x00\xff'
        self.assertEqual(canonical_bytes('source.pptx', data), data)

    def test_runtime_rejects_changed_bytes_without_rewriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'catalog.json').write_bytes(b'{}\n')
            (root / 'knowledge-manifest.json').write_text(json.dumps({'version':'test'}))
            refresh_manifest(root, ['catalog.json'])
            verify_manifest(root)
            changed = b'{}\r\n'
            (root / 'catalog.json').write_bytes(changed)
            with self.assertRaisesRegex(ValueError, 'manifest_hash_mismatch'):
                verify_manifest(root)
            self.assertEqual((root / 'catalog.json').read_bytes(), changed)
