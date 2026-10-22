#!/usr/bin/env python3
"""Bounded public-release audit. Reports paths/categories, never secret values.

A passing result does not establish ownership or exclude unknown secrets.
Human review of the exact archive and contributed material is still required.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import struct
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
from release_policy import DIRECTORIES, REQUIRED, ROOT_FILES, ignored, selected_files

TEXT_EXTENSIONS = {'.py', '.md', '.txt', '.json', '.yaml', '.yml', '.toml', '.csv', '.srt', '.svg'}
PATTERNS = {
    'personal-or-build-path': re.compile(r'/(?:Users|home|root|workspace|mnt/data)/[A-Za-z0-9_.-]+'),
    'application-source-path': re.compile(r'\bOden[\\/](?:Models|Views|Support)[\\/]'),
    'private-application-reference': re.compile(r'(?:github\.com|raw\.githubusercontent\.com)/[^/\s]+/odenmap(?:[/\s"\']|$)', re.I),
    'internal-contract-commit': re.compile(r'(?:native[-_]contract|contract_commit)[\s"\':=]+[a-f0-9]{40}', re.I),
    'access-token': re.compile(r'\b(?:ghp_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{25,}|sk-proj-[A-Za-z0-9_-]{24,})\b'),
    'private-key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'credential-url': re.compile(r'https?://[^\s/@:]+:[^\s/@]+@[^\s/]+'),
    'download-token': re.compile(r'raw\.githubusercontent\.com/[^\s]+[?&]token='),
}


def png_metadata_errors(raw: bytes) -> list[str]:
    if not raw.startswith(b'\x89PNG\r\n\x1a\n'):
        return ['invalid-png']
    offset, issues, found_end = 8, [], False
    while offset + 12 <= len(raw):
        length = struct.unpack('>I', raw[offset:offset + 4])[0]
        kind = raw[offset + 4:offset + 8]
        if offset + 12 + length > len(raw):
            return ['invalid-png']
        if kind in {b'tEXt', b'zTXt', b'iTXt', b'eXIf'}:
            issues.append('png-metadata-needs-review')
        offset += 12 + length
        if kind == b'IEND':
            found_end = True
            break
    if not found_end or offset != len(raw):
        issues.append('invalid-png')
    return issues


def audit_tree(root: Path, require_complete: bool = True) -> dict:
    root = root.resolve()
    issues = []
    def flag(path: str, code: str) -> None:
        issues.append({'path': path, 'code': code})

    try:
        files = selected_files(root)
    except ValueError as exc:
        return {'ok': False, 'issues': [{'path': '.', 'code': 'symlink', 'message': str(exc)}]}
    selected = {p.relative_to(root).as_posix() for p in files}
    if require_complete:
        for name in sorted(REQUIRED - selected):
            flag(name, 'required-file-missing')
    for path in root.rglob('*'):
        rel = path.relative_to(root)
        if ignored(rel) or not path.is_file() or path.suffix in {'.pyc', '.pyo'}:
            continue
        if rel.as_posix() == 'FILE_MANIFEST.json':
            continue
        if rel.as_posix() not in selected:
            flag(rel.as_posix(), 'outside-public-allowlist')
    for path in files:
        rel = path.relative_to(root).as_posix()
        if any(part.endswith('.odenmap') for part in Path(rel).parts):
            flag(rel, 'generated-native-package')
        if path.name == '.incomplete':
            flag(rel, 'incomplete-output')
        if path.suffix == '.png':
            for issue in png_metadata_errors(path.read_bytes()):
                flag(rel, issue)
            continue
        if path.suffix not in TEXT_EXTENSIONS and path.name not in ROOT_FILES:
            flag(rel, 'unreviewed-file-type')
            continue
        try:
            content = path.read_text(encoding='utf8')
        except UnicodeError:
            flag(rel, 'unexpected-binary')
            continue
        for code, pattern in PATTERNS.items():
            # Security test cases must be synthetic and explicitly local to tests.
            if code == 'credential-url' and rel.startswith('tests/'):
                continue
            if pattern.search(content):
                flag(rel, code)
        if path.suffix == '.svg':
            try:
                tree = ET.fromstring(content)
                for node in tree.iter():
                    if node.tag.split('}')[-1] in {'script', 'foreignObject', 'image', 'use', 'style'}:
                        flag(rel, 'active-or-external-svg')
                    for name, value in node.attrib.items():
                        if name.lower().startswith('on') or name.split('}')[-1] == 'href' or 'url(' in value:
                            flag(rel, 'active-or-external-svg')
            except ET.ParseError:
                flag(rel, 'invalid-svg')
    return {'ok': not issues, 'files_checked': len(files), 'issues': issues,
            'scope': 'Defined patterns, allowlist, text encoding and limited image metadata checks.',
            'not_proven': ['all secrets absent', 'IP ownership', 'trademark clearance', 'native application compatibility']}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = audit_tree(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
