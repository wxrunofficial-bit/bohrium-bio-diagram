"""Check declared text/background contrasts and flag color-only encodings."""
import argparse
from pathlib import Path
import scene


def luminance(rgb):
    rgb=rgb.lstrip("#")
    if len(rgb)!=6:
        raise ValueError("Expected a six-digit sRGB color")
    srgb=[int(rgb[i:i+2],16)/255 for i in (0,2,4)]
    linear=[c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4 for c in srgb]
    return sum(a*b for a,b in zip(linear,(.2126,.7152,.0722)))


def ratio(a,b):
    lo,hi=sorted((luminance(a),luminance(b)))
    return (hi+.05)/(lo+.05)


def audit(objects,back):
    issues=[]
    for o in objects:
        if o["type"]=="text":
            actual=ratio(o["color"],o.get("background",back))
            if actual<4.5:
                issues.append({"id":o["id"],"ratio":round(actual,3),"check":"text contrast below 4.5"})
    return issues


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("spec",type=Path)
    args=parser.parse_args()
    spec=scene.read(args.spec)
    objects=scene.elements(spec)
    findings=audit(objects,spec.get("background","#FFFFFF"))
    for f in findings:
        print(f)
    raise SystemExit(bool(findings))
