"""MapPlan -> OdenMap directory package; deliberately new-document-only.

This is an interoperability adapter, not the OdenMap application engine.
It emits the documented output profile, does not import application source,
and only creates new documents. Approximate export geometry is independent
of the application renderer and layout engine.
"""
from __future__ import annotations

from collections import defaultdict, deque
from copy import deepcopy
from pathlib import Path
import re
import uuid
from typing import Any

from . import __version__, FORMAT_PROFILE
from .common import (MAX_DEPTH, MAX_NODES, MAX_TOTAL, SkillError, arr, boolean,
                     digest, enum, exclusive_directory, identifier, json_bytes,
                     load_json, number, obj, read_bytes, reject_symlinks, require,
                     safe_link, safe_relative, text, write_new)
from .plan import BLOCKS, KINDS, CheckedPlan, check_plan
from .export_layout import estimated_geometry, place_nodes


def stable_id(document_id: str, kind: str, key: str) -> str:
    namespace = uuid.uuid5(uuid.NAMESPACE_URL, 'oden-multimodal-map/' + document_id)
    return kind + '.' + str(uuid.uuid5(namespace, kind + ':' + key))


def inline_markdown(inline: dict) -> str:
    value = inline['value']
    if inline['kind'] == 'equation':
        fence = '$$' if inline['display'] else '$'
        return fence + value + fence
    if inline['kind'] == 'softBreak':
        return '  \n'
    marks = inline['marks']
    if marks['code']:
        run = max((len(m.group()) for m in re.finditer(r'`+', value)), default=0)
        fence = '`' * (run + 1)
        pad = ' ' if value.startswith('`') or value.endswith('`') else ''
        return fence + pad + value + pad + fence
    body = re.sub(r'([\\`*_~\[\]$#>+\-])', r'\\\1', value)
    if marks['bold']:
        body = '**' + body + '**'
    if marks['italic']:
        body = '*' + body + '*'
    if marks['strike']:
        body = '~~' + body + '~~'
    if marks.get('link'):
        body = '[' + body + '](' + marks['link'].replace(')', '\\)') + ')'
    return body


def project_content(content: dict) -> str:
    output = []
    for b in content['blocks']:
        body = ''.join(inline_markdown(i) for i in b['inlines'])
        kind = b['kind']
        if kind == 'equation':
            body = '$$\n' + ''.join(i['value'] for i in b['inlines']) + '\n$$'
        elif kind == 'heading':
            body = '#' * b['headingLevel'] + ' ' + body
        elif kind in {'list', 'task'}:
            prefix = ('- [x] ' if b['checked'] else '- [ ] ') if kind == 'task' else (
                str(b['number']) + '. ' if b.get('number') else '- ')
            body = '  ' * b['listDepth'] + prefix + body
        elif kind == 'code':
            raw = ''.join(i['value'] for i in b['inlines'])
            longest = max((len(m.group()) for m in re.finditer(r'`+', raw)), default=0)
            fence = '`' * max(3, longest + 1)
            body = fence + b['language'] + '\n' + raw + '\n' + fence
        output.append(body)
    return '\n'.join(output)


def make_content(document_id: str, nid: str, label: str, body: list[dict]) -> dict:
    blocks = []
    for i, spec in enumerate([{'kind': 'paragraph', 'text': label}, *body]):
        kind = spec['kind']
        if kind == 'equation':
            specs = [{'kind': 'equation', 'latex': spec['latex'], 'display': True}]
        else:
            specs = spec.get('inlines', [{'kind': 'text', 'text': spec.get('text', '')}])
        inlines = []
        for j, s in enumerate(specs):
            ik = s.get('kind', 'text')
            marks = {k: False for k in ('bold', 'italic', 'underline', 'strike', 'code')}
            marks['relativeSize'] = 1
            marks.update(s.get('marks', {}))
            inlines.append({'id': stable_id(document_id, 'inline', f'{nid}:{i}:{j}'),
                            'kind': ik, 'value': s.get('latex', '') if ik == 'equation' else s.get('text', ''),
                            'display': s.get('display', kind == 'equation'), 'marks': marks})
        block = {'id': stable_id(document_id, 'block', f'{nid}:{i}'), 'kind': kind,
                 'headingLevel': spec.get('heading_level', 2), 'listDepth': spec.get('list_depth', 0),
                 'checked': spec.get('checked', False), 'language': spec.get('language', ''),
                 'inlines': inlines}
        if 'number' in spec:
            block['number'] = spec['number']
        blocks.append(block)
    return {'version': 1, 'revision': 0, 'blocks': blocks}


def create_map(checked: CheckedPlan) -> tuple[dict, dict, dict[str, str]]:
    p, did = checked.plan, checked.plan['document_id']
    sources = {s['id']: s for s in p.get('sources', [])}
    asset_specs = {a['id']: a for a in p.get('assets', [])}
    node_specs = {n['id']: n for n in p['nodes']}
    resource_ids = {aid: stable_id(did, 'asset', aid) for aid in checked.assets}
    resources = {}
    for aid, a in checked.assets.items():
        rid = resource_ids[aid]
        r = {'id': rid, 'originalName': a.name, 'contentType': a.uti,
             'relativePath': 'Assets/' + rid, 'byteCount': a.size, 'kind': a.kind, 'isPackage': False}
        if a.dimensions:
            r['aspectRatio'] = a.dimensions[0] / a.dimensions[1]
        resources[aid] = r
    aliases, canonical_hashes = {}, {}
    for aid in sorted(checked.assets):
        a, rid = checked.assets[aid], resource_ids[aid]
        if a.sha256 in canonical_hashes:
            aliases[rid] = canonical_hashes[a.sha256]
        else:
            canonical_hashes[a.sha256] = rid
    manifest = {'schemaVersion': 2 if aliases else 1, 'mapFile': 'map.json',
                'assetsDirectory': 'Assets', 'previewDirectory': 'QuickLook'}
    if aliases:
        manifest['embeddedAssetAliases'] = aliases
    native_nodes = []
    for n in p['nodes']:
        nid, aid = n['id'], n.get('asset_id')
        content = make_content(did, nid, n['label'], n.get('body', []))
        width, height = estimated_geometry(n, checked.assets.get(aid))
        notes = [n.get('note', '')]
        if n['support'] in {'inference', 'uncertain'}:
            notes.append('Evidence status: ' + ('Inference or recommendation, not a source quotation' if n['support'] == 'inference' else 'Uncertain; do not treat as verified'))
        if aid:
            a = asset_specs[aid]
            if a.get('alt'):
                notes.append('Resource: ' + a['alt'])
            if a.get('derivation', {}).get('note'):
                notes.append('Transformation: ' + a['derivation']['note'])
        for ref in n.get('source_refs', []):
            s = sources[ref['source_id']]
            notes.append('Source: ' + s['title'] + ' — ' + ref['locator'] +
                         (' (' + s['uri'] + ')' if s.get('uri') else ' [original not attached / user input]') +
                         ('\nExcerpt: ' + ref['quote'] if ref.get('quote') else ''))
        attachments = []
        for a in n.get('attachment_ids', []):
            attachment = {k: v for k, v in resources[a].items() if k not in {'kind', 'aspectRatio'}}
            if resources[a].get('aspectRatio'):
                attachment['previewAspectRatio'] = resources[a]['aspectRatio']
            attachments.append(attachment)
        nn = {'id': stable_id(did, 'node', nid),
              'parentID': stable_id(did, 'node', n['parent_id']) if n['parent_id'] else None,
              'order': checked.children.get(n['parent_id'], []).index(nid) if n['parent_id'] else 0,
              'text': project_content(content), 'topicContent': content,
              'contentKind': 'resource' if aid else 'text', 'x': 0, 'y': 0,
              'width': width, 'height': height, 'level': checked.levels[nid],
              'style': 'root' if nid == checked.root else ('leaf' if aid else 'branch'),
              'shape': 'rounded', 'note': '\n\n'.join(x for x in notes if x),
              'hyperlink': n.get('hyperlink', ''), 'labels': [], 'markers': [],
              'isCollapsed': n.get('collapsed', False), 'fontSize': 20 if nid == checked.root else 16,
              'placementMode': 'automatic', 'branchSide': p.get('settings', {}).get('layout', 'right'),
              'sizeMode': 'manual' if aid else 'automatic', 'attachments': attachments}
        if aid:
            nn.update(resource=deepcopy(resources[aid]), manualWidth=width,
                      manualHeight=height, heightIsManual=True)
        native_nodes.append(nn)
    by_plan_id = dict(zip(node_specs, native_nodes))
    settings = p.get('settings', {})
    sibling_gap, level_gap = settings.get('sibling_spacing', 30), settings.get('level_spacing', 70)
    place_nodes(checked, by_plan_id, sibling_gap, level_gap)
    relationships = [{'id': stable_id(did, 'relation', n['id']), 'kind': 'hierarchy', 'label': '',
                      'sourceID': stable_id(did, 'node', n['parent_id']),
                      'targetID': stable_id(did, 'node', n['id'])}
                     for n in p['nodes'] if n['parent_id'] is not None]
    links, canvas_attachments = [], {}
    for link in p.get('cross_links', []):
        lid = stable_id(did, 'canvaslink', link['id'])
        label_id = stable_id(did, 'linklabel', link['id'])
        source, target = by_plan_id[link['from']], by_plan_id[link['to']]
        label_content = make_content(did, 'linklabel:' + link['id'], link['label'], [])
        width, height = estimated_geometry({'label': link['label']})
        native_nodes.append({'id': label_id, 'parentID': None, 'order': 0,
                             'text': project_content(label_content), 'topicContent': label_content,
                             'contentKind': 'text', 'x': (source['x'] + target['x']) / 2,
                             'y': (source['y'] + target['y']) / 2, 'width': width, 'height': height,
                             'level': 0, 'style': 'callout', 'shape': 'plain', 'note': 'Cross-branch relation label',
                             'hyperlink': '', 'labels': [], 'markers': [], 'isCollapsed': False,
                             'fontSize': 13, 'placementMode': 'floating', 'sizeMode': 'automatic',
                             'branchSide': 'right', 'attachments': []})
        links.append({'id': lid, 'sourceID': source['id'], 'targetID': target['id'],
                      'sourcePort': 'automatic', 'targetPort': 'automatic', 'adaptivePorts': True,
                      'sourceArrow': 'none', 'targetArrow': 'open', 'bend': 0.18,
                      'appearance': {'id': stable_id(did, 'appearance', link['id']),
                                     'incomingLineOpacity': 0.75, 'incomingLineStyle': 'dashed',
                                     'incomingLineWidth': 1.5}})
        canvas_attachments[label_id] = {'linkID': lid, 'location': 0.5, 'normalOffset': 0}
    result = {'schemaVersion': 15 if links else 13, 'title': p['title'], 'nodes': native_nodes,
              'relationships': relationships,
              'settings': {'layout': settings.get('layout', 'right'), 'interactionMode': 'structured',
                           'palette': 'system', 'showsGrid': False, 'showsFoldButtons': True,
                           'siblingSpacing': sibling_gap, 'levelSpacing': level_gap, 'branchSpacing': 40}}
    if links:
        result.update(canvasLinks=links, canvasAttachments=canvas_attachments)
    return result, manifest, resource_ids


def verify_topic(content: Any, ids: set[str], location: str) -> int:
    c = obj(content, location)
    require(c.get('version') == 1, 'Unsupported topicContent version', location)
    require(type(c.get('revision')) is int and c['revision'] >= 0, 'Invalid revision', location)
    equations = 0
    for b in arr(c.get('blocks'), location, 201):
        obj(b, location)
        bid = identifier(b.get('id'), location)
        require(bid not in ids, 'Duplicate block or inline ID', location)
        ids.add(bid)
        kind = enum(b.get('kind'), BLOCKS, location)
        number(b.get('headingLevel'), location, 1, 6)
        number(b.get('listDepth'), location, 0, 16)
        boolean(b.get('checked'), location)
        text(b.get('language'), location, blank=True)
        for inline in arr(b.get('inlines'), location, 1000):
            obj(inline, location)
            iid = identifier(inline.get('id'), location)
            require(iid not in ids, 'Duplicate block or inline ID', location)
            ids.add(iid)
            ik = enum(inline.get('kind'), {'text', 'equation', 'softBreak'}, location)
            text(inline.get('value'), location, blank=ik != 'equation')
            boolean(inline.get('display'), location)
            marks = obj(inline.get('marks'), location)
            for flag in ('bold', 'italic', 'underline', 'strike', 'code'):
                boolean(marks.get(flag), location)
            number(marks.get('relativeSize'), location, .5, 3)
            if marks.get('link'):
                safe_link(marks['link'], location)
            equations += int(ik == 'equation')
    return equations


def validate_native(package: Path) -> dict:
    """Validate our emitted profile, NOT arbitrary future OdenMap documents."""
    reject_symlinks(package)
    require(package.is_dir(), 'Expected a .odenmap directory package', str(package))
    require(not (package / '.incomplete').exists() and not (package.parent / '.incomplete').exists(),
            'Incomplete output marker exists', str(package), 'incomplete')
    manifest = obj(load_json(package / 'manifest.json'), 'manifest')
    require(type(manifest.get('schemaVersion')) is int and manifest['schemaVersion'] in (1, 2),
            'Unsupported package schema', 'manifest')
    require(manifest.get('mapFile') == 'map.json' and manifest.get('assetsDirectory') == 'Assets',
            'Unexpected map or asset path', 'manifest')
    aliases = obj(manifest.get('embeddedAssetAliases', {}), 'aliases')
    require(not aliases or manifest['schemaVersion'] == 2, 'Aliases require manifest v2')
    physical = {}
    asset_dir = package / 'Assets'
    reject_symlinks(asset_dir)
    require(asset_dir.is_dir(), 'Missing Assets directory')
    total = 0
    for file in asset_dir.iterdir():
        identifier(file.name, 'asset filename')
        raw = read_bytes(file)
        total += len(raw)
        require(total <= MAX_TOTAL, 'Embedded assets exceed budget', code='limit')
        physical[file.name] = {'sha256': digest(raw), 'bytes': len(raw)}
    for alias, target in aliases.items():
        identifier(alias, 'alias'); identifier(target, 'alias target')
        require(alias not in physical and target in physical and target not in aliases,
                'Aliases must be flat and target a physical payload', alias)
    available = dict(physical)
    available.update({k: physical[v] for k, v in aliases.items()})
    m = obj(load_json(package / 'map.json'), 'map')
    require(type(m.get('schemaVersion')) is int and m['schemaVersion'] in (13, 15),
            'Not this compiler profile; do not reinterpret a newer document', 'schemaVersion')
    text(m.get('title'), 'title')
    settings = obj(m.get('settings'), 'settings')
    enum(settings.get('layout'), {'right', 'left'}, 'settings.layout')
    enum(settings.get('interactionMode'), {'structured'}, 'settings.interactionMode')
    nlist = arr(m.get('nodes'), 'nodes', 2 * MAX_NODES)
    require(bool(nlist), 'Empty native map')
    nodes, content_ids = {}, set()
    resources, equations = {}, 0
    for n in nlist:
        obj(n, 'node')
        nid = identifier(n.get('id'), 'node.id')
        require(nid not in nodes, 'Duplicate node ID', nid)
        nodes[nid] = n
        for name in ('x', 'y'):
            number(n.get(name), nid + '.' + name, -10_000_000, 10_000_000)
        for name in ('width', 'height'):
            number(n.get(name), nid + '.' + name, 1, 10000)
        for name in ('order', 'level'):
            require(type(n.get(name)) is int and n[name] >= 0, 'Expected nonnegative integer', nid + '.' + name)
        enum(n.get('contentKind'), {'text', 'resource'}, nid)
        enum(n.get('style'), {'root', 'branch', 'leaf', 'callout'}, nid)
        enum(n.get('shape'), {'rounded', 'plain'}, nid)
        enum(n.get('placementMode'), {'automatic', 'floating'}, nid)
        enum(n.get('sizeMode'), {'automatic', 'manual'}, nid)
        boolean(n.get('isCollapsed', False), nid)
        number(n.get('fontSize'), nid, 1, 1000)
        text(n.get('text'), nid, blank=True)
        text(n.get('note', ''), nid, blank=True)
        if n.get('hyperlink'):
            safe_link(n['hyperlink'], nid)
        equations += verify_topic(n.get('topicContent'), content_ids, nid)
        rs = list(arr(n.get('attachments', []), nid))
        if n['contentKind'] == 'resource':
            require('resource' in n, 'Resource node lacks resource', nid)
            enum(obj(n['resource'], nid).get('kind'), KINDS, nid)
        if n.get('resource'):
            rs.append(n['resource'])
        for r in rs:
            obj(r, nid)
            rid = identifier(r.get('id'), nid)
            require(rid in available, 'Missing embedded asset', rid)
            require(r.get('relativePath') == 'Assets/' + rid, 'Unexpected asset path', rid)
            require(type(r.get('byteCount')) is int and r['byteCount'] == available[rid]['bytes'],
                    'Asset byte count mismatch', rid)
            require(not r.get('linkedPath') and not r.get('linkedBookmark'),
                    'Linked external resources are outside this emitted profile', rid)
            require(r.get('isPackage') is False, 'Embedded directory resources are unsupported', rid)
            text(r.get('originalName'), rid)
            text(r.get('contentType'), rid)
            identity = {k: r[k] for k in ('originalName', 'contentType', 'relativePath', 'byteCount', 'isPackage')}
            require(rid not in resources or resources[rid] == identity, 'Inconsistent resource descriptors', rid)
            resources[rid] = identity
    # Uploaded source documents may keep unused assets; this compiler emits none.
    require(set(resources) == set(available), 'Unreferenced payload or alias in compiler output')
    attachment_map = obj(m.get('canvasAttachments', {}), 'canvasAttachments')
    semantic = {k: n for k, n in nodes.items() if k not in attachment_map}
    roots = [k for k, n in semantic.items() if n.get('parentID') is None]
    require(len(roots) == 1, 'Native map must have exactly one semantic root')
    children = defaultdict(list)
    expected_pairs = set()
    for nid, n in semantic.items():
        pid = n.get('parentID')
        if pid is not None:
            identifier(pid, nid)
            require(pid in semantic and pid != nid, 'Bad native parent', nid)
            children[pid].append(nid)
            expected_pairs.add((pid, nid))
    visited, q = {}, deque([(roots[0], 0)])
    while q:
        nid, level = q.popleft()
        require(nid not in visited and level <= MAX_DEPTH, 'Cycle or excessive depth', nid)
        require(semantic[nid]['level'] == level, 'Incorrect node level', nid)
        visited[nid] = level
        q.extend((c, level + 1) for c in children[nid])
    require(len(visited) == len(semantic), 'Unreachable native node')
    relations, rel_ids = set(), set()
    for r in arr(m.get('relationships'), 'relationships', MAX_NODES):
        obj(r, 'relationship')
        rid = identifier(r.get('id'), 'relationship.id')
        require(rid not in rel_ids, 'Duplicate relationship ID')
        rel_ids.add(rid)
        require(r.get('kind') == 'hierarchy', 'Unexpected relationship kind')
        source, target = identifier(r.get('sourceID'), rid), identifier(r.get('targetID'), rid)
        require((source, target) not in relations, 'Duplicate hierarchy edge')
        relations.add((source, target))
    require(relations == expected_pairs, 'Hierarchy relationships disagree with parentID')
    links = {}
    for link in arr(m.get('canvasLinks', []), 'canvasLinks', MAX_NODES):
        obj(link, 'link')
        lid = identifier(link.get('id'), 'link.id')
        require(lid not in links, 'Duplicate canvas-link ID')
        links[lid] = link
        for key in ('sourceID', 'targetID'):
            endpoint = identifier(link.get(key), lid)
            require(endpoint in semantic, 'Unknown link endpoint', lid)
        require(link['sourceID'] != link['targetID'], 'Self link is unsupported', lid)
        for key in ('sourcePort', 'targetPort'):
            require(link.get(key) == 'automatic', 'Unsupported link port', lid)
        number(link.get('bend'), lid, -10, 10)
        boolean(link.get('adaptivePorts'), lid)
        require(link.get('sourceArrow') == 'none' and link.get('targetArrow') == 'open', 'Unsupported arrow', lid)
        appearance = obj(link.get('appearance'), lid)
        identifier(appearance.get('id'), lid)
        number(appearance.get('incomingLineWidth'), lid, 0, 100)
        number(appearance.get('incomingLineOpacity'), lid, 0, 1)
    require(not links or m['schemaVersion'] == 15, 'Canvas links require emitted schema 15')
    assigned = []
    for nid, a in attachment_map.items():
        obj(a, 'canvasAttachment')
        require(nid in nodes and nodes[nid].get('parentID') is None and nodes[nid]['placementMode'] == 'floating',
                'Invalid floating label attachment', nid)
        lid = identifier(a.get('linkID'), nid)
        require(lid in links, 'Label references missing link', nid)
        number(a.get('location'), nid, 0, 1)
        number(a.get('normalOffset'), nid, -10000, 10000)
        assigned.append(lid)
    require(len(assigned) == len(set(assigned)) and set(assigned) == set(links),
            'Each emitted link needs exactly one attached label')
    return {'ok': True, 'profile': 'oden-skill-0.3', 'title': m['title'],
            'schema_version': m['schemaVersion'], 'semantic_nodes': len(semantic),
            'native_nodes': len(nodes), 'editable_equations': equations, 'canvas_links': len(links),
            'logical_assets': len(available), 'physical_assets': len(physical), 'aliases': len(aliases),
            'native_runtime_observed': False,
            'limitations': ['Static compiler-profile validation only; not a macOS OdenMap execution test.',
                            'Geometry is estimated; native display, editing and save/reopen need host acceptance.']}


def compile_plan(plan: dict, base: Path, output: Path, strict_review: bool = False,
                 memory_workspace: Path | None = None) -> dict:
    """Memory-bound plans must pass a live gate. Ordinary MapPlan 1.0 stays compatible."""
    plan = obj(plan, 'plan')
    extensions = obj(plan.get('extensions', {}), 'extensions')
    bindings = extensions.get('memory_bindings')
    if bindings is None:
        require(memory_workspace is None, 'Supplied memory workspace but plan has no explicit bindings')
        return _compile_plan(plan, base, output, strict_review)
    require(memory_workspace is not None, 'Memory-bound plan needs --memory-workspace; cannot bypass stale-evidence checks', code='evidence')
    from .memory import Memory
    from .evidence_gate import verify_bindings
    with Memory(memory_workspace) as memory:
        with memory.tx():
            check_plan(plan, base)
            audit = verify_bindings(plan, memory)
            return _compile_plan(plan, base, output, strict_review, audit)


def _compile_plan(plan: dict, base: Path, output: Path, strict_review: bool = False,
                  evidence_audit: dict | None = None) -> dict:
    from .review import review_plan
    c = check_plan(plan, base)
    review = review_plan(plan)
    require(not review['errors'], 'Invalid review record: ' + '; '.join(review['errors']), 'audit')
    if strict_review:
        require(review['record_present'] and not review['delivery_blockers'],
                'Strict review requires a record with no unresolved map/delivery blockers', 'audit')
    native, manifest, asset_ids = create_map(c)
    aliases = manifest.get('embeddedAssetAliases', {})
    with exclusive_directory(output) as out:
        package = out / 'map.odenmap'
        (package / 'Assets').mkdir(parents=True)
        asset_inventory = {}
        for aid, info in c.assets.items():
            rid = asset_ids[aid]
            raw = read_bytes(info.path)
            require(digest(raw) == info.sha256, 'Material changed after preflight', aid, 'hash')
            if rid not in aliases:
                write_new(package / 'Assets' / rid, raw)
            asset_inventory[aid] = {'native_id': rid, 'physical_id': aliases.get(rid, rid),
                                    'sha256': info.sha256, 'bytes': info.size, 'original_name': info.name}
        portable = deepcopy(plan)
        for a in portable.get('assets', []):
            a['name'] = c.assets[a['id']].name
            a['path'] = 'map.odenmap/Assets/' + asset_inventory[a['id']]['physical_id']
            a['sha256'] = asset_inventory[a['id']]['sha256']
        source_inventory = {}
        copied = set()
        for s in portable.get('sources', []):
            sid = s['id']
            if sid not in c.source_files:
                continue
            info = c.source_files[sid]
            # ASCII hashed names are portable across filesystems; original title remains in metadata.
            ext = info.path.suffix.lower()
            ext = ext if re.fullmatch(r'\.[a-z0-9]{1,12}', ext) else '.bin'
            relative = 'Sources/' + info.sha256 + ext
            if relative not in copied:
                (out / 'Sources').mkdir(exist_ok=True)
                raw = read_bytes(info.path)
                require(digest(raw) == info.sha256, 'Source changed after preflight', sid, 'hash')
                write_new(out / relative, raw)
                copied.add(relative)
            s['uri'], s['sha256'] = relative, info.sha256
            source_inventory[sid] = {'path': relative, 'sha256': info.sha256, 'bytes': info.size,
                                      'original_name': info.name}
        # Preserve original transformation receipts byte-for-byte in their records.
        # Acquisition paths are historical context, not portable file references.
        # Store the current, hash-verified location alongside the original receipt.
        for transformation in portable.get('audit', {}).get('transformations', []):
            sid = transformation.get('record', {}).get('source', {}).get('id')
            if sid in source_inventory:
                info = source_inventory[sid]
                transformation['source_resolution'] = {
                    'source_id': sid, 'uri': info['path'], 'sha256': info['sha256'],
                    'scope': 'delivery-relative', 'acquisition_path_is_historical': True}
        # The source notes in the native map must refer to the portable source locations too.
        portable_c = check_plan(portable, out)
        native, _, _ = create_map(portable_c)
        write_new(package / 'map.json', json_bytes(native))
        write_new(package / 'manifest.json', json_bytes(manifest))
        write_new(out / 'plan.json', json_bytes(portable))
        write_new(out / 'review.json', json_bytes(review))
        if evidence_audit is not None:
            write_new(out / 'evidence-audit.json', json_bytes(evidence_audit))
        write_new(out / 'README.txt', ('用 OdenMap 打开 map.odenmap 目录包。\n'
                  '保留本交付目录，Sources/ 与 plan.json 提供可追溯原件。\n'
                  '该包只经过静态格式校验，仍需在 macOS 中验收公式、预览、保存与重开。\n').encode())
        delivery = {'delivery_version': '1.0', 'compiler': __version__, 'format_profile': FORMAT_PROFILE,
                    'package': 'map.odenmap', 'assets': asset_inventory, 'sources': source_inventory,
                    'warnings': c.warnings, 'native_runtime_observed': False,
                    'semantic_truth_verified_by_compiler': False, 'files': {}}
        for f in sorted(out.rglob('*')):
            if f.is_file() and f.name != '.incomplete':
                delivery['files'][f.relative_to(out).as_posix()] = digest(read_bytes(f))
        write_new(out / 'delivery.json', json_bytes(delivery))
        # Validator refuses incomplete delivery markers. Remove only our marker after all writes.
        (out / '.incomplete').unlink()
        result = validate_delivery(out)
        # Context manager owns the marker until it exits; recreate for its successful cleanup.
        write_new(out / '.incomplete', b'Finalizing verified output\n')
    result['output'] = str(output)
    return result


def validate_delivery(directory: Path) -> dict:
    require(not (directory / '.incomplete').exists(), 'Incomplete delivery', code='incomplete')
    d = obj(load_json(directory / 'delivery.json'), 'delivery')
    require(d.get('delivery_version') == '1.0' and d.get('package') == 'map.odenmap', 'Unknown delivery format')
    files = obj(d.get('files'), 'delivery.files')
    require('plan.json' in files and 'map.odenmap/map.json' in files and 'map.odenmap/manifest.json' in files,
            'Delivery inventory missing essential entries')
    actual_files = set()
    for f in directory.rglob('*'):
        reject_symlinks(f)
        if f.is_file() and f.name != 'delivery.json':
            actual_files.add(f.relative_to(directory).as_posix())
    require(actual_files == set(files), 'Delivery file inventory differs; files were added or removed')
    for relative, sha in files.items():
        require(digest(read_bytes(safe_relative(directory, relative))) == sha, 'Delivery file hash mismatch', relative, 'hash')
    plan = load_json(directory / 'plan.json')
    extensions = plan.get('extensions', {})
    require(isinstance(extensions, dict), 'Plan extensions must be an object')
    bindings = extensions.get('memory_bindings')
    if bindings is not None:
        from .memory import stable
        require('evidence-audit.json' in files, 'Memory-bound delivery lacks evidence audit')
        audit = load_json(directory / 'evidence-audit.json')
        require(audit.get('ok') is True and audit.get('bindings_hash') == stable(bindings),
                'Bindings differ from audited snapshot', code='hash')
    checked = check_plan(plan, directory)
    expected, manifest, ids = create_map(checked)
    actual = load_json(directory / 'map.odenmap/map.json')
    require(actual == expected, 'Native map does not match the bundled plan')
    require(load_json(directory / 'map.odenmap/manifest.json') == manifest, 'Manifest does not match the plan')
    native = validate_native(directory / 'map.odenmap')
    require(set(obj(d.get('assets'), 'assets')) == set(checked.assets), 'Asset inventory ID mismatch')
    for aid, a in checked.assets.items():
        entry = obj(d['assets'][aid], aid)
        require(entry.get('sha256') == a.sha256 and entry.get('bytes') == a.size and entry.get('native_id') == ids[aid],
                'Asset provenance does not match actual bytes', aid)
    require(set(obj(d.get('sources'), 'sources')) == set(checked.source_files), 'Source inventory ID mismatch')
    for sid, info in checked.source_files.items():
        require(d['sources'][sid].get('sha256') == info.sha256 and d['sources'][sid].get('bytes') == info.size,
                'Source provenance does not match actual bytes', sid)
    for transformation in plan.get('audit', {}).get('transformations', []):
        sid = transformation.get('record', {}).get('source', {}).get('id')
        if sid in checked.source_files:
            require(transformation.get('source_resolution') == {
                'source_id': sid, 'uri': d['sources'][sid]['path'],
                'sha256': checked.source_files[sid].sha256,
                'scope': 'delivery-relative', 'acquisition_path_is_historical': True},
                'Transformation lacks a current portable source resolution', str(sid))
    return {'ok': True, 'native': native, 'local_sources_verified': len(checked.source_files),
            'delivery_files_verified': len(files), 'warnings': d.get('warnings', []),
            'native_runtime_observed': False, 'semantic_truth_verified_by_compiler': False}
