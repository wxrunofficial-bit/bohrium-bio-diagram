# Test the story against the speaking slot

Start with `examples/anscombe-talk.json` for the full data shape. For each slide, put the words the speaker intends to say in `notes`, a one-sentence spoken bridge in `transition`, and the slide's total time in `seconds`. Supply optional `visual_seconds` to account for pointing at evidence or letting the audience read. `next_slide`, if present, is the ID of the next core slide or null at the end. Put backups after the core talk with `appendix: true`.

Set `pacing` at the top of the plan if the audience, language or speaker warrants a different rate. Example: `{"words_per_minute": 140, "han_per_minute": 225, "reserve_seconds": 20}`. Run `python scripts/story.py plan.json /app/work/rehearsal`. The JSON links each headline to source facts, and the CSV gives start, end, estimated narration and remaining time. Rehearse estimates aloud. Equations, numbers, unfamiliar terms and audience questions can require more time than a word- or character-count estimate.

Read the sequence of slide titles on its own. The question, observations, interpretation and caveat should still connect. Inspect the real figures and speaker notes in the rendered deck before finalizing it.
