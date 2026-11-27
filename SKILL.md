---
name: academic-ppt-template
description: Fit academic content into a supplied PPTX, POTX, or style specification using real layouts and editable placeholders. Use for template adaptation, inherited master/theme retention, native footer style, and acceptance checks.
---

# 学术 PPT 模板与格式适配

1. Read `/input/case.json`, the work order, source material, and template. Copy out the exact delivery paths, result fields, slide counts, and what the user requires you to preserve. Record the source slide or page for each new claim and figure.
2. **Fill existing template slides:** Run `python scripts/edit_deck.py inspect template.pptx`. Use the existing shape IDs and before values with `python scripts/edit_deck.py adapt template.pptx plan.json new.pptx`. The output audit tests the original layout, theme, dimensions, relationships, notes and other unchanged package parts.
3. **Append text slides from real reusable layouts:** Run `python scripts/fill_template.py inspect template.potx` against the supplied PPTX/POTX. Select layout part names and placeholder indices from the report. Use `python scripts/fill_template.py build template.potx plan.json new.pptx` and read its audit. The helper appends real layout-linked editable text placeholders and carries through the original template parts and existing slides. See [the plan format](references/template-plan.md).
4. For replacing demonstrations, placing existing editable visuals, adding new notes or handling graphic placeholders, work in a native editor or a compatible OOXML workflow. Reuse the matching layout and master. Confirm actual font, logo, title baseline, footer, numbering and margins against the rendered template. For a purely visual specification, construct a new editable template and record which style values were measured and which had to be inferred.
5. Render reference and final slides at equal size with the same native engine. Inspect changed and dense slides full-size. Verify science and notes survive, and check that every new slide links to the intended template layout. Use the task's exact filenames and source citations. Verify the result with `python scripts/verify_delivery.py /input/case.json /app/output/result.json --artifact YOUR_FILE.pptx`; pass a flag per required physical artifact. Report rendering limits or unresolved instructions in the case's result fields.

Use public examples only to learn the commands and data shapes.
