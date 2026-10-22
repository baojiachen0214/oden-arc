"""Bounded deterministic image/PDF crops with explicit coordinate provenance.

No OCR and no network. This is not a parser sandbox or a color-management system.
Source files are read-only. Outputs are written into a NEW directory transaction.
"""
from __future__ import annotations
import argparse
from io import BytesIO
import json
import math
from pathlib import Path
import sys
from typing import Any

from .common import (MAX_PIXELS, SkillError, digest, exclusive_directory, json_bytes,
                     number, read_bytes, require, write_new)


def box_checked(box: list[float], width: float, height: float) -> list[float]:
    require(isinstance(box, (list, tuple)) and len(box) == 4, 'Box is x0,y0,x1,y1')
    for value in box:
        number(value, 'box', 0, max(width, height))
    x0, y0, x1, y1 = box
    require(x0 < x1 <= width and y0 < y1 <= height, 'Crop box is empty or out of bounds')
    return list(box)


def pillow():
    try:
        from PIL import Image, ImageOps, PngImagePlugin, __version__
    except ImportError as exc:
        raise SkillError('dependency', 'Image crops require Pillow; install the images extra (see docs/getting-started.md)') from exc
    return Image, ImageOps, PngImagePlugin, __version__


def save_result(image: Any, record: dict, out: Path, metadata: dict | None = None) -> dict:
    buf = BytesIO()
    image.save(buf, format='PNG', **(metadata or {}))
    payload = buf.getvalue()
    record['output'] = {'path': 'crop.png', 'sha256': digest(payload),
                        'width': image.width, 'height': image.height, 'bytes': len(payload), 'format': 'PNG'}
    record['semantic_review'] = 'Required: check captions, axes, units, legends and footnotes; crop mechanics do not prove completeness.'
    with exclusive_directory(out) as root:
        write_new(root / 'crop.png', payload)
        write_new(root / 'crop.provenance.json', json_bytes(record))
    return {'ok': True, 'output': str(out), 'record': record}


def crop_image(source: Path, out: Path, box: list[float], frame: int | None = None,
               expected_sha: str | None = None) -> dict:
    Image, ImageOps, PngImagePlugin, version = pillow()
    raw = read_bytes(source)
    sha = digest(raw)
    if expected_sha is not None:
        require(sha == expected_sha, 'Source changed; SHA-256 mismatch', code='hash')
    try:
        with Image.open(BytesIO(raw)) as original:
            nframes = getattr(original, 'n_frames', 1)
            if nframes > 1:
                require(frame is not None, 'Animated/multi-page image requires an explicit --frame (0-based)')
            index = 0 if frame is None else frame
            require(type(index) is int and 0 <= index < nframes, 'Frame index out of range')
            original.seek(index)
            require(original.width * original.height <= MAX_PIXELS, 'Image exceeds pixel budget', code='limit')
            require(original.mode in {'1', 'L', 'LA', 'P', 'RGB', 'RGBA'},
                    f'Mode {original.mode} requires explicit color/bit-depth conversion; refusing silent loss', code='color')
            info = dict(original.info)
            orientation = original.getexif().get(274, 1)
            original_size = list(original.size)
            # TIFF plugins may already apply orientation during load; ImageOps handles
            # the remaining EXIF tag. Output is tested against Pillow's display pixels.
            image = ImageOps.exif_transpose(original)
            if image.mode in {'P', '1'}:
                image = image.convert('RGBA' if image.mode == 'P' else 'L')
            b = box_checked(box, image.width, image.height)
            require(all(type(v) is int or float(v).is_integer() for v in b), 'Image crop uses integral display-pixel edges')
            px = tuple(int(v) for v in b)
            crop = image.crop(px)
            metadata: dict = {}
            for key in ('icc_profile', 'dpi'):
                if info.get(key):
                    metadata[key] = info[key]
            pnginfo = PngImagePlugin.PngInfo()
            if info.get('gamma') is not None:
                import struct
                pnginfo.add(b'gAMA', struct.pack('>I', round(info['gamma'] * 100000)))
            if info.get('srgb') is not None:
                pnginfo.add(b'sRGB', bytes([int(info['srgb'])]))
            metadata['pnginfo'] = pnginfo
            record = {'record_version': '2.0', 'operation': 'crop-image',
                      'source': {'name': source.name, 'sha256': sha, 'size': original_size,
                                 'exif_orientation': orientation, 'frame': index, 'frames': nframes},
                      'coordinates': {'system': 'top-left EXIF-oriented display pixels; right/bottom exclusive',
                                      'display_size': list(image.size), 'box': list(px)},
                      'color': {'input_mode': original.mode, 'output_mode': crop.mode,
                                'icc_retained': bool(info.get('icc_profile')), 'color_conversion': False,
                                'note': 'Palette expansion/1-bit expansion is possible; no ICC profile conversion is performed.'},
                      'tool': {'name': 'Pillow', 'version': version}}
            return save_result(crop, record, out, metadata)
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        if isinstance(exc, SkillError):
            raise
        raise SkillError('image', str(exc)) from exc


def crop_pdf(source: Path, out: Path, page: int, box: list[float], dpi: int = 144,
             annotations: bool = False, expected_sha: str | None = None) -> dict:
    Image, _, _, _ = pillow()
    try:
        import fitz
    except ImportError as exc:
        raise SkillError('dependency', 'PDF crops require the pdf extra; review THIRD_PARTY.md before installing') from exc
    require(type(page) is int and page >= 1, 'PDF page is 1-based')
    require(type(dpi) is int and 36 <= dpi <= 600, 'DPI must be 36..600')
    require(type(annotations) is bool, 'annotations must be boolean')
    data = read_bytes(source)
    sha = digest(data)
    if expected_sha is not None:
        require(sha == expected_sha, 'Source changed; SHA-256 mismatch', code='hash')
    try:
        with fitz.open(stream=data, filetype='pdf') as doc:
            require(not doc.needs_pass, 'Encrypted PDF needs an authorized decrypted copy')
            require(page <= len(doc), 'Page exceeds PDF length')
            p = doc[page-1]
            rect = p.rect
            b = box_checked(box, rect.width, rect.height)
            expected_pixels = math.ceil(rect.width*dpi/72)*math.ceil(rect.height*dpi/72)
            require(expected_pixels <= MAX_PIXELS, 'Full-page render exceeds budget; reduce DPI', code='limit')
            # Render the entire rotated visible page first. Avoid confusing PDF user
            # coordinates, unrotated CropBox coordinates and screenshot coordinates.
            pix = p.get_pixmap(dpi=dpi, alpha=False, annots=annotations, colorspace=fitz.csRGB)
            require(pix.width*pix.height <= MAX_PIXELS, 'Rendered page exceeds budget')
            image = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
            sx, sy = pix.width/rect.width, pix.height/rect.height
            pixels = [math.floor(b[0]*sx), math.floor(b[1]*sy), math.ceil(b[2]*sx), math.ceil(b[3]*sy)]
            pixels[2] = min(pix.width, pixels[2]); pixels[3] = min(pix.height, pixels[3])
            crop = image.crop(tuple(pixels))
            record = {'record_version': '2.0', 'operation': 'crop-pdf',
                      'source': {'name': source.name, 'sha256': sha, 'page': page,
                                 'page_count': len(doc), 'rotation': p.rotation,
                                 'media_box': list(p.mediabox), 'crop_box': list(p.cropbox)},
                      'coordinates': {'system': 'top-left visible rotated page points (72 points/inch), not raw PDF user space',
                                      'page_size_points': [rect.width, rect.height], 'box_points': b,
                                      'render_size_pixels': [pix.width, pix.height], 'pixel_box': pixels,
                                      'rounding': 'outward floor/ceil'},
                      'render': {'dpi': dpi, 'annotations': annotations, 'color': 'MuPDF device RGB rendition'},
                      'tool': {'name': 'PyMuPDF', 'version': fitz.VersionBind}}
            return save_result(crop, record, out, {'dpi': (dpi, dpi)})
    except (OSError, RuntimeError, ValueError) as exc:
        if isinstance(exc, SkillError):
            raise
        raise SkillError('pdf', str(exc)) from exc


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description='Bounded read-only source crops into a new output directory')
    sub = p.add_subparsers(dest='command', required=True)
    for name in ('image', 'pdf'):
        c = sub.add_parser(name)
        c.add_argument('source', type=Path); c.add_argument('--out', required=True, type=Path)
        c.add_argument('--box', required=True, nargs=4, type=float); c.add_argument('--sha256')
        if name == 'image': c.add_argument('--frame', type=int)
        else:
            c.add_argument('--page', required=True, type=int); c.add_argument('--dpi', type=int, default=144)
            c.add_argument('--annotations', action='store_true')
    a = p.parse_args(argv)
    try:
        if a.command == 'image': out = crop_image(a.source, a.out, a.box, a.frame, a.sha256)
        else: out = crop_pdf(a.source, a.out, a.page, a.box, a.dpi, a.annotations, a.sha256)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    except (SkillError, OSError) as exc:
        print(json.dumps(exc.as_dict() if isinstance(exc, SkillError) else {'ok': False, 'message': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
