# 生物机制图与通路图

This release includes a source-led workflow, editable artifact generator, geometry checks, examples and a rerun command. Read [SKILL.md](SKILL.md) before use. The starter examples are independent demonstrations.

```sh
python scripts/illustrate.py examples/editorial-scene.json /tmp/pathway
python scripts/illustrate.py examples/editorial-scene.json /tmp/pathway --verify
python scripts/pathway.py draw examples/feedback.json --edge-table examples/feedback.csv --output /tmp/legacy-graph
```

Use Python 3.10+ with the dependencies in requirements.txt. A general-purpose browser, CairoSVG, or Inkscape can render SVG features outside the bundled basic primitives where installed. Use fresh output paths; preserve original assets for comparison. Demo source IDs refer to explicit text or page, panel and row locators. Validate the scientific meaning in the actual source before editing or publishing an official case.

## Design and testing

The new composition prioritizes the transmitted relationship or scientific comparison and uses direct labels. The scripts map visible vector elements to source evidence, and the run checks include final size, layout, exported geometry and source-preserving behavior. Read [visual brief and sources](references/visual-brief.md) for the external design practices applied.
