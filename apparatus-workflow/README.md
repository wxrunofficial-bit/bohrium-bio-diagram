# Experimental apparatus and research workflow

Render source-linked diagrams and verify the editable vector directly. The Pitot-static probe example is an independently sourced illustration. The official test harness supplies its own cases.

```sh
python -B scripts/plate.py examples/pitot.json /tmp/pitot --profile apparatus
python -B scripts/local_edit.py /tmp/pitot/figure.svg
python -B scripts/local_edit.py /tmp/pitot/figure.svg examples/revise-label.json /tmp/pitot-revised
python -B scripts/check_plate.py /tmp/pitot
```

Use Python 3.10 or newer. With Matplotlib and Pillow the sample runs offline. Inkscape, CairoSVG or librsvg are useful for editing and previewing complex supplied SVGs. The primitive Matplotlib renderer implements exactly the SVG features listed in scripts/plot_preview.py. Use fonts present on the machine. Install Noto Sans CJK SC for Chinese when needed. Choose a fresh output directory for a new revision. Keep the SVG, JSON model and mapped source together.

| Input | Meaning |
|---|---|
| case_id, title, size | Original case identifier, visible figure title, canvas in px |
| sources | Unique id, real document/URL, exact location and verified statement |
| panels | Nonoverlapping rectangular regions with titled panel label and local objects |
| nodes | id, label, box=[x,y,width,height], style, evidence IDs; for apparatus also specify kind and named ports |
| ports | Each port has coordinates [fraction across, fraction down] on a component boundary; use N/S/E/W in a schematic if no special ports are required |
| edges | Source/target node, out/in port, typed style, evidence, optional absolute via waypoints in the same panel |
| callouts | Text plus position [x,y], evidence IDs, optional font_size or anchor |
| raster_scale | Number of raster pixels per SVG viewport unit; for 300 DPI on the default 96 DPI SVG physical scale use 3.125 |
| edits | Separate operations with ID/path, field, actual old value, new value, evidence and reason |

Every rendered component, annotation and relation is individually addressable in the layered SVG. Both directions of evidence lookup are recorded in source-map.json. The verifier reads positions, edge direction, styling and text from the finished SVG, rejects accidental routing through components and warns about intersections. Use explicit waypoints when the automatic routes cannot clear components. Inspect junctions and crossings visually. Here the renderer measures estimated label fit; small symbols and long multilingual labels still require a visual check. The built-in geometry is a rectangular component diagram. Custom contours, arbitrary perspective and complex data plots require additional case-specific drawing with the same evidence model.

The example re-expresses the source's topology and qualifications in two editable panels. It intentionally omits equipment dimensions and visual details that are irrelevant to its explanatory purpose. See the cited document and exact locators embedded in the example source map. [Example source](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/pitot-static-tube-speedometer/)

Shared SVG edit and preview utilities are adapted from the author's public chart project in the same repository.
