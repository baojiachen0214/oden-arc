"""Audit consistency and useful warnings, never automatic semantic certification."""
from __future__ import annotations

from typing import Any
from .common import SkillError, arr, enum, obj, text


def review_plan(plan: dict) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    blockers: list[str] = []
    nodes = {n['id']: n for n in plan.get('nodes', []) if isinstance(n, dict) and isinstance(n.get('id'), str)}
    sources = {s['id']: s for s in plan.get('sources', []) if isinstance(s, dict) and isinstance(s.get('id'), str)}
    assets = {a['id']: a for a in plan.get('assets', []) if isinstance(a, dict) and isinstance(a.get('id'), str)}
    audit = plan.get('audit')
    present = isinstance(audit, dict)
    if not present:
        return {'record_present': False, 'record_valid': False, 'errors': [],
                'delivery_blockers': ['No audit record'], 'warnings': ['No semantic review is recorded'],
                'semantic_truth_verified_by_checker': False, 'native_runtime_observed_by_checker': False}

    def refs(record: dict, field: str, pool: dict, where: str) -> None:
        values = arr(record.get(field, []), where + '.' + field)
        for v in values:
            text(v, where + '.' + field, limit=160)
            if v not in pool:
                errors.append(f'{where}: unknown {field} reference {v}')

    try:
        if audit.get('review_version') != '1.0':
            errors.append('audit.review_version must be 1.0')
        questions = arr(audit.get('questions', []), 'audit.questions')
        found = set()
        for i, question in enumerate(questions):
            q = obj(question, f'questions[{i}]')
            name = text(q.get('question'), 'question')
            if name in found:
                errors.append('Duplicate reviewed question: ' + name)
            found.add(name)
            status = enum(q.get('status'), {'answered', 'partial', 'unanswered', 'out-of-scope'}, 'question.status')
            refs(q, 'node_ids', nodes, 'question')
            if status == 'answered' and not q.get('node_ids'):
                errors.append('Answered question has no answer nodes: ' + name)
            if status != 'answered':
                warnings.append(f'{name}: {status}')
        for needed in plan.get('goal', {}).get('must_answer', []):
            if needed not in found:
                errors.append('User question absent from audit: ' + needed)
        covered = set()
        for i, coverage in enumerate(arr(audit.get('coverage', []), 'audit.coverage')):
            c = obj(coverage, f'coverage[{i}]')
            sid = text(c.get('source_id'), 'coverage.source_id')
            if sid not in sources:
                errors.append('Coverage references unknown source: ' + sid)
                continue
            if sid in covered:
                errors.append('Duplicate source coverage: ' + sid)
            covered.add(sid)
            text(c.get('read_scope', ''), 'read_scope', blank=True)
            text(c.get('unread_scope', ''), 'unread_scope', blank=True)
            text(c.get('method', ''), 'method', blank=True)
            if sources[sid].get('status') == 'partial' and not c.get('unread_scope'):
                errors.append('Partial source must name unread scope: ' + sid)
        for sid, source in sources.items():
            if sid not in covered and source.get('status') not in {'unavailable', 'unread'}:
                errors.append('Read source lacks coverage record: ' + sid)
        for i, decision in enumerate(arr(audit.get('decisions', []), 'decisions')):
            d = obj(decision, f'decisions[{i}]')
            enum(d.get('action'), {'retain', 'merge', 'omit', 'downshift', 'split', 'reframe'}, 'decision.action')
            text(d.get('content'), 'decision.content')
            text(d.get('reason'), 'decision.reason')
            refs(d, 'node_ids', nodes, 'decision')
            refs(d, 'source_ids', sources, 'decision')
        issue_ids = set()
        for issue in arr(audit.get('issues', []), 'issues'):
            issue = obj(issue, 'issue')
            iid = text(issue.get('id'), 'issue.id')
            if iid in issue_ids:
                errors.append('Duplicate issue ID: ' + iid)
            issue_ids.add(iid)
            scope = enum(issue.get('scope'), {'subject', 'map', 'delivery', 'deliverable'}, 'issue.scope')
            severity = enum(issue.get('severity'), {'minor', 'material', 'critical', 'blocker', 'blocking'}, 'issue.severity')
            status = enum(issue.get('status'), {'open', 'resolved', 'accepted'}, 'issue.status')
            text(issue.get('description'), 'issue.description')
            refs(issue, 'node_ids', nodes, 'issue')
            if scope in {'map', 'delivery', 'deliverable'} and severity in {'material', 'critical', 'blocker', 'blocking'} and status != 'resolved':
                blockers.append(iid + ': ' + issue['description'])
            elif status == 'open':
                warnings.append('Unresolved ' + scope + ' issue: ' + iid)
        checks = obj(audit.get('checks', {}), 'checks')
        for name in ('semantic', 'reader', 'numbers_formulas', 'resources', 'native_runtime'):
            if name not in checks:
                errors.append('Missing review dimension: ' + name)
                continue
            check = obj(checks[name], 'checks.' + name)
            status = enum(check.get('status'), {'passed', 'failed', 'partial', 'not_run', 'not_applicable'}, 'check.status')
            text(check.get('reviewer', ''), 'check.reviewer', blank=status == 'not_run')
            text(check.get('evidence', ''), 'check.evidence', blank=status == 'not_run')
            if name != 'native_runtime' and status in {'failed', 'not_run', 'partial'}:
                blockers.append(name + ': ' + status)
            if name == 'native_runtime':
                warnings.append('Native runtime status is an author declaration; checker did not run OdenMap')
        transformed = set()
        for item in arr(audit.get('transformations', []), 'transformations'):
            item = obj(item, 'transformation')
            aid = text(item.get('asset_id'), 'transformation.asset_id')
            if aid not in assets:
                errors.append('Transformation references missing asset: ' + aid)
                continue
            if aid in transformed:
                errors.append('Duplicate final transformation record: ' + aid)
            transformed.add(aid)
            r = obj(item.get('record'), 'transformation.record')
            if 'output' in r:
                output = obj(r['output'], 'transformation.output')
                if assets[aid].get('sha256') and output.get('sha256') != assets[aid]['sha256']:
                    errors.append('Transformation output hash differs from asset: ' + aid)
            if isinstance(r.get('source'), dict) and r['source'].get('id') in sources:
                src = sources[r['source']['id']]
                if src.get('sha256') and r['source'].get('sha256') != src['sha256']:
                    errors.append('Transformation input hash differs from source: ' + aid)
        for aid, asset in assets.items():
            kind = asset.get('derivation', {}).get('kind')
            if kind and kind != 'original' and aid not in transformed:
                warnings.append('Derived asset lacks a detailed transformation record: ' + aid)
        # Content lints are advisory: do not delete nodes solely on string similarity.
        labels = {}
        for nid, n in nodes.items():
            label = n.get('label', '').strip().casefold()
            if label in labels:
                warnings.append(f'Repeated label {nid}/{labels[label]}: inspect meaning before merging')
            labels[label] = nid
            if len(n.get('label', '')) > 100:
                warnings.append(nid + ': long visible label; consider a proposition plus notes')
            if n.get('support') in {'fact', 'inference'} and not n.get('source_refs'):
                warnings.append(nid + ': unsupported claim requires human/AI semantic review')
    except SkillError as exc:
        errors.append(str(exc))
    return {'record_present': present, 'record_valid': not errors,
            'errors': errors, 'delivery_blockers': blockers, 'warnings': warnings,
            'readiness': 'blocked' if errors or blockers else 'static_candidate',
            'semantic_truth_verified_by_checker': False,
            'native_runtime_observed_by_checker': False}
