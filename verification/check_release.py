"""Exercise the public Skill and confirm the persisted artifacts before packaging."""
import argparse
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

def run(root, output, previous=None):
    scripts=root/'scripts'
    examples=root/'examples'
    output.mkdir(parents=True,exist_ok=True)
    def call(script,*args,code=0):
        p=subprocess.run([sys.executable,'-B',str(script),*map(str,args)],capture_output=True,text=True)
        if p.returncode!=code:
            raise RuntimeError(f'{script.name}: {p.returncode}: {p.stdout} {p.stderr}')
        return p.stdout
    def read(file):
        return json.loads(file.read_text(encoding='utf-8'))
    def sha(file):
        return hashlib.sha256(file.read_bytes()).hexdigest()
    def render(name,mode,spec,*args):
        dest=output/name
        call(scripts/'pathway.py',mode,examples/spec,'--output',dest,*args)
        result=read(dest/'result.json')
        assert result['status']=='complete'
        assert all(sha(dest/a['path'])==a['sha256'] for a in result['artifacts'])
        assert all((dest/f'figure.{ext}').is_file() for ext in ('svg','png','pdf'))
        return result
    feedbacks=[]
    for i in range(3):
        feedbacks.append(render(f'feedback-{i}','draw','feedback.json','--edge-table',examples/'feedback.csv'))
        assert feedbacks[-1]['checks']['visible_semantics']['passed']
    hashes=[sha(output/f'feedback-{i}'/'figure.svg') for i in range(3)]
    assert len(set(hashes))==1
    probes=json.loads(call(examples/'check_feedback.py',output/'feedback-0'))
    diagram=render('insulin','draw','insulin.json')
    edit=render('edit','edit','edit.json','--source',output/'insulin/figure.svg')
    chart=render('chart','chart','chart.json','--source',examples/'chart.csv')
    assert len(edit['change_log'])==1 and edit['change_log'][0]['after']=='Insulin receptor (INSR)'
    with (examples/'chart.csv').open() as source:
        rows=list(csv.DictReader(source))
    mapped=read(output/'chart/source_mapping.json')['mapped_rows']
    assert len(rows)==len(mapped) and all(float(r['value'])==m['y'] for r,m in zip(rows,mapped))
    scale=read(output/'feedback-0/edge_mapping.json')
    assert scale['sha256']==sha(examples/'feedback.csv') and scale['rows']['feedback']['end_line']==2
    def width_hits(svg):
        doc=ET.parse(svg)
        expected={'trigger':6.0,'forward':4.0,'feedback':2.5}
        return sum(float(doc.find(f".//*[@id='edge-{key}']/{{*}}polyline").get('stroke-width'))==width for key,width in expected.items())
    result={'repeated_svg_hashes':hashes,'mutation_checks':probes,
            'correct_widths_out_of_3':{'current':width_hits(output/'feedback-0/figure.svg')},
            'exports':{k:r['checks']['export'] for k,r in [('feedback',feedbacks[0]),('insulin',diagram),('edit',edit),('chart',chart)]}}
    assert result['correct_widths_out_of_3']['current']==3
    if previous:
        dest=output/'previous'
        call(previous/'scripts/pathway.py','draw',examples/'feedback.json','--output',dest)
        result['correct_widths_out_of_3']['previous']=width_hits(dest/'figure.svg')
        assert result['correct_widths_out_of_3']['previous']==0
    invalid={'missing':'trigger,0.9\nforward,0.5','duplicate':'feedback,0.2\nfeedback,0.3',
             'outside':'feedback,1.1\ntrigger,0.9\nforward,0.5','nonfinite':'feedback,nan'}
    for name,body in invalid.items():
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            table=folder/'input.csv'
            table.write_text('interaction,weight\n'+body+'\n',encoding='utf-8')
            call(scripts/'pathway.py','draw',examples/'feedback.json','--edge-table',table,'--output',folder/'out',code=2)
            assert read(folder/'out/result.json')['status']=='failed' and not (folder/'out/figure.svg').exists()
    result['rejected_input_cases']=list(invalid)
    (output/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--previous',type=Path)
    a=p.parse_args()
    run(Path(__file__).resolve().parents[1],a.output,a.previous)
