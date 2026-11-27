# 学术 PPT 生成与编辑

Bohrium challenge [ppt-6ad93034](https://play.bohrium.com/challenge/ppt-6ad93034).
Use [SKILL.md](SKILL.md) as the entry point. This release handles a targeted native table correction, a scoped typeface change, a source-linked new deck, and the final delivery check.

## Reproduce

Install the Python dependencies in `requirements.txt`. Use known fonts with coverage for the source language. Run the following with your own PPTX and edits. The example JSON in [references/patch.md](references/patch.md) describes the plan format.

```sh
python scripts/edit_deck.py inspect original.pptx
python scripts/edit_deck.py apply original.pptx plan.json revised.pptx
python scripts/verify_delivery.py case.json result.json --artifact revised.pptx
```

An independent two-slide fixture was reopened as native PowerPoint data after editing. Only the selected slide XML changed. The package audit preserves notes, original relationships, neighboring cells, and the other slide byte for byte. A stale before value was rejected. See [verification](examples/regression-verified.json).

For a new editable slide deck, run `python scripts/deck.py examples/deck-input.json /tmp/academic-editing-demo`. Scientific data stays within the evidence schema. The preview renderer covers authored primitive/text/image objects. Open arbitrary supplied Office decks in a native presenter for full layout and media rendering. Design sources are listed in [references/design.md](references/design.md).
