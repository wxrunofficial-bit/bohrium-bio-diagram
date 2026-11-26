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

Use left-to-right slots for the main cascade and separate rows for branches. Use native SVG markers and shared relation text where appropriate for your workorder. The bundled rendering uses an arrow for `activation` and `modification`, a bar for `inhibition`, a hollow arrow for `transport`, and no directional head for `binding` or `association`. Use an action label for modifications. Use `indirect` for a multi-step directed relation and `certainty: "proposed"` or `"unknown"` for dotted uncertainty when a relationship can be responsibly shown. Set manual routing with SVG coordinate pairs in `via` and one or both ports (`top`, `bottom`, `left`, `right`) for loops or special routes. This editor's categorical legend is generated from the same color table used for fills. Use a separate plotting script for continuous scales and quantitative plots.

## Edit or export

The edit plan uses `operations` with `id`, `field`, `expected`, `value`, `source`, and `reason`. Use a leaf text ID for label changes, or an existing ID and supported presentation attribute for styling. A stale expected value stops the edit. The script records the original SVG hash and verifies unchanged element content outside touched IDs. It reserializes XML, so namespace prefixes, byte offsets, and whitespace outside the XML tree may differ. SVGs using scripts, external assets, or non-embedded SVG references are outside this edit path. Review edits to labels and legend glyphs together if the workorder changes their meaning. Check actual glyphs and wrapping after every edit.

`result.json` records file hashes, structural checks, export information, sources, and limitations. PNG dimensions and file signatures are checked by the program. Open PDF and PNG previews to check visual content, font substitution and clipping. A requested SVG-only run, unresolved node collision, or unavailable renderer leaves an honest partial result. An edge crossover in the report prompts visual inspection. A preview produced by an environment-provided tool can be retained once checked and recorded in the case's result schema.

After running a formal case, map actual fields to its `output_contract`; `--case` supplies the case ID, and `--case-fields` can append case-specific fields. Source location validation checks presence and referential integrity. Review the cited material to establish scientific correctness. To evaluate improvement locally, give a baseline and the Skill the same input and tool budget, review each relation and source before comparing counts, check render integrity after one equivalent edit, and record actual elapsed time and retries. Platform scores come from formal evaluation.

## Plot supplied tabular values

`chart` takes a JSON specification and a UTF-8 CSV. Select `kind` (`line`, `scatter`, `bar`), `x` and `y` column names, `title`, `x_label`, `y_label` and `source_locator`. Optionally set `group`, `error` (a supplied symmetric error width) and `error_label`, `y_limits` or `missing: "skip"` for explicitly allowed omissions. Lines sort numeric x within each group. Bar categories follow source order and axes include zero. Duplicate x positions within a line/bar group, clipping limits, missing values and nonfinite numbers are rejected unless the case explicitly allows missing rows. `source_mapping.json` retains the input hash and each plotted row's original line and value. The illustrative CSV contains synthetic example numbers.
