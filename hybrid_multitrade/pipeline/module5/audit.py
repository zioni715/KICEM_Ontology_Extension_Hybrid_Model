import os
"""Final evidence gate, separate from LOREx scores and its original decisions.
No new candidate/parent is invented here. Unsupported provisional insertions are held.
"""
import sys, json, re
from pathlib import Path
MOD = Path(os.environ['HYBRID_CASE_ROOT']) / 'module5'
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared'))
from common import *
from pydantic import BaseModel, ConfigDict
from typing import Literal

class EvidenceCheck(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source_id: str
    supports_full_concept: bool
    quote: str
    reason: str

class Audit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    relation: Literal['is_a', 'part_of', 'related', 'unclear']
    definition_supported: bool
    duplicate_id: str | None
    reason: str
    evidence: list[EvidenceCheck]
original = MOD / 'outputs/decisions_lorex.json'
if not original.exists():
    write(original, read(MOD / 'outputs/decisions.json'))
metrics_original = MOD / 'reports/lorex_before_evidence_audit.json'
if not metrics_original.exists():
    write(metrics_original, read(MOD / 'reports/lorex_metrics.json'))
decisions = read(original)
base = read(MOD / 'outputs/base_nodes.json')
rows = {r['id']: r for r in read(T / 'module1/outputs/extracted_rows.json') if r['extraction'][domain_text('in_tile_scope')]}
wbs = {w['code']: w for w in read(T / 'shared/wbs.json')}
existing = []
audit = []
aliases = [(['porcelain', '포세린'], ['포세린']), (['ceramic', '세라믹'], ['세라믹']), (['stone', '석재'], ['석재']), (['mosaic', '모자이크'], ['모자이크']), (['nonslip', 'non_slip', '논슬립'], ['논슬립'])]
for d in decisions:
    if d['status'] != 'accepted_provisional':
        continue
    q = d['query']
    sources = []
    discarded = []
    for rid in q.get('row_ids', []):
        if rid not in rows:
            continue
        row = rows[rid]
        text = row['name'] + ' ' + row['specification']
        terms = (q['id'] + ' ' + q['label'] + ' ' + q['definition']).lower()
        required = [tokens for triggers, tokens in aliases if any((t in terms for t in triggers))]
        if any((not any((t in text for t in tokens)) for tokens in required)):
            discarded.append({'source_id': rid, 'reason': domain_text('Specific material in candidate is not stated in source row; generic tile row cannot establish it')})
            continue
        sources.append({'id': rid, 'quote': text, 'cost_role': row['extraction']['cost_role'], 'unit': row['unit'], 'contract_unit_price': row['numbers']['contractUnitPrice'], 'contract_amount': row['numbers']['contractAmount']})
    for code in q.get('wbs_codes', []):
        if code not in wbs:
            continue
        w = wbs[code]
        ancestors = []
        p = w['parent']
        while p:
            ancestors.append({'id': 'WBS:' + p, 'quote': wbs[p]['quote']})
            p = wbs[p]['parent']
        sources.append({'id': 'WBS:' + code, 'quote': w['quote'], 'ancestors': ancestors})
    if not sources:
        d.update(status='held', reason='Final evidence gate: no source states the specific concept/material')
        audit.append({'id': q['id'], 'status': d['status'], 'discarded_sources': discarded, 'reason': d['reason']})
        continue
    review = api('module5', 'final_evidence_gate_v2', domain_text('Assess this ontology candidate against its selected parent and source evidence. Return the requested JSON.\nAn is-a parent is EXPECTED to be broader than the query. Every roof-tile purchase cost is a tile-material purchase cost; the parent need not mention roof tiles. Every painting activity is a WorkTask. Specificity is not a reason to reject a subclass.\nKeep roles distinct: a physical tile is not a COST, while a priced purchase row can establish a material COST subtype. A priced pressure-fixing row can establish an installation COST subtype without describing the entire installation process. For legacy IDs containing Adhesive, use the Korean label and definition as the intended meaning (pressure fixing) and note the naming issue.\nFor ACTIVITY classes, a preparation/application step can be part_of a complete installation instead of is_a installation. It can still be an is_a WorkTask if that is the actual selected parent. Do not silently switch the selected parent.\nJudge the core defining concept, not incidental explanatory prose. A WBS inspection heading supports an inspection class without requiring actual inspection-result data. A general-guidance heading does not by itself establish a specific surface-preparation activity. Do not infer a specific material from a generic tile row.\nFor each source, supports_full_concept means that its text and supplied context support the core concept. A source may support a class while other sources do not. WBS ancestor text can provide context. Quotes must be exact substrings of the source quote field, with only supplied source IDs. Numeric contract columns establish that these are priced rows.\nCheck duplicates only against the provided earlier accepted concepts. When in doubt return unclear or unsupported and explain. Evaluate evidence; do not default to approval or rejection. No new concept or parent edit.\n') + json.dumps({'query': q, 'selected_parent': base[d['parent']], 'other_accepted_concepts': [x for x in existing if x['id'] != q['id']], 'sources': sources}, ensure_ascii=False), 6000, response_schema=Audit.model_json_schema())
    parsed = Audit.model_validate(review)
    byid = {s['id']: s for s in sources}
    quotes = []
    for e in parsed.evidence:
        if e.supports_full_concept and e.source_id in byid and e.quote and (e.quote in byid[e.source_id]['quote']):
            quotes.append({'source_id': e.source_id, 'quote': e.quote})
    keep = parsed.relation == 'is_a' and parsed.definition_supported and (parsed.duplicate_id is None) and bool(quotes)
    d['final_evidence_review'] = review
    d['export_verified_quotes'] = quotes
    if not keep:
        d.update(status='held', reason='Final evidence gate: ' + parsed.reason)
    else:
        existing.append({'id': q['id'], 'label': q['label'], 'definition': q['definition']})
    audit.append({'id': q['id'], 'status': d['status'], 'review': review, 'export_verified_quotes': quotes, 'discarded_sources': discarded})
    print('Final evidence gate', q['id'], d['status'], flush=True)
anchors = set(base) - {x['id'] for x in read(T / 'module1/outputs/initial_schema.json')['classes']} | {domain_text('TileMaterialCostItem'), domain_text('TileInstallationCostItem')}
while True:
    accepted = {x['query']['id'] for x in decisions if x['status'] == 'accepted_provisional'}
    bad = [x for x in decisions if x['status'] == 'accepted_provisional' and x['parent'] not in anchors | accepted]
    if not bad:
        break
    for x in bad:
        x.update(status='held', reason='Final evidence gate: selected parent held')
write(MOD / 'outputs/decisions.json', decisions)
m = read(metrics_original)
m['before_final_evidence_gate'] = {'accepted_provisional': m['accepted_provisional'], 'held': m['held'], 'taxoadapt_accepted': m['taxoadapt_accepted']}
m['accepted_provisional'] = sum((x['status'] == 'accepted_provisional' for x in decisions))
m['held'] = len(decisions) - m['accepted_provisional']
m['strict_lorex_accepted'] = sum((x['status'] == 'accepted_provisional' and x.get('strict_lorex_accept', False) for x in decisions))
m['taxoadapt_accepted'] = sum((x['status'] == 'accepted_provisional' and x['query']['origin'] == 'TaxoAdapt' for x in decisions))
m['deviations'].append('Separate final evidence gate: explicit material mention, per-source semantic support, duplicate and part-of checks; no new candidate or parent invented; not expert gold validation')
write(MOD / 'reports/lorex_metrics.json', m)
write(MOD / 'reports/evidence_audit.json', {'audits': audit, 'before_accepted': read(metrics_original)['accepted_provisional'], 'after_accepted': m['accepted_provisional'], 'remaining_decisions': {d['query']['id']: d['status'] for d in decisions}, 'expert_validated': False})
print('Final evidence gate complete:', m['accepted_provisional'], 'accepted', m['held'], 'held', flush=True)
