"""Draw a declarative evidence scene using editable shapes and live text."""
from pathlib import Path
from collections import Counter
from xml.etree import ElementTree as ET
import hashlib
import json
import math

NS="http://www.w3.org/2000/svg"
INK="http://www.inkscape.org/namespaces/inkscape"
ET.register_namespace("",NS)
ET.register_namespace("inkscape",INK)
INK_BLUE="#192633"
PAPER="#F6F3EC"
TEAL="#086F75"
RUST="#B34B32"
MUTED="#4C5D65"
GRID="#BCC6C3"

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))

def write(path,data):
    Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf8")

def require(condition,message):
    if not condition:
        raise ValueError(message)

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def item(tag,id,color,**values):
    return {"type":tag,"id":id,"color":color,**values}

def text(id,x,y,value,size,color=INK_BLUE,weight=400,evidence=None):
    obj=item("text",id,color,x=x,y=y,value=value,size=size,weight=weight)
    if evidence:
        obj["evidence"]=evidence
    return obj

def line(id,x,y,u,v,color=GRID,width=1.3,evidence=None):
    obj=item("line",id,color,x=x,y=y,u=u,v=v,width=width)
    if evidence:
        obj["evidence"]=evidence
    return obj

def dot(id,x,y,r,color=TEAL,evidence=None):
    obj=item("circle",id,color,x=x,y=y,r=r)
    if evidence:
        obj["evidence"]=evidence
    return obj

def rect(id,x,y,w,h,color=TEAL,evidence=None):
    obj=item("rect",id,color,x=x,y=y,w=w,h=h)
    if evidence:
        obj["evidence"]=evidence
    return obj

def points(panel,prefix,x,y,w,h):
    fields=panel["sets"]
    colors=panel.get("colors",[TEAL,TEAL,TEAL,TEAL])
    xlim=panel.get("xlim",[0,20])
    ylim=panel.get("ylim",[0,14])
    require(len(fields) in (1,2,3,4),"Use one to four small multiples")
    require(len(colors)>=len(fields),"Palette has fewer than the illustrated panels")
    nc=2 if len(fields)>1 else 1
    nr=math.ceil(len(fields)/nc)
    gapx,gapy=40,45
    cw=(w-(nc-1)*gapx)/nc
    ch=(h-(nr-1)*gapy)/nr
    out=[]
    for i,series in enumerate(fields):
        a=x+(i%nc)*(cw+gapx)
        b=y+(i//nc)*(ch+gapy)
        key=f"{prefix}-{i+1}"
        src=series.get("evidence",panel.get("evidence"))
        out.append(text(key+"-label",a,b,series["label"],17,weight=700,evidence=src))
        left,top=a+28,b+30
        graphw,graphh=cw-40,ch-53
        def coords(xx,yy):
            require(xlim[0]<=xx<=xlim[1] and ylim[0]<=yy<=ylim[1],key+": point outside declared axis")
            return left+(xx-xlim[0])*graphw/(xlim[1]-xlim[0]),top+(ylim[1]-yy)*graphh/(ylim[1]-ylim[0])
        for xt in panel.get("xticks",[]):
            px,py=coords(xt,ylim[0])
            out.append(line(key+"-xtick-"+str(xt),px,py,px,py+5,INK_BLUE,1))
            out.append(text(key+"-x-"+str(xt),px-7,py+19,str(xt),11,MUTED))
        for yt in panel.get("yticks",[]):
            px,py=coords(xlim[0],yt)
            out.append(line(key+"-ytick-"+str(yt),px-5,py,px,py,INK_BLUE,1))
            out.append(text(key+"-y-"+str(yt),px-25,py+4,str(yt),11,MUTED))
        ll=coords(xlim[0],ylim[0])
        out.extend([line(key+"-x-axis",*ll,*coords(xlim[1],ylim[0]),INK_BLUE),line(key+"-y-axis",*ll,*coords(xlim[0],ylim[1]),INK_BLUE)])
        if "guide" in series:
            p,q=series["guide"]
            out.append(line(key+"-guide",*coords(*p),*coords(*q),"#8E9B9B",1.8,src))
        for j,values in enumerate(series["xy"],1):
            px,py=coords(*values)
            accent=j in series.get("highlight_rows",[])
            obj=dot(key+"-mark-"+str(j),px,py,4.8 if accent else 3,RUST if accent else colors[i],src)
            obj["data"]={"row":j,"x":values[0],"y":values[1],"group":series["label"]}
            out.append(obj)
    return out

def elements(spec):
    results=[]
    for raw in spec["objects"]:
        if raw["type"]=="scatter":
            results.extend(points(raw,raw["id"],raw["x"],raw["y"],raw["w"],raw["h"]))
        else:
            results.append(raw)
    ids=[o["id"] for o in results]
    require(len(ids)==len(set(ids)),"Repeat object IDs")
    evidence=spec.get("sources",{})
    for obj in results:
        if obj.get("evidence"):
            require(all(key in evidence for key in obj["evidence"]),obj["id"]+": missing citation")
        if obj.get("data"):
            require(obj.get("evidence"),obj["id"]+": unmapped data mark")
    return results

def svg(spec,out):
    w,h=spec["size"]
    root=ET.Element(f"{{{NS}}}svg",{"width":str(w),"height":str(h),"viewBox":f"0 0 {w} {h}",
        "font-family":spec.get("font","DejaVu Sans, Noto Sans CJK SC, Microsoft YaHei, Sans Serif"),"role":"img"})
    def put(dst,tag,contents=None,**kw):
        el=ET.SubElement(dst,f"{{{NS}}}{tag}",{k.replace("_","-"):str(v) for k,v in kw.items()})
        el.text=contents
        return el
    put(root,"title",spec["title"])
    put(root,"desc",spec.get("description",spec["title"]))
    put(root,"rect",id="paper",x=0,y=0,width=w,height=h,fill=spec.get("background",PAPER))
    objects=elements(spec)
    for o in objects:
        g=put(root,"g",id=o["id"])
        g.set(f"{{{INK}}}groupmode","layer")
        g.set(f"{{{INK}}}label",o["id"])
        tag=o["type"]
        col=o["color"]
        x,y=o["x"],o["y"]
        if tag=="text":
            put(g,"text",o["value"],x=x,y=y,font_size=o["size"],font_weight=o.get("weight",400),fill=col)
        elif tag=="line":
            put(g,"line",x1=x,y1=y,x2=o["u"],y2=o["v"],stroke=col,stroke_width=o.get("width",1.5))
        elif tag=="circle":
            r=o["r"]
            put(g,"rect",x=x-r,y=y-r,width=2*r,height=2*r,rx=r,fill=col)
        elif tag=="rect":
            put(g,"rect",x=x,y=y,width=o["w"],height=o["h"],fill=col)
        else:
            raise ValueError("Unknown scene object "+tag)
    ET.ElementTree(root).write(out,encoding="utf-8",xml_declaration=True)
    return objects

def audit_svg(path,objects):
    root=ET.parse(path)
    index={g.get("id"):g for g in root.findall(".//{*}g")}
    for o in objects:
        node=list(index[o["id"]])[0]
        if o["type"]=="text":
            require(node.text==o["value"],o["id"]+": label mismatch")
        if o["type"]=="circle":
            require(abs(float(node.get("x"))+o["r"]-o["x"])<.01 and abs(float(node.get("y"))+o["r"]-o["y"])<.01,
                    o["id"]+": coordinate mismatch")
    return dict(Counter(o["type"] for o in objects))

def lookups(objects,sources):
    forward={o["id"]:{k:o[k] for k in ("evidence","data") if k in o} for o in objects if "evidence" in o}
    reverse={key:[k for k,v in forward.items() if key in v["evidence"]] for key in sources}
    return dict(sources=sources,objects=forward,source_to_objects=reverse)
