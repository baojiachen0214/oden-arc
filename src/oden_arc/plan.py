"""MapPlan 1.0 structural contract and bounded, local resource resolution.

Semantic truth remains a reviewer responsibility. A valid plan is not a claim
that every source was read or that the resulting map is cognitively useful.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
import re
import struct
from typing import Any

from .common import (MAX_ASSET, MAX_DEPTH, MAX_NODES, MAX_PIXELS, MAX_TOTAL,
                     HEX256, SkillError, arr, boolean, digest, enum, identifier,
                     is_remote, number, obj, only_keys, read_bytes, require,
                     safe_link, safe_relative, text)

# Content type identifiers are native Apple UTIs, not MIME strings.
TYPES = {
    '.png': ('public.png', 'image'), '.jpg': ('public.jpeg', 'image'),
    '.jpeg': ('public.jpeg', 'image'), '.gif': ('com.compuserve.gif', 'image'),
    '.tif': ('public.tiff', 'image'), '.tiff': ('public.tiff', 'image'),
    '.webp': ('org.webmproject.webp', 'image'), '.heic': ('public.heic', 'image'),
    '.pdf': ('com.adobe.pdf', 'pdf'), '.md': ('net.daringfireball.markdown', 'text'),
    '.txt': ('public.plain-text', 'text'), '.csv': ('public.comma-separated-values-text', 'text'),
    '.tsv': ('public.tab-separated-values-text', 'text'), '.json': ('public.json', 'text'),
    '.srt': ('public.plain-text', 'text'), '.vtt': ('public.plain-text', 'text'),
    '.mmd': ('public.plain-text', 'text'), '.tex': ('public.plain-text', 'text'),
    '.py': ('public.source-code', 'text'), '.swift': ('public.source-code', 'text'),
    '.rs': ('public.source-code', 'text'), '.js': ('public.source-code', 'text'),
    '.mp3': ('public.mp3', 'audio'), '.wav': ('com.microsoft.waveform-audio', 'audio'),
    '.m4a': ('com.apple.m4a-audio', 'audio'), '.mp4': ('public.mpeg-4', 'video'),
    '.mov': ('com.apple.quicktime-movie', 'video'),
    '.zip': ('public.zip-archive', 'file'), '.7z': ('org.7-zip.7-zip-archive', 'file'),
    '.flac': ('org.xiph.flac', 'audio'), '.aac': ('public.aac-audio', 'audio'),
    '.docx': ('org.openxmlformats.wordprocessingml.document', 'file'),
    '.xlsx': ('org.openxmlformats.spreadsheetml.sheet', 'file'),
    '.pptx': ('org.openxmlformats.presentationml.presentation', 'file'),
}
KINDS = {'image', 'pdf', 'text', 'audio', 'video', 'file'}
SUPPORT = {'fact', 'inference', 'uncertain', 'user', 'structure'}
BLOCKS = {'paragraph', 'heading', 'list', 'task', 'code', 'equation'}
MARKS = {'bold', 'italic', 'underline', 'strike', 'code', 'link', 'relativeSize'}


@dataclass(frozen=True)
class AssetInfo:
    id: str
    path: Path
    sha256: str
    size: int
    name: str
    uti: str
    kind: str
    dimensions: tuple[int, int] | None


@dataclass
class CheckedPlan:
    plan: dict
    base: Path
    assets: dict[str, AssetInfo]
    source_files: dict[str, AssetInfo]
    levels: dict[str, int]
    children: dict[str, list[str]]
    root: str
    warnings: list[str]


def check_hash(value: Any, loc: str) -> str:
    require(isinstance(value, str) and HEX256.fullmatch(value) is not None,
            'Expected lowercase SHA-256 hex', loc)
    return value


def index_items(items: list, location: str) -> dict[str, dict]:
    indexed = {}
    for i, value in enumerate(items):
        item = obj(value, f'{location}[{i}]')
        key = identifier(item.get('id'), f'{location}[{i}].id')
        require(key not in indexed, 'Duplicate ID', f'{location}.{key}')
        indexed[key] = item
    return indexed


def source_refs(value: Any, sources: dict, location: str) -> None:
    for i, item in enumerate(arr(value, location, 1000)):
        ref = obj(item, f'{location}[{i}]')
        sid = identifier(ref.get('source_id'), f'{location}[{i}].source_id')
        require(sid in sources, 'Unknown source', sid)
        text(ref.get('locator'), f'{location}[{i}].locator', limit=4000)
        for key in ('quote', 'cell_range', 'time_range'):
            if key in ref:
                text(ref[key], f'{location}[{i}].{key}', limit=12000)
        if 'page' in ref:
            require(type(ref['page']) is int and ref['page'] >= 1,
                    'PDF page is a 1-based integer', location)
        if 'region' in ref:
            # Legacy records may use a named region object; preserved verbatim.
            require(isinstance(ref['region'], (dict, list)), 'Region must be an object or array', location)


def check_inlines(value: Any, location: str) -> None:
    for j, item in enumerate(arr(value, location, 1000)):
        v = obj(item, f'{location}[{j}]')
        only_keys(v, {'kind', 'text', 'latex', 'marks', 'display'}, location)
        kind = enum(v.get('kind', 'text'), {'text', 'equation', 'softBreak'}, location)
        if kind != 'softBreak':
            text(v.get('latex') if kind == 'equation' else v.get('text'), location,
                 blank=kind == 'text', limit=16000)
        if 'display' in v:
            boolean(v['display'], location)
        marks = obj(v.get('marks', {}), location)
        only_keys(marks, MARKS, location)
        for key, val in marks.items():
            if key == 'link':
                safe_link(val, location)
            elif key == 'relativeSize':
                number(val, location, 0.5, 3)
            else:
                boolean(val, location)


def check_body(value: Any, location: str) -> None:
    for i, item in enumerate(arr(value, location, 200)):
        block = obj(item, f'{location}[{i}]')
        only_keys(block, {'kind', 'latex', 'text', 'inlines', 'heading_level',
                          'list_depth', 'number', 'checked', 'language'}, location)
        kind = enum(block.get('kind'), BLOCKS, location)
        if kind == 'equation':
            text(block.get('latex'), location, limit=16000)
            require('inlines' not in block and 'text' not in block,
                    'Equation uses latex, not mixed representations', location)
        else:
            require(not ('text' in block and 'inlines' in block),
                    'Use either text or inlines, not both', location)
            if 'inlines' in block:
                check_inlines(block['inlines'], location)
            else:
                text(block.get('text', ''), location, blank=True, limit=16000)
        for key, low, high in [('heading_level', 1, 6), ('list_depth', 0, 16), ('number', 1, 100000)]:
            if key in block:
                require(type(block[key]) is int, 'Expected integer', location)
                number(block[key], location, low, high)
        if 'checked' in block:
            boolean(block['checked'], location)
        if 'language' in block:
            text(block['language'], location, blank=True, limit=100)


def inspect_asset(path: Path, name: str, declared_kind: str, key: str,
                  expected_hash: str | None = None) -> AssetInfo:
    name = text(name, f'{key}.name', limit=255)
    require('/' not in name and '\\' not in name and name not in {'.', '..'},
            'Asset display name must be a filename, not a path', key)
    ext = Path(name).suffix.lower()
    require(ext in TYPES, f'Unsupported or active extension {ext!r}; supply a static supported rendition',
            key, 'media')
    uti, inferred = TYPES[ext]
    enum(declared_kind, KINDS, f'{key}.kind')
    require(declared_kind == inferred or declared_kind == 'file',
            f'Kind {declared_kind} disagrees with extension {ext} ({inferred})', key)
    data = read_bytes(path)
    sha = digest(data)
    if expected_hash is not None:
        check_hash(expected_hash, key)
        require(sha == expected_hash, 'SHA-256 mismatch; do not silently rehash changed evidence', key, 'hash')
    dims = None
    if ext == '.png':
        require(len(data) >= 33 and data[:8] == b'\x89PNG\r\n\x1a\n' and data[12:16] == b'IHDR',
                'Invalid PNG signature', key, 'media')
        dims = struct.unpack('>II', data[16:24])
    elif ext in {'.jpg', '.jpeg'}:
        require(data[:3] == b'\xff\xd8\xff', 'Invalid JPEG signature', key, 'media')
    elif ext == '.pdf':
        require(data[:5] == b'%PDF-', 'Invalid PDF signature', key, 'media')
    elif ext == '.gif':
        require(data[:6] in {b'GIF87a', b'GIF89a'}, 'Invalid GIF signature', key, 'media')
    elif ext in {'.tif', '.tiff'}:
        require(data[:4] in {b'II*\x00', b'MM\x00*'}, 'Invalid TIFF signature', key, 'media')
    elif ext == '.webp':
        require(data[:4] == b'RIFF' and data[8:12] == b'WEBP', 'Invalid WebP signature', key, 'media')
    elif ext in {'.docx', '.xlsx', '.pptx'}:
        require(data[:4] == b'PK\x03\x04', 'Expected an OOXML ZIP payload', key, 'media')
    if inferred == 'text' or ext in {'.csv', '.tsv'}:
        try:
            content = data.decode('utf-8-sig')
        except UnicodeDecodeError as exc:
            raise SkillError('encoding', 'Text assets must be UTF-8; retain original separately if converting', key) from exc
        require('\x00' not in content, 'Text asset contains NUL bytes', key)
        if ext == '.md':
            # Deliberately conservative. Links are inert; remote embedded media is not.
            require(not re.search(r'<\s*/?\s*[a-z][^>]*>', content, re.I),
                    'Raw active/externally loading HTML in Markdown is not supported', key, 'active-content')
            require(not re.search(r'!\[[^\]]*\]\s*[\[(]', content), 'Markdown resource images must be separate resource nodes; no automatic loading', key, 'active-content')
            for match in re.finditer(r'!\[[^\]]*\]\(([^)]+)\)', content):
                require(not re.match(r'(https?:|//|data:|file:)', match.group(1).strip(), re.I),
                        'Remote/data image embeddings are not packaged automatically', key, 'active-content')
    if dims:
        require(dims[0] > 0 and dims[1] > 0 and dims[0] * dims[1] <= MAX_PIXELS,
                'Image dimensions exceed budget or are empty', key, 'limit')
    return AssetInfo(key, path, sha, len(data), name, uti, declared_kind, dims)


def check_plan(plan: Any, base: Path) -> CheckedPlan:
    p = obj(plan, 'plan')
    only_keys(p, {'plan_version', 'document_id', 'title', 'goal', 'sources', 'assets',
                  'nodes', 'cross_links', 'audit', 'settings', 'extensions'}, 'plan')
    require(p.get('plan_version') == '1.0', 'Unsupported MapPlan version', 'plan_version')
    identifier(p.get('document_id'), 'document_id')
    text(p.get('title'), 'title', limit=500)
    goal = obj(p.get('goal'), 'goal')
    enum(goal.get('purpose'), {'learn', 'decide', 'act', 'reference', 'explain'}, 'goal.purpose')
    text(goal.get('question'), 'goal.question', limit=4000)
    for field in ('reader', 'detail'):
        if field in goal:
            text(goal[field], f'goal.{field}', limit=1000)
    for field in ('must_answer', 'assumptions'):
        for value in arr(goal.get(field, []), f'goal.{field}', 1000):
            text(value, f'goal.{field}', limit=4000)
    sources = index_items(arr(p.get('sources', []), 'sources', 2000), 'sources')
    assets = index_items(arr(p.get('assets', []), 'assets', 2000), 'assets')
    nodes = index_items(arr(p.get('nodes'), 'nodes', MAX_NODES), 'nodes')
    require(bool(nodes), 'At least one node is required', 'nodes')
    warnings: list[str] = []
    source_files: dict[str, AssetInfo] = {}
    used_paths: dict[str, int] = {}
    for sid, s in sources.items():
        text(s.get('title'), f'{sid}.title', limit=500)
        text(s.get('kind'), f'{sid}.kind', limit=100)
        enum(s.get('status'), {'read', 'partial', 'unread', 'unavailable'}, f'{sid}.status')
        text(s.get('coverage'), f'{sid}.coverage', limit=12000)
        if 'sha256' in s:
            check_hash(s['sha256'], sid)
        if 'uri' in s:
            uri = text(s['uri'], f'{sid}.uri', limit=4096)
            if is_remote(uri):
                safe_link(uri, sid)
                warnings.append(f'{sid}: remote source not fetched or hash-verified')
            else:
                path = safe_relative(base, uri)
                if not path.exists() and s['status'] == 'unavailable':
                    warnings.append(f'{sid}: source is explicitly unavailable')
                else:
                    data = read_bytes(path)
                    sha = digest(data)
                    if 'sha256' in s:
                        require(sha == s['sha256'], 'Source SHA-256 mismatch', sid, 'hash')
                    source_files[sid] = AssetInfo(sid, path, sha, len(data), path.name,
                                                 'public.data', 'file', None)
                    used_paths[str(path)] = len(data)
        elif s.get('kind') != 'user':
            warnings.append(f'{sid}: original source absent; supplied hash is a declaration, not verification')
    resolved: dict[str, AssetInfo] = {}
    for aid, a in assets.items():
        only_keys(a, {'id', 'path', 'name', 'kind', 'alt', 'source_refs', 'derivation',
                      'sha256', 'extensions'}, aid)
        path = safe_relative(base, a.get('path'))
        info = inspect_asset(path, a.get('name', path.name), a.get('kind'), aid, a.get('sha256'))
        resolved[aid] = info
        used_paths[str(path)] = info.size
        source_refs(a.get('source_refs', []), sources, f'{aid}.source_refs')
        if 'alt' in a:
            text(a['alt'], f'{aid}.alt', limit=4000)
        elif a['kind'] == 'image':
            warnings.append(f'{aid}: add an alt description and inspect the actual image')
        if 'derivation' in a:
            d = obj(a['derivation'], f'{aid}.derivation')
            enum(d.get('kind'), {'original', 'crop', 'redraw', 'generated', 'render', 'transcribe', 'extract', 'calculation'}, aid)
            if 'note' in d:
                text(d['note'], aid, limit=8000)
        else:
            warnings.append(f'{aid}: derivation provenance is not specified')
    require(sum(used_paths.values()) <= MAX_TOTAL, 'Material set exceeds 256 MiB input budget', code='limit')
    children: dict[str, list[str]] = defaultdict(list)
    roots = []
    for nid, n in nodes.items():
        only_keys(n, {'id', 'parent_id', 'label', 'role', 'support', 'source_refs', 'note',
                      'body', 'asset_id', 'attachment_ids', 'collapsed', 'hyperlink',
                      'extensions'}, nid)
        text(n.get('label'), f'{nid}.label', limit=1000)
        text(n.get('role'), f'{nid}.role', limit=100)
        enum(n.get('support'), SUPPORT, f'{nid}.support')
        require('parent_id' in n, 'parent_id is required; use null only for root', nid)
        parent = n['parent_id']
        if parent is None:
            roots.append(nid)
        else:
            identifier(parent, f'{nid}.parent_id')
            require(parent in nodes and parent != nid, 'Missing or self parent', nid)
            children[parent].append(nid)
        source_refs(n.get('source_refs', []), sources, f'{nid}.source_refs')
        if n['support'] in {'fact', 'inference'} and not n.get('source_refs'):
            warnings.append(f'{nid}: substantive claim lacks source references')
        if 'note' in n:
            text(n['note'], f'{nid}.note', blank=True)
        if 'collapsed' in n:
            boolean(n['collapsed'], nid)
        if 'hyperlink' in n and n['hyperlink']:
            safe_link(n['hyperlink'], nid)
        check_body(n.get('body', []), f'{nid}.body')
        if 'asset_id' in n:
            identifier(n['asset_id'], nid)
            require(n['asset_id'] in assets, 'Unknown resource asset', nid)
            require(not n.get('body'), 'Standalone resource nodes cannot also have editable body; use a sibling text node', nid)
        attachments = arr(n.get('attachment_ids', []), f'{nid}.attachment_ids', 2000)
        require(all(isinstance(a, str) for a in attachments), 'Attachment IDs must be strings', nid)
        require(len(attachments) == len(set(attachments)), 'Duplicate attachment ID', nid)
        require(all(a in assets for a in attachments), 'Unknown attachment asset', nid)
    require(len(roots) == 1, 'Exactly one semantic root is required', 'nodes')
    levels = {roots[0]: 0}
    queue = deque([roots[0]])
    while queue:
        current = queue.popleft()
        for child in children[current]:
            require(child not in levels, 'Cycle or repeated parent', child)
            levels[child] = levels[current] + 1
            require(levels[child] <= MAX_DEPTH, f'Tree exceeds depth budget {MAX_DEPTH}', child, 'limit')
            queue.append(child)
    require(len(levels) == len(nodes), 'Disconnected cycle or unreachable node', 'nodes')
    links = index_items(arr(p.get('cross_links', []), 'cross_links', MAX_NODES), 'cross_links')
    for lid, link in links.items():
        only_keys(link, {'id', 'from', 'to', 'label'}, lid)
        for field in ('from', 'to'):
            identifier(link.get(field), lid)
            require(link[field] in nodes, 'Unknown cross-link endpoint', lid)
        require(link['from'] != link['to'], 'Self cross-links are not supported', lid)
        text(link.get('label'), lid, limit=1000)
    settings = obj(p.get('settings', {}), 'settings')
    only_keys(settings, {'layout', 'sibling_spacing', 'level_spacing'}, 'settings')
    if 'layout' in settings:
        enum(settings['layout'], {'right', 'left'}, 'settings.layout')
    for key in ('sibling_spacing', 'level_spacing'):
        if key in settings:
            number(settings[key], f'settings.{key}', 16, 200)
    if 'audit' in p:
        obj(p['audit'], 'audit')
    else:
        warnings.append('No audit record; semantic readiness is not established')
    return CheckedPlan(p, base, resolved, source_files, levels, dict(children), roots[0], warnings)
