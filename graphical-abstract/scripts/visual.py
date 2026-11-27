"""Build, check, and export an editable graphical abstract."""
import argparse
from pathlib import Path
import scene
import svgtools


def render(spec,out):
    for key,v in spec["sources"].items():
        scene.require(all(v.get(k) for k in ("document","location","fact")),key+": incomplete source")
    out.mkdir(parents=True,exist_ok=False)
    vector=out/"figure.svg"
    objects=scene.svg(spec,vector)
    audit=scene.audit_svg(vector,objects)
    scene.write(out/"spec.json",spec)
    scene.write(out/"evidence.json",scene.lookups(objects,spec["sources"]))
    result={"case_id":spec["case_id"],"status":"partial","scientific_takeaway":spec["title"],
            "alt_text":spec["description"],"checks":audit,"artifacts":["figure.svg","spec.json","evidence.json"],"uncertainty":[]}
    try:
        root=svgtools.read_svg(vector)
        result["export"]=svgtools.export(vector,root,spec.get("raster_scale",2))
        result["artifacts"].extend(["figure.png","figure.pdf"])
        result["status"]="ok"
    except (FileNotFoundError,ValueError,RuntimeError) as exc:
        result["uncertainty"].append(str(exc))
    scene.write(out/"result.json",result)
    print(result["status"],audit)
    return result

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("spec",type=Path)
    ap.add_argument("output",type=Path)
    args=ap.parse_args()
    raise SystemExit(render(scene.read(args.spec),args.output)["status"]!="ok")
