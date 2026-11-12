import os
"""LOREx paper adaptation: rank/chunk/filter/retrieve and lineage verification."""
import sys
import json
import hashlib
from pathlib import Path
MOD = Path(os.environ['HYBRID_CASE_ROOT']) / 'module5'
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared'))
from common import *
sys.path.insert(0, str(CODE_ROOT / 'module4/adapters'))
from local_runtime import initialize_local_runtime
from vllm import SamplingParams
original, args, lock, runtime = initialize_local_runtime('llama_scoring_runtime.json')
llm = args.client['vllm']
tokenizer = llm.get_tokenizer()
rankings = read(MOD / 'outputs/rankings.json')
base = read(MOD / 'outputs/base_nodes.json')
rows = {r['id']: r for r in read(T / 'module1/outputs/extracted_rows.json') if r['extraction'][domain_text('in_tile_scope')]}
wbs = {w['code']: w for w in read(T / 'shared/wbs.json')}
decisions = []

def lineage_scores(query, candidates):
    paths = [' > '.join([base[p]['label'] for p in c['path'] if p in base] + [query['label']]) for c in candidates]
    user = 'Select the most plausible is-a taxonomy lineage for the final query concept. A work part, method or material is not a cost item. Return exactly one of the candidate lineages.\nQuery: ' + query['label'] + ': ' + query['definition'] + '\nCandidates:\n' + '\n'.join(paths)
    prefix = tokenizer.apply_chat_template([{'role': 'system', 'content': 'You reason about construction ontology hierarchies.'}, {'role': 'user', 'content': user}], tokenize=False, add_generation_prompt=True)
    key = hashlib.sha256(json.dumps({'prefix': prefix, 'paths': paths, 'parents': [c['parent'] for c in candidates], 'model': lock, 'runtime': runtime}, sort_keys=True).encode()).hexdigest()
    cache = MOD / 'outputs/lineage_cache' / (key + '.json')
    if cache.exists():
        return read(cache)['scores']
    prefix_ids = tokenizer.encode(prefix, add_special_tokens=False)
    requests, starts = ([], [])
    for path in paths:
        ids = tokenizer.encode(prefix + path, add_special_tokens=False)
        start = 0
        for a, b in zip(prefix_ids, ids):
            if a != b:
                break
            start += 1
        if len(ids) + 1 > runtime['max_model_len']:
            raise RuntimeError('Lineage prompt exceeds context')
        requests.append({'prompt_token_ids': ids})
        starts.append(start)
    generated = llm.generate(requests, SamplingParams(max_tokens=1, temperature=0, prompt_logprobs=1), use_tqdm=False)
    scores = []
    for candidate, path, start, result in zip(candidates, paths, starts, generated):
        values = [result.prompt_logprobs[i][result.prompt_token_ids[i]].logprob for i in range(start, len(result.prompt_token_ids)) if result.prompt_logprobs[i] is not None]
        scores.append({'parent': candidate['parent'], 'path': path, 'mean_token_logprob': sum(values) / len(values), 'scored_tokens': len(values)})
    scores = sorted(scores, key=lambda x: -x['mean_token_logprob'])
    write(cache, {'prefix': prefix, 'paths': paths, 'scores': scores, 'model': lock})
    return scores
for position, entry in enumerate(rankings):
    q = entry['query']
    evidence = [{'id': rid, 'name': rows[rid]['name'], 'specification': rows[rid]['specification']} for rid in q.get('row_ids', []) if rid in rows][:8]
    evidence += [{'id': 'WBS:' + code, 'text': wbs[code]['quote']} for code in q.get('wbs_codes', []) if code in wbs][:8]
    if not evidence:
        decisions.append({'query': q, 'status': 'held', 'reason': 'LLM hypothesis has no verified documentary/WBS support', 'attempts': []})
        continue
    chunks = [entry['ranked'][i:i + 8] for i in range(0, len(entry['ranked']), 8)]
    chunk_view = [{'chunk': i, 'parents': [{'id': c['parent'], 'label': base[c['parent']]['label'], 'definition': base[c['parent']]['definition']} for c in chunk]} for i, chunk in enumerate(chunks)]
    filtering = api('module5', 'lorex_filter', 'Identify chunks containing a plausible direct is-a parent for this query. Cost item / task / method / material are distinct roles. Return JSON {"relevant_chunks":[0],"reason":"..."}; return [] if none. Select at most two chunks.\n' + json.dumps({'query': q, 'chunks': chunk_view}, ensure_ascii=False), 600)
    attempts = []
    decision = None
    for chunk_id in filtering['relevant_chunks'][:2]:
        if type(chunk_id) is not int or not 0 <= chunk_id < len(chunks):
            continue
        chunk = chunks[chunk_id]
        choices = [{'id': c['parent'], 'label': base[c['parent']]['label'], 'definition': base[c['parent']]['definition'], 'path': c['path']} for c in chunk]
        retrieval = api('module5', 'lorex_retrieve', 'Select the best direct is-a parent, NOT just a related concept. If no suitable parent exists return parent_id:null. Return JSON {"parent_id":null,"reason":"..."}.\n' + json.dumps({'query': q, 'parents': choices, 'evidence': evidence}, ensure_ascii=False), 650)
        parent = retrieval.get('parent_id')
        if parent not in {x['parent'] for x in chunk}:
            attempts.append({'chunk': chunk_id, 'retrieval': retrieval, 'result': 'not_found'})
            continue
        chosen = next((c for c in chunk if c['parent'] == parent))
        compare = [chosen] + [c for c in chunk if c['parent'] != parent][:2]
        scores = lineage_scores(q, compare)
        review = api('module5', 'ontology_evidence_verifier', 'Verify this proposed OWL is-a relation and documentary evidence.\nDo not equate same material, work part, method and cost. A cost subtype must refer to a COST, a work subtype to an ACTIVITY.\nCheck the query definition actually matches the row names/WBS; e.g. adhesive fixing is NOT automatically pressure fixing.\nOnly cite exact substrings from supplied evidence. Do not accept a duplicate of an existing class.\nReturn JSON {"is_a":true,"supported":true,"duplicate_of":null,"reason":"...","quotes":[{"source_id":"...","quote":"..."}]}.\n' + json.dumps({'query': q, 'parent': base[parent], 'existing_classes': {k: v['label'] for k, v in base.items() if k != q['id']}, 'evidence': evidence}, ensure_ascii=False), 1100)
        valid_quotes = []
        for item in review.get('quotes', []):
            source = next((e for e in evidence if e['id'] == item.get('source_id')), None)
            if source and item.get('quote') and any((item['quote'] in str(value) for key, value in source.items() if key != 'id')):
                valid_quotes.append(item)
        strict = scores[0]['parent'] == parent
        semantic = review.get('is_a') is True and review.get('supported') is True and (review.get('duplicate_of') is None) and bool(valid_quotes)
        attempt = {'chunk': chunk_id, 'retrieval': retrieval, 'lineage_scores': scores, 'paper_strict_verifier_agreement': strict, 'semantic_review': review, 'verified_quotes': valid_quotes}
        attempts.append(attempt)
        if semantic:
            decision = {'query': q, 'parent': parent, 'status': 'accepted_provisional', 'strict_lorex_accept': strict, 'reason': 'source-supported semantic verification; lineage agreement recorded separately', 'attempts': attempts}
            break
    if decision is None:
        decision = {'query': q, 'status': 'held', 'reason': 'No grounded, semantically valid parent found in reviewed chunks', 'attempts': attempts}
    decisions.append(decision)
    write(MOD / 'outputs/decisions.partial.json', decisions)
    print('LOREx', position + 1, '/', len(rankings), q['id'], decision['status'], flush=True)
initial_ids = {x['id'] for x in read(T / 'module1/outputs/initial_schema.json')['classes']}
anchors = set(base) - initial_ids | {domain_text('TileMaterialCostItem'), domain_text('TileInstallationCostItem')}
while True:
    accepted = {x['query']['id'] for x in decisions if x['status'] == 'accepted_provisional'}
    bad = [x for x in decisions if x['status'] == 'accepted_provisional' and x['parent'] not in anchors | accepted]
    if not bad:
        break
    for x in bad:
        x.update(status='held', reason='Selected parent not accepted')
import networkx as nx
graph = nx.DiGraph()
graph.add_edges_from(((x['parent'], x['query']['id']) for x in decisions if x['status'] == 'accepted_provisional'))
cycles = list(nx.simple_cycles(graph))
cycle_ids = {node for cycle in cycles for node in cycle}
for x in decisions:
    if x['status'] == 'accepted_provisional' and x['query']['id'] in cycle_ids:
        x.update(status='held', reason='Proposed parent relations form a cycle; no arbitrary edge selected')
while True:
    accepted = {x['query']['id'] for x in decisions if x['status'] == 'accepted_provisional'}
    bad = [x for x in decisions if x['status'] == 'accepted_provisional' and x['parent'] not in anchors | accepted]
    if not bad:
        break
    for x in bad:
        x.update(status='held', reason='Selected parent not accepted after cycle review')
graph = nx.DiGraph(((x['parent'], x['query']['id']) for x in decisions if x['status'] == 'accepted_provisional'))
assert nx.is_directed_acyclic_graph(graph)
write(MOD / 'outputs/decisions.json', decisions)
new_ids = {x['id'] for x in read(T / 'module4/outputs/proposals.json')}
assert new_ids <= {x['query']['id'] for x in decisions}
write(MOD / 'reports/lorex_metrics.json', {'candidates': len(decisions), 'accepted_provisional': sum((x['status'] == 'accepted_provisional' for x in decisions)), 'held': sum((x['status'] == 'held' for x in decisions)), 'strict_lorex_accepted': sum((x.get('strict_lorex_accept', False) and x['status'] == 'accepted_provisional' for x in decisions)), 'taxoadapt_generated': len(new_ids), 'taxoadapt_processed': len(new_ids & {x['query']['id'] for x in decisions}), 'taxoadapt_accepted': sum((x['query']['id'] in new_ids and x['status'] == 'accepted_provisional' for x in decisions)), 'deviations': ['No official LOREx code; paper-based implementation', 'top two relevant chunks and two alternative verification paths per chunk', 'Llama teacher-forced mean token logprob implements path scoring', 'source-supported semantic verification may retain logprob-disagreed candidates provisionally; paper-strict count separately reported'], 'expert_validated': False, 'runtime': runtime, 'local_model': lock})
print('Module5 reasoning complete', flush=True)
