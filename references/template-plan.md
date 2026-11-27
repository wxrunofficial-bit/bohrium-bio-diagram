# Fill real layout placeholders

Use `python scripts/fill_template.py inspect supplied.potx` to find the exact layout part and editable indices. This is an illustrative plan, so replace the layout path and indices with those returned for the supplied file.

```json
{
  "slides": [
    {
      "layout": "ppt/slideLayouts/slideLayout2.xml",
      "text": {"0": "The test distinguishes the two conditions", "1": "First finding\nSecond finding"}
    }
  ]
}
```

Run `python scripts/fill_template.py build supplied.potx plan.json final.pptx`. The audit reports created slide and layout parts, exact template dimensions, and hashes for the supplied file. The new text sits within editable placeholders. Existing slides are retained. For a deck containing sample slides, fulfill the work order's required slide count by using the scenario's existing targets or removing samples in a native editor. In a native editor handle charts, figures, inherited graphics, manual footer changes and new speaker notes. Render final and reference in the same engine and check that any inherited logo, footer and numbering appear as expected.
