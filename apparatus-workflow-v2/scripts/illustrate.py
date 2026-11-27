"""Evidence-linked editable vector illustration for source-specified diagrams."""
import argparse
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

import svgtools

SVG = "http://www.w3.org/2000/svg"
INKSCAPE = "http://www.inkscape.org/namespaces/inkscape"
ET.register_namespace("", SVG)
ET.register_namespace("inkscape", INKSCAPE)
INK = "#192633"
MUTED = "#415663"
RELATIONS = {"activation": "arrow", "transport": "arrow", "flow": "arrow", "inhibition": "bar",
             "binding": "plain", "association": "plain", "pressure": "plain", "wire": "plain",
             "leader": "plain", "influence": "arrow"}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def add(parent, name, text=None, **attrs):
    obj = ET.SubElement(parent, f"{{{SVG}}}{name}", {k.replace("_", "-"): str(v) for k, v in attrs.items()})
    obj.text = text
    return obj


def bounded(point, size):
    return len(point) == 2 and all(math.isfinite(v) and 0 <= v <= limit for v, limit in zip(point, size))


def marker(start, end, form):
    dx, dy = end[0] - start[0], end[1] - start[1]
    distance = math.hypot(dx, dy)
    require(distance >= 9 or form == "plain", "Connection end too short for its head")
    if form == "plain":
        return []
    ux, uy = dx / distance, dy / distance
    width = 6.8 if form == "arrow" else 7.5
    depth = 13 if form == "arrow" else 0
    bx, by = end[0] - ux * depth, end[1] - uy * depth
    wings = [(bx - uy * width, by + ux * width), (bx + uy * width, by - ux * width)]
    return [wings[0], end if form == "arrow" else (bx, by), wings[1]]


def as_points(points):
    return " ".join(f"{x:.5f},{y:.5f}" for x, y in points)


def emit(group, obj, size):
    tag = obj["type"]
    col = obj.get("stroke", INK)
    line_width = obj.get("width", 2)
    if tag == "text":
        require(bounded((obj["x"], obj["y"]), size), "Text anchor outside canvas")
        return add(group, "text", obj["label"], x=obj["x"], y=obj["y"], fill=obj.get("fill", INK),
                   font_size=obj.get("size", 19), font_weight=obj.get("weight", 400),
                   **{"text_anchor": obj.get("anchor", "start")})
    if tag in {"rect", "circle"}:
        if tag == "circle":
            radius = obj["r"]
            x, y = obj["x"] - radius, obj["y"] - radius
            w = h = 2 * radius
        else:
            x, y, w, h = obj["box"]
            radius = obj.get("r", 0)
        require(w > 0 and h > 0 and bounded((x, y), size) and bounded((x + w, y + h), size), "Invalid shape bounds")
        return add(group, "rect", x=x, y=y, width=w, height=h, rx=radius,
                   fill=obj.get("fill", "none"), stroke=obj.get("stroke", "none"), stroke_width=line_width)
    points = obj["points"]
    require(len(points) >= 2 and all(bounded(p, size) for p in points), "Incomplete route or off-canvas point")
    if tag == "polygon":
        path = "M" + " L".join(f"{a},{b}" for a, b in points) + " Z"
        return add(group, "path", d=path, fill=obj.get("fill", "none"), stroke=col, stroke_width=line_width)
    require(tag in {"line", "edge"}, "Unsupported vector mark")
    attrs = {"fill": "none", "stroke": col, "stroke_width": line_width, "stroke_linejoin": "round"}
    if obj.get("dash") or obj.get("certainty") == "proposed":
        attrs["stroke_dasharray"] = "7 5"
    curve = add(group, "polyline", points=as_points(points), **attrs)
    if tag == "edge":
        form = RELATIONS[obj["relation"]]
        g = marker(points[-2], points[-1], form)
        if g:
            add(group, "polyline", points=as_points(g), stroke=col, fill="none", stroke_width=line_width,
                stroke_linejoin="round", **{"data_glyph": form})
    return curve


def prepare(spec):
    size = spec["size"]
    require(len(size) == 2 and all(isinstance(x, int) and 240 <= x <= 4000 for x in size), "Invalid canvas dimensions")
    evidence = spec["evidence"]
    for key, fact in evidence.items():
        require(all(fact.get(k) for k in ("document", "locator", "fact")), key + ": source is incomplete")
    objects = {}
    for o in spec["objects"]:
        k = o["id"]
        require(re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]*", k) and k not in objects, "Invalid or repeated ID")
        require(all(e in evidence for e in o.get("evidence", [])), k + ": unknown source")
        require(o.get("evidence") or o.get("role") == "decoration", k + ": missing scientific evidence")
        objects[k] = o
    for k, o in objects.items():
        ports = o.get("ports", {})
        require(all(bounded(point, size) for point in ports.values()), k + ": port is off-canvas")
        for v in o["marks"]:
            if v["type"] != "edge":
                continue
            start, end = v["from"], v["to"]
            for i, sid in enumerate((start, end)):
                source, port_id = sid.split("/", 1)
                lookup = objects[source]["ports"][port_id]
                require(v["points"][0 if i == 0 else -1] == lookup, k + ": route differs from a declared port")
            require(v["relation"] in RELATIONS, k + ": undefined edge semantics")
            require(v.get("certainty", "supported") in {"supported", "proposed"}, k + ": invalid evidence qualifier")
    return objects


def draw(spec, out):
    objects = prepare(spec)
    size = spec["size"]
    root = ET.Element(f"{{{SVG}}}svg", {"width":str(size[0]),"height":str(size[1]),
        "viewBox":f"0 0 {size[0]} {size[1]}", "role":"img",
        "font-family":"DejaVu Sans, Noto Sans CJK SC, Microsoft YaHei, Sans Serif"})
    add(root, "title", spec["title"])
    add(root, "desc", spec["description"])
    add(root, "rect", x=0, y=0, width=size[0], height=size[1], fill=spec.get("background", "#FFFFFF"))
    for k, o in objects.items():
        group = add(root, "g", id=k)
        group.set(f"{{{INKSCAPE}}}groupmode", "layer")
        group.set(f"{{{INKSCAPE}}}label", o.get("label", k))
        for i, m in enumerate(o["marks"], 1):
            node = emit(group, m, size)
            node.set("id", f"{k}-{i}")
    ET.ElementTree(root).write(out, encoding="utf-8", xml_declaration=True)
    return objects


def check_text_fit(spec):
    from matplotlib import font_manager
    from matplotlib.ft2font import FT2Font
    from matplotlib.textpath import TextToPath

    weights = {}
    for weight in (400, 700):
        fonts = []
        for name in ("DejaVu Sans", "Noto Sans CJK SC", "Microsoft YaHei"):
            try:
                path = font_manager.findfont(font_manager.FontProperties(family=name, weight=weight),
                                             fallback_to_default=False)
            except ValueError:
                continue
            fonts.append((path, FT2Font(path).get_charmap()))
        weights[weight] = fonts
    measure = TextToPath()
    for group in spec["objects"]:
        for mark in group["marks"]:
            if mark["type"] != "text":
                continue
            label = mark["label"]
            weight = 700 if mark.get("weight",400) >= 700 else 400
            glyphs = {ord(c) for c in label if not c.isspace()}
            path = next((p for p, glyphmap in weights[weight] if glyphs.issubset(glyphmap)), None)
            require(path, group["id"] + ": no installed font covers this label")
            font = font_manager.FontProperties(fname=path, size=mark.get("size",19))
            w,h,desc = measure.get_text_width_height_descent(label, font, ismath=False)
            fraction = {"start":0, "middle":.5, "end":1}[mark.get("anchor","start")]
            x0 = mark["x"] - w*fraction
            y1 = mark["y"] + desc
            require(x0>=0 and x0+w<=spec["size"][0] and y1-h>=0 and y1<=spec["size"][1],
                    group["id"] + ": label extends off the canvas: " + label)


def audit(spec, svg):
    objects = prepare(spec)
    root = ET.parse(svg).getroot()
    by_id = {n.get("id"): n for n in root.iter() if n.get("id")}
    checks = Counter()
    for k, o in objects.items():
        for i, m in enumerate(o["marks"], 1):
            node = by_id[f"{k}-{i}"]
            tag = m["type"]
            checks[tag] += 1
            if tag == "text":
                require(node.text == m["label"], k + ": altered text")
                require(float(node.get("x")) == m["x"] and float(node.get("y")) == m["y"], k + ": shifted text")
            if tag in ("line", "edge"):
                require(node.get("points") == as_points(m["points"]), k + ": geometry mismatch")
            if tag == "edge":
                group = list(by_id[k])
                require((node.get("stroke-dasharray") is not None) ==
                        (bool(m.get("dash")) or m.get("certainty") == "proposed"), k + ": uncertainty encoding mismatch")
                expected = RELATIONS[m["relation"]]
                if expected != "plain":
                    glyph = group[group.index(node) + 1]
                    require(glyph.get("data-glyph") == expected and
                            glyph.get("points") == as_points(marker(m["points"][-2], m["points"][-1], expected)),
                            k + ": wrong terminal glyph")
    return dict(checks)


def json_write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf8")


def run(source, dest):
    spec = json.loads(source.read_text(encoding="utf-8-sig"))
    prepare(spec)
    check_text_fit(spec)
    dest.mkdir(parents=True, exist_ok=False)
    out = dest / "figure.svg"
    objects = draw(spec, out)
    counts = audit(spec, out)
    by_source = {e:[k for k,o in objects.items() if e in o.get("evidence", [])] for e in spec["evidence"]}
    json_write(dest / "evidence.json", {"sources":spec["evidence"],"objects":objects,"source_to_objects":by_source})
    json_write(dest / "scene.json", spec)
    result = {"case_id":spec["case_id"],"status":"partial","description":spec["description"],
              "source_spec_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
              "geometry_checks":counts,"uncertainty":[],"artifacts":["figure.svg","scene.json","evidence.json"]}
    try:
        result["export"] = svgtools.export(out, svgtools.read_svg(out), spec.get("scale", 2))
        result["artifacts"].extend(["figure.pdf","figure.png"])
        result["status"] = "complete"
    except (ValueError, RuntimeError, OSError) as err:
        result["uncertainty"].append(str(err))
    json_write(dest / "result.json", result)
    print(result["status"], counts)
    return int(result["status"] != "complete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--verify", action="store_true", help="Read back an existing OUTPUT/figure.svg")
    args = parser.parse_args()
    if args.verify:
        spec = json.loads(args.spec.read_text(encoding="utf-8-sig"))
        print(audit(spec, args.output / "figure.svg"))
    else:
        raise SystemExit(run(args.spec, args.output))
