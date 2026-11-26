"""Recheck a generated example and probe whether visible SVG errors are detected."""
import argparse
import copy
import json
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
sys.path.insert(0,str(here.parent/'scripts'))
import audit_figure
import edge_scale
import svgtools


def run(folder):
    spec=json.loads((here/'feedback.json').read_text(encoding='utf-8'))
    mapping=edge_scale.read(spec,here/'feedback.csv')
    root=svgtools.read_svg(folder/'figure.svg')
    original=audit_figure.verify(root,spec,mapping)
    if not original['passed']:
        raise ValueError(original['findings'])
    probes=[
        ('scale drift', 'edge-feedback', '{*}polyline','stroke-width','8','line width'),
        ('sign change', 'edge-feedback','{*}g/{*}path','d','M0,0 L-10,-5 L-10,5 Z','terminal glyph'),
        ('direction change', 'edge-feedback','{*}polyline','points','0,0 10,10','source and target attachment'),
        ('lost uncertainty', 'edge-feedback','{*}polyline','stroke-dasharray','none','line pattern'),
        ('wrong category key', 'key-category-input',None,'fill','#000000','categorical key'),
        ('unit drift', 'scale-title',None,'text','Weight (%)','title and units'),
        ('label drift', 'node-text-relay-1',None,'text','Cue','visible label'),
        ('displaced glyph', 'node-shape-relay',None,'y','0','drawn compartment'),
    ]
    caught=[]
    for name,key,child,field,value,expected in probes:
        variant=copy.deepcopy(root)
        node=svgtools.summarize(variant)[key]
        if child:
            node=node.find(child)
        if field=='text':
            node.text=value
        else:
            node.set(field,value)
        result=audit_figure.verify(variant,spec,mapping)
        if expected not in {issue['field'] for issue in result['findings']}:
            raise ValueError(f'{name} escaped detection')
        caught.append(name)
    return {'clean_figure_passed':True,'detected':caught}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder',type=Path)
    print(json.dumps(run(parser.parse_args().folder),indent=2))
