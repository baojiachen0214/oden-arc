#!/usr/bin/env python3
"""Build the synthetic examples with the current implementation."""
import argparse
import json
from pathlib import Path
import sys
import shutil
import tempfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from oden_arc.common import exclusive_directory,json_bytes,load_json,write_new
from oden_arc.native import compile_plan


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);p.add_argument('--with-atlas',action='store_true');a=p.parse_args()
    reports=[]
    with exclusive_directory(a.out) as out:
        for source in sorted((ROOT/'examples'/name for name in ('quickstart','math','decision','action','crop'))):
            report=compile_plan(load_json(source/'plan.json'),source,out/source.name,strict_review=True)
            report['output']=source.name
            reports.append(report)
        if a.with_atlas:
            from demo_atlas import run
            with tempfile.TemporaryDirectory(prefix='oden-atlas-example-', dir=Path(tempfile.gettempdir()).resolve()) as tmp:
                demo=Path(tmp)/'demo'
                report=run(demo)
                shutil.copytree(demo/'delivery',out/'context-atlas')
                report['output']='context-atlas';reports.append(report)
        write_new(out/'build-report.json',json_bytes({'examples':reports,'native_runtime_observed':False}))
    print(json.dumps({'ok':True,'out':str(a.out),'examples':len(reports),'native_runtime_observed':False},ensure_ascii=False))


if __name__=='__main__':raise SystemExit(main())
