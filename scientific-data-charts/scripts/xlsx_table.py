"""Extract one rectangular Excel range with original worksheet addresses. Standard library."""
import argparse,csv,hashlib,json,posixpath,re,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
def coordinate(s):
    m=re.fullmatch(r"([A-Z]+)([1-9]\d*)",s)
    if not m:raise ValueError("Expected an A1 coordinate")
    col=0
    for c in m[1]:col=26*col+ord(c)-64
    return int(m[2]),col
def name(c):
    s=""
    while c:c,r=divmod(c-1,26);s=chr(65+r)+s
    return s
def extract(src,sheet,area,out):
    with zipfile.ZipFile(src) as z:
        wb=ET.fromstring(z.read("xl/workbook.xml"))
        rel=ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        names={s.get("name"):next(v for k,v in s.attrib.items() if k.endswith("}id")) for s in wb.findall(".//{*}sheet")}
        if sheet not in names:raise ValueError("Available sheets: "+", ".join(names))
        target=next(r.get("Target") for r in rel if r.get("Id")==names[sheet])
        target=target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("xl",target))
        ws=ET.fromstring(z.read(target));strings=[]
        if "xl/sharedStrings.xml" in z.namelist():
            strings=["".join(t.text or "" for t in si.findall(".//{*}t")) for si in ET.fromstring(z.read("xl/sharedStrings.xml"))]
        cells={c.get("r"):c for c in ws.findall(".//{*}c")}
        start,end=map(coordinate,area.split(":"));r0,c0=start;r1,c1=end
        if r1<=r0 or c1<c0:raise ValueError("Include one header row plus records")
        table=[];addresses=[]
        for r in range(r0,r1+1):
            row=[];refs=[]
            for c in range(c0,c1+1):
                ref=name(c)+str(r);node=cells.get(ref);value=""
                if node is not None:
                    t=node.get("t");v=node.find("{*}v")
                    if node.find("{*}f") is not None and (v is None or v.text is None):raise ValueError("Uncached formula "+ref)
                    if t=="e":raise ValueError("Excel error at "+ref)
                    value=(v.text or "") if v is not None else ""
                    if t=="s":value=strings[int(value)]
                    if t=="inlineStr":value="".join(q.text or "" for q in node.findall(".//{*}t"))
                row.append(value);refs.append(sheet+"!"+ref)
            table.append(row);addresses.append(refs)
    if not all(table[0]) or len(set(table[0]))!=len(table[0]):raise ValueError("Choose unique unmerged column headers")
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("x",encoding="utf8",newline="") as f:csv.writer(f).writerows(table)
    audit=dict(workbook=src.name,sha256=hashlib.sha256(src.read_bytes()).hexdigest(),sheet=sheet,range=area,
               headers=table[0],records={str(i):dict(zip(table[0],a)) for i,a in enumerate(addresses[1:],2)})
    out.with_suffix(".cells.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf8")
if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("xlsx",type=Path);a.add_argument("sheet");a.add_argument("range");a.add_argument("out",type=Path)
    v=a.parse_args();extract(v.xlsx,v.sheet,v.range,v.out)
