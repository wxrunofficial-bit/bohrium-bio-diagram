"""Render the precise SVG subset emitted by graph.py via Matplotlib."""

import re


def save(root, png, pdf, width, height, pixel_width, pixel_height):
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt
    from matplotlib.colors import to_rgba
    from matplotlib.font_manager import FontProperties, findfont
    from matplotlib.ft2font import FT2Font
    from matplotlib.patches import FancyBboxPatch, Polygon
    from matplotlib.transforms import Affine2D

    # The browser/editor remains the reference for SVG features outside this subset.
    root_attrs = dict(root.attrib)
    if set(root_attrs) - {'width','height','viewBox','font-family','role'}:
        raise ValueError('Matplotlib renderer expects the pathway SVG subset')
    limits = {
        'g': {'transform'}, 'title': set(), 'desc': set(),
        'rect': {'x','y','width','height','rx','fill','fill-opacity','stroke','stroke-width'},
        'line': {'x1','x2','y1','y2','stroke','stroke-width'},
        'text': {'x','y','font-size','fill','font-weight','text-anchor'},
        'polyline': {'points','fill','stroke','stroke-width','stroke-dasharray','stroke-linejoin'},
        'path': {'d','fill','stroke','stroke-width'},
    }
    viewport = [float(v) for v in root_attrs['viewBox'].split()]
    if viewport != [0,0,width,height]:
        raise ValueError('Matplotlib renderer requires an integer zero-based viewport')
    font_options = root_attrs.get('font-family', 'sans-serif').split(',')
    fonts = {}

    def font_for(label, weight):
        chars = frozenset(ord(c) for c in label if not c.isspace())
        for family in [*(f.strip() for f in font_options), 'DejaVu Sans']:
            if family in {'sans-serif', 'serif', 'monospace'}:
                continue
            key = family, weight
            if key not in fonts:
                font = FontProperties(family=family, weight=weight)
                try:
                    path = findfont(font, fallback_to_default=False)
                    fonts[key] = (FontProperties(fname=path), FT2Font(path).get_charmap())
                except ValueError:
                    fonts[key] = (None, {})
            font, charmap = fonts[key]
            if chars.issubset(charmap) and font:
                return font
        raise ValueError(f'no installed font covers the label {label[:45]!r}')

    def color(node, key, opacity=1):
        value = node.get(key, 'none')
        return to_rgba(value, opacity) if value != 'none' else 'none'

    fig = plt.figure(figsize=(width/96,height/96), dpi=96)
    ax = fig.add_axes([0,0,1,1], xlim=(0,width), ylim=(height,0))
    ax.axis('off')
    z = 0

    def draw(node, tf):
        nonlocal z
        if not isinstance(node.tag, str):
            return
        tag = node.tag.rsplit('}',1)[-1]
        attrs = {k for k in node.keys() if not k.startswith(('data-', '{')) and k != 'id'}
        if tag not in limits or attrs - limits[tag]:
            raise ValueError(f'Matplotlib renderer does not implement SVG {tag} {sorted(attrs-limits.get(tag,set()))}')
        if tag in {'title', 'desc'}:
            return
        if tag == 'g':
            transform = node.get('transform')
            if transform:
                match = re.fullmatch(r'translate\(([-+\d.eE]+),([-+\d.eE]+)\) rotate\(([-+\d.eE]+)\)', transform)
                if not match:
                    raise ValueError('unsupported SVG transform')
                x,y,angle = map(float,match.groups())
                tf = Affine2D().rotate_deg(angle).translate(x,y) + tf
            for child in node:
                draw(child,tf)
            return
        if list(node):
            raise ValueError('unsupported nested SVG drawable')
        z += 1
        def metric(key, default=0):
            return float(node.get(key,default))
        style = {'transform': tf + ax.transData, 'zorder': z}
        stroke, fill = color(node,'stroke'), color(node,'fill',metric('fill-opacity',1))
        line_width = metric('stroke-width',1)*.75
        if tag == 'text':
            label = node.text or ''
            if label:
                anchor = {'start':'left','middle':'center','end':'right'}[node.get('text-anchor','start')]
                ax.text(metric('x'),metric('y'),label,ha=anchor,va='baseline',
                        fontproperties=font_for(label,int(metric('font-weight',400))),
                        fontsize=metric('font-size',14)*.75,color=fill,**style)
        elif tag == 'rect':
            x,y,w,h = map(metric,('x','y','width','height'))
            patch = FancyBboxPatch((x,y),w,h,boxstyle=f'round,pad=0,rounding_size={metric("rx")}',
                                   facecolor=fill,edgecolor=stroke,linewidth=line_width,**style)
            ax.add_patch(patch)
        elif tag == 'path':
            path = node.get('d','')
            if not re.fullmatch(r'M[-+\d.,]+(?: L[-+\d.,]+)+(?: Z)?',path):
                raise ValueError('unsupported SVG path grammar')
            points = [tuple(map(float, pair.split(','))) for pair in re.findall(r'[ML]([-+\d.,]+)',path)]
            ax.add_patch(Polygon(points,closed=path.endswith('Z'),facecolor=fill,edgecolor=stroke,
                                 linewidth=line_width,**style))
        else:
            if tag == 'line':
                points = [(metric('x1'),metric('y1')),(metric('x2'),metric('y2'))]
            else:
                points = [tuple(map(float,v.split(','))) for v in node.get('points','').split()]
            stroke_dash = node.get('stroke-dasharray','none')
            line_obj, = ax.plot(*zip(*points),color=stroke,linewidth=line_width,solid_joinstyle='round',**style)
            if stroke_dash != 'none':
                line_obj.set_dashes([float(v)*.75/line_width for v in stroke_dash.split()])

    try:
        for child in root:
            draw(child,Affine2D())
        with matplotlib.rc_context({'pdf.fonttype': 42}):
            fig.savefig(pdf,format='pdf',dpi=96,metadata={'CreationDate': None,'ModDate': None})
        raster_dpi = 96 * pixel_width / width
        fig.set_size_inches((pixel_width + .01) / raster_dpi, (pixel_height + .01) / raster_dpi)
        fig.savefig(png,format='png',dpi=raster_dpi)
    finally:
        plt.close(fig)
