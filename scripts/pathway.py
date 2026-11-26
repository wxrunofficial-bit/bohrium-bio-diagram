"""CLI for evidence-linked diagram creation, export, and source-preserving edits."""

import argparse
import json
import os
import sys
import tempfile
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import graph
import svgtools


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write_json(path, value):
    fd, filename = tempfile.mkstemp(dir=path.parent, prefix='.pathway-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write('\n')
        os.replace(filename, path)
    finally:
        Path(filename).unlink(missing_ok=True)


def artifact(path, out, role):
    return {'path': path.relative_to(out).as_posix(), 'role': role, 'sha256': svgtools.digest(path), 'bytes': path.stat().st_size}


def build(args):
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    result = {'case_id': args.case_id or '', 'status': 'failed', 'main_result': '', 'sources': [],
              'uncertainties': [], 'change_log': [], 'artifacts': [], 'checks': {}}
    errors = []
    try:
        data = read_json(args.input)
        if args.case and not args.case_id:
            case = read_json(args.case)
            result['case_id'] = case.get('case_id', '')
        result['case_id'] = result['case_id'] or data.get('case_id', '')
        if not result['case_id']:
            raise ValueError('supply a case_id in the input, --case, or --case-id')
        if not isinstance(data.get('uncertainties', []), list):
            raise ValueError('uncertainties must be a list')
        result['uncertainties'] = list(data.get('uncertainties', []))
        if args.mode == 'chart':
            import chart
            with tempfile.TemporaryDirectory(prefix='.chart-',dir=out) as temp_name:
                chart_dir = Path(temp_name)
                audit = chart.render(data,args.source,chart_dir,args.scale)
                for ext, role in (('svg','editable_svg'),('png','rendered_png'),('pdf','rendered_pdf')):
                    path = out/f'figure.{ext}'
                    shutil.move(chart_dir/path.name, path)
                    result['artifacts'].append(artifact(path, out, role))
            map_path = out/'source_mapping.json'
            write_json(map_path,audit)
            result['artifacts'].append(artifact(map_path,out,'data_provenance'))
            result['sources'] = [{'document':args.source.name,'locator':audit['source_locator'],'sha256':audit['source_sha256']}]
            if audit['omitted_end_lines']:
                result['uncertainties'].append({'kind':'declared_missing_rows','lines':audit['omitted_end_lines']})
            result['checks']['export'] = audit['checks']
            result['main_result'] = f"Rendered {len(audit['mapped_rows'])} supplied data rows."
            result['status'] = 'complete'
            return finish(out,result,errors,args)
        if args.mode == 'draw':
            root, notes = graph.render(data)
            result['checks']['graph'] = {'evidence_reference_check': 'passed',
                'nodes': len(data['nodes']), 'edges': len(data.get('edges', [])), 'layout_findings': notes}
            result['sources'] = data['sources']
            graph_file = out/'graph.json'
            write_json(graph_file, data)
            result['artifacts'].append(artifact(graph_file, out, 'evidence_linked_graph'))
            result['uncertainties'].extend(notes)
            result['main_result'] = f"Generated an editable pathway with {len(data['nodes'])} nodes and {len(data.get('edges', []))} relationships."
        else:
            if args.source.resolve() == (out/'figure.svg').resolve():
                raise ValueError('provide a distinct output directory to preserve the source SVG')
            root = svgtools.read_svg(args.source)
            audit = svgtools.edit(root, data)
            svgtools.dimensions(root)
            audit['source_filename'] = args.source.name
            audit['source_sha256'] = svgtools.digest(args.source)
            result['change_log'] = audit['changes']
            result['sources'] = list(dict.fromkeys(e['source'] for e in audit['changes']))
            result['checks']['edit'] = {k: v for k,v in audit.items() if k != 'changes'}
            result['main_result'] = f"Applied {len(audit['changes'])} field change(s) in the supplied SVG, preserving other elements."

        svg = out/'figure.svg'
        with tempfile.TemporaryDirectory(prefix='.verify-', dir=out) as temp_name:
            checked_svg = Path(temp_name)/'figure.svg'
            svgtools.write_svg(root, checked_svg)
            root = svgtools.read_svg(checked_svg)
            svgtools.summarize(root)
            checked_svg.replace(svg)
        result['artifacts'].append(artifact(svg, out, 'editable_svg'))
        result['status'] = 'partial'
        if not args.svg_only:
            result['checks']['export'] = svgtools.export(svg, root, args.scale)
            result['artifacts'].extend(artifact(svg.with_suffix(ext), out, role)
                                       for ext, role in [('.png','rendered_png'),('.pdf','rendered_pdf')])
            if not any(n.get('kind') in {'route_obstruction', 'label_needs_position'}
                       for n in result['checks'].get('graph', {}).get('layout_findings', [])):
                result['status'] = 'complete'
        else:
            result['uncertainties'].append({'kind': 'export_not_run', 'detail': 'SVG-only mode requested'})
    except (ValueError, TypeError, KeyError, OSError, RuntimeError, ET.ParseError) as error:
        errors.append({'kind': 'processing_error', 'detail': str(error)})

    return finish(out,result,errors,args)


def finish(out,result,errors,args):
    if args.case_fields:
        try:
            extra = read_json(args.case_fields)
            if not isinstance(extra, dict):
                raise ValueError('case fields must be a JSON object')
            reserved = set(extra) & set(result)
            if reserved:
                raise ValueError(f'case fields cannot overwrite measured values: {", ".join(sorted(reserved))}')
            result.update(extra)
        except (ValueError, OSError) as error:
            errors.append({'kind': 'case_fields_error', 'detail': str(error)})
            if result['status'] == 'complete':
                result['status'] = 'partial'

    result['uncertainties'].extend(errors)
    write_json(out/'result.json', result)
    print(f"{result['status']}: {out / 'result.json'}")
    for issue in errors:
        print(issue['detail'], file=sys.stderr)
    return 0 if result['status'] == 'complete' else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    for mode in ('draw', 'edit', 'chart'):
        command = modes.add_parser(mode)
        command.add_argument('input', type=Path, help='graph, edit plan or chart specification JSON')
        command.add_argument('--output', required=True, type=Path)
        command.add_argument('--case', type=Path, help='official case.json, used to obtain case_id')
        command.add_argument('--case-id', help='override case_id')
        command.add_argument('--case-fields', type=Path, help='JSON object with extra case-specific contract fields')
        command.add_argument('--scale', type=float, default=1.5, help='PNG scale relative to the SVG viewport')
        command.set_defaults(svg_only=False)
        if mode != 'chart':
            command.add_argument('--svg-only', action='store_true', help='retain an intermediate SVG and mark the run partial')
        if mode != 'draw':
            command.add_argument('--source', required=True, type=Path, help='editable source SVG (edit) or data CSV (chart)')
    args = parser.parse_args()
    if not 0.25 <= args.scale <= 5:
        parser.error('--scale must be between 0.25 and 5')
    return build(args)


if __name__ == '__main__':
    sys.exit(main())
