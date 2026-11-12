"""Execute original TaxoAdapt Node/classification/width/depth on tile evidence."""
import sys
import json
import hashlib
from pathlib import Path
from collections import deque
MOD = Path(__file__).resolve().parent
sys.path.insert(0, str(MOD.parent / 'shared'))
from common import *
sys.path.insert(0, str(MOD / 'source'))
sys.path.insert(0, str(MOD / 'adapters'))
from local_runtime import initialize_local_runtime
original, args, lock, runtime = initialize_local_runtime()
import model_definitions as backend
import classification
import taxonomy
import expansion
from paper import Paper

schema = read(T / 'module1/outputs/initial_schema.json')
rows = [r for r in read(T / 'module1/outputs/extracted_rows.json') if r['extraction']['in_tile_scope']]
wbs = read(T / 'shared/wbs.json')
taxopro = {r['query']: r['ranked'][:3] for r in read(T / 'module2/outputs/parent_rankings.json') if r['domain'] == 1}
mila = read(T / 'module3/outputs/alignment.json')
calls = []
def construct(args, system, main):
    if args.llm == 'gpt':
        return [{'role': 'system', 'content': system}, {'role': 'user', 'content': main}]
    return args.client['vllm'].get_tokenizer().apply_chat_template(
        [{'role': 'system', 'content': system}, {'role': 'user', 'content': main}], tokenize=False, add_generation_prompt=True)

def prompt(args, prompts, schema=None, max_new_tokens=1024, json_mode=True, temperature=.1, top_p=.99):
    outputs = []
    if args.llm == 'gpt':
        for p in prompts:
            obj = api('module4', 'taxoadapt_cluster', json.dumps(p, ensure_ascii=False) +
                      '\nOutput JSON schema: ' + json.dumps(schema.model_json_schema()), min(max_new_tokens, 3000), temperature=0)
            schema.model_validate(obj)
            outputs.append(json.dumps(obj, ensure_ascii=False))
    else:
        formatted = [p if '<|begin_of_text|>' in p else construct(args, 'You classify tile-construction evidence. Return JSON only.', p) for p in prompts]
        tokenizer = args.client['vllm'].get_tokenizer()
        for p in formatted:
            if len(tokenizer.encode(p)) + min(max_new_tokens, 450) > runtime['max_model_len']:
                raise RuntimeError('Prompt exceeds pinned context; split evidence instead of silent truncation')
        # Avoid exponential bounded-string FSMs; validate the original constraints
        # after decoding. One prompt at a time also avoids large processor copies.
        def relaxed(value):
            if isinstance(value, dict):
                return {k: relaxed(v) for k, v in value.items() if k not in ('maxLength', 'maxItems', 'uniqueItems')}
            if isinstance(value, list): return [relaxed(x) for x in value]
            return value
        class DecodeSchema:
            @classmethod
            def model_json_schema(cls): return relaxed(schema.model_json_schema())
        for p in formatted:
            key = hashlib.sha256(json.dumps({'prompt':p, 'schema':schema.model_json_schema(), 'model':lock, 'runtime':runtime, 'tokens':min(max_new_tokens,450)},sort_keys=True).encode()).hexdigest()
            cache = MOD / 'outputs/local_cache' / (key + '.json')
            if cache.exists():
                output = read(cache)['output']
            else:
                output = original.promptLlamaVLLM(args, [p], schema=DecodeSchema, max_new_tokens=min(max_new_tokens, 450), temperature=0, top_p=1)[0]
                raw_output = output
                parsed = json.loads(output)
                normalization = None
                if schema.__name__ == 'ClassifySchema' and len(parsed.get('explanation','')) > 250:
                    parsed['explanation'] = parsed['explanation'][:250]
                    output = json.dumps(parsed, ensure_ascii=False)
                    normalization = 'Explanation metadata clipped to original 250-character limit; labels unchanged; full response retained'
                schema.model_validate_json(output)
                write(cache, {'prompt':p, 'output':output, 'raw_output':raw_output, 'normalization':normalization, 'schema':schema.__name__})
            schema.model_validate_json(output)
            outputs.append(output)
            print('Local response', schema.__name__, key[:10], flush=True)
    calls.extend({'backend': args.llm, 'prompt': p, 'response': o, 'schema': schema.__name__} for p, o in zip(prompts, outputs))
    write(MOD / 'reports/llm_calls.json', calls)
    return outputs

backend.constructPrompt = construct
backend.promptLLM = prompt
expansion.constructPrompt = construct
expansion.promptLLM = prompt
taxonomy.promptLLM = prompt

def classify(node, paper):
    return 'Classify this tile evidence into existing class labels. Only use tightly applicable classes; otherwise class_labels=[]. Work breakdown is not is-a. Return JSON with explanation and class_labels.\n' + json.dumps(
        {'parent': node.label, 'parent_definition': node.description, 'evidence': paper.abstract,
         'classes': {k: v.description for k, v in node.children.items()}}, ensure_ascii=False)
taxonomy.classify_prompt = classify

def proposal(paper, node, ancestors):
    return 'Propose ONE specific is-a subclass of the parent supported by this tile evidence. It may be absent from WBS. Do not use part-of as subclass. Keep cost items distinct from activities/methods/materials. Use an English snake_case label, no instance sizes or product IDs. Return JSON {"new_subtopic_label":"..."}.\n' + json.dumps(
        {'parent': node.label, 'definition': node.description, 'ancestors': ancestors,
         'existing_children': list(node.children), 'evidence': paper.abstract}, ensure_ascii=False)
expansion.width_system_instruction = expansion.depth_system_instruction = 'Expand a tile ontology using evidence, not an exhaustive WBS whitelist.'
expansion.width_main_prompt = expansion.depth_main_prompt = proposal

def cluster(options, node, ancestors, all_labels):
    return 'Consolidate evidence-generated tile subclass proposals into at most THREE distinct useful subclasses of the parent. Return new_cluster_topics with label (English snake_case), description (Korean, <=200 characters), covered_paper_topics (exact input labels). Preserve meaning; do not invent numeric specifications. Cost-item taxonomy is not a method or material taxonomy. Avoid current node and existing node labels.\n' + json.dumps(
        {'parent': node.label, 'definition': node.description, 'ancestors': ancestors,
         'proposals': options, 'existing_labels': all_labels}, ensure_ascii=False)
expansion.width_cluster_system_instruction = expansion.depth_cluster_system_instruction = 'You consolidate tile ontology extension candidates. Return JSON only.'
expansion.width_cluster_main_prompt = expansion.depth_cluster_main_prompt = cluster

args.max_density = 2
id2node, label2node, origins = {}, {}, {}
roots = []
initial = {c['id']: c for c in schema['classes']}
def root_of(cid):
    seen = set()
    while cid in initial:
        if cid in seen:
            raise ValueError('Initial schema cycle')
        seen.add(cid); cid = initial[cid]['parent']
    return cid

for anchor, dimension, description in [('CostItem', 'cost', '타일 자재 또는 설치 작업의 비용대상. 문서항목과 구분한다.'),
                                        ('WorkTask', 'work', '타일 시공 및 검사·보양·청소 작업 활동 유형. 비용대상이나 재료와 구분한다.')]:
    root = taxonomy.Node(len(id2node), anchor, dimension, description)
    roots.append(root); id2node[root.id] = root; label2node[anchor + '_' + dimension] = root; origins[root.id] = anchor
    pending = [c for c in schema['classes'] if root_of(c['id']) == anchor]
    while pending:
        before = len(pending)
        for c in list(pending):
            parent = label2node.get(c['parent'] + '_' + dimension)
            if parent is None: continue
            node = taxonomy.Node(len(id2node), c['id'], dimension, c['definition'], parents=[parent])
            parent.add_child(node.label, node); id2node[node.id] = node; label2node[node.label + '_' + dimension] = node; origins[node.id] = c['id']; pending.remove(c)
        assert len(pending) < before
    if dimension == 'cost':
        # Group duplicate line-item descriptions; keep all original row references.
        groups = {}
        for row in rows:
            groups.setdefault(row['extraction']['concept_label'], []).append(row)
        for i, (label, group) in enumerate(groups.items()):
            evidence = {'label': label, 'rows': [{'id': r['id'], 'name': r['name'], 'specification': r['specification']} for r in group[:3]],
                        'all_row_ids': [r['id'] for r in group], 'wbs_codes': sorted({x for r in group for x in r['extraction']['wbs_codes']}),
                        'taxopro_hints': taxopro.get(next((x['class_id'] for x in schema['row_classes'] if x['row_id'] == group[0]['id']), ''), [])}
            root.papers['row_group_' + str(i)] = Paper('row_group_' + str(i), label, json.dumps(evidence, ensure_ascii=False), [dimension])
    else:
        for w in wbs:
            if any(x['parent'] == w['code'] for x in wbs): continue
            evidence = {'wbs_code': w['code'], 'label': w['label'], 'quote': w['quote']}
            root.papers['wbs_' + w['code']] = Paper('wbs_' + w['code'], w['label'], json.dumps(evidence, ensure_ascii=False), [dimension])

events = []
# Bounded first pilot: each root width pass and one populated child depth pass.
for root in roots:
    args.llm = 'vllm'
    if root.children:
        root.classify_node(args, label2node, set())
        added = expansion.expandNodeWidth(args, root, id2node, label2node)
        events.append({'parent': root.label, 'mode': 'width', 'added': added})
        if added: root.classify_node(args, label2node, set())
        candidates = sorted([x for x in root.children.values() if x.papers], key=lambda x: (-len(x.papers), x.id))[:1]
    else:
        candidates = [root]
    for node in candidates:
        added, success = expansion.expandNodeDepth(args, node, id2node, label2node)
        events.append({'parent': node.label, 'mode': 'depth', 'added': added, 'success': success})
        if added:
            args.llm = 'vllm'; node.classify_node(args, label2node, set())

def uid(node):
    return origins.get(node.id, 'TA_' + hashlib.sha256((node.dimension + ':' + node.label).encode()).hexdigest()[:12])
nodes, proposals = [], []
for node in id2node.values():
    evidence = [json.loads(p.abstract) for p in node.papers.values()]
    row_ids = sorted({x for e in evidence for x in e.get('all_row_ids', [])})
    wbs_codes = sorted({e['wbs_code'] for e in evidence if 'wbs_code' in e})
    record = {'id': uid(node), 'label': node.label, 'definition': node.description, 'parents': [uid(p) for p in node.parents],
              'source': node.source or 'initial', 'dimension': node.dimension, 'row_ids': row_ids, 'wbs_codes': wbs_codes}
    nodes.append(record)
    if node.source in ['width', 'depth']:
        proposals.append({**record, 'parent': record['parents'][0], 'kind': 'class', 'origin': 'TaxoAdapt',
                          'evidence_status': 'document_or_wbs_candidate' if row_ids or wbs_codes else 'llm_hypothesis'})
write(MOD / 'outputs/taxonomy.json', nodes)
write(MOD / 'outputs/proposals.json', proposals)
write(MOD / 'reports/metrics.json', {'generated_candidates': len(proposals), 'events': events,
      'local_model': lock, 'runtime': runtime, 'mila_matches_available': sum(bool(x['Correspondence']) for x in mila),
      'deviations': ['tile evidence/Paper adapter and domain prompts', 'chat template and bounded token lengths', 'single-request decoding, swap_space=0, length constraints checked after relaxed JSON decoding; explanation metadata clipped with full raw response retained',
                     'two roots, one width and one populated-child depth pass each', 'depth empty-return tuple bug fixed',
                     'original Node classification, pseudo-label generation, frequency counting and GPT clustering retained'],
      'handoff': 'Every generated proposal ID is passed to module5, including ungrounded hypotheses'})
print('Module4 complete:', len(proposals), 'new proposals', flush=True)
