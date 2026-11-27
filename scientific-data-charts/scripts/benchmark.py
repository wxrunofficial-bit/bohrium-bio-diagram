"""Repeatable smoke comparison and corruption controls; not a platform score."""
import argparse,csv,hashlib,json,shutil,statistics,sys,time
from pathlib import Path
from xml.etree import ElementTree as ET
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from figure import build,read_spec,dump
from verify import verify
def main(out):
    base=Path(__file__).resolve().parents[1];out.mkdir(parents=True,exist_ok=False)
    src=base/"examples"/"quartet.json";spec=read_spec(src)
    with (src.parent/spec["data"]).open(newline="") as f: rows=list(csv.DictReader(f))
    raw=hashlib.sha256((src.parent/spec["data"]).read_bytes()).hexdigest()
    baseline=out/"default";baseline.mkdir()
    # Same panels, source, dimensions, resolution, colors, labels and fit convention.
    def ordinary():
        with mpl.rc_context(mpl.rcParamsDefault):
            fig,axes=plt.subplots(2,2,figsize=np.array(spec["style"]["mm"])/25.4)
            for ax,p in zip(axes.flat,spec["panels"]):
                x=np.array([float(r[p["x"]]) for r in rows]);y=np.array([float(r[p["y"]]) for r in rows]);ab=np.polyfit(x,y,1)
                ax.scatter(x,y,c="#0072B2");xx=np.array([min(x),max(x)])
                ax.plot(xx,np.polyval(ab,xx),"--",c="#0072B2",lw=1)
                ax.set(xlabel=p["xlabel"],ylabel=p["ylabel"],xlim=p["xlim"],ylim=p["ylim"],title=p["title"])
            fig.supxlabel(spec["caption"],fontsize=8);fig.tight_layout()
            for ext in ("svg","png","pdf"):fig.savefig(baseline/("figure."+ext),dpi=spec["style"]["dpi"])
            plt.close(fig)
    start=time.perf_counter();ordinary();t0=time.perf_counter()-start
    full=out/"audited";full.mkdir();start=time.perf_counter();build(src,full);audit=verify(full);t1=time.perf_counter()-start
    mapping=read_spec(full/"mapping.json")
    tolerances=[]
    for i,p in enumerate(spec["panels"]):
        x=[float(r[p["x"]]) for r in rows];y=[float(r[p["y"]]) for r in rows];a,b=np.polyfit(x,y,1)
        record=dict(panel=i+1,n=len(x),mean_x=np.mean(x),mean_y=np.mean(y),slope=a,intercept=b,r_squared=np.corrcoef(x,y)[0,1]**2)
        if not(len(x)==11 and np.mean(x)==9 and abs(np.mean(y)-7.5)<.002 and abs(a-.5)<.001 and abs(b-3)<.005 and abs(record["r_squared"]-.667)<.001):raise ValueError("Reference summary mismatch")
        tolerances.append(record)
    # Exercise exported artifacts, not a mock of the auditor.
    failures={}
    def damage(name,change):
        dst=out/name;shutil.copytree(full,dst);change(dst)
        try:verify(dst)
        except (ValueError,KeyError) as exc:failures[name]=str(exc)
        else:raise AssertionError("Undetected "+name)
    def move(d):
        svg=d/"figure.svg";tree=ET.parse(svg);item=tree.find(".//*[@id='"+mapping["marks"][0]["id"]+"']");point=item.find(".//{*}use");point.set("x",str(float(point.get("x"))+4));tree.write(svg)
    damage("point-shift",move)
    def reverse(d):
        path=d/"reverse.csv";lines=path.read_bytes().splitlines(keepends=True);path.write_bytes(b"".join(lines[:-1]))
    damage("missing-backlink",reverse)
    def source(d):
        path=d/"source.csv";path.write_bytes(path.read_bytes().replace(b"8.04",b"9.04",1))
    damage("changed-data",source)
    def count(path):return len(ET.parse(path).findall(".//{*}text"))
    report=dict(design="One paired local run of ordinary Matplotlib versus audited pipeline. Both include scientific source data and OLS. Timings include export, single machine; no inference about an agent or human time.",
                source_sha256=raw,reference="Anscombe 1973, pp.18-19, figs.1-4 and data table",reference_check=tolerances,
                default=dict(seconds=round(t0,3),editable_svg_text=count(baseline/"figure.svg"),explicit_row_field_links=0),
                skill=dict(seconds=round(t1,3),editable_svg_text=count(full/"figure.svg"),explicit_row_field_links=audit["reverse_links"],geometry_checks=audit["geometry_verified"]),
                negative_controls=failures)
    dump(out/"comparison.json",report);print(json.dumps(report,indent=2))
if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("fresh_output",type=Path);main(a.parse_args().fresh_output)
