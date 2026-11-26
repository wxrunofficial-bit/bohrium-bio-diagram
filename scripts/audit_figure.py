"""Check a generated pathway SVG against the reviewed graph and source CSV."""
import argparse
import json
import math
import re
from pathlib import Path

import edge_scale
import graph
import svgtools


def verify(root, spec, mapping=None):
    ids = svgtools.summarize(root)
    issues = []
    def check(ok, item, field):
        if not ok:
            issues.append({'id': item, 'field': field})
    def number(node, key):
        return float(node.get(key, 'nan')) if node is not None else math.nan
    def texts(node):
        return ' '.join(' '.join(node.itertext()).split()) if node is not None else ''
    def face(point, box):
        if box is None:
            return False
        x,y = point
        left,top,w,h = (number(box,k) for k in ('x','y','width','height'))
        right,bottom = left+w, top+h
        return ((min(abs(x-left),abs(x-right)) < .01 and top-.01 <= y <= bottom+.01)
                or (min(abs(y-top),abs(y-bottom)) < .01 and left-.01 <= x <= right+.01))
    def glyph(group, relation, certainty, width, item):
        line = group.find('{*}polyline') if group is not None else None
        color, _, kind, dash = graph.TYPES[relation]
        check(line is not None, item, 'stroke present')
        if line is None:
            return []
        check(line.get('stroke') == color, item, 'relation color')
        check(line.get('stroke-dasharray') == ('3 5' if certainty in ('unknown','proposed') else dash or 'none'), item, 'line pattern')
        check(math.isclose(number(line,'stroke-width'), width, abs_tol=.001), item, 'line width')
        pts=[tuple(map(float,p.split(','))) for p in line.get('points','').split()]
        head = group.find('{*}g')
        path = None if head is None else head.find('{*}path')
        shape = {'arrow':'M0,0 L-10,-5 L-10,5 Z','open':'M-10,-5 L0,0 L-10,5','bar':'M-2,-7 L-2,7'}
        if kind == 'none':
            check(head is None, item, 'undirected terminus')
        else:
            check(path is not None and path.get('d') == shape[kind], item, 'terminal glyph')
            if head is not None and len(pts)>=2:
                t=re.fullmatch(r'translate\(([^,]+),([^)]+)\) rotate\(([^)]+)\)', head.get('transform',''))
                angle=math.degrees(math.atan2(pts[-1][1]-pts[-2][1],pts[-1][0]-pts[-2][0]))
                check(t and math.dist((float(t[1]),float(t[2])),pts[-1])<.01
                      and abs((float(t[3])-angle+180)%360-180)<.01, item, 'terminal position/direction')
        return pts

    sources, _, nodes, edges = graph.validate(spec)
    groups = {k for k in ids if k.startswith('edge-') and ids[k].get('data-relation')}
    check(groups == {'edge-'+k for k in edges}, 'figure', 'edge inventory')
    check({k for k in ids if ids[k].get('data-kind')} == {'node-'+k for k in nodes}, 'figure', 'entity inventory')
    cats = {c['id']:c for c in spec.get('encoding',{}).get('categories',[])}
    for key, n in nodes.items():
        group, box = ids.get('node-'+key), ids.get('node-shape-'+key)
        check(group is not None and box is not None, key, 'entity shape')
        if group is None or box is None:
            continue
        label = ' '.join(texts(t) for t in group.findall('{*}text'))
        check(label == ' '.join(graph.wrapped(n['label'],22)), key, 'visible label')
        check(group.get('data-kind') == n['kind'] and group.get('data-lane') == n['lane'], key, 'class and compartment')
        lane=ids.get('lane-'+n['lane'])
        region=None if lane is None else lane.find('{*}rect')
        center=number(box,'y')+number(box,'height')/2
        check(number(region,'y') <= center <= number(region,'y')+number(region,'height'),key,'drawn compartment')
        check(group.get('data-evidence','').split()==n['evidence'],key,'entity provenance')
        expected = cats[n['category']]['fill'] if n.get('category') else graph.KINDS[n['kind']][0]
        check(box.get('fill')==expected, key, 'visible fill')
    for key,c in cats.items():
        swatch=ids.get('key-category-'+key)
        check(swatch is not None and swatch.get('fill')==c['fill']
              and texts(ids.get('key-category-label-'+key))==c['label'], key, 'categorical key')
    for key,e in edges.items():
        group=ids.get('edge-'+key)
        if group is not None:
            check(group.get('data-evidence','').split()==e['evidence'],key,'edge provenance')
        pts=glyph(group,e['relation'],e.get('certainty'),mapping['rows'][key]['width'] if mapping else 2.7,key)
        check(len(pts)>=2 and face(pts[0],ids.get('node-shape-'+e['source']))
              and face(pts[-1],ids.get('node-shape-'+e['target'])),key,'source and target attachment')
        if e.get('label'):
            check(texts(ids.get('edge-label-'+key))==' '.join(e['label'].split()),key,'visible interaction label')
    for rel in {e['relation'] for e in edges.values()}:
        key='key-'+rel
        swatch=ids.get(key)
        glyph(swatch,rel,'observed',2.7,key)
        check(texts(swatch)==graph.TYPES[rel][1],key,'legend label')
    if any(e.get('certainty') in ('unknown','proposed') for e in edges.values()):
        sample = ids.get('key-uncertainty')
        line = None if sample is None else sample.find('{*}polyline')
        check(line is not None and line.get('stroke-dasharray')=='3 5' and sample.find('{*}g') is None,
              'key-uncertainty','uncertainty is independent of interaction direction')
    if mapping:
        check(texts(ids.get('scale-title'))==f"{mapping['label']} ({mapping['unit']})",'scale','title and units')
        for i,tick in enumerate(mapping['ticks']):
            check(math.isclose(number(ids.get(f'scale-mark-{i}'),'stroke-width'),tick['width'],abs_tol=.001)
                  and texts(ids.get(f'scale-label-{i}'))==format(tick['value'],'.8g'),'scale',f'tick {i}')
    return {'passed': not issues, 'entities':len(nodes), 'interactions':len(edges),
            'source_records':len(sources), 'findings':issues}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('graph',type=Path)
    parser.add_argument('svg',type=Path)
    parser.add_argument('--edge-table',type=Path)
    args=parser.parse_args()
    spec=json.loads(args.graph.read_text(encoding='utf-8-sig'))
    report=verify(svgtools.read_svg(args.svg),spec,edge_scale.read(spec,args.edge_table))
    print(json.dumps(report,ensure_ascii=False,indent=2))
    raise SystemExit(0 if report['passed'] else 2)
