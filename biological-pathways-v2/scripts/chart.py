"""Render supplied CSV values with editable axes, marks and labels."""

import csv
import math
import re
from collections import defaultdict

import svgtools


COLORS = ('#27649d','#147e6d','#a35518','#934b83','#556c3c','#8c5060','#424f87','#8c7524')


def render(spec, csv_path, out, scale):
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt

    kind = spec['kind']
    if kind not in {'bar', 'line', 'scatter'}:
        raise ValueError('chart kind must be bar, line or scatter')
    if not all(str(spec.get(f,'')).strip() for f in ('title','x_label','y_label','x','y','source_locator')):
        raise ValueError('chart requires title, axis labels, columns and source_locator')
    columns = [spec[f] for f in ('x','y','group','error') if f in spec]
    groups = defaultdict(list)
    rows = []
    omitted = []
    categories = []
    with csv_path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        if len(set(headers)) != len(headers) or any(col not in headers for col in columns):
            raise ValueError('CSV headers are duplicated or requested columns are missing')
        for row in reader:
            line = reader.line_num
            if None in row or any(row[col] is None for col in columns):
                raise ValueError(f'CSV row ending on line {line} has the wrong number of fields')
            if any(not row[col].strip() for col in columns):
                if spec.get('missing') != 'skip':
                    raise ValueError(f'CSV row ending on line {line} has missing values')
                omitted.append(line)
                continue
            x = row[spec['x']].strip() if kind == 'bar' else float(row[spec['x']])
            y = float(row[spec['y']])
            error = float(row[spec['error']]) if 'error' in spec else None
            if not math.isfinite(y) or (kind != 'bar' and not math.isfinite(x)) or (error is not None and (not math.isfinite(error) or error < 0)):
                raise ValueError(f'CSV row ending on line {line} contains an invalid number or error width')
            group = row[spec['group']].strip() if 'group' in spec else ''
            if kind == 'bar' and x not in categories:
                categories.append(x)
            item = {'end_line': line, 'x': x, 'y': y, 'group': group, 'error': error}
            rows.append(item)
            groups[group].append(item)
    if not rows or len(groups) > len(COLORS):
        raise ValueError('no plottable rows or too many groups for one panel')
    if kind in {'bar','line'} and any(len({r['x'] for r in values}) != len(values) for values in groups.values()):
        raise ValueError('repeated x in a bar or line group; supply distinct series or use scatter')
    if 'error' in spec and not spec.get('error_label'):
        raise ValueError('describe what the supplied error widths represent with error_label')
    if kind == 'bar' and spec.get('y_limits') and not spec['y_limits'][0] <= 0 <= spec['y_limits'][1]:
        raise ValueError('bar y limits must include zero')
    if spec.get('y_limits'):
        low,high = spec['y_limits']
        if any(r['y']-(r['error'] or 0) < low or r['y']+(r['error'] or 0) > high for r in rows):
            raise ValueError('requested y limits clip supplied values or error bars')

    width = max(780, 85*len(categories)+180)
    height = 570
    pw,ph = round(width*scale),round(height*scale)
    if max(pw,ph) > 10000 or pw*ph > 30_000_000:
        raise ValueError('chart export exceeds pixel budget')
    fig, ax = plt.subplots(figsize=(width/96,height/96), dpi=96, layout='constrained')
    try:
        ax.set(xlabel=spec['x_label'], ylabel=spec['y_label'])
        for side in ('top','right'):
            ax.spines[side].set_visible(False)
        ax.grid(axis='y', color='#dce5ee', linewidth=.7)
        ax.set_axisbelow(True)
        for i,(group, values) in enumerate(groups.items()):
            if kind == 'line':
                values = sorted(values, key=lambda r:r['x'])
            xs = [r['x'] for r in values]
            ys = [r['y'] for r in values]
            errors = [r['error'] for r in values] if 'error' in spec else None
            if kind == 'bar':
                bar_width = .75/len(groups)
                slots = [categories.index(x) + bar_width*(i-(len(groups)-1)/2) for x in xs]
                ax.bar(slots,ys,width=bar_width,color=COLORS[i],label=group or None,yerr=errors,capsize=3)
            else:
                ax.errorbar(xs,ys,yerr=errors,fmt=('o-' if kind=='line' else 'o'),
                            color=COLORS[i],label=group or None,capsize=3,markersize=5,linewidth=1.6)
        if kind == 'bar':
            ax.set_xticks(range(len(categories)),categories,rotation=25 if len(categories)>5 else 0)
        if 'group' in spec:
            ax.legend(frameon=False)
        if spec.get('y_limits'):
            ax.set_ylim(*spec['y_limits'])
        title = spec['title']
        if 'error' in spec:
            title += f"\nError bars: {spec['error_label']}"
        ax.set_title(title)
        svg,png,pdf = (out/f'figure.{ext}' for ext in ('svg','png','pdf'))
        with matplotlib.rc_context({'svg.fonttype':'none','svg.hashsalt':'evidence-chart','pdf.fonttype':42}):
            fig.savefig(svg, format='svg', metadata={'Date':None})
            # The in-file SVG DTD is metadata only; remove Matplotlib's fixed declaration
            # so this standalone, internally linked SVG is usable by the safe local editor.
            svg.write_text(re.sub(r'<!DOCTYPE svg PUBLIC[^>]*>\s*','',svg.read_text(encoding='utf-8'), count=1),encoding='utf-8')
            fig.savefig(pdf, format='pdf', metadata={'CreationDate':None,'ModDate':None})
            fig.set_size_inches((pw+.01)/96,(ph+.01)/96)
            fig.savefig(png, format='png', dpi=96)
        checks = svgtools.verify_exports(png,pdf,pw,ph)
    finally:
        plt.close(fig)
    return {'source_filename': csv_path.name,'source_sha256':svgtools.digest(csv_path),
            'source_locator':spec['source_locator'],'mapped_rows':rows,'omitted_end_lines':omitted,
            'checks':{'renderer':'matplotlib','scale':scale,**checks}}
