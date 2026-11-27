---
name: weekly-skill
description: Create or edit source-verified experimental apparatus and research-workflow diagrams with physical cross-sections, named ports, measurement channels, readouts and editable vector previews. 实验装置与技术路线图。
---

# 实验装置与技术路线图

Read the actual workorder, `/input/case.json` and its output_contract, the source assets, and the case environment resources. Preserve originals and work under `/app/work`. Write final case artifacts under `/app/output` with stable filenames. Inspect the sources and the rendered output before recording success. Use the checks and references in `references/visual-brief.md`.

1. Parse the task, actual method and original apparatus. Write an inventory of quantities, sensors, actuators, physical ports and sequence steps. Distinguish material flow, pressure transfer, electrical leads, signal/data paths, optical rays and operations. Identify direction, units, environmental conditions, and which steps or settings are documented. Label any schematic that omits physical dimensions or is not to scale.
2. Choose one principal view for the physical setup and one visibly separate stage for the experimental or analysis sequence if needed. Use a cross-section when passages matter. Use connection semantics rather than color alone. Preserve the physical endpoints, direction, independence of channels and why a quantity is measured before showing an equation or inference. Use short aligned callouts with their quantity and unit where known. Give high contrast to the experimental pathway. Keep secondary hardware and unmeasured working assumptions subordinate.
3. For geometry and a source-bound schematic, run `python scripts/illustrate.py scene.json /app/work/apparatus`. Named port readback confirms that links attach to the declared physical points. Use `scripts/plate.py` for topology-first setup or workflow order. Use `scripts/local_edit.py` and the original SVG for bounded revisions. Do not recalculate or propose new operating parameters unless the task requests this and evidence supports the change.
4. Trace each channel independently from physical input through named instrument ports to the result. Confirm that crossings do not imply unintended connections. Check physical versus signal flow arrows, experimental sequence, units, scale, and qualifiers. Report differences from the source and check the raster and printable exports at the same size.

Write the original case_id and each required field in result.json. Use exact requested nested schema, editable source, rendered previews, evidence, edit log, numeric/semantic checks, and limitations. Fit the file format and asset conventions stated by this case. Record a partial result if unsupported. The public examples exercise the workflow and are independent of the evaluator’s inputs.
