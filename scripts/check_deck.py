"""Read actual PPTX objects, check science-mark positions and render a preview."""
import argparse
import hashlib
import io
from pathlib import Path
import shutil
import subprocess
import tempfile
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE, MSO_SHAPE
from PIL import Image, ImageDraw
import scene


def examine(path,out,expected=None):
    from matplotlib import pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.patches import Ellipse, Rectangle
    from matplotlib.font_manager import FontProperties
    plt.switch_backend("Agg")
    out.mkdir(parents=True,exist_ok=False)
    prs=Presentation(path)
    w,h=prs.slide_width.pt,prs.slide_height.pt
    flags=[]
    count=0
    pages=[]
    with PdfPages(out/"deck.pdf",metadata={"CreationDate":None,"ModDate":None}) as pdf:
        for i,s in enumerate(prs.slides,1):
            names={shape.name:shape for shape in s.shapes}
            count+=len(s.shapes)
            if expected:
                targets=expected[i-1]["expected"]
                scene.require(len(names)==len(targets),f"Slide {i}: object count changed")
                for obj in targets:
                    shp=names[obj["id"]]
                    if obj["type"]=="text":
                        scene.require(shp.text==obj["value"],f"Slide {i}: text changed")
                    if obj["type"]=="circle":
                        scene.require(abs(shp.left.pt+shp.width.pt/2-obj["x"])<.01 and abs(shp.top.pt+shp.height.pt/2-obj["y"])<.01,
                                      f"Slide {i}: data mark moved")
                    if obj["type"]=="picture":
                        scene.require(hashlib.sha256(shp.image.blob).hexdigest()==obj["asset_sha256"],
                                      f"Slide {i}: imported source figure changed")
                scene.require(s.has_notes_slide and s.notes_slide.notes_text_frame.text,f"Slide {i}: notes lost")
            fig=plt.figure(figsize=(w/72,h/72),dpi=96)
            ax=fig.add_axes([0,0,1,1],xlim=(0,w),ylim=(h,0))
            ax.set_axis_off()
            try:
                fig.patch.set_facecolor("#"+str(s.background.fill.fore_color.rgb))
            except (AttributeError,TypeError):
                fig.patch.set_facecolor("white")
            for rank,shape in enumerate(s.shapes,1):
                x,y=shape.left.pt,shape.top.pt
                sw,sh=shape.width.pt,shape.height.pt
                if any((x<-.01,y<-.01,x+sw>w+.01,y+sh>h+.01)) and shape.shape_type!=MSO_SHAPE_TYPE.LINE:
                    flags.append(f"Slide {i}: {shape.name} extends past the canvas")
                if shape.shape_type==MSO_SHAPE_TYPE.LINE:
                    ax.plot([shape.begin_x.pt,shape.end_x.pt],[shape.begin_y.pt,shape.end_y.pt],
                            color="#"+str(shape.line.color.rgb),lw=shape.line.width.pt,zorder=rank)
                elif shape.shape_type==MSO_SHAPE_TYPE.PICTURE:
                    with Image.open(io.BytesIO(shape.image.blob)) as raster:
                        ax.imshow(raster.convert("RGBA"),extent=(x,x+sw,y+sh,y),aspect="auto",zorder=rank)
                elif shape.has_text_frame and shape.text:
                    ybase=y+sh*.52
                    for para in shape.text_frame.paragraphs:
                        st=para.runs[0].font if para.runs else None
                        if not st or not st.size:
                            flags.append(f"Slide {i}: {shape.name} uses inherited text styles")
                            continue
                        tx=ax.text(x,ybase,para.text,va="center",ha="left",color="#"+str(st.color.rgb),
                                   fontproperties=FontProperties(family=st.name,weight="bold" if st.bold else "normal",size=st.size.pt),
                                   parse_math=False,zorder=rank)
                        fig.canvas.draw()
                        b=tx.get_window_extent()
                        if b.x1>fig.bbox.x1-12 or b.y0<0 or b.y1>fig.bbox.y1:
                            flags.append(f"Slide {i}: text exceeds safe canvas: {shape.name}")
                        ybase+=st.size.pt*1.2
                elif shape.shape_type==MSO_SHAPE_TYPE.AUTO_SHAPE:
                    color="#"+str(shape.fill.fore_color.rgb)
                    patch=Ellipse((x+sw/2,y+sh/2),sw,sh,facecolor=color,zorder=rank) if shape.auto_shape_type==MSO_SHAPE.OVAL else Rectangle((x,y),sw,sh,facecolor=color,zorder=rank)
                    ax.add_patch(patch)
                else:
                    flags.append(f"Slide {i}: {shape.name} needs a native renderer")
            pdf.savefig(fig)
            tile=out/f"slide-{i:02d}.png"
            fig.savefig(tile,dpi=96)
            plt.close(fig)
            pages.append(tile)
    perrow=2
    thumbw=440
    thumbh=round(thumbw*h/w)
    sheet=Image.new("RGB",(perrow*thumbw,((len(pages)+1)//2)*thumbh),"#E1E7E7")
    for i,p in enumerate(pages):
        with Image.open(p) as im:
            sample=im.convert("RGB").resize((thumbw,thumbh),Image.Resampling.LANCZOS)
            sheet.paste(sample,(i%perrow*thumbw,i//perrow*thumbh))
    sheet.save(out/"thumbnail.png")
    return {"slide_count":len(prs.slides),"objects":count,"warnings":list(dict.fromkeys(flags)),
            "renderer":"Matplotlib readback of the authored native-PPTX primitive subset",
            "note":"Use PowerPoint or LibreOffice for complete Office layout, master, media and font rendering."}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("pptx",type=Path)
    p.add_argument("out",type=Path)
    args=p.parse_args()
    print(examine(args.pptx,args.out))
