"""Audit the SVG itself against the copied source table and declared coordinate frames."""
import csv
import hashlib
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import Counter
import matplotlib as mpl
import numpy as np
from PIL import Image

def need(test, why):
    if not test: raise ValueError(why)

def pairs(d):
    return [(float(a),float(b)) for a,b in re.findall(r"[ML]\s*([-\d.eE+]+)[, ]+([-\d.eE+]+)",d)]

def verify(root):
    root=Path(root)
    read=lambda p:json.loads((root/p).read_text(encoding="utf8"))
    mapping=read("mapping.json");spec=read("figure.json");result=read("result.json")
    need(hashlib.sha256((root/"source.csv").read_bytes()).hexdigest()==mapping["source_sha256"]==result["input_sha256"],"Source checksum mismatch")
    with (root/"source.csv").open(encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f,delimiter=spec.get("delimiter",",")))
    tree=ET.parse(root/"figure.svg")
    ids={e.get("id"):e for e in tree.iter() if e.get("id")}
    need(len(ids)==sum(1 for e in tree.iter() if e.get("id")),"Duplicate SVG IDs")
    labels=[t.text or "" for t in tree.findall(".//{*}text")]
    need(labels,"Editable SVG text missing")
    frames=mapping["panels"];total=0
    reverse=set()
    for mark in mapping["marks"]:
        ident=mark["id"]; role=mark["role"]; geom=mark["geometry"]
        need(ident in ids,"Missing SVG element "+ident)
        obj=ids[ident];src=[rows[i-2] for i in mark["records"]]
        for i in mark["records"]:
            need(2<=i<=len(rows)+1,"Record out of range")
            for key in mark["fields"]:
                need(key in rows[i-2],"Absent field "+key);reverse.add((str(i),key,ident))
        fr=frames[mark["panel"]-1];left,top,w,h=fr["rect"]
        def fraction(v,axis):
            a,b=fr[axis+"lim"]
            if fr[axis+"scale"]=="log": v,a,b=map(math.log,(v,a,b))
            return (v-a)/(b-a)
        def px(x,y):
            return (left+w*fraction(x,"x"),top+h*(1-fraction(y,"y")))
        paths=[q for q in obj.findall(".//{*}path") if q.get("d") and not q.get("id")]
        vertices=pairs(paths[0].get("d")) if paths else []
        uses=[(float(e.get("x")),float(e.get("y"))) for e in obj.findall(".//{*}use") if e.get("x") is not None]
        def close(a,b):
            return bool(np.allclose(a,b,rtol=0,atol=.035))
        def compare(a,b):
            need(len(a)==len(b) and close(a,b),f"{ident}: geometry disagrees with CSV")
        def coord(r):
            return (geom["ix"] if "ix" in geom else float(r[geom["xfield"]]),float(r[geom["yfield"]]))
        if role in ("point","line"):
            expect=[px(*coord(r)) for r in src]
            compare(uses if role=="point" else vertices,expect)
        elif role=="interval":
            x,_=coord(src[0])
            compare(vertices,[px(x,float(src[0][key])) for key in geom["bounds"]])
        elif role=="bar":
            x,y=coord(src[0]);need(len(vertices)>=4,ident+": missing rectangle")
            xx=[p[0] for p in vertices[:4]]
            compare([((min(xx)+max(xx))/2,vertices[0][1]),((min(xx)+max(xx))/2,vertices[2][1])],[px(x,0),px(x,y)])
        elif role=="cell":
            val=float(src[0][geom["field"]]);lo,hi=geom["domain"]
            rgb=mpl.colors.to_hex(mpl.colormaps[geom["cmap"]]((val-lo)/(hi-lo)))
            need(rgb.lower() in paths[0].get("style","").lower(),ident+": wrong cell color")
            x,y=geom["ix"],geom["iy"]
            compare(vertices[:4],[px(x-.5,y-.5),px(x+.5,y-.5),px(x+.5,y+.5),px(x-.5,y+.5)])
        elif role=="annotation":
            need([t.text for t in obj.findall(".//{*}text")]==[src[0][geom["field"]]],ident+": annotation mismatch")
        elif role.startswith("box-"):
            values=np.array([float(r[geom["field"]]) for r in src])
            q1,med,q3=np.percentile(values,[25,50,75]);spread=q3-q1
            low=min(values[values>=q1-1.5*spread]);high=max(values[values<=q3+1.5*spread])
            low=min(low,q1);high=max(high,q3);side=geom.get("side",0);center=geom["ix"]
            if role=="box-fliers":
                outliers=np.concatenate((values[values<low],values[values>high]))
                compare(uses,[px(center,v) for v in outliers])
            else:
                expected={"box-medians":[med,med],"box-whiskers":[[q1,low],[q3,high]][side],
                          "box-caps":[[low,low],[high,high]][side],
                          "box-boxes":[q1,q1,q3,q3]}[role]
                compare([q[1] for q in vertices[:len(expected)]],[px(center,v)[1] for v in expected])
        elif role=="ols":
            x=[float(r[geom["xfield"]]) for r in src];y=[float(r[geom["yfield"]]) for r in src]
            a,b=np.polyfit(x,y,1);compare(vertices,[px(t,a*t+b) for t in (min(x),max(x))])
        else: continue
        total+=1
        if role in ("point","line","bar","interval","ols"):
            if mark["series"] and not (role=="interval" and spec["panels"][mark["panel"]-1]["kind"]=="bar"):
                legend=next(l for l in mapping["legends"] if l["panel"]==mark["panel"])
                col=legend["colors"][legend["labels"].index(mark["series"])]
                need(any(col.lower() in n.get("style","").lower() for n in obj.iter()),ident+": plotted color disagrees with legend")
            for r in src:
                x,y=coord(r)
                need(-1e-8<=fraction(x,"x")<=1.00000001 and -1e-8<=fraction(y,"y")<=1.00000001,ident+": point clipped by axis limits")
                if role=="interval":
                    need(all(-1e-8<=fraction(float(r[k]),"y")<=1.00000001 for k in geom["bounds"]),ident+": interval clipped")
    for legend in mapping["legends"]:
        if legend.get("mode") == "direct":
            for label,col in zip(legend["labels"],legend["colors"]):
                refs=[m for m in mapping["marks"] if m["panel"]==legend["panel"] and m["series"]==label and m["role"]=="annotation"]
                visible=[n for m in refs for n in ids[m["id"]].findall(".//{*}text") if n.text==label]
                need(len(visible)==1 and col.lower() in visible[0].get("style","").lower(),
                     "Direct series label absent or mismatched")
            continue
        item=ids["legend-"+str(legend["panel"])]
        texts=[q.text for q in item.findall(".//{*}text")]
        need(texts==legend["labels"],"Legend series/order mismatch")
        # Match legend handle styles in drawing order, allowing stroke and fill duplicates.
        found=[]
        for group in list(item):
            candidates=[q.get("style","").lower() for q in group.iter()]
            for col in legend["colors"]:
                if any(col.lower() in sty for sty in candidates):
                    found.append(col);break
        need(found==legend["colors"],"Legend handle colors mismatch")
    with (root/"reverse.csv").open(encoding="utf8",newline="") as f:
        need(set(map(tuple,list(csv.reader(f))[1:]))==reverse,"Reverse index incomplete")
    for p in spec["panels"]:
        for label in (p.get("title"),p.get("xlabel",p["x"]),p.get("ylabel",p["y"]),p.get("error_label")):
            if label: need(label in labels,"Missing editable label "+label)
    pdf=(root/"figure.pdf").read_bytes()
    need(pdf.startswith(b"%PDF-") and b"%%EOF" in pdf[-64:] and b"/FontFile2" in pdf,"Invalid PDF or embedded TrueType font missing")
    style=spec.get("style",{});mm=style.get("mm",[180,115]);dpi=style.get("dpi",300)
    with Image.open(root/"figure.png") as img:
        img.load();need(all(abs(a-v*dpi/25.4)<=1.1 for a,v in zip(img.size,mm)),"PNG physical size mismatch")
        need(all(abs(v-dpi)<.1 for v in img.info.get("dpi",[0])),"PNG resolution mismatch")
        if style.get("transparent"):need(img.mode=="RGBA" and img.getextrema()[3][0]==0,"Missing transparent background")
    return dict(status="pass",geometry_verified=total,svg_groups=len(mapping["marks"]),editable_text=len(labels),reverse_links=len(reverse),
                roles=dict(Counter(m["role"] for m in mapping["marks"])),warnings=result["uncertainty"])
if __name__=="__main__":
    print(json.dumps(verify(sys.argv[1]),ensure_ascii=True,indent=2))
