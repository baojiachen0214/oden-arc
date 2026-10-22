#!/usr/bin/env python3
"""Create an audited public source ZIP. Never publishes or reads Git history."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from oden_arc import __version__
from audit_public import audit_tree
from release_policy import ARCHIVE_ROOT, REQUIRED, selected_directories, selected_files

# Small named interfaces also exercised by archive round-trip tests.
files = selected_files
directories = selected_directories


def write_archive(root, selected, directory_names, manifest_file, output):
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in directory_names:
            archive.write(root/name, arcname=f'{ARCHIVE_ROOT}/{name}/')
        for file in [*selected, manifest_file]:
            archive.write(file, arcname=f'{ARCHIVE_ROOT}/{file.relative_to(root).as_posix()}')
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError('ZIP CRC check failed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    output = args.out.absolute()
    if output.resolve().is_relative_to(ROOT.resolve()):
        parser.error('Write the source ZIP outside the checkout')
    if output.exists():
        parser.error('Output exists; choose a new name')
    audit = audit_tree(ROOT)
    if not audit['ok']:
        print(json.dumps(audit, indent=2), file=sys.stderr)
        return 1
    selected = files(ROOT)
    dirs = directories(ROOT)
    records = [{'path': f.relative_to(ROOT).as_posix(), 'bytes': f.stat().st_size,
                'sha256': hashlib.sha256(f.read_bytes()).hexdigest()} for f in selected]
    manifest = {'format': 'oden-arc-source-manifest/1', 'version': __version__,
                'created_utc': datetime.now(timezone.utc).isoformat(), 'directories': dirs,
                'note': 'Inventory is not an independently signed identity.', 'files': records}
    manifest_file = ROOT/'FILE_MANIFEST.json'
    manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    output.parent.mkdir(parents=True, exist_ok=True)
    write_archive(ROOT, selected, dirs, manifest_file, output)
    print(json.dumps({'ok': True, 'files': len(selected)+1, 'directories': len(dirs),
                      'bytes': output.stat().st_size,
                      'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
