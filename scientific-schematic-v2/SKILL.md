---
name: weekly-skill
description: Generate or edit source-grounded scientific schematics that make physical geometry and active relations legible, with selective edits, editable SVG and geometry checks. 科研示意图生成与编辑。
---

# 科研示意图生成与编辑

Read the actual workorder, `/input/case.json` and its output_contract, the source assets, and the case environment resources. Preserve originals and work under `/app/work`. Write final case artifacts under `/app/output` with stable filenames. Inspect the sources and the rendered output before recording success. Use the checks and references in `references/visual-brief.md`.

1. Review the primary source drawing, caption, assignment and supplied assets. Identify the question the schematic must answer, the perspective (plane, section, exploded or data-flow), entities, location/order, scientific connections and which facts the source actually supports. Source each scientific object and relation by original page/panel/label or trusted written reference. Distinguish direct geometry from intentionally simplified or inferred features.
2. Choose the main view before drawing. Match physical shape and order where they matter. Use a flat composition grouped by the real structure, a limited line hierarchy, restrained color by function, and short aligned annotations. Use visible symbols or geometry that represent the actual device or process. Route along clear axes, remove unnecessary crossings and mark junctions deliberately. Give enough space to labels and reserve insets for an essential view rather than to fill empty space.
3. For a geometry-led figure use `python scripts/illustrate.py scene.json /app/work/output`. It checks stable layer IDs, named endpoints, evidence and exact glyphs. For a topology-led view use `scripts/plate.py` so nodes and routed connectors can be laid out automatically. For an edit use the original native file and `scripts/local_edit.py` where the request applies to SVG. Inspect source IDs, set expected old values, change only the target, then verify the rest. Never swap an original figure for an unrelated vector recreation if the case asks for in-place editing.
4. Review at reference size and full size. Trace each connection from input to output, count the semantically distinct systems and check the grouping visually. Record which simplifications are intentional, whether schematic dimensions are to scale, and what remains unknown. Export reproducible SVG/PDF/PNG with the actual source map.

Write the original case_id and each required field in result.json. Use exact requested nested schema, editable source, rendered previews, evidence, edit log, numeric/semantic checks, and limitations. Fit the file format and asset conventions stated by this case. Record a partial result if unsupported. The public examples exercise the workflow and are independent of the evaluator’s inputs.
