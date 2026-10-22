"""Compact CLI for durable context. Redirect outputs to files to avoid flooding chat."""
from __future__ import annotations
import argparse
from pathlib import Path
import sqlite3
import sys
from .common import SkillError, load_json
from .memory import Memory, compact


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description='OdenMap durable context workbench; local, no model/network calls')
    p.add_argument('--workspace', required=True, type=Path)
    sub = p.add_subparsers(dest='command', required=True)
    c = sub.add_parser('init'); c.add_argument('--goal', required=True, type=Path); c.add_argument('--storage-mib', type=int, default=512)
    c = sub.add_parser('ingest'); c.add_argument('paths', nargs='+', type=Path); c.add_argument('--key')
    c = sub.add_parser('ingest-units'); c.add_argument('--original', required=True, type=Path); c.add_argument('--units', required=True, type=Path); c.add_argument('--extractor', required=True); c.add_argument('--key')
    c = sub.add_parser('set-goal'); c.add_argument('goal', type=Path)
    c = sub.add_parser('deactivate-source'); c.add_argument('id'); c.add_argument('--reason', required=True)
    c = sub.add_parser('next'); c.add_argument('--worker', default='main'); c.add_argument('--limit', type=int, default=4); c.add_argument('--budget-bytes', type=int, default=24000); c.add_argument('--lease-seconds', type=int, default=900)
    c = sub.add_parser('commit'); c.add_argument('result', type=Path)
    c = sub.add_parser('renew'); c.add_argument('lease'); c.add_argument('--lease-seconds', type=int, default=900)
    for name in ('retry', 'exclude'):
        c = sub.add_parser(name); c.add_argument('id'); c.add_argument('--reason', required=True)
    c = sub.add_parser('status'); c.add_argument('--offset', type=int, default=0); c.add_argument('--limit', type=int, default=50)
    c = sub.add_parser('recover'); c.add_argument('--budget-bytes', type=int, default=14000)
    c = sub.add_parser('recall'); c.add_argument('--query', default=''); c.add_argument('--room', default=''); c.add_argument('--limit', type=int, default=12); c.add_argument('--budget-bytes', type=int, default=16000)
    c = sub.add_parser('read'); c.add_argument('id'); c.add_argument('--reason', required=True)
    for name in ('checkpoint', 'room-put', 'usage-add'):
        c = sub.add_parser(name); c.add_argument('record', type=Path)
    c = sub.add_parser('export-source'); c.add_argument('id'); c.add_argument('--out', required=True, type=Path)
    c = sub.add_parser('backup'); c.add_argument('--out', required=True, type=Path)
    c = sub.add_parser('enable-atlas'); c.add_argument('--out', required=True, type=Path)
    for name in ('annotate', 'link', 'context'):
        c = sub.add_parser(name); c.add_argument('record', type=Path)
    c = sub.add_parser('retire-link'); c.add_argument('id'); c.add_argument('--reason', required=True)
    c = sub.add_parser('session-new'); c.add_argument('--id')
    c = sub.add_parser('session-reset'); c.add_argument('id')
    c = sub.add_parser('ack'); c.add_argument('packet'); c.add_argument('--session', required=True); c.add_argument('--epoch', required=True, type=int)
    sub.add_parser('atlas-audit')
    sub.add_parser('stats'); sub.add_parser('integrity')
    a = p.parse_args(argv)
    try:
        if a.command == 'init':
            out = Memory.create(a.workspace, load_json(a.goal), a.storage_mib)
        else:
            with Memory(a.workspace) as m:
                if a.command == 'enable-atlas':
                    from .atlas import upgrade_copy
                    out = upgrade_copy(m, a.out)
                elif a.command in {'annotate', 'link', 'context', 'retire-link', 'session-new', 'session-reset', 'ack', 'atlas-audit'}:
                    from .atlas import Atlas
                    atlas = Atlas(m)
                    if a.command in {'annotate', 'link', 'context'}:
                        out = getattr(atlas, a.command)(load_json(a.record))
                    elif a.command == 'retire-link': out = atlas.retire_link(a.id, a.reason)
                    elif a.command == 'session-new': out = atlas.session(a.id)
                    elif a.command == 'session-reset': out = atlas.session(a.id, reset=True)
                    elif a.command == 'ack': out = atlas.acknowledge(a.packet, a.session, a.epoch)
                    else: out = atlas.audit()
                elif a.command == 'ingest':
                    if a.key and len(a.paths) != 1:
                        raise SkillError('argument', '--key is only for one logical source')
                    out = {'results': [m.ingest(path, a.key) for path in a.paths]}
                elif a.command == 'ingest-units': out = m.ingest(a.original, a.key, load_json(a.units), a.extractor)
                elif a.command == 'set-goal': out = m.set_goal(load_json(a.goal))
                elif a.command == 'deactivate-source': out = m.remove_source(a.id, a.reason)
                elif a.command == 'next': out = m.next_batch(a.worker, a.limit, a.budget_bytes, a.lease_seconds)
                elif a.command == 'commit': out = m.commit(load_json(a.result))
                elif a.command == 'renew': out = m.renew(a.lease, a.lease_seconds)
                elif a.command == 'retry': out = m.retry(a.id, a.reason)
                elif a.command == 'exclude': out = m.exclude(a.id, a.reason)
                elif a.command == 'status': out = m.status(a.offset, a.limit)
                elif a.command == 'recover': out = m.recover(a.budget_bytes)
                elif a.command == 'recall': out = m.cards(a.query, a.room, a.limit, a.budget_bytes)
                elif a.command == 'read': out = m.read_chunk(a.id, a.reason)
                elif a.command == 'checkpoint': out = m.checkpoint(load_json(a.record))
                elif a.command == 'room-put': out = m.room_put(load_json(a.record))
                elif a.command == 'usage-add': out = m.usage_add(load_json(a.record))
                elif a.command == 'export-source': out = m.export_source(a.id, a.out)
                elif a.command == 'backup': out = m.backup(a.out)
                elif a.command == 'stats': out = m.stats()
                else: out = m.integrity()
        print(compact(out))
        return 0
    except (SkillError, OSError, sqlite3.Error) as exc:
        out = exc.as_dict() if isinstance(exc, SkillError) else {'ok': False, 'code': 'io-or-database', 'message': str(exc), 'recovery': 'Keep workspace; restore a verified backup if integrity fails. Never reset silently.'}
        print(compact(out), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
