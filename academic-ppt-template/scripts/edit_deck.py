"""Edit a bounded part of a PPTX while proving all other ZIP members survive."""
import argparse
from copy import copy
import json
from pathlib import Path
import posixpath
from zipfile import ZipFile
from lxml import etree

P="http://schemas.openxmlformats.org/presentationml/2006/main"
A="http://schemas.openxmlformats.org/drawingml/2006/main"
R="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS={"p":P,"a":A,"r":R}


def parse(payload):
    return etree.fromstring(payload,parser=etree.XMLParser(resolve_entities=False,no_network=True))


def one(obj,query):
    return obj.find(query,NS)


def all_of(obj,query):
    return obj.findall(query,NS)


def shape_list(root):
    return [(int(c.get("id")),c.get("name"),c.getparent().getparent()) for c in all_of(root,".//p:cNvPr")
            if c.getparent().getparent().tag!=f"{{{P}}}spTree"]


def manifest(z):
    p=parse(z.read("ppt/presentation.xml"))
    rels=parse(z.read("ppt/_rels/presentation.xml.rels"))
    links={r.get("Id"):r.get("Target") for r in rels}
    members=[posixpath.normpath(posixpath.join("ppt",links[s.get(f"{{{R}}}id")]))
             for s in all_of(p,"p:sldIdLst/p:sldId")]
    size=one(p,"p:sldSz")
    support=[n for n in z.namelist() if n.startswith(("ppt/slideMasters/","ppt/slideLayouts/","ppt/theme/")) and n.endswith(".xml")]
    return members,dict(size.attrib),support


def inspect(z):
    slides,size,support=manifest(z)
    report=[]
    for i,name in enumerate(slides,1):
        root=parse(z.read(name))
        objs=[]
        for key,label,shape in shape_list(root):
            texts=[n.text or "" for n in all_of(shape,"p:txBody/a:p/a:r/a:t")]
            geom=one(shape,"p:spPr/a:xfrm")
            ph=one(shape,".//p:ph")
            props=dict(id=key,name=label,run_text=texts,placeholder=dict(ph.attrib) if ph is not None else None)
            if geom is not None:
                o,e=one(geom,"a:off"),one(geom,"a:ext")
                props["box_emu"]=[int(o.get("x")),int(o.get("y")),int(e.get("cx")),int(e.get("cy"))]
            objs.append(props)
        report.append(dict(slide=i,zip_member=name,objects=objs))
    return dict(size_emu=size,template_parts=support,slides=report)


def patch(input_path,plan,output,mode):
    if output.exists() or input_path.resolve()==output.resolve():
        raise ValueError("Choose a fresh output PPTX")
    if mode=="adapt" and not plan.get("template_source"):
        raise ValueError("Identify the supplied template and layout constraints")
    changed={}
    operations=[]
    edited=set()
    with ZipFile(input_path) as z:
        if len(z.namelist())!=len(set(z.namelist())):
            raise ValueError("The package has duplicate ZIP keys")
        slide_names,size,support=manifest(z)
        for e in plan["operations"]:
            if not(e.get("source") and e.get("reason")):
                raise ValueError("Each edit needs evidence and a reason")
            ident=(e["slide"],e["shape_id"],e["action"],e.get("run",0))
            if ident in edited:
                raise ValueError("Repeated edit target")
            edited.add(ident)
            if not 1<=e["slide"]<=len(slide_names):
                raise ValueError("Slide index out of range")
            name=slide_names[e["slide"]-1]
            if name not in changed:
                changed[name]=parse(z.read(name))
            shape=next((o for key,_,o in shape_list(changed[name]) if key==e["shape_id"]),None)
            if shape is None:
                raise ValueError("Object ID absent")
            action=e["action"]
            runs=all_of(shape,"p:txBody/a:p/a:r")
            if action in ("text","font_size"):
                run=runs[e.get("run",0)]
                if action=="text":
                    t=one(run,"a:t")
                    old=t.text or ""
                    if old!=e["expected"]:
                        raise ValueError("Stale text value")
                    t.text=e["value"]
                else:
                    p=one(run,"a:rPr")
                    old=int(p.get("sz")) if p is not None and p.get("sz") is not None else None
                    if old!=e["expected"] or not 800<=e["value"]<=12000:
                        raise ValueError("Stale font size or requested size outside 8–120 pt")
                    if p is None:
                        p=etree.Element(f"{{{A}}}rPr")
                        run.insert(0,p)
                    p.set("sz",str(e["value"]))
            elif action=="box":
                xfrm=one(shape,"p:spPr/a:xfrm")
                off,ext=one(xfrm,"a:off"),one(xfrm,"a:ext")
                old=[int(off.get("x")),int(off.get("y")),int(ext.get("cx")),int(ext.get("cy"))]
                x,y,w,h=e["value"]
                if old!=e["expected"] or min(x,y)<0 or min(w,h)<=0 or x+w>int(size["cx"]) or y+h>int(size["cy"]):
                    raise ValueError("Stale or off-canvas box")
                for node,key,value in ((off,"x",x),(off,"y",y),(ext,"cx",w),(ext,"cy",h)):
                    node.set(key,str(value))
            else:
                raise ValueError("Unsupported operation "+action)
            operations.append({**e,"old":old,"member":name})
        if not operations:
            raise ValueError("No edits supplied")
        output.parent.mkdir(exist_ok=True,parents=True)
        with ZipFile(output,"x") as out:
            for member in z.infolist():
                payload=etree.tostring(changed[member.filename],encoding="UTF-8",xml_declaration=True,standalone=True) if member.filename in changed else z.read(member)
                out.writestr(copy(member),payload)
        with ZipFile(output) as final:
            if final.testzip() is not None:
                raise ValueError("Invalid ZIP member")
            filenames=[n for n in z.namelist() if z.read(n)!=final.read(n)]
            if set(filenames)!=set(changed):
                raise ValueError("Unexpected change list")
            if manifest(final)!=(slide_names,size,support):
                raise ValueError("Slide order or template structure changed")
            check=inspect(final)
    result=dict(case_id=plan["case_id"],status="ok",mode=mode,changed_slide_parts=filenames,actual_changes=operations,
                preserved_zip_members=len(z.namelist())-len(filenames),preserved_template_parts=len(support),
                dimensions_emu=size,slide_count=len(slide_names),template_source=plan.get("template_source"),
                rendering_required=True,inspection=check)
    output.with_suffix(".audit.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps({k:v for k,v in result.items() if k not in ("inspection","actual_changes")},ensure_ascii=True))


if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("mode",choices=("inspect","apply","adapt"))
    a.add_argument("pptx",type=Path)
    a.add_argument("plan",nargs="?",type=Path)
    a.add_argument("out",nargs="?",type=Path)
    v=a.parse_args()
    if v.mode=="inspect":
        with ZipFile(v.pptx) as z: print(json.dumps(inspect(z),ensure_ascii=True,indent=2))
    else:
        patch(v.pptx,json.loads(v.plan.read_text(encoding="utf-8-sig")),v.out,v.mode)
