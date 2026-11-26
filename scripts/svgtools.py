"""Edit existing SVGs without recomposition and render real preview files."""

import hashlib
import io
import importlib.util
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from graph import SVG


def local(name):
    return name.rsplit('}', 1)[-1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_svg(path):
    data = path.read_bytes()
    if len(data) > 12_000_000:
        raise ValueError('SVG source exceeds 12 MB')
    # Parse offline. Do not pass active SVGs or externally linked assets to a renderer.
    decoded = data.decode('utf-8-sig')
    if re.search(r'<!\s*(DOCTYPE|ENTITY)|<\?xml-stylesheet', decoded, re.I):
        raise ValueError('SVG uses external XML processing features')
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True))
    root = ET.fromstring(decoded, parser=parser)
    if root.tag != f'{{{SVG}}}svg':
        raise ValueError('expected an SVG document')
    for node in root.iter():
        if not isinstance(node.tag, str):
            continue
        if local(node.tag).lower() in {'script', 'foreignobject', 'iframe', 'object', 'embed', 'animate', 'animatetransform', 'animatemotion', 'set', 'discard'}:
            raise ValueError(f'unsupported SVG element: {local(node.tag)}')
        for key, value in node.attrib.items():
            name = local(key).lower()
            if name.startswith('on') or name == 'base':
                raise ValueError(f'unsupported SVG attribute: {name}')
            if name in {'href', 'src'} and not (value.startswith('#') or re.match(r'^data:image/(png|jpe?g|webp|gif);base64,', value, re.I)):
                raise ValueError('SVG references a non-embedded resource')
        css = ' '.join(node.attrib.values()) + ((node.text or '') if local(node.tag) == 'style' else '')
        if re.search(r'@import|@font-face|\\[0-9a-fA-F]{1,6}', css, re.I):
            raise ValueError('SVG uses unsupported CSS resources')
        for value in re.findall(r'url\s*\(([^)]*)\)', css, re.I):
            if not value.strip(' \t\n\r\"\'').startswith('#'):
                raise ValueError('SVG CSS references a non-embedded resource')
    return root


def write_svg(root, path):
    ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)


def summarize(root):
    records = {}
    for node in root.iter():
        key = node.get('id')
        if key:
            if key in records:
                raise ValueError(f'duplicate SVG ID: {key}')
            records[key] = node
    return records


def node_payload(node):
    return (node.tag, dict(node.attrib), node.text, node.tail)


def edit(root, plan):
    """Replace an identified label fragment or allowlisted style attribute."""
    records = summarize(root)
    before = [node_payload(n) for n in root.iter()]
    allowed = {'fill', 'stroke', 'stroke-width', 'stroke-dasharray', 'font-size', 'opacity', 'visibility', 'marker-end', 'marker-start'}
    targets = set()
    changes = []
    for op in plan['operations']:
        key, field = op['id'], op['field']
        if key not in records or not op.get('source') or not op.get('reason'):
            raise ValueError(f'{key}: edit needs a valid ID, source and reason')
        if 'expected' not in op or 'value' not in op or (key, field) in targets:
            raise ValueError(f'{key}: edit needs unique field, expected value and replacement')
        node, new = records[key], op['value']
        if not isinstance(new, str):
            raise ValueError(f'{key}: replacement must be a string')
        if field == 'text':
            if local(node.tag) not in {'text', 'tspan', 'title', 'desc'} or list(node):
                raise ValueError(f'{key}: target a plain text or leaf tspan, not a container')
            old = node.text or ''
        elif field in allowed:
            if field.startswith('marker-') and new != 'none':
                marker = re.fullmatch(r'url\(#([A-Za-z_][A-Za-z0-9_.:-]*)\)', new)
                if not marker or marker[1] not in records or local(records[marker[1]].tag) != 'marker':
                    raise ValueError(f'{key}: marker must reference an existing marker ID')
            elif not field.startswith('marker-') and not re.fullmatch(r'[a-zA-Z0-9#.% ,+-]+', new):
                raise ValueError(f'{key}: invalid style replacement')
            old = node.get(field)
        else:
            raise ValueError(f'{key}: unsupported edit field {field!r}')
        if old != op['expected']:
            raise ValueError(f'{key}.{field}: expected {op["expected"]!r}; found {old!r}')
        targets.add((key, field))
        if old == new:
            continue
        if field == 'text':
            node.text = new
        else:
            node.set(field, new)
        changes.append({'id': key, 'field': field, 'before': old, 'after': new,
                        'source': op['source'], 'reason': op['reason']})

    edited = {entry['id'] for entry in changes}
    after = list(root.iter())
    if len(before) != len(after) or any(node_payload(n) != snapshot for n, snapshot in zip(after, before)
                                      if n.get('id') not in edited):
        raise ValueError('unexpected modification to an untargeted element')
    return {'changes': changes, 'untouched_id_count': len(records)-len(edited),
            'untouched_element_count': len(after)-len(edited), 'element_count': len(after)}


def dimensions(root):
    raw = [float(x) for x in re.split(r'[\s,]+', root.get('viewBox', '').strip()) if x]
    if len(raw) == 4:
        width, height = raw[2:]
    else:
        values = [re.fullmatch(r'(\d+(?:\.\d+)?)(px)?', root.get(k, '')) for k in ('width', 'height')]
        if not all(values):
            raise ValueError('SVG needs a viewBox or explicit pixel width and height')
        width, height = (float(v[1]) for v in values)
    if not (0 < width <= 10000 and 0 < height <= 10000):
        raise ValueError('invalid or excessive SVG viewport')
    return max(1, round(width)), max(1, round(height))


def run(args):
    result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=35)
    if result.returncode:
        raise RuntimeError((result.stderr.strip() or result.stdout.strip() or f'exit {result.returncode}')[-400:])


def browser_path():
    for name in ('chromium', 'chromium-browser', 'google-chrome', 'msedge', 'chrome'):
        path = shutil.which(name)
        if path:
            return path
    for folder in ('ProgramFiles(x86)', 'ProgramFiles', 'LOCALAPPDATA'):
        if folder in os.environ:
            for path in ('Microsoft/Edge/Application/msedge.exe', 'Google/Chrome/Application/chrome.exe'):
                candidate = Path(os.environ[folder], path)
                if candidate.is_file():
                    return str(candidate)
    return None


def render_browser(browser, svg, png, pdf, w, h, pw, ph, temp):
    # Render only the validated local SVG, with its aspect ratio fixed by the page.
    import html
    wrapper = temp/'print.html'
    wrapper.write_text('<!doctype html><meta charset="utf-8">'
                       '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src file: data:; style-src \'unsafe-inline\'">'
                       f'<style>@page{{size:{w}px {h}px;margin:0}} html,body{{margin:0;overflow:hidden;background:white}} '
                       'img{display:block;width:100vw;height:100vh;object-fit:contain}</style>'
                       f'<img src="{html.escape(svg.resolve().as_uri(), quote=True)}">', encoding='utf-8')
    common = [browser, '--headless', '--disable-gpu', '--disable-background-networking', '--no-first-run',
              '--no-default-browser-check', f'--user-data-dir={temp / "profile"}']
    run([*common, f'--window-size={pw},{ph}', f'--screenshot={png}', wrapper.as_uri()])
    run([*common, '--no-pdf-header-footer', f'--print-to-pdf={pdf}', wrapper.as_uri()])


def verify_exports(png, pdf, width, height):
    data = png.read_bytes()
    if not data.startswith(b'\x89PNG\r\n\x1a\n') or len(data) < 250:
        raise ValueError('missing or invalid PNG')
    size = struct.unpack('>II', data[16:24])
    if size != (width, height):
        raise ValueError(f'wrong PNG dimensions: {size}; expected {(width, height)}')
    data = pdf.read_bytes()
    if not data.startswith(b'%PDF-') or b'%%EOF' not in data[-1024:] or len(data) < 400:
        raise ValueError('missing or invalid PDF')
    try:
        from PIL import Image
    except ImportError:
        return {'png_pixels': list(size), 'png_nonblank_check': 'not_run', 'pdf_checks': ['signature', 'EOF']}
    with Image.open(png) as im:
        rgba = im.convert('RGBA')
        white = Image.new('RGBA', im.size, 'white')
        white.alpha_composite(rgba)
        if all(lo == hi for lo, hi in white.convert('RGB').getextrema()):
            raise ValueError('PNG has no visible content')
    checks = {'png_pixels': list(size), 'png_nonblank_check': 'passed', 'pdf_checks': ['signature', 'EOF'],
              'pdf_raster_check': 'not_run'}
    info, raster = shutil.which('pdfinfo'), shutil.which('pdftoppm')
    if info and raster:
        env = dict(os.environ, LC_ALL='C', LANG='C')
        def poppler(cmd):
            p = subprocess.run(cmd, capture_output=True, timeout=35, env=env)
            if p.returncode:
                raise ValueError('PDF inspection failed: '+p.stderr.decode(errors='replace')[:300])
            return p.stdout
        meta = poppler([info, str(pdf)]).decode(errors='replace')
        if not re.search(r'^Pages:\s+1\s*$', meta, re.M):
            raise ValueError('expected a single-page figure PDF')
        bitmap = poppler([raster, '-f','1','-l','1','-singlefile','-scale-to','384','-png',str(pdf)])
        with Image.open(io.BytesIO(bitmap)) as page:
            preview = page.convert('RGB')
        if all(a==b for a,b in preview.getextrema()):
            raise ValueError('PDF renders to an empty page')
        if abs(preview.width/preview.height/(width/height)-1) > max(.02, 2/min(preview.size)):
            raise ValueError('rasterized PDF and requested PNG have different aspect ratios')
        from PIL import ImageChops, ImageStat
        delta = ImageChops.difference(white.convert('RGB').resize(preview.size, Image.Resampling.LANCZOS), preview)
        checks.update(pdf_raster_check='passed', pdf_preview_pixels=list(preview.size),
                      pdf_png_mean_abs_rgb_0_to_255=round(sum(ImageStat.Stat(delta).mean)/3,3))
        checks['pdf_checks'] += ['single_page','raster_nonblank','aspect_ratio']
    return checks


def export(svg, root, scale):
    w,h = dimensions(root)
    pw,ph = round(w*scale),round(h*scale)
    if not (1 <= pw <= 10000 and 1 <= ph <= 10000 and pw*ph <= 30_000_000):
        raise ValueError('PNG dimensions exceed the supported pixel budget')
    svg = svg.resolve()
    methods = []
    if inkscape := shutil.which('inkscape'):
        def with_inkscape(png, pdf, _):
            run([inkscape, str(svg), f'--export-filename={png}', f'--export-width={pw}', f'--export-height={ph}'])
            run([inkscape, str(svg), f'--export-filename={pdf}'])
        methods.append(('inkscape', with_inkscape))
    if importlib.util.find_spec('cairosvg'):
        def with_cairo(png, pdf, _):
            run([sys.executable, '-m', 'cairosvg', str(svg), '-o', str(png), '--output-width', str(pw), '--output-height', str(ph)])
            run([sys.executable, '-m', 'cairosvg', str(svg), '-o', str(pdf)])
        methods.append(('cairosvg', with_cairo))
    if rsvg := shutil.which('rsvg-convert'):
        def with_rsvg(png, pdf, _):
            run([rsvg, '--width', str(pw), '--height', str(ph), '--output', str(png), str(svg)])
            run([rsvg, '--format', 'pdf', '--output', str(pdf), str(svg)])
        methods.append(('rsvg-convert', with_rsvg))
    if importlib.util.find_spec('matplotlib'):
        def with_plot(png, pdf, _):
            from plot_preview import save
            save(root,png,pdf,w,h,pw,ph)
        methods.append(('matplotlib-svg-subset', with_plot))
    if browser := browser_path():
        methods.append(('chromium', lambda png,pdf,temp: render_browser(browser,svg,png,pdf,w,h,pw,ph,temp)))
    errors = []
    for name, render in methods:
        try:
            with tempfile.TemporaryDirectory(prefix='pathway-render-', dir=svg.parent) as temp_name:
                tmp = Path(temp_name)
                png, pdf = tmp/'image.png', tmp/'image.pdf'
                render(png, pdf, tmp)
                checks = verify_exports(png, pdf, pw, ph)
                png.replace(svg.with_suffix('.png'))
                pdf.replace(svg.with_suffix('.pdf'))
            return {'renderer': name, 'source_viewport': [w,h], 'scale': scale, **checks}
        except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as error:
            errors.append(f'{name}: {error}')
    raise RuntimeError('; '.join(errors) or 'No supported SVG renderer was found')
