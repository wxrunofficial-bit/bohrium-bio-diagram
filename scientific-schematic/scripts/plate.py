"""Evidence-linked scientific drawings with independently audited SVG geometry."""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from xml.etree import ElementTree as ET
import svgtools


NS = "http://www.w3.org/2000/svg"
INK = "http://www.inkscape.org/namespaces/inkscape"
ET.register_namespace("", NS)
ET.register_namespace("inkscape", INK)
COLORS = {
    "material": "#007280", "pressure": "#2455A4", "signal": "#8555A2",
    "light": "#BA691D", "sequence": "#32465F", "proposed": "#827287",
    "inhibits": "#A64044", "association": "#486F78",
}
PALE = {"material":"#E3F2F0","pressure":"#E9F1FA","signal":"#F4EBFA",
        "light":"#FFF0D6","sequence":"#EBF0F6","proposed":"#F3EDF7",
        "inhibits":"#FCECE9","association":"#E7F0EF"}


def require(test, message):
    if not test:
        raise ValueError(message)


def indexes(items):
    result={item["id"]:item for item in items}
    require(len(result)==len(items),"Duplicate identifier")
    for ident in result:
        require(bool(ident) and all(c.isascii() and (c.isalnum() or c in "._-") for c in ident),
                f"Bad identifier {ident!r}")
    return result


def add(parent, tag, value=None, **attrs):
    node=ET.SubElement(parent,f"{{{NS}}}{tag}",{k.replace("_","-"):str(v) for k,v in attrs.items()})
    node.text=value
    return node


def text(parent,x,y,label,size=15,anchor="start",weight=400,**attrs):
    return add(parent,"text",label,x=x,y=y,font_size=size,text_anchor=anchor,font_weight=weight,
               fill=attrs.pop("fill","#102A43"),**attrs)


def layer(parent, ident, name):
    group=add(parent,"g",id=ident)
    group.set(f"{{{INK}}}groupmode","layer")
    group.set(f"{{{INK}}}label",name)
    return group


def box_contains(box, point):
    x,y,w,h=box
    return x<=point[0]<=x+w and y<=point[1]<=y+h


def intersects(a,b):
    return max(a[0],b[0])<min(a[0]+a[2],b[0]+b[2]) and max(a[1],b[1])<min(a[1]+a[3],b[1]+b[3])


def port(node,name):
    x,y,w,h=node["box"]
    sides={"W":(0,.5),"E":(1,.5),"N":(.5,0),"S":(.5,1)}
    a,b=node.get("ports",{}).get(name,sides.get(name,(None,None)))
    require(a is not None and 0<=a<=1 and 0<=b<=1 and (a in (0,1) or b in (0,1)),
            f"{node['id']}: {name} must identify a port on the boundary")
    return (x+a*w,y+b*h)


def port_gate(node,name,point,distance=12):
    x,y,w,h=node["box"]
    px,py=point
    if px==x: return (px-distance,py)
    if px==x+w: return (px+distance,py)
    if py==y: return (px,py-distance)
    return (px,py+distance)


def crossing_box(start,end,box):
    x,y,w,h=box[0]+1,box[1]+1,box[2]-2,box[3]-2
    left,top,right,bottom=x,y,x+w,y+h
    lower,upper=0.,1.
    dx,dy=end[0]-start[0],end[1]-start[1]
    for p,q in ((-dx,start[0]-left),(dx,right-start[0]),(-dy,start[1]-top),(dy,bottom-start[1])):
        if p==0:
            if q<0:
                return False
            continue
        t=q/p
        if p<0:
            lower=max(t,lower)
        else:
            upper=min(t,upper)
        if lower>upper:
            return False
    return True


def proper_cross(a,b,c,d):
    def turn(p,q,r):
        return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
    return turn(a,b,c)*turn(a,b,d)<0 and turn(c,d,a)*turn(c,d,b)<0


def layout(panel, nodes):
    routes={}
    alerts=[]
    edges=indexes(panel.get("edges",[]))
    for edge in edges.values():
        a,b=edge["source"],edge["target"]
        require(a!=b,"Route a self relation through a separate process node with explicit evidence")
        first,last=port(nodes[a],edge["out"]),port(nodes[b],edge["in"])
        start=port_gate(nodes[a],edge["out"],first)
        end=port_gate(nodes[b],edge["in"],last)
        if "via" in edge:
            candidates=[[start,*[tuple(p) for p in edge["via"]],end]]
        else:
            x,y=start
            u,v=end
            midx,midy=(x+u)/2,(y+v)/2
            candidates=[[start,end]] if x==u or y==v else []
            candidates.extend(([start,(midx,y),(midx,v),end],[start,(x,midy),(u,midy),end],
                               [start,(x,v),end],[start,(u,y),end]))
        def score(route):
            cuts=0
            for start,end in zip(route,route[1:]):
                cuts+=sum(crossing_box(start,end,n["box"]) for n in nodes.values())
            crosses=sum(proper_cross(p,q,s,t) for p,q in zip(route,route[1:])
                        for other in routes.values() for s,t in zip(other,other[1:]))
            length=sum(math.dist(p,q) for p,q in zip(route,route[1:]))
            return cuts,crosses,length
        guarded=[[first,*r,last] for r in candidates]
        candidates=[list(p for i,p in enumerate(r) if i==0 or p!=r[i-1]) for r in guarded]
        options=[r for r in candidates if len(r)>1 and all(box_contains(panel["box"],p) for p in r)]
        require(options,f"{edge['id']}: empty route or route leaves panel")
        route=min(options,key=score)
        cuts,crosses,_=score(route)
        require(cuts==0,f"{edge['id']}: route crosses component body. Change port or add via waypoints.")
        if crosses:
            alerts.append(edge["id"]+" crosses another route; no junction is implied. Verify legibility.")
        routes[edge["id"]]=route
    return routes,alerts


def validate(spec, profile):
    width,height=spec["size"]
    require(360<=width<=4200 and 220<=height<=4200 and int(width)==width and int(height)==height,
            "Canvas must use integer dimensions within 360–4200 × 220–4200")
    require(spec["case_id"] and spec["title"],"Provide case_id and figure title")
    sources=indexes(spec["sources"])
    require(sources,"At least one real source is required")
    for source in sources.values():
        require(all(str(source.get(k,"")).strip() for k in ["document","location","statement"]),
                f"{source['id']}: source needs document, location and checked statement")
    panels=indexes(spec["panels"])
    require(panels,"At least one panel is required")
    all_ids=set()
    def check(item):
        require(item["id"] not in all_ids,f"Figure-wide duplicate {item['id']}")
        all_ids.add(item["id"])
        require(item.get("evidence") and all(k in sources for k in item["evidence"]),
                f"{item['id']}: no linked evidence")
    for panel in panels.values():
        nodes=indexes(panel["nodes"])
        require(nodes and panel.get("title"),"Every panel requires a title and components")
        x,y,w,h=panel["box"]
        require(x>=12 and y>=72 and w>=140 and h>=120 and x+w<=width-12 and y+h<=height-36,
                f"{panel['id']}: panel outside content area")
        for i,node in enumerate(nodes.values()):
            check(node)
            a,b,c,d=node["box"]
            require(c>=40 and d>=28 and a>=x+9 and b>=y+45 and a+c<=x+w-9 and b+d<=y+h-9,
                    f"{node['id']}: node does not fit in content area")
            require(not any(intersects(node["box"],other["box"]) for other in list(nodes.values())[:i]),
                    f"{node['id']}: component overlap")
            require(node.get("label"),f"{node['id']}: label missing")
            if profile=="apparatus":
                require(node.get("kind") in ("instrument","port","sample","process","data","control"),
                        f"{node['id']}: explicit apparatus kind required")
        for edge in panel.get("edges",[]):
            check(edge)
            require(edge["source"] in nodes and edge["target"] in nodes,"Missing connection endpoint in panel")
            require(edge.get("style") in COLORS,"Select a relation/flow type")
            if profile=="apparatus":
                require(edge["style"] in ("material","pressure","signal","light","sequence","proposed"),
                        "Use distinct signal, material, pressure, light or sequence connections")
                for endpoint,key in (("source","out"),("target","in")):
                    require(edge[key] in nodes[edge[endpoint]].get("ports",{}),
                            f"{edge['id']}: explicit apparatus ports required")
        for label in panel.get("callouts",[]):
            check(label)
            require(box_contains(panel["box"],label["at"]), "Callout outside panel")
    for i,p in enumerate(panels.values()):
        require(not any(intersects(p["box"],q["box"]) for q in list(panels.values())[:i]),"Panels overlap")
    return panels,sources


def draw_arrow(group, points, style, ident):
    line={"stroke":COLORS[style],"stroke_width":2.6,"fill":"none","stroke_linejoin":"round"}
    if style in ("proposed","signal"):
        line["stroke_dasharray"]="6 4"
    add(group,"polyline",id=ident+"-route",points=" ".join(f"{x:.6g},{y:.6g}" for x,y in points),**line)
    if style=="association":
        return
    end=points[-1]
    dx,dy=end[0]-points[-2][0],end[1]-points[-2][1]
    d=math.hypot(dx,dy)
    vx,vy=dx/d,dy/d
    x,y=end
    left=(x-vx*11-4.8*vy,y-vy*11+4.8*vx)
    right=(x-vx*11+4.8*vy,y-vy*11-4.8*vx)
    if style=="inhibits":
        add(group,"line",x1=x-6*vy,y1=y+6*vx,x2=x+6*vy,y2=y-6*vx,stroke=COLORS[style],stroke_width=2.6)
    else:
        tri="M"+f"{x:.4f},{y:.4f}"+"".join(f" L{a:.4f},{b:.4f}" for a,b in (left,right))+" Z"
        add(group,"path",d=tri,fill=COLORS[style])


def render(spec,profile):
    panels,sources=validate(spec,profile)
    width,height=spec["size"]
    root=ET.Element(f"{{{NS}}}svg",{"width":str(width),"height":str(height),"viewBox":f"0 0 {width} {height}",
           "font-family":"DejaVu Sans, Noto Sans CJK SC, Microsoft YaHei, Sans Serif","role":"img"})
    add(root,"title",spec["title"])
    add(root,"desc",spec.get("description","Evidence-linked scientific figure"))
    base=layer(root,"backdrop","Canvas")
    add(base,"rect",x=0,y=0,width=width,height=height,fill="#FFFFFF")
    text(base,24,35,spec["title"],24,weight=700)
    if spec.get("subtitle"):
        text(base,24,57,spec["subtitle"],13,fill="#465F72")
    mapping={}
    alerts=[]
    types=[]
    for p in panels.values():
        x,y,w,h=p["box"]
        background=layer(root,"panel-"+p["id"],p["title"])
        add(background,"rect",x=x,y=y,width=w,height=h,rx=10,fill="#F8FAFC",stroke="#C7D4DE")
        text(background,x+15,y+26,p["title"],17,weight=700)
        nodes=indexes(p["nodes"])
        routes,notes=layout(p,nodes)
        alerts.extend(notes)
        flows=layer(root,"routes-"+p["id"],"Relations")
        for edge in p.get("edges",[]):
            ident=edge["id"]
            mode=edge["style"]
            group=add(flows,"g",id="data-"+ident,data_source=edge["source"],data_target=edge["target"])
            draw_arrow(group,routes[ident],mode,"data-"+ident)
            if mode not in types:
                types.append(mode)
            mapping[ident]={**edge,"panel":p["id"],"geometry":[list(q) for q in routes[ident]]}
        shapes=layer(root,"components-"+p["id"],"Entities")
        for node in nodes.values():
            ident=node["id"]
            a,b,c,d=node["box"]
            tint=node.get("style","sequence")
            require(tint in PALE,f"Unknown entity style {tint}")
            group=add(shapes,"g",id="data-"+ident)
            add(group,"rect",id="data-"+ident+"-box",x=a,y=b,width=c,height=d,rx=4 if node.get("kind")=="instrument" else 9,
                fill=PALE[tint],stroke=COLORS[tint],stroke_width=1.4)
            lines=node["label"].split("\n")
            line_height=float(node.get("font_size",15))+3
            if line_height*len(lines)>d-5 or any(len(line)*line_height*.52>c-12 for line in lines):
                alerts.append(ident+": inspect fitted entity label; wrap or enlarge the box.")
            for i,label in enumerate(lines):
                text(group,a+c/2,b+d/2+(i-(len(lines)-1)/2)*line_height+4,label,line_height-3,"middle",700,
                     id="data-"+ident+"-text-"+str(i))
            for key in node.get("show_ports",[]):
                tx,ty=port(node,key)
                add(group,"rect",x=tx-2,y=ty-2,width=4,height=4,rx=1,fill=COLORS[tint])
            mapping[ident]={**node,"panel":p["id"]}
        labels=layer(root,"notes-"+p["id"],"Annotations")
        for label in p.get("callouts",[]):
            text(labels,*label["at"],label["text"],int(label.get("font_size",13)),label.get("anchor","start"),id="data-"+label["id"])
            mapping[label["id"]]={**label,"panel":p["id"]}
    footer=layer(root,"legend","Legend")
    if spec.get("caption"):
        text(footer,24,height-12,spec["caption"],12,fill="#465F72")
    shown=spec.get("legend",{})
    for i,mode in enumerate(types):
        x=25+(width-45)*i/len(types)
        draw_arrow(footer,[(x,height-29),(x+26,height-29)],mode,"legend-"+mode)
        text(footer,x+34,height-25,shown.get(mode,mode.title()),11)
    return root,mapping,sources,alerts


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_write(path, data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf8")


def audit(svg,mapping):
    root=ET.parse(svg).getroot()
    ids=svgtools.summarize(root)
    counts={"connections":0,"entities":0,"annotations":0}
    for ident,item in mapping.items():
        prefix="data-"+ident
        obj=ids[prefix]
        if "geometry" in item:
            route=ids[prefix+"-route"]
            actual=[tuple(map(float,p.split(","))) for p in route.get("points").split()]
            require(len(actual)==len(item["geometry"]) and all(math.dist(a,b)<=.02 for a,b in zip(actual,item["geometry"])),
                    ident+": rendered path deviates from evidence map")
            require(obj.get("data-source")==item["source"] and obj.get("data-target")==item["target"],
                    ident+": endpoints reversed or swapped")
            for point,name,label in ((actual[0],item["source"],item["out"]),(actual[-1],item["target"],item["in"])):
                entity=mapping[name]
                require(math.dist(point,port(entity,label))<=.02,ident+": connection misses its named port")
            require(route.get("stroke")==COLORS[item["style"]],ident+": connection type color mismatch")
            marker=obj.find(f"{{{NS}}}path")
            if item["style"] not in ("association","inhibits"):
                hx,hy=map(float,marker.get("d").split()[0][1:].split(","))
                require(math.dist((hx,hy),actual[-1])<=.02,ident+": arrowhead does not point at target")
            counts["connections"]+=1
        elif "box" in item:
            box=ids[prefix+"-box"]
            require([float(box.get(k)) for k in ("x","y","width","height")]==item["box"],ident+": entity geometry changed")
            require([n.text for n in obj.findall(f"{{{NS}}}text")]==item["label"].split("\n"),ident+": entity text mismatch")
            counts["entities"]+=1
        else:
            require(obj.text==item["text"],ident+": annotation text mismatch")
            counts["annotations"]+=1
    return counts


def run(path,out,profile):
    spec=json.loads(path.read_text(encoding="utf-8-sig"))
    root,mapping,sources,alerts=render(spec,profile)
    out.mkdir(exist_ok=False,parents=True)
    svgtools.write_svg(root,out/"figure.svg")
    report=audit(out/"figure.svg",mapping)
    json_write(out/"figure-spec.json",spec)
    index={key:sorted(ident for ident,item in mapping.items() if key in item["evidence"]) for key in sources}
    json_write(out/"source-map.json",{"elements":mapping,"sources":sources,"source_to_elements":index})
    result={"case_id":spec["case_id"],"status":"needs_review" if alerts else "ok","source_spec_sha256":file_hash(path),
            "artifacts":["figure.svg","figure-spec.json","source-map.json","result.json"],"checks":report,
            "sources":list(sources.values()),"changes":spec.get("changes",[]),"uncertainty":alerts}
    try:
        result["exports"]=svgtools.export(out/"figure.svg",root,float(spec.get("raster_scale",2)))
        result["artifacts"].extend(["figure.pdf","figure.png"])
    except Exception as exc:
        result["status"]="partial"
        alerts.append(str(exc))
    json_write(out/"result.json",result)
    print(json.dumps({"status":result["status"],"checks":report,"uncertainty":alerts},ensure_ascii=True))
    return int(result["status"]=="partial")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec",type=Path)
    parser.add_argument("out",type=Path)
    parser.add_argument("--profile",choices=("schematic","apparatus"),required=True)
    args=parser.parse_args()
    try:
        sys.exit(run(args.spec,args.out,args.profile))
    except (ValueError, KeyError, OSError) as error:
        print(json.dumps({"status":"failed","error":str(error)},ensure_ascii=True),file=sys.stderr)
        sys.exit(2)
