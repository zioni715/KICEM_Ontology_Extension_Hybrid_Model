"""Read the original workbook and WBS afresh; preserve source-cell evidence."""
import sys
import re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared'))
from common import ROOT, T, write, sha
import xlrd
from rdflib import Graph, RDF, RDFS, OWL, URIRef

wbs_path = ROOT / 'KCS_41_48_01_타일공사_시공구조.md'
wbs = []
for line in wbs_path.read_text().splitlines():
    m = re.match(r'^(?:#{2,3}\s+|-\s+)(3(?:\.\d+)*)(?:\.)?\s+(.+)$', line)
    if m:
        wbs.append({'code': m[1], 'label': m[2].strip(),
                    'parent': m[1].rsplit('.', 1)[0] if '.' in m[1] else None, 'quote': line})
assert len(wbs) == len({x['code'] for x in wbs})
path = next((ROOT / 'documents/Documents_2').glob('*.xls'))
book = xlrd.open_workbook(str(path))
fields = {'contractQuantity': 3, 'materialUnitCost': 4, 'laborUnitCost': 6,
          'expenseUnitCost': 8, 'contractUnitPrice': 10, 'contractAmount': 11,
          'previousCumulativeQuantity': 12, 'previousCumulativeAmount': 20,
          'currentQuantity': 21, 'currentAmount': 29, 'cumulativeQuantity': 30,
          'cumulativeAmount': 38, 'remainingQuantity': 39, 'remainingAmount': 47}
rows, excluded = [], []
for name, offset in [('건내', 0), ('건(인)내', 2)]:
    sheet = book.sheet_by_name(name)
    section = ''
    for i in range(5, sheet.nrows):
        title, spec, unit = [str(sheet.cell_value(i, offset + j)).strip() for j in range(3)]
        if re.match(r'^\d{6}\s', title):
            section = title
            continue
        if not title or not unit:
            continue
        tile_section = '타일공사' in section.replace(' ', '')
        mentions = bool(re.search('타일|TILE', title + ' ' + spec, re.I))
        if not tile_section:
            if mentions:
                excluded.append({'sheet': name, 'row': i + 1, 'name': title, 'reason': 'outside_tile_trade_section'})
            continue
        # Include ALL priced rows in the tile section; an LLM reviews adjacent work.
        numbers, cells = {}, {}
        for key, col in fields.items():
            cell = sheet.cell(i, col + offset)
            numbers[key] = cell.value if cell.ctype == xlrd.XL_CELL_NUMBER else None
            cells[key] = {'row': i + 1, 'column': col + offset + 1, 'raw': cell.value, 'type': cell.ctype}
        rows.append({'id': f'{name}:{i + 1}', 'file': path.name, 'sheet': name, 'row': i + 1,
                     'section': section, 'name': title, 'specification': spec, 'unit': unit,
                     'mentions_tile': mentions, 'numbers': numbers, 'cells': cells})
g = Graph().parse(ROOT / 'KO/OWL2/rcpp-owl-final.ttl')
elements = []
for kind in [OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty]:
    for s in sorted(set(g.subjects(RDF.type, kind))):
        if not isinstance(s, URIRef):
            continue
        elements.append({'id': str(s).split('#')[-1], 'iri': str(s), 'type': str(kind).split('#')[-1],
                         'labels': [str(x) for x in g.objects(s, RDFS.label)],
                         'comments': [str(x) for x in g.objects(s, RDFS.comment)],
                         'parents': [str(x).split('#')[-1] for x in g.objects(s, RDFS.subClassOf) if isinstance(x, URIRef)],
                         'domains': [str(x).split('#')[-1] for x in g.objects(s, RDFS.domain) if isinstance(x, URIRef)]})
write(T / 'module1/outputs/raw_rows.json', rows)
write(T / 'module1/outputs/excluded_rows.json', excluded)
write(T / 'shared/wbs.json', wbs)
write(T / 'shared/seed_elements.json', elements)
write(T / 'module1/reports/preparation.json', {'section_rows': len(rows), 'wbs_nodes': len(wbs),
      'inputs': {str(p.relative_to(ROOT)): sha(p) for p in [path, wbs_path, ROOT / 'KO/OWL2/rcpp-owl-final.ttl']}})
print('Prepared', len(rows), 'section rows and', len(wbs), 'WBS nodes', flush=True)
