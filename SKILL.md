---
name: academic-presentation-story
description: Construct a scientific presentation with evidence-led claims, timed narration, optional backup slides, and a checked PPTX. Use for reorganizing an academic talk, creating speaker notes and transitions, and fitting an audience and time budget.
---

# 学术汇报内容组织

1. Read the actual work order, `/input/case.json`, paper, and any source deck. Capture the required output fields, audience, duration, language, and material to preserve. Use precise page, figure, panel, table or slide locators.
2. Make an evidence ledger before drafting. Record source, comparand, result, caveat, and speaking purpose for each selected claim. Open with a specific question and stakes. Give only the methods needed to read the results. Put the strongest evidence before interpretation and connect the qualifying limitation to the conclusion. Use backup slides for secondary results or anticipated questions.
3. Build a plan with one claim, the needed visual, actual spoken notes and one sentence handing off to the next slide. Run `python scripts/story.py plan.json /app/work/rehearsal`. Read the timing CSV and story JSON. Each row records claim, source, slot, readout estimate, time to inspect the visual, and next slide. Repair every overfull core slot, rehearse the transitions aloud, and leave the requested reserve. See [the rehearsal plan](references/rehearsal.md).
4. Build or revise the editable PPTX. For a new deck composed of native shapes and source images, run `python scripts/deck.py plan.json /app/work/deck`. Put one meaningful visual at the center of each evidence slide and move speaking detail into the notes. Render the actual PPTX using the installed native presenter, inspect the full deck at ordinary viewing size, and compare the notes and slide order with the rehearsal plan. See [design and visual checks](references/design.md).
5. Deliver only what the case requires under `/app/output`. Keep the original case ID, valid evidence locators, and exact path and field spelling. Check `python scripts/verify_delivery.py /input/case.json /app/output/result.json --artifact YOUR_FILE.pptx`; add a flag per required physical artifact. Record unresolved issues in the required result fields.

Use the example as a data format reference. Derive all real talk content from the supplied material.
