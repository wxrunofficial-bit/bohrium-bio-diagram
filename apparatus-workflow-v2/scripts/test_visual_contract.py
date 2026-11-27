"""Deliberate negative controls for geometry, scientific ports and label fit."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from xml.etree import ElementTree as ET

from illustrate import audit, check_text_fit, prepare


def expects_failure(run, prompt):
    try:
        run()
    except ValueError as err:
        if prompt in str(err):
            return str(err)
        raise
    raise AssertionError("Negative control was not rejected")


def test(spec, svg):
    result = {"svg_correct":audit(spec,svg)}
    edited = deepcopy(spec)
    one = next(m for o in edited["objects"] for m in o["marks"] if m["type"]=="edge")
    one["points"][0] = [0,0]
    result["wrong_port"] = expects_failure(lambda:prepare(edited),"declared port")
    edited = deepcopy(spec)
    first_title = next(m for o in edited["objects"] for m in o["marks"] if m["type"]=="text")
    first_title["label"] *= 8
    result["clipped_label"] = expects_failure(lambda:check_text_fit(edited),"off the canvas")
    with tempfile.TemporaryDirectory() as d:
        temp = Path(d)/"altered.svg"
        tree = ET.parse(svg)
        glyph = next((m for m in tree.getroot().iter() if m.get("data-glyph")), None)
        if glyph is not None:
            glyph.set("data-glyph","wrong-marker")
            check = "terminal glyph"
        else:
            node = next(m for m in tree.getroot().iter() if m.tag.endswith("polyline"))
            node.set("points", "1,1 10,10")
            check = "geometry mismatch"
        tree.write(temp,encoding="utf-8",xml_declaration=True)
        result["tampered_export"] = expects_failure(lambda:audit(spec,temp),check)
    return result


if __name__ == "__main__":
    a=argparse.ArgumentParser()
    a.add_argument("spec",type=Path)
    a.add_argument("svg",type=Path)
    v=a.parse_args()
    spec=json.loads(v.spec.read_text(encoding="utf-8-sig"))
    print(json.dumps(test(spec,v.svg),ensure_ascii=True,indent=2))
