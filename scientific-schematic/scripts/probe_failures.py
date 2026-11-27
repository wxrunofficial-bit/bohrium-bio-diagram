"""Negative controls for source validation, final SVG and bounded edits."""
import argparse
import copy
import json
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

from plate import audit, render
from local_edit import run


def fail(name, action, phrase):
    try:
        action()
    except (ValueError, KeyError) as error:
        if phrase not in str(error):
            raise ValueError(name + " failed for an unexpected reason") from error
        return str(error)
    raise AssertionError(name + " passed unexpectedly")


def checks(folder, profile):
    spec=json.loads((folder/"figure-spec.json").read_text(encoding="utf8"))
    mapping=json.loads((folder/"source-map.json").read_text(encoding="utf8"))["elements"]
    wrong_source=copy.deepcopy(spec)
    wrong_source["panels"][0]["edges"][0]["evidence"]=["unverified"]
    edge=next(k for k,v in mapping.items() if "geometry" in v)
    with tempfile.TemporaryDirectory() as d:
        scratch=Path(d)
        svg=scratch/"changed.svg"
        t=ET.parse(folder/"figure.svg")
        n=t.find(".//*[@id='data-"+edge+"']")
        n.set("data-target",n.get("data-source"))
        t.write(svg,encoding="utf-8")
        label=next(g.get("id") for g in t.findall(".//{*}text") if g.get("id"))
        stale={"case_id":"stale","operations":[{"id":label,"field":"text","expected":"placeholder text","value":"unwanted","source":"negative control","reason":"test stale edit"}]}
        report={
            "missing_evidence":fail("missing evidence",lambda:render(wrong_source,profile),"no linked evidence"),
            "changed_vector_endpoint":fail("reversed or substituted connection",lambda:audit(svg,mapping),"swapped"),
            "stale_edit":fail("stale edit",lambda:run(folder/"figure.svg",stale,scratch/"stale"),"expected"),
        }
        assert not (scratch/"stale").exists()
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("folder",type=Path)
    parser.add_argument("--profile",required=True)
    a=parser.parse_args()
    print(json.dumps(checks(a.folder,a.profile),indent=2))
