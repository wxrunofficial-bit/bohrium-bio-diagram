# 学术 PPT 模板与格式适配

Bohrium challenge [ppt-710fbc72](https://play.bohrium.com/challenge/ppt-710fbc72).
Start with [SKILL.md](SKILL.md). Match a supplied PPTX or POTX by filling its editable placeholders or creating slides attached to its original layout. The runnable scripts are under [scripts](scripts).

## Reproduce

Install Python dependencies from `requirements.txt` if needed. Use your own template with the layout and placeholder indices returned by the first command.

```sh
python scripts/fill_template.py inspect supplied.potx
python scripts/fill_template.py build supplied.potx plan.json final.pptx
```

See [the plan format](references/template-plan.md). The script appends text slides and keeps the template's canvas, layouts, theme and master objects. Use the native presenter for complete rendering, editing charts and creating notes on new slides. For editing objects already present, run `python scripts/edit_deck.py inspect original.pptx`, then use the `adapt` command with the requested existing slide objects.

[Verification](examples/regression-verified.json) used an independent 4:3 template. The new slide opens with its real editable placeholders. The original slides, notes, layouts and masters stayed byte-identical. Judge the final render against the actual supplied template for logos, fonts, footers and numbering. Design sources appear in [references/design.md](references/design.md).
