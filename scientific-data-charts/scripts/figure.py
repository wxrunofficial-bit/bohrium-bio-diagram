"""Render a portable scientific figure specification. CSV records start at 2."""
import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
import warnings
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import colors, font_manager
from matplotlib.ft2font import FT2Font
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
from matplotlib.text import Text
from PIL import Image

VERSION = "1.0.0"
PALETTE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#332288", "#555555"]
SYMBOLS = ["o", "s", "^", "D", "v", "P", "X"]
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf8")

def read_spec(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def cell(row, field):
    if field not in row or row[field] is None or not row[field].strip():
        raise ValueError(f"Absent or empty field {field!r} at record {row.get('__record__')}")
    return row[field]

def number(row, key):
    v = float(cell(row, key))
    if not math.isfinite(v):
        raise ValueError(f"Nonfinite {key}, record {row['__record__']}")
    return v

def ordered(seq):
    return list(dict.fromkeys(seq))

def font_for(fig, requested):
    letters = {ord(c) for t in fig.findobj(Text) for c in t.get_text() if ord(c) > 32}
    preferred = [requested] if requested else []
    preferred += ["DejaVu Sans", "Noto Sans CJK SC", "Microsoft YaHei", "SimHei", "WenQuanYi Zen Hei"]
    fonts = sorted(font_manager.fontManager.ttflist, key=lambda a: (a.name not in preferred, preferred.index(a.name) if a.name in preferred else 99, a.style != "normal", a.weight != 400, a.name))
    for f in fonts:
        try:
            if letters.issubset(FT2Font(f.fname).get_charmap()):
                mpl.rcParams["font.family"] = [f.name]
                for t in fig.findobj(Text):
                    t.set_fontfamily(f.name)
                return f.name
        except RuntimeError:
            continue
    raise ValueError("No installed font covers all labels. Install Noto Sans CJK or supply the requested font, then rerun.")

def build(specpath, dest):
    specpath = Path(specpath).resolve()
    s = read_spec(specpath)
    style = s.get("style", {})
    source = specpath.parent / s["data"]
    with source.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=s.get("delimiter", ","))
        fields = reader.fieldnames or []
        if len(fields) != len(set(fields)) or "__record__" in fields:
            raise ValueError("Duplicate or reserved column name")
        rows = [dict(row, __record__=i) for i, row in enumerate(reader, 2)]
    if not rows or any(None in r for r in rows):
        raise ValueError("Empty or ragged table")
    panels = s["panels"]
    size = style.get("mm", [180, 115])
    dpi = int(style.get("dpi", 300))
    if not panels or min(size) <= 0 or dpi <= 0:
        raise ValueError("Give a positive physical size, resolution and at least one panel")
    mpl.rcParams.update({"svg.fonttype":"none", "pdf.fonttype":42, "svg.hashsalt":"linked-figure-v1",
                         "font.size":style.get("pt", 9), "axes.linewidth":style.get("line_pt", 0.8),
                         "axes.spines.top":False, "axes.spines.right":False, "axes.axisbelow":True,
                         "axes.unicode_minus":False, "text.parse_math":False, "path.simplify":False})
    cols = min(len(panels), int(style.get("columns", 2)))
    fig, axes = plt.subplots(math.ceil(len(panels)/cols), cols, squeeze=False, figsize=np.array(size)/25.4, dpi=72)
    axes = list(axes.flat)
    marks, frames, notes, legend_contract = [], [], [], []
    color_by = style.get("colors", {})
    def register(artist, pi, role, group, records, keys, geom=None):
        gid = f"p{pi}-{role}-{len(marks)+1}"
        artist.set_gid(gid)
        marks.append(dict(id=gid, panel=pi, role=role, series=group, records=[r["__record__"] for r in records],
                          fields=keys, geometry=geom))
        return gid
    for pi, (ax, p) in enumerate(zip(axes, panels), 1):
        kind = p["kind"]
        selected = [r for r in rows if all(cell(r,k)==str(v) for k,v in p.get("where", {}).items())]
        if not selected:
            raise ValueError(f"Panel {pi} has no matching records")
        x, y, by = p["x"], p["y"], p.get("series")
        groups = ordered(cell(r,by) if by else "" for r in selected)
        allgroups = ordered(cell(r,by) for r in rows) if by else [""]
        cats = ordered(cell(r,x) for r in selected)
        if "order" in p:
            if set(cats) != set(p["order"]) or len(cats)!=len(p["order"]):
                raise ValueError("Category order does not match data")
            cats = p["order"]
        ax.set_title(p.get("title",""), loc="left", fontweight="bold")
        ax.set_xlabel(p.get("xlabel",x)); ax.set_ylabel(p.get("ylabel",y))
        ax.set_xscale(p.get("xscale","linear")); ax.set_yscale(p.get("yscale","linear"))
        if kind in ("bar","box","heatmap") and p.get("xscale","linear")!="linear":
            raise ValueError("Categorical axes require a linear scale")
        handles, labels = [], []
        for gi, group in enumerate(groups):
            rr = [r for r in selected if not by or cell(r,by)==group]
            idx = allgroups.index(group)
            co = color_by.get(group, PALETTE[idx%len(PALETTE)])
            symbol = SYMBOLS[idx%len(SYMBOLS)]
            keys = [k for k in [x,y,by] if k]
            offset = (gi-(len(groups)-1)/2)*.76/len(groups)
            handle = Patch(facecolor=co) if kind in ("bar","box") else Line2D([],[],color=co,marker=symbol,linestyle="-" if kind=="line" else "")
            if by:
                handles.append(handle); labels.append(group)
            if kind == "heatmap":
                if by: raise ValueError("Use facets for multiple heatmaps")
                val = p["value"]; yc = ordered(cell(r,y) for r in rr)
                vals = [number(r,val) for r in rr]
                lo, hi = p.get("domain",[min(vals),max(vals)])
                if hi < lo or min(vals)<lo or max(vals)>hi: raise ValueError("Heatmap domain clips observed values")
                norm = colors.Normalize(lo,hi if hi>lo else lo+1)
                cmap = mpl.colormaps[p.get("cmap","viridis")]
                seen = set()
                for r, value in zip(rr,vals):
                    a,b = cats.index(cell(r,x)),yc.index(cell(r,y))
                    if (a,b) in seen: raise ValueError("Duplicate heatmap cell")
                    seen.add((a,b))
                    box = ax.add_patch(Rectangle((a-.5,b-.5),1,1,facecolor=cmap(norm(value)),edgecolor="none"))
                    register(box,pi,"cell",group,[r],keys+[val],dict(ix=a,iy=b,field=val,domain=[norm.vmin,norm.vmax],cmap=cmap.name))
                if len(seen)!=len(cats)*len(yc): notes.append(f"Panel {pi}: unobserved matrix cells are blank.")
                ax.set(xlim=(-.5,len(cats)-.5),ylim=(len(yc)-.5,-.5))
                ax.set_xticks(range(len(cats)),cats);ax.set_yticks(range(len(yc)),yc)
                fig.colorbar(mpl.cm.ScalarMappable(norm=norm,cmap=cmap),ax=ax,label=p.get("colorlabel",val))
                continue
            if kind == "box":
                for ci,c in enumerate(cats):
                    subset = [r for r in rr if cell(r,x)==c]
                    if not subset: continue
                    vals=[number(r,y) for r in subset]
                    bp=ax.boxplot(vals,positions=[ci+offset],widths=.64/len(groups),patch_artist=True,manage_ticks=False,
                                  boxprops={"facecolor":co,"alpha":.65},medianprops={"color":"black"},whis=1.5)
                    for part, artists in bp.items():
                        for side,artist in enumerate(artists):
                            register(artist,pi,"box-"+part,group,subset,keys,dict(ix=ci+offset,field=y,side=side))
                continue
            if kind not in ("bar","scatter","line"): raise ValueError(f"Unknown chart type {kind}")
            bounds = p.get("bounds")
            if bounds and (len(bounds)!=2 or not p.get("error_label")): raise ValueError("Specify [lower,upper] and error_label with interval meaning")
            if kind=="bar" and len(rr)!=len(set(cell(r,x) for r in rr)): raise ValueError("Duplicate bars: supply grouping or explicit aggregation")
            pairs=[]
            for r in rr:
                xx = cats.index(cell(r,x))+offset if kind=="bar" else number(r,x)
                yy = number(r,y)
                if (p.get("yscale")=="log" and (yy<=0 or kind=="bar")) or (p.get("xscale")=="log" and xx<=0):
                    raise ValueError("Nonpositive coordinate or zero-baseline bar on logarithmic axis")
                geom=dict(xfield=x,yfield=y)
                if kind=="bar":
                    geom["ix"]=xx
                    art=ax.bar(xx, yy, width=.68/len(groups), color=co)[0]
                else:
                    art,=ax.plot(xx,yy,marker=symbol,color=co,ms=style.get("marker_pt",4),ls="none",zorder=3)
                register(art,pi,"bar" if kind=="bar" else "point",group,[r],keys,geom)
                if p.get("annotation"):
                    field=p["annotation"]
                    if r.get(field,"").strip():
                        top=number(r,bounds[1]) if bounds else yy
                        label=ax.annotate(cell(r,field),(xx,top),xytext=(0,5),textcoords="offset points",ha="center",va="bottom",fontsize=style.get("pt",9)-1)
                        register(label,pi,"annotation",group,[r],[field]+keys,dict(field=field))
                if bounds:
                    low,high = (number(r,k) for k in bounds)
                    if not low<=yy<=high or (p.get("yscale")=="log" and low<=0): raise ValueError("Invalid interval")
                    err,=ax.plot([xx,xx],[low,high],color="#202020" if kind=="bar" else co,marker="_",ms=5,linewidth=1,zorder=4)
                    register(err,pi,"interval",group,[r],keys+bounds,dict(**geom,bounds=bounds))
                pairs.append((xx,yy,r))
            if kind=="line":
                if p.get("sort_x",True): pairs.sort(key=lambda t:t[0])
                line,=ax.plot([t[0] for t in pairs],[t[1] for t in pairs],color=co,linewidth=style.get("line_pt",1.2))
                register(line,pi,"line",group,[t[2] for t in pairs],keys,dict(xfield=x,yfield=y))
            if p.get("fit")=="ols":
                if len(set(t[0] for t in pairs))<2: raise ValueError("Undefined linear fit")
                slope,intercept=np.polyfit([t[0] for t in pairs],[t[1] for t in pairs],1)
                ar=np.array([min(t[0] for t in pairs),max(t[0] for t in pairs)])
                fit,=ax.plot(ar,ar*slope+intercept,color=co,ls="--",lw=1)
                register(fit,pi,"ols",group,rr,keys,dict(xfield=x,yfield=y,slope=slope,intercept=intercept))
        if kind in ("bar","box"): ax.set_xticks(range(len(cats)),cats)
        for axis in ("x","y"):
            if axis+"lim" in p: getattr(ax,"set_"+axis+"lim")(p[axis+"lim"])
        if p.get("xtick_rotation"): ax.tick_params(axis="x",labelrotation=p["xtick_rotation"])
        if labels:
            leg=ax.legend(handles,labels,loc=p.get("legend","best"),frameon=False)
            leg.set_gid(f"legend-{pi}")
            legend_contract.append(dict(panel=pi,labels=labels,colors=[colors.to_hex(color_by.get(g,PALETTE[allgroups.index(g)%len(PALETTE)])) for g in labels]))
        if p.get("error_label"):
            ax.set_xlabel(ax.get_xlabel()+"\n"+p["error_label"])
    for ax in axes[len(panels):]: ax.remove()
    if s.get("caption"): fig.supxlabel(s["caption"],fontsize=style.get("pt",9)-1)
    font=font_for(fig,style.get("font"))
    if style.get("font") and font!=style["font"]: notes.append("Font fallback: "+font)
    with warnings.catch_warnings(record=True) as wr:
        warnings.simplefilter("always")
        fig.tight_layout(pad=1.2)
        fig.canvas.draw()
        renderer=fig.canvas.get_renderer()
        for pi,ax in enumerate(axes[:len(panels)],1):
            box=ax.get_window_extent()
            frames.append(dict(panel=pi,rect=[box.x0,fig.bbox.height-box.y1,box.width,box.height],
                               xlim=list(ax.get_xlim()),ylim=list(ax.get_ylim()),xscale=ax.get_xscale(),yscale=ax.get_yscale()))
            for axis in [ax.xaxis,ax.yaxis]:
                ticks=[t.get_window_extent(renderer) for t in axis.get_ticklabels() if t.get_visible() and t.get_text()]
                if any(a.overlaps(b) for a,b in zip(ticks,ticks[1:])): notes.append(f"Panel {pi}: adjacent {axis.axis_name} tick labels overlap; increase size or rotate ticks.")
        # Matplotlib allocates locators just outside the visible axis. Only
        # exported labels should enter the final clipping check in verify.py.
        transparent=bool(style.get("transparent",False))
        fig.savefig(dest/"figure.svg",metadata={"Date":None},transparent=transparent)
        fig.savefig(dest/"figure.pdf",metadata={"CreationDate":None,"ModDate":None},transparent=transparent)
        fig.savefig(dest/"figure.png",dpi=dpi,transparent=transparent)
        notes.extend(str(w.message) for w in wr if "Glyph" in str(w.message) or "layout" in str(w.message).lower())
    plt.close(fig)
    export_spec=dict(s,data="source.csv")
    shutil.copyfile(source,dest/"source.csv"); dump(dest/"figure.json",export_spec)
    dump(dest/"mapping.json",dict(source_sha256=digest(source),source_name=source.name,source_locator=s.get("source_locator"),marks=marks,panels=frames,legends=legend_contract))
    with (dest/"reverse.csv").open("w",encoding="utf8",newline="") as f:
        writer=csv.writer(f);writer.writerow(["csv_record","field","svg_id"])
        for mark in marks:
            writer.writerows((r,k,mark["id"]) for r in mark["records"] for k in mark["fields"])
    with Image.open(dest/"figure.png") as img: raster=dict(pixels=list(img.size),dpi=img.info.get("dpi"),mode=img.mode)
    dump(dest/"result.json",dict(case_id=s["id"],status="needs_review" if notes else "ok",version=VERSION,
         input_sha256=digest(source),spec_sha256=digest(specpath),outputs=["figure.svg","figure.pdf","figure.png","figure.json","source.csv","mapping.json","reverse.csv"],
         font=font,physical_mm=size,raster=raster,requested_dpi=dpi,matplotlib=mpl.__version__,numpy=np.__version__,uncertainty=ordered(notes),
         changes=s.get("changes",[]),source_locator=s.get("source_locator"),human_confirmations=s.get("human_confirmations",[])))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("spec",type=Path);ap.add_argument("out",type=Path)
    args=ap.parse_args()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    if args.out.exists(): ap.error("Choose a fresh output directory for this revision")
    with tempfile.TemporaryDirectory(dir=args.out.parent) as td:
        dest=Path(td)/"work";dest.mkdir()
        try:
            build(args.spec,dest)
            from verify import verify
            dump(dest/"audit.json",verify(dest))
            dest.rename(args.out)
        except Exception as exc:
            print(json.dumps({"status":"failed","reason":str(exc)},ensure_ascii=True),file=sys.stderr)
            return 2
    print(json.dumps({"output":str(args.out),"status":read_spec(args.out/"result.json")["status"]}))
    return 0
if __name__=="__main__":
    sys.exit(main())
