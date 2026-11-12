"""OmEGa-inspired evidence extraction; API adaptation, not its trained LoRA model."""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared'))
from common import *
from pydantic import BaseModel, ConfigDict
from typing import Literal

class Attribute(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: Literal['material', 'surface', 'dimensions', 'thickness', 'method', 'finish', 'color', 'other']
    value: str
    quote: str

class RowExtraction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    in_tile_scope: bool
    scope_reason: str
    cost_role: Literal['material', 'installation', 'combined', 'other']
    concept_label: str
    definition: str
    wbs_codes: list[str]
    wbs_relation_reason: str
    attributes: list[Attribute]

class BatchExtraction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    rows: list[RowExtraction]

rows = read(T / 'module1/outputs/raw_rows.json')
wbs = read(T / 'shared/wbs.json')
codes = {x['code'] for x in wbs}
results, issues = [], []
for start in range(0, len(rows), 6):
    batch = rows[start:start + 6]
    compact = [{k: r[k] for k in ['id', 'section', 'name', 'specification', 'unit']} for r in batch]
    for item, row in zip(compact, batch):
        item['unit_cost_components'] = {k: row['numbers'][k] for k in ['materialUnitCost', 'laborUnitCost', 'expenseUnitCost']}
    prompt = '''Extract construction ontology information from these Korean tile-trade progress-payment rows.
Return {"rows":[{"id":...,"in_tile_scope":true,"scope_reason":...,"cost_role":"material",
"concept_label":...,"definition":...,"wbs_codes":[...],"wbs_relation_reason":...,
"attributes":[{"name":"material","value":...,"quote":...}]}]}.
Extract ALL explicitly stated attributes: material, surface, dimensions, thickness, method, finish, color, other.
Each attribute name must be exactly ONE of those labels. Multiple attributes per row are expected where supported.
cost_role MUST be exactly ONE of material, installation, combined, other (no pipe-separated values).
Interpret the row title and its unit cost components: tile supply rows with zero labor are material;
tile fixing rows describe installation even when installation consumables contribute material costs.
Return one record per input row. Attribute quote MUST be an exact substring of that row's name or specification;
do not infer dimensions, color, methods, or material properties that the source does not state.
Do not equate ceramic material to floor work. Use the actual specification to identify surface.
Include stair tile even when absent from WBS. Waterproofing adjacent to tile is not automatically tile work.
WBS is a seed, not a whitelist. Empty wbs_codes is allowed. Work breakdown is not OWL subclass.
Use Korean labels and definitions. Do not generate quantities; they are read deterministically.
WBS: ''' + json.dumps(wbs, ensure_ascii=False) + '\nROWS: ' + json.dumps(compact, ensure_ascii=False)
    output_schema = BatchExtraction.model_json_schema()
    output_schema['$defs']['RowExtraction']['properties']['id']['enum'] = [r['id'] for r in batch]
    output_schema['$defs']['RowExtraction']['properties']['wbs_codes']['items']['enum'] = sorted(codes)
    out = api('module1', f'extract_rows_structured_{start}', prompt, 7000, response_schema=output_schema)
    BatchExtraction.model_validate(out)
    mapping = {r['id']: r for r in out['rows']}
    assert set(mapping) == {r['id'] for r in batch}, 'Missing/duplicate row extraction'
    for raw in batch:
        r = mapping[raw['id']]
        assert type(r['in_tile_scope']) is bool
        assert r['cost_role'] in ['material', 'installation', 'combined', 'other']
        assert set(r['wbs_codes']) <= codes
        if not raw['mentions_tile'] and '방수' in raw['name']:
            issues.append({'row': raw['id'], 'original_scope_judgment': r['in_tile_scope'],
                           'reason': 'Adjacent waterproofing retained as related evidence, excluded from tile cost scope'})
            r['in_tile_scope'] = False
            r['scope_reason'] = '타일 구간에 인접한 별도 방수 작업; 타일 비용항목에서 제외'
        accepted = []
        for a in r['attributes']:
            if a.get('quote') and any(a['quote'] in raw[k] for k in ['name', 'specification']):
                accepted.append(a)
            else:
                issues.append({'row': raw['id'], 'attribute': a, 'reason': 'quote_not_in_source_row'})
        r['attributes'] = accepted
        # Exact source-token fallback, recorded separately from LLM extraction.
        for token in ['개량압착', '압착', '접착']:
            if token in raw['name'] and not any(a['name'] == 'method' for a in accepted):
                accepted.append({'name': 'method', 'value': token, 'quote': token, 'origin': 'exact_source_token_adapter'})
                break
        results.append({**raw, 'extraction': r})
    write(T / 'module1/outputs/extracted_rows.partial.json', results)
    print('Extracted', len(results), '/', len(rows), flush=True)
write(T / 'module1/outputs/extracted_rows.json', results)
write(T / 'module1/reports/extraction_audit.json', {'rejected_attributes': issues, 'rows': len(results)})
import runpy
runpy.run_path(str(Path(__file__).with_name('schema.py')), run_name='__main__')
