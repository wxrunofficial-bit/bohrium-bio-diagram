"""Inspect / patch supplied SVG objects with a checked before-value."""
import argparse
import copy
import csv
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET
import svgtools as sv

def read_original(path):
    # Accept Matplotlib's fixed SVG 1.1 DOCTYPE, without fetching its DTD.
    raw=path.read_bytes()
    raw=re.sub(rb'<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN"\s+"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">',b'',raw)
    with tempfile.TemporaryDirectory() as d:
        safe=Path(d)/"source.svg";safe.write_bytes(raw)
        return sv.read_svg(safe)

def inventory(root):
    def walk(node,where):
        if isinstance(node.tag,str):
            yield where,node
        for i,child in enumerate(node):
            yield from walk(child,where+"/"+str(i))
    return dict(walk(root,"0"))

def run(src,plan,out):
    root=read_original(src); nodes=inventory(root); ids=sv.summarize(root)
    before={k:sv.node_payload(v) for k,v in nodes.items()}
    by_obj={id(v):k for k,v in nodes.items()}
    changes=[];touch=set()
    for op in plan["operations"]:
        node=ids[op["id"]] if "id" in op else nodes[op["path"]]
        path=by_obj[id(node)];field=op["field"];val=op["value"]
        if not op.get("source") or not op.get("reason") or (path,field) in touch: raise ValueError("Missing evidence or duplicate edit")
        if field=="text":
            if sv.local(node.tag) not in ("text","tspan","title","desc") or len(node): raise ValueError("Select a leaf text element")
            old=node.text or ""
        elif field.startswith("style."):
            prop=field[6:]
            if prop not in ("fill","stroke","stroke-width","font-size","font-weight","opacity","stroke-dasharray"): raise ValueError("Unsupported style property")
            parts=[p.strip() for p in node.get("style","").split(";") if p.strip()]
            sty=dict(v.split(":",1) for v in parts);old=sty.get(prop);old=old.strip() if old else old
        elif field in ("fill","stroke","stroke-width","font-size","opacity","x","y","width","height","d","points","transform"):
            old=node.get(field)
        else: raise ValueError("Unsupported edit field "+field)
        if old!=op["expected"]: raise ValueError(f"{path}.{field}: expected {op['expected']!r}, source has {old!r}")
        if field!="text" and not re.fullmatch(r"[A-Za-z0-9_.,%#+() \t-]+",val): raise ValueError("Invalid attribute value")
        if field=="text":node.text=val
        elif field.startswith("style."):
            sty[prop]=val;node.set("style","; ".join(k+":"+v for k,v in sty.items()))
        else:node.set(field,val)
        touch.add((path,field));changes.append(dict(path=path,id=node.get("id"),field=field,before=old,after=val,source=op["source"],reason=op["reason"]))
    touched={p for p,_ in touch}
    if any(before[p]!=sv.node_payload(node) for p,node in nodes.items() if p not in touched):raise ValueError("Untargeted node changed")
    out.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(src,out/"original.svg");sv.write_svg(root,out/"figure.svg")
    result=dict(case_id=plan["case_id"],status="partial",input_sha256=sv.digest(src),changes=changes,
                untouched_nodes=len(nodes)-len(touched),outputs=["original.svg","figure.svg","edit.json"],uncertainty=[])
    def save(name,obj): (out/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf8")
    save("edit.json",plan)
    try:
        result["export"]=sv.export(out/"figure.svg",root,float(plan.get("scale",2)))
        result["outputs"].extend(["figure.png","figure.pdf"]);result["status"]="ok"
    except Exception as exc:result["uncertainty"].append(str(exc))
    save("result.json",result);print(json.dumps(result,ensure_ascii=True))
    return result["status"]!="ok"

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("source",type=Path);ap.add_argument("plan",type=Path,nargs="?");ap.add_argument("out",type=Path,nargs="?")
    args=ap.parse_args()
    if args.plan and args.out:sys.exit(run(args.source,json.loads(args.plan.read_text(encoding="utf-8-sig")),args.out))
    for key,n in inventory(read_original(args.source)).items():
        print(json.dumps(dict(path=key,tag=sv.local(n.tag),id=n.get("id"),text=(n.text or "").strip()[:160],attributes=n.attrib),ensure_ascii=True))
