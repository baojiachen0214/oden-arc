"""Machine-readable CLI. Success certifies structure, never content truth."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import sqlite3
import tempfile

from . import __version__, FORMAT_PROFILE
from .common import SkillError, load_json
from .native import compile_plan, validate_delivery, validate_native
from .plan import check_plan
from .review import review_plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Oden ARC: evidence workflows and OdenMap files')
    parser.add_argument('--version', action='version', version=__version__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('capabilities', help='Report supported scope and explicit limitations')
    for name in ('check-plan', 'review-plan', 'preflight'):
        cmd = commands.add_parser(name)
        cmd.add_argument('plan', type=Path)
        if name == 'preflight':
            cmd.add_argument('--memory-workspace', type=Path)
    compile_cmd = commands.add_parser('compile')
    compile_cmd.add_argument('plan', type=Path)
    compile_cmd.add_argument('--out', required=True, type=Path, help='New delivery directory, NOT an existing .odenmap')
    compile_cmd.add_argument('--strict-review', action='store_true')
    compile_cmd.add_argument('--memory-workspace', type=Path)
    for name in ('validate', 'inspect', 'validate-delivery'):
        cmd = commands.add_parser(name)
        cmd.add_argument('path', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'capabilities':
            result = {'version': __version__, 'format_profile': FORMAT_PROFILE,
                      'plan_version': '1.0', 'new_document_only': True,
                      'native_features': ['editable_text', 'rich_text_marks', 'editable_latex', 'resource_nodes',
                                          'attachments', 'notes', 'external_links', 'canvas_links', 'asset_deduplication'],
                      'self_contained_delivery': True, 'network_calls': False,
                      'durable_memory_entrypoint': 'scripts/arc_memory.py',
                      'memory_features': ['hash_cache','bounded_batches','leases','idempotent_commit','restart_recovery','dependency_invalidation','portable_backup','typed_memory','multi_query_retrieval','critical_evidence_closure','acknowledged_context_deltas','live_map_evidence_gate'],
                      'limits': {'nodes': 5000, 'depth': 512, 'asset_mib': 64, 'total_material_mib': 256,
                                 'crop_output_pixels': 40000000},
                      'not_implemented': ['LLM inference', 'OCR', 'speech transcription', 'Office parsing',
                                          'Mermaid rendering', 'MCP server', 'native app automation',
                                          'existing-map merge', 'active HTML/SVG', 'iWork FileWrapper generation'],
                      'native_runtime_observed': False}
        elif args.command in ('check-plan', 'review-plan', 'preflight', 'compile'):
            plan = load_json(args.plan)
            c = check_plan(plan, args.plan.parent)
            if args.command == 'check-plan':
                result = {'ok': True, 'nodes': len(plan['nodes']), 'assets': len(c.assets),
                          'local_sources_verified': len(c.source_files), 'warnings': c.warnings}
            elif args.command == 'review-plan':
                result = review_plan(plan)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 0 if not result['errors'] and not result['delivery_blockers'] else 2
            elif args.command == 'preflight':
                with tempfile.TemporaryDirectory(prefix='oden-preflight-', dir=Path(tempfile.gettempdir()).resolve()) as tmp:
                    result = compile_plan(plan, args.plan.parent, Path(tmp) / 'candidate', strict_review=True, memory_workspace=args.memory_workspace)
                    result.pop('output', None)
                    result['preflight'] = 'compiled-and-statically-validated-in-temporary-directory'
            else:
                result = compile_plan(plan, args.plan.parent, args.out, args.strict_review, args.memory_workspace)
        elif args.command == 'validate-delivery':
            result = validate_delivery(args.path)
        else:
            result = validate_native(args.path)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (SkillError, OSError, sqlite3.Error) as exc:
        result = exc.as_dict() if isinstance(exc, SkillError) else {'ok': False, 'code': 'io', 'message': str(exc)}
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
