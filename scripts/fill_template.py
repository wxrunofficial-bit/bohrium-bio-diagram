"""Instantiate a supplied PPTX/POTX's real text placeholders without rewriting its masters."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import posixpath
import re
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree

from edit_deck import A, P, R, all_of, manifest, one, parse, part_name


REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
CONTENT_TYPES = "[Content_Types].xml"
PRESENTATION = "ppt/presentation.xml"
PRESENTATION_RELS = "ppt/_rels/presentation.xml.rels"
SLIDE = "application/vnd.openxmlformats-officedocument.presentationml.slide+xml"
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"
POTX = "application/vnd.openxmlformats-officedocument.presentationml.template.main+xml"
INHERITED = {"dt", "ftr", "hdr", "sldNum"}


def child(parent, ns, tag, **attrib):
    return etree.SubElement(parent, f"{{{ns}}}{tag}", **attrib)


def xml(element):
    return etree.tostring(element, encoding="utf-8", xml_declaration=True, standalone=True)


def inspect_layouts(package):
    result = {}
    for name in package.namelist():
        if not re.fullmatch(r"ppt/slideLayouts/[^/]+\.xml", name):
            continue
        root = parse(package.read(name))
        common = one(root, "p:cSld")
        placeholders = {}
        inherited = []
        for shape in all_of(common, "p:spTree/p:sp"):
            marker = one(shape, "p:nvSpPr/p:nvPr/p:ph")
            if marker is None:
                continue
            kind, idx = marker.get("type", "obj"), marker.get("idx", "0")
            if kind in INHERITED:
                inherited.append(kind)
                continue
            if idx in placeholders:
                raise ValueError(f"{name}: ambiguous placeholder index {idx}")
            label = one(shape, "p:nvSpPr/p:cNvPr").get("name")
            box = one(shape, "p:spPr/a:xfrm")
            placeholders[idx] = {"type": kind, "name": label, "marker": dict(marker.attrib),
                                 "layout_has_explicit_geometry": box is not None}
        result[name] = {"name": common.get("name", ""), "placeholders": placeholders,
                        "inherited_markers": inherited, "show_master_shapes": root.get("showMasterSp", "1")}
    return result


def make_slide(layout, values):
    root = etree.Element(f"{{{P}}}sld", nsmap={"p": P, "a": A, "r": R})
    if layout["show_master_shapes"] == "0":
        root.set("showMasterSp", "0")
    tree = child(child(root, P, "cSld"), P, "spTree")
    group = child(tree, P, "nvGrpSpPr")
    child(group, P, "cNvPr", id="1", name="")
    child(group, P, "cNvGrpSpPr")
    child(group, P, "nvPr")
    child(tree, P, "grpSpPr")
    for shape_id, (key, value) in enumerate(values.items(), 2):
        item = layout["placeholders"].get(key)
        if item is None or item["type"] not in {"title", "ctrTitle", "subTitle", "body", "obj"}:
            raise ValueError(f"{key}: select a native text placeholder from the specified layout")
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key}: supply non-empty placeholder text")
        shape = child(tree, P, "sp")
        nv = child(shape, P, "nvSpPr")
        child(nv, P, "cNvPr", id=str(shape_id), name=item["name"] or f"Placeholder {key}")
        child(nv, P, "cNvSpPr")
        child(child(nv, P, "nvPr"), P, "ph", **item["marker"])
        child(shape, P, "spPr")
        text = child(shape, P, "txBody")
        child(text, A, "bodyPr")
        child(text, A, "lstStyle")
        for paragraph in value.splitlines():
            p = child(text, A, "p")
            child(child(p, A, "r"), A, "t").text = paragraph
    child(child(root, P, "clrMapOvr"), A, "masterClrMapping")
    return root


def build(source, plan, output):
    if output.suffix.lower() != ".pptx" or output.exists():
        raise ValueError("Choose a fresh .pptx output")
    if not plan.get("slides"):
        raise ValueError("Supply the slides to append to the provided template")
    with ZipFile(source) as old:
        if len(set(old.namelist())) != len(old.namelist()):
            raise ValueError("Duplicate parts in the supplied Office package")
        if any(name.lower().endswith("vbaproject.bin") or name.startswith("_xmlsignatures/") for name in old.namelist()):
            raise ValueError("Use a native editor for a signed or macro-enabled presentation")
        layouts = inspect_layouts(old)
        existing, dimensions, support = manifest(old)
        p = parse(old.read(PRESENTATION))
        relations = parse(old.read(PRESENTATION_RELS))
        types = parse(old.read(CONTENT_TYPES))
        content = next(x for x in types if x.get("PartName") == "/" + PRESENTATION)
        subtype = content.get("ContentType")
        if subtype not in (POTX, PPTX):
            raise ValueError("Expected a standard PPTX or POTX presentation")
        content.set("ContentType", PPTX)
        slide_list = one(p, "p:sldIdLst")
        if slide_list is None:
            slide_list = etree.Element(f"{{{P}}}sldIdLst")
            size = one(p, "p:sldSz")
            p.insert(p.index(size), slide_list)
        next_number = max((int(x.group(1)) for name in old.namelist()
                           if (x := re.fullmatch(r"ppt/slides/slide(\d+)\.xml", name))), default=0) + 1
        slide_id = max((int(s.get("id")) for s in slide_list), default=255)
        occupied = {x.get("Id") for x in relations}
        append = {}
        audit = []
        for number, item in enumerate(plan["slides"], next_number):
            if set(item) - {"layout", "text"} or not item.get("text"):
                raise ValueError("Each slide takes a layout part and text map; use a native editor for other content")
            layout_name = item["layout"]
            layout = layouts[layout_name]
            name = f"ppt/slides/slide{number}.xml"
            append[name] = xml(make_slide(layout, item["text"]))
            linked = etree.Element(f"{{{REL}}}Relationships", nsmap={None: REL})
            child(linked, REL, "Relationship", Id="rId1", Type=R+"/slideLayout",
                  Target=posixpath.relpath(layout_name, "ppt/slides"))
            append[f"ppt/slides/_rels/slide{number}.xml.rels"] = xml(linked)
            slide_id += 1
            rid = f"rIdAddedSlide{slide_id}"
            if rid in occupied:
                raise ValueError(f"Conflicting presentation relationship {rid}")
            item_id = child(slide_list, P, "sldId", id=str(slide_id))
            item_id.set(f"{{{R}}}id", rid)
            child(relations, REL, "Relationship", Id=rid, Type=R+"/slide", Target=posixpath.relpath(name, "ppt"))
            child(types, CT, "Override", PartName="/"+name, ContentType=SLIDE)
            audit.append({"slide": len(existing)+len(audit)+1, "member": name, "layout": layout_name,
                          "placeholder_indices": list(item["text"])})
        replaced = {PRESENTATION: xml(p), PRESENTATION_RELS: xml(relations), CONTENT_TYPES: xml(types)}
        output.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(output, "x", ZIP_DEFLATED) as final:
            for name in old.namelist():
                final.writestr(name, replaced.get(name) or old.read(name))
            for name, payload in append.items():
                final.writestr(name, payload)
        with ZipFile(output) as final:
            names, final_dimensions, final_support = manifest(final)
            changed = {name for name in old.namelist() if old.read(name) != final.read(name)}
            if (final.testzip() or names != existing+[x["member"] for x in audit] or
                    changed - set(replaced) or final_support != support or final_dimensions != dimensions):
                raise ValueError("Native template preservation check failed")
            for row in audit:
                member = row["member"]
                rels = posixpath.join("ppt/slides/_rels", posixpath.basename(member)+".rels")
                layout = part_name("ppt/slides", parse(final.read(rels))[0].get("Target"))
                if layout != row["layout"]:
                    raise ValueError("Slide-to-layout relationship failed readback")
    return {"new_slides": audit, "original_slide_count": len(existing), "slide_size_emu": dimensions,
            "preserved_template_members": len(support), "changed_original_parts": sorted(changed),
            "source_sha256": sha256(source.read_bytes()).hexdigest(), "rendering_required": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("inspect", "build"))
    parser.add_argument("template", type=Path)
    parser.add_argument("plan", nargs="?", type=Path)
    parser.add_argument("output", nargs="?", type=Path)
    args = parser.parse_args()
    if args.mode == "inspect":
        with ZipFile(args.template) as package:
            report = inspect_layouts(package)
    else:
        if not args.plan or not args.output:
            parser.error("build needs a JSON plan and output .pptx")
        plan = json.loads(args.plan.read_text(encoding="utf-8-sig"))
        report = build(args.template, plan, args.output)
        args.output.with_suffix(".audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
