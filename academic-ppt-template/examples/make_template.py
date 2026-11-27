"""Build a portable, illustrative 4:3 institutional template with placeholders."""
from pathlib import Path
import sys,json
from pptx import Presentation
from pptx.util import Pt
from pptx.dml.color import RGBColor

out=Path(sys.argv[1])
out.mkdir(exist_ok=False,parents=True)
p=Presentation()
p.slide_width,p.slide_height=Pt(720),Pt(540)
s=p.slides.add_slide(p.slide_layouts[5])
s.background.fill.solid()
s.background.fill.fore_color.rgb=RGBColor.from_string("F3F5F6")
title=s.shapes.title
title.left,title.top,title.width,title.height=Pt(43),Pt(38),Pt(630),Pt(92)
r=title.text_frame.paragraphs[0].add_run()
r.text="Insert a source-grounded claim"
r.font.name="DejaVu Sans"
r.font.size=Pt(28)
r.font.bold=True
r.font.color.rgb=RGBColor.from_string("16334D")
footer=s.shapes.add_textbox(Pt(43),Pt(497),Pt(633),Pt(25))
r=footer.text_frame.paragraphs[0].add_run()
r.text="Quantitative methods seminar"
r.font.name="DejaVu Sans"
r.font.size=Pt(11)
r.font.color.rgb=RGBColor.from_string("16334D")
body=s.shapes.add_textbox(Pt(43),Pt(184),Pt(635),Pt(78))
r=body.text_frame.paragraphs[0].add_run()
r.text="Insert the observed comparand and qualification"
r.font.name="DejaVu Sans"
r.font.size=Pt(20)
r.font.color.rgb=RGBColor.from_string("16334D")
s.notes_slide.notes_text_frame.text="Demonstration deck. Source and file ownership remain with the author."
p.save(out/"template.pptx")
ops=[dict(slide=1,shape_id=title.shape_id,run=0,action="text",expected="Insert a source-grounded claim",
          value="A rounded fit can hide four patterns",source="Anscombe (1973), Figs. 1–4",reason="Insert the evidence-led claim into the native title placeholder."),
     dict(slide=1,shape_id=body.shape_id,run=0,action="text",expected="Insert the observed comparand and qualification",
          value="Four datasets, 11 observations each",source="Anscombe (1973), p. 19 table",reason="Fill the supplied body text zone.")]
(out/"adapt.json").write_text(json.dumps(dict(case_id="public-template-example",template_source="Illustrative 4:3 title layout with a native master and footer",operations=ops),indent=2),encoding="utf8")
