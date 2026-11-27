"""Produce a rehearsal timeline and an auditable slide-to-evidence map."""
import argparse
import csv
from pathlib import Path
import re

import scene
from deck import validate_plan


HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
WORD = re.compile(r"[\w]+(?:[’.\-][\w]+)*", re.UNICODE)


def estimate_speech(text, words_per_minute, han_per_minute):
    han_count = len(HAN.findall(text))
    other_words = len(WORD.findall(HAN.sub(" ", text)))
    return round(60 * (other_words / words_per_minute + han_count / han_per_minute), 1)


def plan(spec,out):
    duration=validate_plan(spec)
    scene.require(spec.get("audience") and spec.get("objective"),"Identify audience and its learning objective")
    head=[s["headline"].strip().replace("\n"," ") for s in spec["slides"]]
    scene.require(len(set(head))==len(head),"Duplicated slide headline")
    pacing = spec.get("pacing", {})
    words_per_minute = pacing.get("words_per_minute", 145)
    han_per_minute = pacing.get("han_per_minute", 240)
    reserve = pacing.get("reserve_seconds", 0)
    scene.require(min(words_per_minute, han_per_minute) > 0 and reserve >= 0, "Invalid rehearsal settings")
    scene.require(duration["main"] + reserve <= spec["budget_seconds"], "Core slides leave less than the requested reserve")
    clock = 0
    rows = []
    warnings = []
    main = [slide for slide in spec["slides"] if not slide.get("appendix")]
    scene.require(main, "At least one main slide is required")
    following = {a["id"]: b["id"] for a, b in zip(main, main[1:])}
    appendix_started = False
    for i,s in enumerate(spec["slides"],1):
        start=None if s.get("appendix") else clock
        appendix_started = appendix_started or start is None
        scene.require(not (appendix_started and start is not None), "Place backup slides after the main story")
        next_id = following.get(s["id"])
        if "next_slide" in s:
            scene.require(s["next_slide"] == next_id, f"{s['id']}: next_slide does not follow the actual core order")
        dwell = s.get("visual_seconds", 0)
        scene.require(type(dwell) in (int, float) and dwell >= 0, f"{s['id']}: invalid visual_seconds")
        speech = estimate_speech(s["notes"] + " " + s["transition"], words_per_minute, han_per_minute)
        slack = round(s["seconds"] - dwell - speech, 1)
        if start is not None:
            clock+=s["seconds"]
            if slack < 0:
                warnings.append({"slide_id": s["id"], "seconds_over": -slack,
                                 "issue": "Readout and figure interpretation exceed this slide's allocation"})
        rows.append(dict(slide=i,id=s["id"],section="appendix" if start is None else "main",
                         start_seconds=start,end_seconds=None if start is None else clock,
                         duration_seconds=s["seconds"],role=s.get("role","finding"),
                         spoken_seconds=speech,visual_seconds=dwell,slack_seconds=slack,next_slide=next_id,
                         claim=head[i-1],transition=s["transition"],notes=s["notes"],
                         evidence=[{"id":key,**spec["sources"][key]} for key in s["evidence"]]))
    out.mkdir(parents=True,exist_ok=False)
    scene.write(out/"story.json",dict(case_id=spec["case_id"],audience=spec["audience"],objective=spec["objective"],
                     time=duration,buffer_seconds=spec["budget_seconds"]-duration["main"],rows=rows,
                     pacing={"words_per_minute": words_per_minute, "han_per_minute": han_per_minute,
                             "requested_reserve_seconds": reserve},warnings=warnings))
    with (out/"timing.csv").open("w",encoding="utf8",newline="") as f:
        fields=["slide","section","start_seconds","end_seconds","duration_seconds","spoken_seconds",
                "visual_seconds","slack_seconds","next_slide","role","claim","transition"]
        writer=csv.DictWriter(f,fields,extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print("Slideshow",len(rows),"slides, core",duration["main"],"seconds, appendix",duration["appendix"],"seconds")
    for warning in warnings:
        print(f"Rehearse {warning['slide_id']}: estimated {warning['seconds_over']} seconds over allocation")
    return rows

if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("spec",type=Path)
    a.add_argument("output",type=Path)
    v=a.parse_args()
    plan(scene.read(v.spec),v.output)
