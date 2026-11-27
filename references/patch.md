# Target one native object at a time

Run `python scripts/edit_deck.py inspect original.pptx` to obtain slide order, stable shape IDs, runs, table cells and explicit geometry. For a table, row, column and run indices are zero-based. Slide numbers are one-based. Look for the editable cell anchor when cells are merged.

```json
{
  "case_id": "example",
  "operations": [
    {
      "slide": 2, "shape_id": 7, "row": 2, "column": 1, "run": 0,
      "action": "table_text", "expected": "9.6 ms", "value": "9.8 ms",
      "source": "Revision memo, updated benchmark table, row B",
      "reason": "Replace the single corrected benchmark value"
    }
  ]
}
```

Use `text` for a regular run, `font_size` in hundredths of a point, `typeface` with script `latin`, `ea` or `cs`, and `box` with `[x, y, width, height]` in EMU in the slide's coordinate system. A null `expected` typeface or size means the run inherits that property. For chart data, grouped-child positioning, new objects, text stored as fields and complex edits, use a native application and verify the changed objects separately. Compare both the audit and a native presentation-size render before reporting completion.
