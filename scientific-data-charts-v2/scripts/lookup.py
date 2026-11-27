"""Resolve an SVG object to exact cells, or a CSV record/field to objects."""
import argparse,csv,json
from pathlib import Path
def main():
    p=argparse.ArgumentParser();p.add_argument("figure_folder",type=Path)
    q=p.add_mutually_exclusive_group(required=True);q.add_argument("--id");q.add_argument("--record",type=int);p.add_argument("--field")
    args=p.parse_args();root=args.figure_folder
    mapping=json.loads((root/"mapping.json").read_text(encoding="utf8"))
    spec=json.loads((root/"figure.json").read_text(encoding="utf8"))
    with (root/"source.csv").open(encoding="utf-8-sig",newline="") as f:rows=list(csv.DictReader(f,delimiter=spec.get("delimiter",",")))
    selected=[]
    for m in mapping["marks"]:
        if args.id and m["id"]!=args.id:continue
        if args.record is not None and args.record not in m["records"]:continue
        if args.field and args.field not in m["fields"]:continue
        selected.append({"svg_id":m["id"],"role":m["role"],"series":m["series"],"cells":[{"record":r,"values":{k:rows[r-2][k] for k in m["fields"]}} for r in m["records"]]})
    print(json.dumps({"source":mapping["source_name"],"source_sha256":mapping["source_sha256"],"matches":selected},indent=2,ensure_ascii=True))
    return 0 if selected else 1
if __name__=="__main__":raise SystemExit(main())
