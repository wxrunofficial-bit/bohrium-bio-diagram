"""Compare traceable figure revisions at the data and visible-object levels."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from verify import verify


def load(folder):
    return json.loads((folder / "mapping.json").read_text(encoding="utf8"))


def geometry(obj):
    geom = obj["geometry"] or {}
    return json.dumps({k:v for k,v in geom.items() if k not in ("color","colormap","cmap")},
                      sort_keys=True, separators=(",",":"))


def compare(before, after):
    a, b = load(before), load(after)
    outcomes = [verify(before), verify(after)]
    if a["source_sha256"] != b["source_sha256"]:
        raise ValueError("Source CSV content changed")
    def payload(d):
        return Counter((m["panel"], m["role"], m["series"], tuple(m["records"]),
                        tuple(m["fields"]), geometry(m)) for m in d["marks"] if m["role"] != "annotation")
    if payload(a) != payload(b):
        raise ValueError("Quantitative mark, grouping or source-cell match changed")
    return {"source_sha256": a["source_sha256"],"preserved_quantitative_marks":sum(payload(a).values()),
            "before":outcomes[0],"after":outcomes[1]}


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("before",type=Path)
    ap.add_argument("after",type=Path)
    args=ap.parse_args()
    print(json.dumps(compare(args.before,args.after),ensure_ascii=True,indent=2))
