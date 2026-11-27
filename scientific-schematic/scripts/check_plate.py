"""Read back every mapped object and verify real previews."""
import argparse
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from plate import audit
from svgtools import verify_exports

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("folder",type=Path)
    args=parser.parse_args()
    root=args.folder
    evidence=json.loads((root/"source-map.json").read_text(encoding="utf8"))
    result=json.loads((root/"result.json").read_text(encoding="utf8"))
    counts=audit(root/"figure.svg",evidence["elements"])
    for name,ids in evidence["source_to_elements"].items():
        assert sorted(ids)==sorted(k for k,v in evidence["elements"].items() if name in v["evidence"]),name
    out=verify_exports(root/"figure.png",root/"figure.pdf",*result["exports"]["png_pixels"])
    print(json.dumps({"elements":counts,"exports":out},indent=2))
