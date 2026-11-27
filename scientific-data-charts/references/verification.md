# Public demonstrations, independent of the official cases

| Task | Direct checks on artifacts |
|---|---|
| Anscombe quartet | 44 point positions and four OLS segments matched the CSV after rendering. 65 editable SVG text nodes, 176 reverse links, one-page 178 × 147 mm PDF. |
| Source-supplied intervals, two lines | Six point positions, six asymmetric interval paths and two connecting paths checked. Units and interval meaning remain editable text. |
| Grouped bars | Four bars and four supplied intervals verified. Contrasting dark intervals remain visible through the colored bars. |
| Signed heatmap | Four positions and color assignments verified, including a negative source value. |
| Grouped boxes | 28 vector groups verified across four boxes, including quartiles, medians, whiskers, caps and fliers. |
| Existing SVG | Replaced one source label. Seven other XML nodes preserved. Rasterized PDF and PNG were nonblank; mean absolute RGB difference at preview size was 2.063/255. |
| Negative controls | Shifted an SVG mark horizontally by 4 pt, removed one reverse link, or changed 8.04 to 9.04 after rendering. Each independent corruption caused verification to fail. |

See examples/quartet-preview.svg for the generated plate and examples/comparison.json for raw paired results. These are independent public examples, not formal tests. A standard Matplotlib script drew the data correctly but its default SVG contained zero editable text nodes and provided no explicit per-object source links. The audited run produced the geometry checks shown above. One run per method cannot estimate general time savings. Reproduce by running scripts/benchmark.py into a fresh directory.

## From a discrepancy back to a cell

Run `python scripts/lookup.py OUTPUT --id p1-point-1` to inspect the first plotted observation in the quartet. Run `python scripts/lookup.py OUTPUT --record 2 --field y1` to locate both the point and the fitted line depending on that cell. For XLSX follow the same CSV record and field in the accompanying *.cells.json file. Resolve every flagged value before final export.
