# Evidence-linked biological pathway figures

This package turns an evidence inventory into a layered SVG, a PNG, a PDF, and a machine-readable result. It also applies bounded edits to a supplied SVG and records every requested change. The article or case materials remain the source of truth for the biological content.

## Run the illustrative example

Use Python 3.10 or newer from the submission directory. Preview export uses installed Inkscape, CairoSVG, `rsvg-convert`, Chromium/Edge, or Matplotlib for this package's SVG subset. The `chart` mode uses Matplotlib. Pillow, when available, checks PNG content. Use the evaluator's environment tools if none of the listed renderers is installed.

```sh
python3 -B scripts/pathway.py draw examples/insulin.json --output /tmp/pathway-example
python3 -B scripts/pathway.py edit examples/edit.json --source /tmp/pathway-example/figure.svg --output /tmp/pathway-edit
python3 -B scripts/pathway.py chart examples/chart.json --source examples/chart.csv --output /tmp/pathway-chart
```

On Windows, use writable Windows paths instead of `/tmp` and use the installed Python executable instead of `python3` where necessary. Use a fresh output directory per run so stale files cannot be mistaken for current outputs. The example is illustrative and is unrelated to the official case set. It depicts a limited human insulin signaling excerpt grounded in the three Reactome records linked in the graph input. `edit.json` requests one label edit, so the audit should report exactly one change with other SVG elements preserved.

## Prepare `graph.json`

| Field | Contents |
|---|---|
| `case_id`, `title`, `subtitle` | Input identifier, display title, and optional short scope or condition |
| `sources[]` | `id`, `document`, `locator`, `statement`, and optional `url` or `version`. Use a short paraphrase with a verifiable source location. |
| `lanes[]` | Ordered compartments with `id`, `label`, optional `rows` (default 1) and optional `kind: "membrane"`. In single-row membrane lanes the node overlaps a paired membrane line. |
| `nodes[]` | `id`, `label`, `kind`, `lane`, `column`, optional `row`, and `evidence` (source IDs). Kinds include `gene`, `protein`, `receptor`, `complex`, `molecule`, `process`, `phenotype`, `cell`, `other`. |
| `edges[]` | `id`, `source`, `target`, `relation`, `evidence`, optional `label`, `certainty`, and optional `source_port`, `target_port`, `via`. IDs are stable within a figure. |
| `uncertainties[]` | Optional list of explicit scope or evidence limitations. |
| `encoding` | Optional categorical fill mapping, with `channel: "node_fill"`, `label`, and `categories` entries containing `id`, `label`, `fill` as six-digit hex. For mapped nodes, use `category` and cite the source record supporting the mapping. |

Use left-to-right slots for the main cascade and separate rows for branches. Use native SVG markers and shared relation text where appropriate for your workorder. The bundled rendering uses an arrow for `activation` and `modification`, a bar for `inhibition`, a hollow arrow for `transport`, and no directional head for `binding` or `association`. Use an action label for modifications. Use `indirect` for a multi-step directed relation and `certainty: "proposed"` or `"unknown"` for dotted uncertainty when a relationship can be responsibly shown. Set manual routing with SVG coordinate pairs in `via` and one or both ports (`top`, `bottom`, `left`, `right`) for loops or special routes. This editor's categorical legend is generated from the same color table used for fills. For continuous edge weights, use the CSV join below. Use chart mode for a standalone quantitative panel.

## Edit or export

The edit plan uses `operations` with `id`, `field`, `expected`, `value`, `source`, and `reason`. Use a leaf text ID for label changes, or an existing ID and supported presentation attribute for styling. A stale expected value stops the edit. The script records the original SVG hash and verifies unchanged element content outside touched IDs. It reserializes XML, so namespace prefixes, byte offsets, and whitespace outside the XML tree may differ. SVGs using scripts, external assets, or non-embedded SVG references are outside this edit path. Review edits to labels and legend glyphs together if the workorder changes their meaning. Check actual glyphs and wrapping after every edit.

`result.json` records file hashes, structural checks, export information, sources, and limitations. PNG dimensions and file signatures are checked by the program. Open PDF and PNG previews to check visual content, font substitution and clipping. A requested SVG-only run, unresolved node collision, or unavailable renderer leaves an honest partial result. An edge crossover in the report prompts visual inspection. A preview produced by an environment-provided tool can be retained once checked and recorded in the case's result schema.

After running a formal case, map actual fields to its `output_contract`; `--case` supplies the case ID, and `--case-fields` can append case-specific fields. Source location validation checks presence and referential integrity. Review the cited material to establish scientific correctness. To evaluate improvement locally, give a baseline and the Skill the same input and tool budget, review each relation and source before comparing counts, check render integrity after one equivalent edit, and record actual elapsed time and retries. Platform scores come from formal evaluation.

## Plot supplied tabular values

`chart` takes a JSON specification and a UTF-8 CSV. Select `kind` (`line`, `scatter`, `bar`), `x` and `y` column names, `title`, `x_label`, `y_label` and `source_locator`. Optionally set `group`, `error` (a supplied symmetric error width) and `error_label`, `y_limits` or `missing: "skip"` for explicitly allowed omissions. Lines sort numeric x within each group. Bar categories follow source order and axes include zero. Duplicate x positions within a line/bar group, clipping limits, missing values and nonfinite numbers are rejected unless the case explicitly allows missing rows. `source_mapping.json` retains the input hash and each plotted row's original line and value. The illustrative CSV contains synthetic example numbers.

## Quantitative edges and semantic checks

In `examples/feedback.json`, a fictional cue activates a membrane relay and a proposed feedback edge inhibits it. The adjoining CSV deliberately places rows in a different order from the graph. Join the interaction ID to the source row. The declared domain [0, 1] maps linearly to widths [1.5, 6.5] in SVG units. The output preserves the CSV hash, column names, original row numbers, units, data values and widths. The legend uses the same scale. Missing, repeated, unrecognized, nonfinite and out-of-domain measurements stop drawing with the affected ID or line. Additional non-edge rows should be filtered into a documented case-specific table first; retain the unmodified source and the extraction rule.

```sh
python3 -B scripts/pathway.py draw examples/feedback.json --edge-table examples/feedback.csv --output /tmp/pathway-feedback
python3 -B scripts/audit_figure.py examples/feedback.json /tmp/pathway-feedback/figure.svg --edge-table examples/feedback.csv
python3 -B examples/check_feedback.py /tmp/pathway-feedback
```

The expected illustrative widths are 2.5 for feedback, 6 for trigger and 4 for forward. The standalone audit rereads the SVG and checks visible labels, gene/protein classes declared by the graph, compartment placement, source and target attachments, terminal shape and rotation, legend swatches, line patterns, numeric ticks, and provenance references. Scientific interpretation still needs a source review. The corruption exercise makes independent in-memory edits to a copy of the SVG. It tests wrong direction, a lost inhibition bar, a missing uncertainty pattern, a displaced glyph, a wrong legend color, unit, line width and entity label.

For a numeric line scale use `edge_scale.label`, `unit`, `domain`, `range_px`, `id_column` and `value_column`. The span must increase, widths must fall within 1–9 SVG units, and every drawn edge must have exactly one supplied measurement. Signed values can use a declared signed domain. Interpret sign separately if the source uses it for regulation. Keep absent measurements distinct from measured zero. For channels such as continuous fill and per-node size use the case's plotting tools and verify the resulting glyphs against the table.

When Pillow and Poppler's `pdfinfo` and `pdftoppm` are installed, the exporter checks that the PDF contains one page, renders to a nonblank bitmap, and matches the requested aspect ratio. It records the mean absolute RGB difference against the resized PNG in 0–255 levels. Inspect visible differences and glyph coverage at the final display size. Minimal environments retain the available checks in result.json.

Report reproducible issues through the public repository, including the command, package revision, sanitized minimal inputs, and renderer. Keep private case data out of public issues.
