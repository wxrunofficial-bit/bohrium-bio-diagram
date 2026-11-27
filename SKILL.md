---
name: academic-ppt-editing
description: Edit an academic PPTX in place or build a new evidence-led deck from source materials. Use for targeted slide, text, table, visual, or typography changes with editability and a readback audit.
---

# 学术 PPT 生成与编辑

1. Read `/input/case.json`, the work order, and source materials before editing. List the requested outputs and field names from the actual contract. Write final files under `/app/output`, retaining the exact case ID. Use the supplied paper, slide, figure, or table as the source for each scientific change.
2. **Existing PPTX:** Inspect with `python scripts/edit_deck.py inspect original.pptx`. Map each request to a slide, native object ID, and exact before value. For text, native table cells, typeface, font size, and geometry, apply the JSON plan with `python scripts/edit_deck.py apply original.pptx plan.json revised.pptx`. See [the edit plan](references/patch.md). A package audit lists the changed slide parts and checks that every other ZIP member matches the input. Use native Office editing for actions outside the helper's scope. For a requested chart value change synchronize its workbook and cache, then inspect the plotted value and source.
3. **New PPTX:** Use the real evidence and a claim-to-slide plan. For the supported editable scene types, run `python scripts/deck.py plan.json /app/work/deck`. Use an evidence-led headline, one primary visual per slide, an appropriate visual scale, brief slide labels, and source detail in speaker notes. See [design and rendering checks](references/design.md).
4. **Review:** Render the actual original and final PPTX through the same native engine, preferably LibreOffice where installed. Inspect every changed slide at presentation size. Verify long strings fit, table data and units are correct, aspect ratio and labels survive, and scope is limited to requested slides and objects. A primitive-only preview may be used for authored primitives. Label any renderer limits and unresolved differences.
5. **Deliver:** Place the real PPTX and requested exports at the exact requested paths. Write `result.json` with the revision, evidence locators, and side-by-side or package verification. Run `python scripts/verify_delivery.py /input/case.json /app/output/result.json --artifact YOUR_FILE.pptx` with a flag per required physical artifact. Fix concrete errors before finalizing. Check the full task specification for conditional outputs and special contract constraints.

Use the bundled examples only to learn the plan format.
