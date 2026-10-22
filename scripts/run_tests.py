#!/usr/bin/env python3
"""Run the bundled tests; optionally preserve fresh logs in a new directory."""
from datetime import datetime, timezone
from io import StringIO
import argparse
import json
from pathlib import Path
import platform
import sys
import time
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from oden_arc import __version__
from oden_arc.common import exclusive_directory, json_bytes, write_new


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path);a=p.parse_args()
    stream=StringIO(); start=time.perf_counter()
    # macOS exposes its temporary root through /var, a system symlink.
    # Canonicalize our own disposable fixtures; keep user path checks strict.
    tempfile.tempdir = str(Path(tempfile.gettempdir()).resolve())
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    report={'version':__version__,'executed_at_utc':datetime.now(timezone.utc).isoformat(),
            'python':platform.python_version(),'platform':platform.platform(),
            'tests_run':result.testsRun,'passed':result.testsRun-len(result.errors)-len(result.failures)-len(result.skipped),
            'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
            'elapsed_seconds':round(time.perf_counter()-start,4),'successful':result.wasSuccessful(),
            'skip_details':[(str(t),r) for t,r in result.skipped],
            'limitations':['Synthetic code tests, not an independent AI quality benchmark.',
                           'No macOS OdenMap runtime, render, edit or save/reopen execution.']}
    try:
        from PIL import __version__ as pv
        import fitz
        report['media_environment']={'Pillow':pv,'PyMuPDF':fitz.VersionBind}
    except ImportError:
        report['media_environment']='optional dependencies absent'
    if a.out:
        with exclusive_directory(a.out) as out:
            write_new(out/'results.json',json_bytes(report));write_new(out/'tests.log',stream.getvalue().encode())
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if not result.wasSuccessful(): print(stream.getvalue(),file=sys.stderr)
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
