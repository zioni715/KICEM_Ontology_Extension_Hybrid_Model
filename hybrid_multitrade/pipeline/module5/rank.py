import os
"""Paper-based TEMPORA: verbalized lineage, dynamic margin, dual-path loss."""
import sys
import random
from pathlib import Path
MOD = Path(os.environ['HYBRID_CASE_ROOT']) / 'module5'
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared'))
from common import *
import torch
import networkx as nx
from transformers import AutoModel, AutoTokenizer
torch.set_num_threads(4)
torch.manual_seed(42)
random.seed(42)
seed = [x for x in read(T / 'shared/seed_elements.json') if x['type'] == 'Class']
schema = read(T / 'module1/outputs/initial_schema.json')
bridge_definitions = {domain_text('TileMaterialCostItem'): domain_text('타일 자재의 공급·구매에 대한 비용대상. 자재 자체나 설치 작업 비용은 아니다.'), domain_text('TileInstallationCostItem'): domain_text('타일 설치 시공 작업에 대한 비용대상. 작업 활동 자체나 자재 공급 비용은 아니다.')}
for c in schema['classes']:
    if c['id'] in bridge_definitions:
        c['definition'] = bridge_definitions[c['id']]
rc = {'RebarCostItem', 'RebarMaterialCostItem', 'RebarFabricationAssemblyCostItem', 'ConcreteCostItem', 'ConcretePlacementCostItem', 'ReadyMixedConcreteMaterialCostItem', 'FormworkCostItem', 'ShoringCostItem'}
nodes = {x['id']: {'id': x['id'], 'label': ' '.join(x['labels']), 'definition': ' '.join(x['comments']), 'parents': x['parents'], 'origin': 'seed'} for x in seed}
nodes['OntologyEntity'] = {'id': 'OntologyEntity', 'label': '온톨로지 개체 유형', 'definition': 'Taxonomy training root only; not exported OWL class', 'parents': [], 'origin': 'training_root'}
for name in ['WorkTask', 'InstallationMethod', domain_text('TileMaterial'), 'ApplicationSurface']:
    nodes[name] = {'id': name, 'label': name, 'definition': {'WorkTask': domain_text('타일 시공 작업 활동'), 'InstallationMethod': domain_text('타일 시공 방법'), domain_text('TileMaterial'): domain_text('타일 재료 유형'), 'ApplicationSurface': domain_text('타일 적용 표면')}[name], 'parents': ['OntologyEntity'], 'origin': 'researcher_anchor'}
for c in schema['classes']:
    nodes[c['id']] = {**c, 'parents': [c['parent']]}
graph = nx.DiGraph()
graph.add_nodes_from(nodes)
for k, v in nodes.items():
    for parent in v['parents'] or ([] if k == 'OntologyEntity' else ['OntologyEntity']):
        graph.add_edge(parent, k)
assert nx.is_directed_acyclic_graph(graph)

def lineage(g, anchor):
    return nx.shortest_path(g, 'OntologyEntity', anchor)

def verbal(g, anchor):
    chain = lineage(g, anchor)
    parts = []
    for child, parent in zip(reversed(chain[1:]), reversed(chain[:-1])):
        parts.append(f"{nodes[child]['label']} is child of {nodes[parent]['label']}.")
    for parent, child in zip(chain[:-1], chain[1:]):
        for sibling in sorted(g.successors(parent)):
            if sibling != child:
                parts.append(f"{nodes[parent]['label']} is parent of {nodes[sibling]['label']}; return to {nodes[parent]['label']}.")
        parts.append(f"{nodes[parent]['label']} is parent of {nodes[child]['label']}.")
    for child in sorted(g.successors(anchor)):
        parts.append(f"{nodes[anchor]['label']} is parent of {nodes[child]['label']}; return to {nodes[anchor]['label']}.")
    return ' '.join(parts)
tokenizer = AutoTokenizer.from_pretrained(model_path('bert'), local_files_only=True)
encoder = AutoModel.from_pretrained(model_path('bert'), local_files_only=True).cuda()
head = torch.nn.Sequential(torch.nn.Linear(768, 256), torch.nn.ReLU(), torch.nn.Linear(256, 1)).cuda()
params = list(encoder.parameters()) + list(head.parameters())
opt = torch.optim.AdamW(params, lr=1e-05)

def scores(texts):
    tokens = tokenizer(texts, padding=True, truncation=True, max_length=256, return_tensors='pt').to('cuda')
    return head(encoder(**tokens).last_hidden_state[:, 0]).flatten()
examples = []
for q in sorted(graph):
    if q == 'OntologyEntity' or graph.out_degree(q) > 0:
        continue
    parents = list(graph.predecessors(q))
    if not parents:
        continue
    p = parents[0]
    g = graph.copy()
    g.remove_node(q)
    negatives = [n for n in g if n not in parents and n != 'OntologyEntity']
    for n in random.sample(negatives, min(2, len(negatives))):
        pos, neg = (verbal(g, p), verbal(g, n))
        a, b = (set(lineage(g, p)), set(lineage(g, n)))
        margin = (len(a | b) / max(1, len(a & b)) - 1) * 0.1
        desc = nodes[q]['label'] + ': ' + nodes[q]['definition']
        examples.append({'query': q, 'positive': p, 'negative': n, 'texts': [desc + ' [SEP] ' + pos, desc + ' [SEP] ' + neg, pos, neg], 'margin': margin})
logs = []
for epoch in range(2):
    random.shuffle(examples)
    encoder.train()
    head.train()
    values = []
    for ex in examples:
        opt.zero_grad()
        v = scores(ex['texts'])
        main = torch.relu(-v[0] + v[1] + ex['margin'])
        positive = (v[0] - v[2]).square()
        negative = torch.relu(v[1] - v[3])
        loss = main + 0.1 * positive + 0.1 * negative
        loss.backward()
        torch.nn.utils.clip_grad_norm_(params, 1)
        opt.step()
        values.append(loss.item())
    logs.append({'epoch': epoch + 1, 'loss': sum(values) / len(values)})
    print(logs[-1], flush=True)
proposals = [{**c, 'kind': 'class', 'origin': c.get('origin', 'module1'), 'evidence_status': 'document_or_wbs_candidate'} for c in schema['classes'] if c['id'] not in [domain_text('TileMaterialCostItem'), domain_text('TileInstallationCostItem')]]
proposals += read(T / 'module4/outputs/proposals.json')
for h in schema['hypotheses']:
    proposals.append({**h, 'id': 'H_' + h['id'], 'kind': 'class', 'origin': 'LLM_hypothesis', 'row_ids': [], 'wbs_codes': [], 'evidence_status': 'llm_hypothesis'})
base = {k: v for k, v in nodes.items() if k not in rc and k != 'OntologyEntity'}
encoder.eval()
head.eval()
rankings = []
with torch.inference_mode():
    for q in proposals:
        candidates = [k for k in base if k != q['id'] and (q['id'] not in graph or k not in nx.descendants(graph, q['id']))]
        g = graph.copy()
        if q['id'] in g:
            parents = list(g.predecessors(q['id']))
            children = list(g.successors(q['id']))
            g.remove_node(q['id'])
            g.add_edges_from(((p, c) for p in parents for c in children))
        values = []
        for start in range(0, len(candidates), 8):
            values.extend(scores([q['label'] + ': ' + q['definition'] + ' [SEP] ' + verbal(g, p) for p in candidates[start:start + 8]]).cpu().tolist())
        ordered = sorted([{'parent': p, 'score': s, 'path': lineage(g, p)[1:]} for p, s in zip(candidates, values)], key=lambda x: -x['score'])
        rankings.append({'query': q, 'ranked': ordered})
checkpoint = MOD / 'checkpoints'
checkpoint.mkdir(exist_ok=True)
torch.save({'encoder': encoder.state_dict(), 'head': head.state_dict()}, checkpoint / 'tempora.pt')
write(MOD / 'outputs/rankings.json', rankings)
write(MOD / 'outputs/base_nodes.json', base)
write(MOD / 'reports/ranker_training.json', {'seed': 42, 'epochs': 2, 'examples': examples, 'losses': logs, 'trainable_encoder': True, 'loss': 'dynamic path margin + 0.1 positive dual-path squared distance + 0.1 negative dual-path hinge', 'paper_equations': [3, 4, 5, 6, 7], 'adaptations': ['multilingual BERT', domain_text('small seed plus provisional initial tile taxonomy'), 'two epochs', 'max text length 256', 'researcher cost-role anchors clarified for final verification; upstream results retained unchanged'], 'heldout_accuracy_reported': False, 'checkpoint_sha256': sha(checkpoint / 'tempora.pt')})
print('TEMPORA ranking complete:', len(rankings), 'candidates', flush=True)
