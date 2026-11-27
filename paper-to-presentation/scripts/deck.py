"""Source-linked academic decks with native editable PowerPoint objects."""
import argparse
from pathlib import Path
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import MSO_ANCHOR
from pptx.util import Pt
import scene


def rgb(hexcode):
    return RGBColor.from_string(hexcode.lstrip("#").upper())


def layout(spec,slide,index):
    w,h=spec.get("dimensions",[960,540])
    ink=spec.get("ink",scene.INK_BLUE)
    accent=spec.get("accent",scene.TEAL)
    mode=slide.get("layout","evidence")
    if mode=="cover":
        return [scene.text("title-"+str(i),54,143+i*50,s,43,ink,700,slide["evidence"]) for i,s in enumerate(slide["headline"].split("\n"))]+[
            scene.text("description",54,290,slide.get("subtitle",""),19,scene.MUTED),
            *slide.get("objects",[])]
    lines=slide["headline"].split("\n")
    scene.require(len(lines)<=2,"Use at most two headline lines")
    y=55
    objects=[scene.text("claim-"+str(i),54,y+i*39,s,34,ink,700,slide["evidence"]) for i,s in enumerate(lines)]
    objects.extend(slide.get("objects",[]))
    if slide.get("plot"):
        plot=dict(slide["plot"])
        plot.update(type="scatter",id="evidence",x=58,y=110 if len(lines)==1 else 155,w=w-117,h=367 if len(lines)==1 else 310)
        objects.append(plot)
    if slide.get("citation"):
        objects.extend([scene.line("footer-rule",54,h-35,w-54,h-35,scene.GRID,1),
                        scene.text("citation",54,h-17,slide["citation"],10,scene.MUTED,400,slide["evidence"])])
    return objects


def place(slide,obj,font,asset_root):
    objects=slide.shapes
    kind=obj["type"]
    x,y=obj["x"],obj["y"]
    color=rgb(obj.get("color",scene.INK_BLUE))
    if kind=="text":
        size=obj["size"]
        shp=objects.add_textbox(Pt(x),Pt(y-size),Pt(obj.get("w",1100-x)),Pt(size*1.25))
        t=shp.text_frame
        t.word_wrap=False
        t.margin_left=t.margin_top=t.margin_bottom=t.margin_right=0
        t.vertical_anchor=MSO_ANCHOR.MIDDLE
        p=t.paragraphs[0]
        p.space_before=p.space_after=0
        r=p.add_run()
        r.text=obj["value"]
        r.font.name=font
        r.font.size=Pt(size)
        r.font.bold=obj.get("weight",400)>=700
        r.font.color.rgb=color
    elif kind=="line":
        shp=objects.add_connector(MSO_CONNECTOR.STRAIGHT,Pt(x),Pt(y),Pt(obj["u"]),Pt(obj["v"]))
        shp.line.color.rgb=color
        shp.line.width=Pt(obj.get("width",1.3))
    elif kind=="circle":
        radius=obj["r"]
        shp=objects.add_shape(MSO_SHAPE.OVAL,Pt(x-radius),Pt(y-radius),Pt(2*radius),Pt(2*radius))
        shp.fill.solid()
        shp.fill.fore_color.rgb=color
        shp.line.fill.background()
    elif kind=="rect":
        shp=objects.add_shape(MSO_SHAPE.RECTANGLE,Pt(x),Pt(y),Pt(obj["w"]),Pt(obj["h"]))
        shp.fill.solid()
        shp.fill.fore_color.rgb=color
        shp.line.fill.background()
    elif kind=="picture":
        source=(asset_root/obj["path"]).resolve()
        scene.require(obj.get("evidence"),"A photograph or original plot needs a source locator")
        with Image.open(source) as im:
            width,height=im.size
        scale=min(obj["w"]/width,obj["h"]/height)
        sw,sh=width*scale,height*scale
        shp=objects.add_picture(str(source),Pt(x+(obj["w"]-sw)/2),Pt(y+(obj["h"]-sh)/2),Pt(sw),Pt(sh))
        obj["asset_sha256"]=scene.digest(source)
    else:
        raise ValueError("Unknown native shape: "+kind)
    shp.name=obj["id"]
    return shp


def validate_plan(spec):
    sources=spec["sources"]
    scene.require(sources and all(all(v.get(k) for k in ("document","location","fact")) for v in sources.values()),"Source locators and stated facts are required")
    used=set()
    totals={"main":0,"appendix":0}
    scene.require(spec["slides"],"Provide at least one slide")
    for slide in spec["slides"]:
        identity=slide["id"]
        scene.require(identity not in used,"Repeated slide "+identity)
        used.add(identity)
        scene.require(slide.get("headline") and slide.get("notes") and slide.get("transition"),identity+": headline, notes and transition required")
        scene.require(slide.get("evidence") and all(e in sources for e in slide["evidence"]),identity+": claim is missing source evidence")
        scene.require(isinstance(slide["seconds"],int) and slide["seconds"]>0,identity+": invalid timing")
        totals["appendix" if slide.get("appendix") else "main"]+=slide["seconds"]
    scene.require(totals["main"]<=spec["budget_seconds"],"Talk exceeds time budget")
    return totals


def render(spec,out,asset_root=Path(".")):
    totals=validate_plan(spec)
    out.mkdir(parents=True,exist_ok=False)
    ppt=Presentation()
    w,h=spec.get("dimensions",[960,540])
    ppt.slide_width,ppt.slide_height=Pt(w),Pt(h)
    font=spec.get("font","DejaVu Sans")
    maps=[]
    for i,data in enumerate(spec["slides"],1):
        slide=ppt.slides.add_slide(ppt.slide_layouts[6])
        bg=slide.background.fill
        bg.solid()
        bg.fore_color.rgb=rgb(spec.get("background",scene.PAPER))
        raw=layout(spec,data,i)
        values=scene.elements({"objects":raw,"sources":spec["sources"]})
        for obj in values:
            if obj["type"]=="text":
                obj["w"]=w-obj["x"]-36
            place(slide,obj,font,asset_root)
        notes=slide.notes_slide.notes_text_frame
        notes.text=data["notes"]+"\n\nTransition: "+data["transition"]+"\n\n"+\
            "\n".join(f"{key}: {spec['sources'][key]['document']} • {spec['sources'][key]['location']}" for key in data["evidence"])
        maps.append({"slide":i,"slide_id":data["id"],"headline":data["headline"],"seconds":data["seconds"],
                     "appendix":bool(data.get("appendix")),"claim_evidence":data["evidence"],
                     "figure_evidence":scene.lookups(values,spec["sources"]), "expected":values})
    name=out/"figure.pptx"
    ppt.save(name)
    scene.write(out/"slide-spec.json",spec)
    scene.write(out/"evidence.json",maps)
    from check_deck import examine
    report=examine(name,out/"preview",maps)
    result={"case_id":spec["case_id"],"status":"needs_review" if report["warnings"] else "ok",
            "artifacts":["figure.pptx","evidence.json","slide-spec.json","preview/deck.pdf","preview/thumbnail.png"],
            "timing_seconds":totals,"editability":report,"uncertainty":report["warnings"]}
    scene.write(out/"result.json",result)
    print(result["status"],"slides",report["slide_count"],"native objects",report["objects"])
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("spec",type=Path)
    p.add_argument("out",type=Path)
    a=p.parse_args()
    render(scene.read(a.spec),a.out,a.spec.resolve().parent)
