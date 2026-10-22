"""Bind a synthesized MapPlan to live evidence without changing OdenMap's format.

This checks identity, version, graph coverage and declared visibility. It cannot
prove that a label faithfully expresses the evidence or that an agent read it.
Call under the Memory transaction; the native compiler holds it until emission.
"""
from __future__ import annotations
from .common import arr, enum, identifier, obj, only_keys, require
from .atlas import Atlas
from .memory import Memory, stable


def verify_bindings(plan: dict, memory: Memory) -> dict:
    ext = obj(plan.get('extensions'), 'extensions')
    b = obj(ext.get('memory_bindings'), 'memory_bindings')
    only_keys(b, {'version', 'workspace_id', 'goal_rev', 'nodes'}, 'memory_bindings')
    require(b.get('version') == '1.0', 'Unknown bindings version')
    require(b.get('workspace_id') == memory.get('workspace_id'), 'Wrong memory workspace', code='workspace')
    require(type(b.get('goal_rev')) is int and b['goal_rev'] == memory.get('goal_rev'),
            'Map uses a superseded goal', code='stale')
    nodes = {n['id']: n for n in plan['nodes']}
    sources = {s['id']: s for s in plan.get('sources', [])}
    atlas = Atlas(memory)
    bindings = obj(b.get('nodes'), 'memory_bindings.nodes')
    require(0 < len(bindings) <= 5000, 'Bind at least one node; max 5000')
    represented: dict[str, list[tuple[str, str]]] = {}
    cache = {}
    partial = []
    for nid, refs in bindings.items():
        require(nid in nodes, 'Binding references missing map node', nid)
        refs = arr(refs, 'evidence refs', 100)
        require(bool(refs), 'An empty binding does not establish provenance', nid)
        for ref in refs:
            ref = obj(ref, 'evidence ref')
            only_keys(ref, {'chunk_id', 'card_hash', 'plan_source_id', 'placement'}, 'evidence ref')
            cid = identifier(ref.get('chunk_id'), 'chunk_id')
            placement = enum(ref.get('placement'), {'label', 'body', 'note', 'resource'}, 'placement')
            if placement == 'body':
                require(bool(nodes[nid].get('body')), 'Body placement needs an actual node body', nid)
            if placement == 'note':
                require(bool(nodes[nid].get('note')), 'Note placement needs an actual note', nid)
            if placement == 'resource':
                require(bool(nodes[nid].get('asset_id') or nodes[nid].get('attachment_ids')), 'Resource placement needs an asset', nid)
            if cid not in cache:
                cache[cid] = atlas._card(cid)
            card = cache[cid]
            require(card is not None and card['card_hash'] == ref.get('card_hash'),
                    'Map refers to stale/unreviewed evidence', cid, 'stale')
            sid = identifier(ref.get('plan_source_id'), 'plan_source_id')
            require(sid in sources and sources[sid].get('sha256') == card['source_sha256'],
                    'Plan source hash differs from evidence snapshot', sid, 'hash')
            require(any(r['source_id'] == sid for r in nodes[nid].get('source_refs', [])),
                    'Node lacks a source_ref matching its memory binding', nid)
            require(sources[sid].get('status') not in {'unread', 'unavailable'}, 'Bound evidence conflicts with source status', sid)
            if card['coverage'] == 'partial':
                require(sources[sid].get('status') == 'partial', 'Partially reviewed card cannot mark source fully read', sid)
                partial.append(cid)
            represented.setdefault(cid, []).append((nid, placement))
    for nid, n in nodes.items():
        if n.get('support') in {'fact', 'inference'}:
            require(nid in bindings, 'Memory-backed factual/inference node lacks an evidence binding', nid)

    def visible(cid: str) -> bool:
        for nid, placement in represented.get(cid, []):
            if placement not in {'label', 'body'}:
                continue
            seen = {nid}
            parent = nodes[nid].get('parent_id')
            hidden = False
            while parent is not None:
                require(parent in nodes and parent not in seen, 'Invalid parent chain in evidence gate')
                seen.add(parent)
                if nodes[parent].get('collapsed', False):
                    hidden = True
                    break
                parent = nodes[parent].get('parent_id')
            if not hidden:
                return True
        return False

    checked = set()
    edge_ids = set()
    for cid in represented:
        if cid in checked:
            continue
        component, edges, issue = atlas._component(cid, cache)
        require(issue is None, 'Critical evidence requires revalidation: '+str(issue), cid, 'critical_evidence')
        require(component <= set(represented), 'Map drops linked critical evidence; bind it or explicitly retire a wrong relation', cid, 'critical_evidence')
        for e in edges:
            if e['kind'] in {'contradicts', 'qualifies', 'requires'} and (visible(e['source']) or visible(e['target'])):
                require(visible(e['source']) and visible(e['target']),
                        'Visible conclusion cannot hide its critical counterpart in a note/resource/fold', e['id'], 'visibility')
            edge_ids.add(e['id'])
        checked.update(component)
    return {'ok': True, 'bindings_version': '1.0', 'bindings_hash': stable(b),
            'workspace_id': memory.get('workspace_id'), 'goal_rev': memory.get('goal_rev'),
            'evidence_snapshot': atlas._snapshot(), 'bound_nodes': len(bindings),
            'bound_cards': len(represented), 'critical_relations_checked': len(edge_ids),
            'partial_cards': sorted(set(partial)), 'semantic_truth_verified': False,
            'visibility_is_declarative': True, 'native_runtime_observed': False}
