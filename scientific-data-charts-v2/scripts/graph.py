"""Deterministic layout and SVG rendering for a source-grounded pathway."""

import math
import re
import textwrap
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

SVG = 'http://www.w3.org/2000/svg'
INK = 'http://www.inkscape.org/namespaces/inkscape'
ET.register_namespace('', SVG)
ET.register_namespace('inkscape', INK)

W, H, DX, DY = 164, 56, 247, 116
LEFT, TOP = 190, 126
FONT = 'Arial, Liberation Sans, Noto Sans CJK SC, sans-serif'
TYPES = {
    'activation': ('#087c68', 'Activation', 'arrow', ''),
    'inhibition': ('#a43350', 'Inhibition', 'bar', ''),
    'binding': ('#7645a4', 'Binding', 'none', ''),
    'modification': ('#986013', 'Modification', 'arrow', ''),
    'transport': ('#2565ad', 'Transport', 'open', ''),
    'indirect': ('#56687f', 'Indirect / multistep', 'arrow', '7 5'),
    'association': ('#56687f', 'Undirected association', 'none', '4 4'),
}
KINDS = {
    'gene': ('#ede8fc', '#7254a3'), 'protein': ('#e7f0ff', '#365e99'),
    'receptor': ('#d9f1f0', '#267a80'), 'complex': ('#e4f1ef', '#39766a'),
    'molecule': ('#fff0d8', '#936015'), 'process': ('#edf0f4', '#68788d'),
    'phenotype': ('#f9e8ef', '#9c4765'), 'cell': ('#e9f4e0', '#5b7c3d'),
    'other': ('#f1f3f5', '#65758a'),
}
EVIDENCE = {'observed', 'inferred', 'proposed', 'unknown'}


def element(parent, tag, value=None, **attrs):
    node = ET.SubElement(parent, f'{{{SVG}}}{tag}', {k.replace('_', '-'): str(v) for k, v in attrs.items()})
    node.text = value
    return node


def layer(parent, key, label):
    return element(parent, 'g', id=key, **{f'{{{INK}}}groupmode': 'layer', f'{{{INK}}}label': label})


def text(parent, x, y, value, size=14, color='#20334a', weight=400, **attrs):
    return element(parent, 'text', value, x=x, y=y, font_size=size, fill=color, font_weight=weight, **attrs)


def wrapped(value, limit):
    # Count ideographs conservatively so long CJK labels receive more space.
    result = []
    for paragraph in value.splitlines() or ['']:
        width = limit // 2 if any(ord(char) > 0x2e80 for char in paragraph) else limit
        result.extend(textwrap.wrap(paragraph, width) or [''])
    return result


def index(items, name):
    result = {}
    for item in items:
        key = item.get('id', '')
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,59}', key) or key in result:
            raise ValueError(f'{name}: invalid or duplicate id {key!r}')
        result[key] = item
    return result


def validate(graph):
    if not str(graph.get('title', '')).strip():
        raise ValueError('graph title is required')
    sources = index(graph['sources'], 'sources')
    lanes = index(graph['lanes'], 'lanes')
    nodes = index(graph['nodes'], 'nodes')
    edges = index(graph.get('edges', []), 'edges')
    if not lanes or not nodes:
        raise ValueError('at least one lane and node are required')

    for key, source in sources.items():
        if not source.get('document') or not source.get('locator') or not source.get('statement'):
            raise ValueError(f'{key}: provide document, locator and a concise evidence statement')
    for key, lane in lanes.items():
        if not lane.get('label') or not isinstance(lane.get('rows', 1), int) or not 1 <= lane.get('rows', 1) <= 10:
            raise ValueError(f'{key}: lane needs a label and between 1 and 10 rows')
    for key, item in {**nodes, **edges}.items():
        if not isinstance(item.get('evidence'), list) or not item['evidence'] or any(ref not in sources for ref in item['evidence']):
            raise ValueError(f'{key}: missing or unknown evidence ID')
        if item.get('certainty', 'observed') not in EVIDENCE:
            raise ValueError(f'{key}: invalid certainty')
    if nodes.keys() & edges.keys():
        raise ValueError('node and edge IDs must be distinct')
    for key, node in nodes.items():
        if not str(node.get('label', '')).strip() or len(wrapped(node['label'], 22)) > 3:
            raise ValueError(f'{key}: node label must fit within three lines')
        if node.get('kind') not in KINDS or node.get('lane') not in lanes:
            raise ValueError(f'{key}: unknown node kind or lane')
        if not isinstance(node.get('column'), int) or not 0 <= node['column'] < 16:
            raise ValueError(f'{key}: column must be an integer from 0 to 15')
        if not isinstance(node.get('row', 0), int) or not 0 <= node.get('row', 0) < lanes[node['lane']].get('rows', 1):
            raise ValueError(f'{key}: row is outside lane')
    counts = Counter((n['lane'], n.get('row', 0), n['column']) for n in nodes.values())
    if any(count > 1 for count in counts.values()):
        raise ValueError('nodes share a lane, row and column; assign distinct slots')
    if graph.get('subtitle') and len(wrapped(graph['subtitle'], 80)) > 2:
        raise ValueError('subtitle must fit within two lines')
    for key, edge in edges.items():
        if edge.get('relation') not in TYPES or edge.get('source') not in nodes or edge.get('target') not in nodes:
            raise ValueError(f'{key}: unknown relation or endpoint')
        for face in ('source_port', 'target_port'):
            if face in edge and edge[face] not in {'left','right','top','bottom'}:
                raise ValueError(f'{key}: invalid {face}')
        if 'via' in edge and (not isinstance(edge['via'], list) or not edge['via'] or any(
                not isinstance(p, list) or len(p) != 2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in p)
                for p in edge['via'])):
            raise ValueError(f'{key}: via needs finite x,y point pairs')
        if edge['source'] == edge['target'] and 'via' not in edge:
            raise ValueError(f'{key}: self-loop requires explicit via points')
    return sources, lanes, nodes, edges


def touches_box(a, b, box, margin=4):
    # Liang-Barsky clipping, including a small line clearance.
    x, y, w, h = box
    dx, dy = b[0] - a[0], b[1] - a[1]
    lo, hi = 0.0, 1.0
    for p, q in ((-dx, a[0] - x + margin), (dx, x + w + margin - a[0]),
                 (-dy, a[1] - y + margin), (dy, y + h + margin - a[1])):
        if p == 0:
            if q < 0:
                return False
            continue
        cut = q / p
        if p < 0:
            lo = max(lo, cut)
        else:
            hi = min(hi, cut)
        if lo > hi:
            return False
    return True


def cross(a, b, c, d):
    def side(u, v, p):
        return (v[0]-u[0])*(p[1]-u[1]) - (v[1]-u[1])*(p[0]-u[0])
    if side(a, b, c) == side(a, b, d) == 0:
        axis = 0 if a[0] != b[0] else 1
        return min(max(a[axis], b[axis]), max(c[axis], d[axis])) > max(min(a[axis], b[axis]), min(c[axis], d[axis]))
    return side(a, b, c) * side(a, b, d) < 0 and side(c, d, a) * side(c, d, b) < 0


def ports(box):
    x, y, w, h = box
    return {'left': (x, y+h/2), 'right': (x+w, y+h/2), 'top': (x+w/2, y), 'bottom': (x+w/2, y+h)}


def segments(path):
    return [(a, b) for a, b in zip(path, path[1:]) if a != b]


def candidates(start, end, source_port, target_port):
    # A short stub ensures arrows enter and exit the selected node face.
    offsets = {'left': (-14, 0), 'right': (14, 0), 'top': (0, -14), 'bottom': (0, 14)}
    def offset(point, port):
        return tuple(a + b for a, b in zip(point, offsets[port]))
    a, b = offset(start, source_port), offset(end, target_port)
    yield [start, a, (a[0], b[1]), b, end]
    yield [start, a, (b[0], a[1]), b, end]
    for x in {(a[0]+b[0])/2, min(a[0], b[0])-24, max(a[0], b[0])+24}:
        yield [start, a, (x, a[1]), (x, b[1]), b, end]
    for y in {(a[1]+b[1])/2, min(a[1], b[1])-24, max(a[1], b[1])+24}:
        yield [start, a, (a[0], y), (b[0], y), b, end]


def route(edge, boxes, earlier, bounds):
    start_box, end_box = boxes[edge['source']], boxes[edge['target']]
    source_ports, target_ports = ports(start_box), ports(end_box)
    obstacles = [v for k, v in boxes.items() if k not in (edge['source'], edge['target'])]

    def cost(path):
        lines = segments(path)
        hits = sum(any(touches_box(a, b, box) for a, b in lines) for box in obstacles)
        hits += any(touches_box(a, b, start_box, -1) for a, b in lines)
        hits += any(touches_box(a, b, end_box, -1) for a, b in lines)
        outside = any(not(bounds[0] <= x <= bounds[2] and bounds[1] <= y <= bounds[3]) for x, y in path)
        conflicts = sum(cross(a,b,c,d) for a,b in lines for c,d in earlier)
        distance = sum(math.dist(a,b) for a,b in lines)
        return hits + int(outside), conflicts, distance + 14*len(lines)

    source_names = [edge['source_port']] if 'source_port' in edge else list(source_ports)
    target_names = [edge['target_port']] if 'target_port' in edge else list(target_ports)
    options = []
    for sp in source_names:
        for tp in target_names:
            a, b = source_ports[sp], target_ports[tp]
            if 'via' in edge:
                middle = [tuple(point) for point in edge['via']]
                options.append([a, *middle, b])
            elif a != b:
                options.extend(candidates(a, b, sp, tp))
    if not options:
        raise ValueError(f"{edge['id']}: no usable path")
    path = min(options, key=cost)
    return segments(path), cost(path)


def draw_edge(group, lines, relation, certainty='observed', width=2.7):
    color, _, marker, dash = TYPES[relation]
    if not lines:
        raise ValueError('edge path has zero length')
    dash = '3 5' if certainty in {'proposed', 'unknown'} else dash
    path = [lines[0][0], *(b for _, b in lines)]
    element(group, 'polyline', points=' '.join(f'{x:g},{y:g}' for x,y in path), fill='none',
            stroke=color, stroke_width=width, stroke_dasharray=dash or 'none', stroke_linejoin='round')
    if marker == 'none':
        return
    start, tip = lines[-1]
    angle = math.degrees(math.atan2(tip[1]-start[1], tip[0]-start[0]))
    head = element(group, 'g', transform=f'translate({tip[0]},{tip[1]}) rotate({angle})')
    if marker == 'bar':
        element(head, 'path', d='M-2,-7 L-2,7', fill='none', stroke=color, stroke_width=3.2)
    elif marker == 'open':
        element(head, 'path', d='M-10,-5 L0,0 L-10,5', fill='none', stroke=color, stroke_width=2.5)
    else:
        element(head, 'path', d='M0,0 L-10,-5 L-10,5 Z', fill=color)


def render(graph, mapping=None):
    _, lanes, nodes, edges = validate(graph)
    width = max(790, LEFT + max(n['column'] for n in nodes.values()) * DX + W + 60)
    lane_y = {}
    cursor = TOP
    for key, lane in lanes.items():
        lane_y[key] = cursor
        cursor += lane.get('rows', 1) * DY
    ncols = max(1, (width - 70) // 229)
    relations = list(dict.fromkeys(e['relation'] for e in edges.values()))
    qualifiers = any(e.get('certainty') in {'proposed', 'unknown'} for e in edges.values())
    legend_rows = max(1, math.ceil((len(relations) + int(qualifiers) + int(bool(graph.get('encoding')))) / ncols))
    height = cursor + 74 + legend_rows*28
    root = ET.Element(f'{{{SVG}}}svg', {'width': str(width), 'height': str(height), 'viewBox': f'0 0 {width} {height}', 'font-family': FONT, 'role': 'img'})
    element(root, 'title', graph['title'])
    element(root, 'desc', graph.get('subtitle') or 'Editable pathway. See graph.json for source IDs and locators.')
    back = layer(root, 'background', 'Canvas and compartments')
    element(back, 'rect', x=0, y=0, width=width, height=height, fill='#ffffff')
    title_size = max(16, min(34, (width - 80) * 1.7 / max(1, len(graph['title']))))
    text(back, 38, 54, graph['title'], round(title_size, 1), weight=700, id='diagram-title')
    for i, line in enumerate(wrapped(graph.get('subtitle', ''), 110)):
        text(back, 39, 82+i*18, line, 15, color='#52667b')
    for i, (key, lane) in enumerate(lanes.items()):
        ly = lane_y[key]
        lane_height = lane.get('rows', 1)*DY
        membrane = lane.get('kind') == 'membrane'
        fill = '#e4f1f0' if membrane else ('#eef5fc' if i % 2 == 0 else '#f1f6f5')
        region = element(back, 'g', id=f'lane-{key}')
        element(region, 'rect', x=36, y=ly, width=width-72, height=lane_height-3, rx=12, fill=fill)
        if membrane:
            for offset in (-13, 13):
                element(region, 'line', x1=151, x2=width-48, y1=ly+lane_height/2+offset,
                        y2=ly+lane_height/2+offset, stroke='#87b9b7', stroke_width=1.6)
        for j, line in enumerate(wrapped(lane['label'], 17)):
            text(region, 52, ly+25+j*17, line, 13, color='#3c5b70', weight=700)

    boxes = {key: (LEFT+n['column']*DX, lane_y[n['lane']] + n.get('row', 0)*DY + (DY-H)/2, W, H)
             for key, n in nodes.items()}
    edge_layer = layer(root, 'edges', 'Interactions')
    node_layer = layer(root, 'nodes', 'Entities')
    label_layer = layer(root, 'labels', 'Interaction labels')
    notes = []
    earlier = []
    edge_labels = {}
    for key, edge in edges.items():
        lines, score = route(edge, boxes, earlier, (151, TOP+4, width-43, cursor-4))
        if score[0]:
            notes.append({'kind': 'route_obstruction', 'id': key, 'count': score[0]})
        if score[1]:
            notes.append({'kind': 'edge_crossing_or_overlap', 'id': key, 'count': score[1]})
        g = element(edge_layer, 'g', id=f'edge-{key}', data_evidence=' '.join(edge['evidence']),
                    data_relation=edge['relation'], data_source=edge['source'], data_target=edge['target'])
        draw_edge(g, lines, edge['relation'], edge.get('certainty', 'observed'),
                  mapping['rows'][key]['width'] if mapping else 2.7)
        earlier.extend(lines)
        if edge.get('label'):
            edge_labels[key] = (lines, edge['label'])

    fixed_labels = []
    for key, (lines, label) in edge_labels.items():
        tw = max(36, max(len(line) for line in label.splitlines())*7.1+14)
        th = 9 + 16*len(label.splitlines())
        positions = []
        for a,b in sorted(lines, key=lambda item: -math.dist(*item)):
            for f in (.5, .32, .68, .2, .8):
                x,y = (a[0] + f*(b[0]-a[0]), a[1] + f*(b[1]-a[1]))
                positions.extend([(x-tw/2,y-th-6), (x-tw/2,y+7), (x+9,y-th/2), (x-tw-9,y-th/2)])
                for step in (17, 35):
                    positions.extend([(x-tw/2,y-th-step), (x-tw/2,y+step),
                                      (x+9,y-th/2-step), (x+9,y-th/2+step)])
        def label_cost(p):
            x,y = p
            if x < 155 or y < TOP+4 or x+tw > width-43 or y+th > cursor-4:
                return (10000, 0)
            overlaps = sum(x < bx+bw+4 and x+tw+4 > bx and y < by+bh+4 and y+th+4 > by for bx,by,bw,bh in (*boxes.values(), *fixed_labels))
            line_hits = sum(touches_box(a,b,(x,y,tw,th),1) for a,b in earlier)
            distance = min(math.dist((x+tw/2, y+th/2), ((a[0]+b[0])/2,(a[1]+b[1])/2)) for a,b in lines)
            return overlaps, line_hits, distance
        x,y = min(positions, key=label_cost)
        if label_cost((x,y))[0]:
            notes.append({'kind': 'label_needs_position', 'id': key, 'label': label})
            continue
        fixed_labels.append((x,y,tw,th))
        label_group = element(label_layer, 'g', id=f'edge-label-{key}')
        element(label_group, 'rect', x=x, y=y, width=tw, height=th, rx=5, fill='#ffffff', fill_opacity=.96)
        for j, line in enumerate(label.splitlines()):
            text(label_group, x+tw/2, y+16+16*j, line, 12, text_anchor='middle')

    encoding = graph.get('encoding')
    if encoding:
        if encoding.get('channel') != 'node_fill' or not encoding.get('label') or not encoding.get('categories'):
            raise ValueError('encoding needs node_fill, label and categories')
        categories = index(encoding['categories'], 'encoding categories')
        if any(not re.fullmatch(r'#[0-9a-fA-F]{6}', c.get('fill', '')) or not c.get('label') for c in categories.values()):
            raise ValueError('invalid encoding category label or fill')
        if any(len(c['label']) > 24 for c in categories.values()):
            raise ValueError('shorten encoding category labels to 24 characters')
    else:
        categories = {}

    for key, n in nodes.items():
        x,y,w,h = boxes[key]
        fill, stroke = KINDS[n['kind']]
        category = n.get('category')
        if category:
            if category not in categories:
                raise ValueError(f'{key}: unknown data category {category}')
            fill = categories[category]['fill']
        g = element(node_layer, 'g', id=f'node-{key}', data_kind=n['kind'], data_evidence=' '.join(n['evidence']),
                    data_category=category or '', data_lane=n['lane'])
        element(g, 'title', f"{n['label']} ({n['kind']}) · {', '.join(n['evidence'])}")
        element(g, 'rect', id=f'node-shape-{key}', x=x, y=y, width=w, height=h,
                rx=24 if n['kind']=='molecule' else 11, fill=fill, stroke=stroke, stroke_width=1.8)
        rows = wrapped(n['label'], 22)
        for j, line_text in enumerate(rows):
            text(g, x+w/2, y+h/2+5+(j-(len(rows)-1)/2)*15, line_text,
                 14, weight=700, text_anchor='middle', id=f'node-text-{key}-{j+1}')

    legend = layer(root, 'legend', 'Legend')
    text(legend, 38, cursor+24, 'Interaction key', 15, weight=700)
    legend_items = [(name, TYPES[name][1], 'observed') for name in relations]
    if qualifiers:
        legend_items.append(('activation', 'Dotted · uncertain', 'proposed'))
    for i,(name,label,certainty) in enumerate(legend_items):
        x,y = 40+(i%ncols)*229, cursor+46+(i//ncols)*28
        swatch = element(legend, 'g', id='key-'+(name if certainty=='observed' else 'uncertainty'))
        if certainty == 'observed':
            draw_edge(swatch, [((x,y),(x+31,y))], name)
        else:
            element(swatch, 'polyline', points=f'{x},{y} {x+31},{y}', fill='none',
                    stroke='#56687f', stroke_width=2.7, stroke_dasharray='3 5')
        text(swatch, x+41, y+5, label, 13)
    if categories:
        legend_top = cursor+54+math.ceil(len(legend_items)/ncols)*28
        text(legend, 38, legend_top, encoding['label'], 15, weight=700)
        for i,c in enumerate(categories.values()):
            x,y = 40+(i%ncols)*229, legend_top+24+(i//ncols)*28
            element(legend, 'rect', id='key-category-'+c['id'], x=x, y=y-12, width=19, height=15, rx=3, fill=c['fill'], stroke='#62788b')
            text(legend, x+27, y, c['label'], 13, id='key-category-label-'+c['id'])
        height = max(height, legend_top+35+math.ceil(len(categories)/ncols)*28)
        root.set('height', str(height))
        root.set('viewBox', f'0 0 {width} {height}')
        back[0].set('height', str(height))
    if mapping:
        import edge_scale
        edge_scale.legend(root, legend, mapping)
    return root, notes
