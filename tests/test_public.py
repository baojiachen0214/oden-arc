"""Public repository contracts: packaging, privacy boundaries and user entrypoints."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from audit_public import audit_tree, png_metadata_errors
from release_policy import REQUIRED, selected_files
from verify_bundle import safe_member
from oden_arc import __version__
from oden_arc.common import load_json
from oden_arc.native import compile_plan, validate_delivery


class PublicRepositoryTests(unittest.TestCase):
    def test_complete_public_tree_passes_audit(self):
        result = audit_tree(ROOT)
        self.assertTrue(result['ok'], result)

    def test_required_members_are_allowlisted(self):
        names = {p.relative_to(ROOT).as_posix() for p in selected_files(ROOT)}
        self.assertFalse(REQUIRED - names)

    def test_audit_reports_category_without_disclosing_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            token = 'ghp_' + 'A'*30
            (root/'README.md').write_text(token, encoding='utf8')
            result = audit_tree(root, require_complete=False)
            self.assertIn('access-token', {i['code'] for i in result['issues']})
            self.assertNotIn(token, json.dumps(result))

    def test_audit_rejects_personal_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'README.md').write_text('/'+'Users'+'/sample/doc.txt')
            result = audit_tree(root, require_complete=False)
            self.assertIn('personal-or-build-path', {i['code'] for i in result['issues']})

    def test_audit_rejects_unknown_archives_and_databases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'src').mkdir()
            (root/'src/session.sqlite').write_bytes(b'synthetic')
            (root/'backup.zip').write_bytes(b'synthetic')
            result = audit_tree(root, require_complete=False)
            self.assertFalse(result['ok'])
            codes = {i['code'] for i in result['issues']}
            self.assertIn('unreviewed-file-type', codes)
            self.assertIn('outside-public-allowlist', codes)

    def test_audit_rejects_generated_native_documents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root/'examples/generated.odenmap'
            folder.mkdir(parents=True)
            (folder/'map.json').write_text('{}')
            result = audit_tree(root, require_complete=False)
            self.assertIn('generated-native-package', {i['code'] for i in result['issues']})

    def test_audit_rejects_application_source_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'README.md').write_text('Oden'+'/Models/'+'Internal.swift')
            result = audit_tree(root, require_complete=False)
            self.assertIn('application-source-path', {i['code'] for i in result['issues']})

    def test_audit_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'README.md').symlink_to(root/'absent')
            self.assertFalse(audit_tree(root, require_complete=False)['ok'])

    def test_manifest_rejects_traversal_and_symlink_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'root';root.mkdir()
            for name in ('../outside', '/absolute', 'folder\\file', 'C:drive'):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    safe_member(root, name)
            (root/'link').symlink_to(Path(tmp), target_is_directory=True)
            with self.assertRaises(ValueError):
                safe_member(root, 'link/outside')

    def test_logo_png_is_transparent_and_metadata_clean(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Optional Pillow is absent')
        for path in (ROOT/'assets/brand').glob('*.png'):
            self.assertEqual(png_metadata_errors(path.read_bytes()), [])
            with Image.open(path) as image:
                self.assertEqual(image.mode, 'RGBA')
                self.assertEqual(image.getchannel('A').getextrema(), (0, 255))
                self.assertTrue(all(image.getpixel(c)[3] == 0 for c in
                                    ((0,0),(image.width-1,0),(0,image.height-1))))

    def test_local_document_links_exist(self):
        paths = [*ROOT.glob('*.md'), *(ROOT/'docs').rglob('*.md'),
                 *(ROOT/'references').glob('*.md'), *(ROOT/'examples').glob('README.md')]
        for path in paths:
            contents = path.read_text()
            links = re.findall(r'\]\(([^)\s]+)\)', contents)
            links += re.findall(r'(?:href|src|srcset)="([^"]+)"', contents)
            for link in links:
                if '://' in link or link.startswith(('mailto:', '#')):
                    continue
                location = link.split('#', 1)[0]
                with self.subTest(path=path.name, link=link):
                    self.assertTrue((path.parent/location).exists())

    def test_readmes_use_public_name_and_share_quickstart(self):
        for name in ('README.md', 'README.zh-CN.md', 'README.zh-TW.md'):
            text = (ROOT/name).read_text()
            self.assertIn('Oden ARC', text)
            self.assertIn('OdenMap', text)
            self.assertIn('examples/quickstart/plan.json', text)
            self.assertIn('scripts/arc.py', text)
            self.assertIn('MIT', text)
            self.assertIn('PyMuPDF', text)
            self.assertNotRegex(text.split('##',1)[0], r'v?0\.[345]\.0')

    def test_quickstart_compiles_and_remains_portable(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            inputs = ROOT/'examples/quickstart'
            result = compile_plan(load_json(inputs/'plan.json'), inputs,
                                  base/'first', strict_review=True)
            self.assertTrue(result['ok'])
            shutil.move(base/'first', base/'relocated')
            self.assertTrue(validate_delivery(base/'relocated')['ok'])

    def test_dependency_free_cli_executes_without_site_packages(self):
        run = subprocess.run([sys.executable, '-S', str(ROOT/'scripts/arc.py'),
                              'preflight', str(ROOT/'examples/quickstart/plan.json')],
                             capture_output=True, text=True, timeout=25)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertTrue(json.loads(run.stdout)['ok'])

    def test_project_metadata_is_consistent_and_optional(self):
        text = (ROOT/'pyproject.toml').read_text()
        self.assertIn('dependencies = []', text)
        images = text.split('images = ',1)[1].splitlines()[0]
        self.assertNotIn('PyMuPDF', images)
        self.assertIn('license = "MIT"', text)
        self.assertIn('version = {attr = "oden_arc.__version__"}', text)
        self.assertIn(__version__, (ROOT/'SKILL.md').read_text())
        self.assertIn('name: oden-arc', (ROOT/'SKILL.md').read_text())

    def test_git_filters_preserve_hashed_example_bytes(self):
        if not shutil.which('git'):
            self.skipTest('Git is not installed')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copy2(ROOT/'.gitattributes', root/'.gitattributes')
            files = ['examples/math/example-data/observations.csv',
                     'examples/quickstart/source.md']
            for name in files:
                p = root/name;p.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT/name, p)
            def git(*args):
                return subprocess.run(['git','-C',str(root),*args], check=True,
                                      capture_output=True, timeout=15).stdout
            git('init','-q')
            git('-c','core.autocrlf=true','add','.')
            for name in files:
                self.assertEqual(git('show', ':'+name), (ROOT/name).read_bytes())


if __name__ == '__main__':
    unittest.main()
