#!/usr/bin/env python3
"""Verify a source release inventory without networking or extraction."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from release_policy import REQUIRED


def safe_member(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or '\\' in name or ':' in name:
        raise ValueError('Unsafe member name')
    relative = PurePosixPath(name)
    if relative.is_absolute() or '..' in relative.parts or '.' in relative.parts:
        raise ValueError('Unsafe relative path')
    current = root
    for part in relative.parts:
        current = current/part
        if current.is_symlink():
            raise ValueError('Symlink in member path')
    if not current.resolve().is_relative_to(root.resolve()):
        raise ValueError('Escaping member path')
    return current


def verify(root: Path, strict: bool = False) -> dict:
    errors = []
    try:
        manifest = json.loads((root/'FILE_MANIFEST.json').read_text('utf8'))
        records = manifest['files']
        expected = set()
        for record in records:
            name = record['path']
            try:
                path = safe_member(root, name)
                if name in expected:
                    raise ValueError('Duplicate manifest member')
                expected.add(name)
                if not path.is_file():
                    raise ValueError('Missing file')
                raw = path.read_bytes()
                if len(raw) != record['bytes'] or hashlib.sha256(raw).hexdigest() != record['sha256']:
                    raise ValueError('Changed file')
            except (ValueError, OSError) as exc:
                errors.append(f'{name}: {exc}')
        for name in manifest.get('directories', []):
            try:
                if not safe_member(root, name).is_dir():
                    raise ValueError('Missing directory')
            except (ValueError, OSError) as exc:
                errors.append(f'{name}: {exc}')
        for name in sorted(REQUIRED - expected):
            errors.append('Required member absent: '+name)
        expected.add('FILE_MANIFEST.json')
        if strict:
            for path in root.rglob('*'):
                rel = path.relative_to(root)
                if '__pycache__' in rel.parts or path.suffix in {'.pyc', '.pyo'}:
                    continue
                if path.is_symlink():
                    errors.append('Untrusted symlink: '+rel.as_posix())
                elif path.is_file() and rel.as_posix() not in expected:
                    errors.append('Unlisted file: '+rel.as_posix())
        return {'ok': not errors, 'files_checked': len(records),
                'directories_checked': len(manifest.get('directories', [])), 'errors': errors,
                'note': 'Hashes verify this inventory, not independently signed authorship.'}
    except (OSError, KeyError, TypeError, ValueError) as exc:
        return {'ok': False, 'errors': ['Invalid source manifest: '+str(exc)]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--strict', action='store_true')
    args = parser.parse_args()
    result = verify(args.root.absolute(), args.strict)
    print(json.dumps(result, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
