import os
"""Conservative researcher evidence rules, NOT another LLM or paper method.
These rules only remove unsupported source assignments/insertions. No parent or
candidate is invented and WBS membership is not required for document concepts.
"""
import sys, re
from pathlib import Path
MOD = Path(os.environ['HYBRID_CASE_ROOT']) / 'module5'
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared'))
from common import *
import networkx as nx
snapshot = MOD / 'outputs/decisions_before_grounding_rules.json'
if not snapshot.exists():
    write(snapshot, read(MOD / 'outputs/decisions.json'))
msnapshot = MOD / 'reports/lorex_before_grounding_rules.json'
if not msnapshot.exists():
    write(msnapshot, read(MOD / 'reports/lorex_metrics.json'))
decisions = read(snapshot)
base = read(MOD / 'outputs/base_nodes.json')
rows = {r['id']: r for r in read(T / 'module1/outputs/extracted_rows.json') if r['extraction'][domain_text('in_tile_scope')]}
wbs = {w['code']: w for w in read(T / 'shared/wbs.json')}
graph = nx.DiGraph()
for k, v in base.items():
    for p in v.get('parents', []):
        graph.add_edge(k, p)
for d in decisions:
    if d['status'] == 'accepted_provisional':
        graph.remove_edges_from(list(graph.out_edges(d['query']['id']))) if d['query']['id'] in graph else None
        graph.add_edge(d['query']['id'], d['parent'])

def isa(cid, parent):
    return cid == parent or (cid in graph and parent in graph and nx.has_path(graph, cid, parent))

def supports(q, reference):
    sid = reference['source_id']
    quote = reference['quote']
    if sid in rows:
        r = rows[sid]
        text = r['name'] + ' ' + r['specification']
        if quote not in text:
            return (False, 'Quote is not in the source row')
        if isa(q['id'], domain_text('TileMaterialCostItem')) and r['extraction']['cost_role'] != 'material':
            return (False, 'Material cost requires a material row')
        if isa(q['id'], domain_text('TileInstallationCostItem')) and r['extraction']['cost_role'] != 'installation':
            return (False, 'Installation cost requires an installation row')
        if '압착' in q['label'] + ' ' + q['definition'] and '압착' not in text:
            return (False, 'Pressure fixing is not explicit in this row')
        return (True, 'Explicit row supports the specified cost role; material-name filter applied in audit')
    if sid.startswith('WBS:') and sid[4:] in wbs:
        w = wbs[sid[4:]]
        text = w['quote']
        context = text
        p = w['parent']
        while p:
            context += ' ' + wbs[p]['quote']
            p = wbs[p]['parent']
        if quote not in text:
            return (False, 'Quote is not in the cited WBS node')
        terms = (q['label'] + ' ' + q['definition']).lower()
        if re.search('준비|prepar', terms):
            return (bool(re.search('준비|바탕.*처리|표면.*처리', text)), 'Preparation must be stated explicitly, not inferred from general guidance or a fixing method')
        if re.search('접착제를.*적용|접착제.*도포|adhesive_application', terms):
            return (bool(re.search('접착제.*(?:도포|바르|적용)', text)), 'Adhesive application is not established by pressure fixing or generic adhesive fixing')
        if '벽' in terms or 'wall' in terms:
            return ('벽' in context and bool(re.search('붙이기|붙임|설치', text)) and (not bool(re.search('검사|시험|보양|청소', text))), 'Wall installation needs explicit wall context and a fixing activity')
        if re.search('검사|inspection', terms):
            return (bool(re.search('검사|시험', text)), 'Inspection needs an explicit inspection/test node')
        if re.search('설치|시공|installation', terms):
            return (bool(re.search('붙이기|붙임|설치', text)) and (not bool(re.search('검사|시험|보양|청소|일반사항', text))), 'Installation requires a fixing/installation node, not a generic construction heading')
        return (False, 'Task defining feature has no implemented documentary support rule; retain for expert review')
    return (False, 'Unknown evidence source')
changes = []
for d in decisions:
    if d['status'] != 'accepted_provisional':
        continue
    kept = []
    rejected = []
    for ref in d['export_verified_quotes']:
        ok, reason = supports(d['query'], ref)
        if ok:
            kept.append(ref)
        else:
            rejected.append({**ref, 'reason': reason})
    d['export_verified_quotes'] = kept
    d['grounding_rule_rejections'] = rejected
    if not kept:
        d.update(status='held', reason='Explicit grounding rules: source does not state the defining activity/material/role')
    changes.append({'id': d['query']['id'], 'status': d['status'], 'retained': kept, 'removed': rejected})
anchors = set(base) - {x['id'] for x in read(T / 'module1/outputs/initial_schema.json')['classes']} | {domain_text('TileMaterialCostItem'), domain_text('TileInstallationCostItem')}
while True:
    kept = {x['query']['id'] for x in decisions if x['status'] == 'accepted_provisional'}
    bad = [x for x in decisions if x['status'] == 'accepted_provisional' and x['parent'] not in anchors | kept]
    if not bad:
        break
    for x in bad:
        x.update(status='held', reason='Explicit grounding rules: selected parent not retained')
m = read(msnapshot)
m['before_grounding_rules'] = {'accepted_provisional': m['accepted_provisional'], 'held': m['held'], 'taxoadapt_accepted': m['taxoadapt_accepted']}
m['accepted_provisional'] = sum((x['status'] == 'accepted_provisional' for x in decisions))
m['held'] = len(decisions) - m['accepted_provisional']
m['strict_lorex_accepted'] = sum((x['status'] == 'accepted_provisional' and x.get('strict_lorex_accept', False) for x in decisions))
m['taxoadapt_accepted'] = sum((x['status'] == 'accepted_provisional' and x['query']['origin'] == 'TaxoAdapt' for x in decisions))
m['deviations'].append('Researcher-defined final lexical/context evidence rules remove unsupported activity assignments; LLM review alone did not establish reliable grounding. No parent or candidate invented.')
write(MOD / 'outputs/decisions.json', decisions)
write(MOD / 'reports/lorex_metrics.json', m)
write(MOD / 'reports/grounding_rules.json', {'before_accepted': read(msnapshot)['accepted_provisional'], 'after_accepted': m['accepted_provisional'], 'changes': changes, 'method': 'Conservative explicit wording/context filters; may produce false negatives; not expert validation or faithful LOREx', 'wbs_is_whitelist': False})
print('Final grounded candidates:', m['accepted_provisional'], 'accepted,', m['held'], 'held; TaxoAdapt accepted', m['taxoadapt_accepted'], flush=True)
