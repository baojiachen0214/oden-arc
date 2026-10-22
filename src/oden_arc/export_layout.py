"""Independent, generic initial placement for exported documents.

No application rendering, typography, interaction or layout code is used.
The estimates merely make a new file readable enough for native inspection.
They do not predict the product's exact layout or font metrics.
"""
from __future__ import annotations
from collections import defaultdict, deque
import math
import unicodedata
from typing import Any

def estimated_geometry(n: dict, asset: Any = None) -> tuple[float, float]:
    if asset:
        if asset.kind == 'image' and asset.dimensions:
            w, h = asset.dimensions
            factor = min(420 / w, 480 / h)
            return max(80, w * factor), max(60, h * factor)
        return {'image': (320, 240), 'pdf': (280, 220), 'video': (280, 180),
                'audio': (250, 100), 'text': (280, 170), 'file': (240, 90)}[asset.kind]
    def units(s: str) -> int:
        return sum(2 if unicodedata.east_asian_width(c) in {'W', 'F'} else 1 for c in s)
    width = min(520, max(180, 24 + units(n['label']) * 8))
    if n.get('body'):
        width = max(360, width)
    height = 24 + 24 * max(1, math.ceil(units(n['label']) * 8 / (width - 24)))
    for b in n.get('body', []):
        raw = b.get('latex', b.get('text', ''.join(i.get('text', i.get('latex', '')) for i in b.get('inlines', []))))
        lines = sum(max(1, math.ceil(units(s) * 8 / (width - 24))) for s in raw.split('\n'))
        height += (42 if b['kind'] == 'equation' else 24) * lines
    return width, min(9000, height)



def place_nodes(checked: Any, by_plan_id: dict, sibling_gap: float, level_gap: float) -> None:
    """Place a checked tree using depth columns and bottom-up subtree spans."""
    node_specs = {node['id']: node for node in checked.plan['nodes']}
    settings = checked.plan.get('settings', {})
    # Generic tree spans: a deterministic initial estimate, not application layout.
    spans = {}
    for nid in sorted(node_specs, key=lambda x: checked.levels[x], reverse=True):
        kids = checked.children.get(nid, [])
        spans[nid] = max(by_plan_id[nid]['height'], sum(spans[c] for c in kids) + sibling_gap * max(0, len(kids) - 1))
    max_width = defaultdict(float)
    for nid, n in by_plan_id.items():
        max_width[checked.levels[nid]] = max(max_width[checked.levels[nid]], n['width'])
    xs = {0: 0}
    for d in range(1, max(checked.levels.values()) + 1):
        xs[d] = xs[d - 1] + max_width[d - 1] / 2 + level_gap + max_width[d] / 2
    tops = {checked.root: -spans[checked.root] / 2}
    queue = deque([checked.root])
    sign = -1 if settings.get('layout') == 'left' else 1
    while queue:
        nid = queue.popleft()
        by_plan_id[nid]['x'] = sign * xs[checked.levels[nid]]
        by_plan_id[nid]['y'] = tops[nid] + spans[nid] / 2
        kids = checked.children.get(nid, [])
        total = sum(spans[c] for c in kids) + sibling_gap * max(0, len(kids) - 1)
        top = by_plan_id[nid]['y'] - total / 2
        for child in kids:
            tops[child] = top
            top += spans[child] + sibling_gap
            queue.append(child)
