# 学术汇报内容组织

Bohrium challenge [challenge-20870c35](https://play.bohrium.com/challenge/challenge-20870c35).
Start with [SKILL.md](SKILL.md). The workflow turns source evidence into an audience-specific presentation, timed narration, and native editable slides.

## Reproduce

Install the Python dependencies in `requirements.txt`. Use separate, fresh output directories for each command.

```sh
python scripts/story.py examples/anscombe-talk.json /tmp/rehearsal
python scripts/deck.py examples/anscombe-talk.json /tmp/talk
```

Read [the rehearsal plan](references/rehearsal.md) for how to allocate time to evidence and separate backup slides. The resulting CSV and JSON link each claim, source, speaking slot and upcoming slide. They surface likely time overruns before final rendering. They provide estimates to check through actual rehearsal.

The [verification](examples/regression-verified.json) added a backup slide and tested a deliberately overfull version. All six native slides were reopened with real speaker notes. In that fixture the main talk occupied 204 seconds with 26 seconds left. The editable PPTX and its primitive preview can be built together. For final work, render the PPTX natively and inspect the actual figures and slide order. Source and design influences are listed in [references/design.md](references/design.md).
