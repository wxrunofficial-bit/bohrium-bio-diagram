"""Check narrative structure, budget and the relation of each slide to evidence."""
import argparse,csv
from pathlib import Path
import scene
from deck import validate_plan


def plan(spec,out):
    duration=validate_plan(spec)
    scene.require(spec.get("audience") and spec.get("objective"),"Identify audience and its learning objective")
    head=[s["headline"].strip().replace("\n"," ") for s in spec["slides"]]
    scene.require(len(set(head))==len(head),"Duplicated slide headline")
    out.mkdir(parents=True,exist_ok=False)
    clock=0
    rows=[]
    for i,s in enumerate(spec["slides"],1):
        start=None if s.get("appendix") else clock
        if start is not None:
            clock+=s["seconds"]
        rows.append(dict(slide=i,id=s["id"],section="appendix" if start is None else "main",
                         start_seconds=start,duration_seconds=s["seconds"],role=s.get("role","finding"),
                         claim=head[i-1],transition=s["transition"],notes=s["notes"],
                         evidence=[{"id":key,**spec["sources"][key]} for key in s["evidence"]]))
    scene.write(out/"story.json",dict(case_id=spec["case_id"],audience=spec["audience"],objective=spec["objective"],
                     time=duration,buffer_seconds=spec["budget_seconds"]-duration["main"],rows=rows))
    with (out/"timing.csv").open("w",encoding="utf8",newline="") as f:
        fields=["slide","section","start_seconds","duration_seconds","role","claim","transition"]
        writer=csv.DictWriter(f,fields,extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print("Slideshow",len(rows),"slides, core",duration["main"],"seconds, appendix",duration["appendix"],"seconds")
    return rows

if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("spec",type=Path)
    a.add_argument("output",type=Path)
    v=a.parse_args()
    plan(scene.read(v.spec),v.output)
