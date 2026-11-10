"""Check distributed preview references independently of a local knowledge base."""
import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
KITS = ROOT / 'assets' / 'style-kits'


class StylePreviewManifestTest(unittest.TestCase):
    def test_all_style_previews_exist_and_match_profile(self):
        manifest = json.loads((KITS / 'manifest.json').read_text(encoding='utf-8-sig'))
        self.assertEqual(set(manifest['styles']), {'blue', 'red', 'deep-blue-tech'})
        for theme, entry in manifest['styles'].items():
            with self.subTest(theme=theme):
                profile_path = KITS / entry['profile']
                profile = json.loads(profile_path.read_text(encoding='utf-8-sig'))
                declared = [(ROOT / p).resolve() for p in entry['previews']]
                samples = profile['sample_records']
                recorded = [(profile_path.parent / row['preview']).resolve() for row in samples]
                self.assertTrue(declared)
                self.assertEqual(set(declared), set(recorded))
                for path in declared:
                    self.assertTrue(path.is_relative_to(ROOT.resolve()), str(path))
                    self.assertTrue(path.is_file(), f'Missing preview: {path}')
                for row, path in zip(samples, recorded):
                    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), row['sha256'], str(path))


if __name__ == '__main__':
    unittest.main()
