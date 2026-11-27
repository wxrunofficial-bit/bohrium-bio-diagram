"""Merge case-required, evidence-backed fields into /app/output/result.json."""
import argparse
import json
from pathlib import Path
def read(p):return json.loads(Path(p).read_text(encoding="utf-8-sig"))
def keys(contract):
    if isinstance(contract,list):
        return [v if isinstance(v,str) else v.get("name",v.get("field")) for v in contract]
    if "required" in contract and isinstance(contract["required"],list):return keys(contract["required"])
    if "fields" in contract and isinstance(contract["fields"],(dict,list)):return keys(contract["fields"])
    if "properties" in contract:return list(contract["properties"])
    return list(contract)
if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("case");a.add_argument("actual");a.add_argument("result");v=a.parse_args()
    case=read(v.case);actual=read(v.actual);out=Path(v.result)
    data=read(out) if out.exists() else {}
    data.update(actual);data["case_id"]=case["case_id"]
    missing=[k for k in keys(case.get("output_contract",{})) if not k or k not in data or data[k] is None]
    if missing:
        data["status"]="partial";data.setdefault("uncertainty",[]).append({"missing_contract_fields":missing})
    out.parent.mkdir(parents=True,exist_ok=True)
    temp=out.with_suffix(".tmp");temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf8");temp.replace(out)
    print(json.dumps({"status":data.get("status"),"missing":missing}));raise SystemExit(bool(missing))
