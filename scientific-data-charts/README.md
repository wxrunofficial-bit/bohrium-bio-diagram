# Scientific data charts and source-preserving edits

Generate publication figures from an actual CSV or Excel range. Deliver a layered SVG, a PDF with embedded font, a resolution-controlled PNG, the original data and an editable drawing specification. Run from the directory that contains SKILL.md. Python 3.10+, Matplotlib, NumPy and Pillow are required for quantitative generation. Install requirements.txt if necessary. Use an installed sans-serif font covering every character. For Chinese use Noto Sans CJK SC or Microsoft YaHei. Set MPLCONFIGDIR to a writable cache in managed environments. No external model or paid service is used.

## First figure

```sh
python -B scripts/figure.py examples/assay.json /tmp/assay-v1
python -B scripts/verify.py /tmp/assay-v1
python -B scripts/figure.py examples/quartet.json /tmp/quartet-v1
python -B scripts/benchmark.py /tmp/paired-demo
python -B scripts/local_edit.py examples/edit-source.svg examples/edit-plan.json /tmp/label-edit
```

The assay is synthetic. The second example reconstructs four published datasets. Run each command into a fresh directory. Reopen figure.svg in Inkscape to change individual text/marks. The drawing specification and copied source rerender the figure from scratch. The SVG group IDs are stable across style-only edits with the same panel order and row set. Source edits can use XPath-like numeric child paths when an imported object lacks an ID. A before-value mismatch aborts before writing.

## Data contract

| Key | Meaning |
|---|---|
| id, data, source_locator | Case ID, CSV path relative to spec, source file version and exact sheet/table/page locator. delimiter defaults to comma. CSV record 2 is the first data record following the header, including quoted multiline records as one record. |
| panels | Ordered panel objects. kind = bar, line, scatter, box or heatmap. x/y are source field names, series is optional. where filters exact field values. xlabel/ylabel carry the quantity and units. |
| bounds, error_label | Two source columns for absolute lower and upper limits, plus the scientific meaning. Preserve supplied asymmetric intervals. annotation optionally names a source text column for a point/bar label. |
| box | Supply raw observations; groups use the median, IQR and 1.5×IQR whisker convention; outliers remain visible. Precomputed quantile summaries require a separate bxp adaptation. |
| heatmap | x and y are categorical keys, value is numeric. Provide domain, cmap and colorlabel as required. Missing cells are blank and reported. Reject duplicate coordinates. |
| order, sort_x, xlim, ylim, xscale, yscale | Ordered categories, line traversal, fixed physical coordinate domains and scale. Keep case-mandated axis direction. Use positive values for log scales. |
| style | mm=[width,height], dpi, pt, line_pt, marker_pt, columns, font, transparent, colors mapping from exact series strings to color. Dimensions apply to the whole multi-panel figure. |
| changes, human_confirmations | Actual edits/confirmations, before/after, source, reason. |
| source.csv, figure.json | Portable editable inputs. Retain original workbook and extraction map alongside them when Excel is used. |
| mapping.json, reverse.csv | SVG object to source record/field, and record/field to all visual objects, including derived fits. Source byte SHA-256 detects later replacement. |
| audit.json, result.json | Checks of the final export, adaptations, software versions and uncertainty. Distinguish a clean geometric audit from a font, layout or interpretation warning. |

For box plots, all contributing records map to each derived object. The verifier independently recalculates quartiles, the median, adjacent values, caps and individual outliers. For heatmaps use facets for separate series. Unit conversion, imported PDF digitization, journal-specific ICC conversion and the statistical validity of significance tests need case-specific work. PNG uses the RGB color model; the default export does not attach a journal ICC profile. SVG uses editable live text and a named font; PDF embeds the resolved font. Install the recorded font on editing machines. An SVG edit uses installed Inkscape, CairoSVG, librsvg, the restricted Matplotlib primitive renderer, or headless Chromium depending on availability. Inspect renderer, preview differences and partial status before publishing. For high-density figures do a preview inspection at final size.

## Reproduction, comparisons and credits

Anscombe, F. J. (1973), *Graphs in Statistical Analysis*, pp. 18–19, Figs. 1–4 and the 11-row table. Our four panels reproduce the source coordinates and fit; colors, titles and layout are adapted for a combined plate. In II the curvature is visible, in III the high response is at x=13, and in IV ten points share x=8 while the eleventh has x=19. The original rounded line y=3+0.5x and R²≈0.667 are checked with stated tolerances. Fit segments span the observed x domain; the original shows longer extensions. [Original paper](https://doi.org/10.1080/00031305.1973.10478966) · [Independent table transcription](https://www2.stat.duke.edu/courses/Fall03/sta290/Lectures/Anscombe.html).

The mark/encoding specification draws on the declarative grammar described by Satyanarayan et al. The renderer uses Matplotlib's SVG, PDF and Agg backends. We add point-to-cell evidence, reverse indexing, SVG geometry readback, and a preconditioned edit of supplied artwork. The paired demo compares these features with an ordinary Matplotlib script using the same observations, panel count, scale bounds, format, size and resolution. Timing measures the local scripted run. The platform measures Agent improvement on its own cases. [Vega-Lite paper](https://doi.org/10.1109/TVCG.2016.2599030) · [Matplotlib export settings](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.savefig.html).

The source-preserving SVG utilities and schematic layout reuse the author's [evidence-linked drawing project](https://github.com/wxrunofficial-bit/bohrium-bio-diagram). This folder contains the complete chart entry point and its resources.
