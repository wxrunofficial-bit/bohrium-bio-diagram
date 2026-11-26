"""Join source rows to edge IDs and render the scale used in the pathway."""
import csv
import hashlib
import math

from graph import element, text


def interval(values, name):
    if not isinstance(values, list) or len(values) != 2:
        raise ValueError(f'{name} must contain two numbers')
    if any(type(v) not in (float, int) or not math.isfinite(v) for v in values) or values[0] >= values[1]:
        raise ValueError(f'{name} must contain increasing finite numbers')
    return values


def read(graph, table):
    spec = graph.get('edge_scale')
    if spec is None and table is None:
        return None
    if not isinstance(spec, dict) or table is None:
        raise ValueError('edge_scale and --edge-table CSV must be supplied together')
    label, unit, key, field = (spec[k] for k in ('label', 'unit', 'id_column', 'value_column'))
    if not all(isinstance(v, str) and v.strip() for v in (label, unit, key, field)) or key == field:
        raise ValueError('edge_scale needs a label, unit and two different CSV columns')
    lo, hi = interval(spec['domain'], 'domain')
    thin, thick = interval(spec.get('range_px', [1.5, 6.5]), 'range_px')
    if thin < 1 or thick > 9:
        raise ValueError('use stroke widths between 1 and 9 SVG units')
    def width(v):
        return thin + (v-lo)/(hi-lo)*(thick-thin)
    expected = {e['id'] for e in graph.get('edges', [])}
    rows = {}
    with table.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        if len(set(headers)) != len(headers) or key not in headers or field not in headers:
            raise ValueError('CSV has duplicate or missing headers')
        for row in reader:
            line = reader.line_num
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f'CSV line {line}: wrong number of fields')
            edge_id = row[key].strip()
            if edge_id not in expected or edge_id in rows:
                raise ValueError(f'CSV line {line}: unknown or repeated edge {edge_id!r}')
            v = float(row[field])
            if not math.isfinite(v) or not lo <= v <= hi:
                raise ValueError(f'CSV line {line}: value is nonfinite or outside domain')
            rows[edge_id] = dict(value=v, width=width(v), end_line=line)
    if not rows or expected != rows.keys():
        raise ValueError(f'CSV needs one row per edge. Missing: {sorted(expected-rows.keys())}')
    ticks = [dict(value=v, width=width(v)) for v in (lo, (lo+hi)/2, hi)]
    return dict(label=label, unit=unit, domain=[lo,hi], range_px=[thin,thick],
                source=table.name, sha256=hashlib.sha256(table.read_bytes()).hexdigest(),
                id_column=key, value_column=field, rows=rows, ticks=ticks)


def legend(root, layer, mapping):
    y = int(root.get('height'))
    height = y + 75
    root.set('height', str(height))
    root.set('viewBox', f"0 0 {root.get('width')} {height}")
    root.find(".//*[@id='background']")[0].set('height', str(height))
    text(layer, 38, y+16, f"{mapping['label']} ({mapping['unit']})", 15, weight=700, id='scale-title')
    for i, tick in enumerate(mapping['ticks']):
        x = 40+i*215
        element(layer, 'line', id=f'scale-mark-{i}', x1=x, x2=x+42, y1=y+43, y2=y+43,
                stroke='#344457', stroke_width=tick['width'])
        text(layer, x+54, y+48, format(tick['value'], '.8g'), 13, id=f'scale-label-{i}')
