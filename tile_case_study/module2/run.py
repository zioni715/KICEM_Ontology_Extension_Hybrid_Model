"""Original TaxoPro model/custom LoRA/BCE with a small OWL dataset adapter."""
import sys
import random
from pathlib import Path
from types import SimpleNamespace
from dataclasses import dataclass
MOD = Path(__file__).resolve().parent
sys.path.insert(0, str(MOD.parent / 'shared'))
from common import *
sys.path.insert(0, str(MOD / 'source/TaxoPro'))
import torch
from model.model import TacoPromptTaxoProCompletion
from model.loss import bce_loss

torch.set_num_threads(4)
torch.manual_seed(42)
random.seed(42)
seed = [x for x in read(T / 'shared/seed_elements.json') if x['type'] == 'Class']
schema = read(T / 'module1/outputs/initial_schema.json')

@dataclass(frozen=True)
class Taxon:
    name: str
    description: str


def dataset(records):
    taxa = [Taxon(x['id'], x.get('definition') or ' '.join([x['id']] + x.get('labels', []) + x.get('comments', []))) for x in records]
    taxa.append(Taxon('LEAF', 'No child; insert the query as a leaf concept.'))
    return SimpleNamespace(id2taxon=dict(enumerate(taxa)), taxon2id={x: i for i, x in enumerate(taxa)},
        train_allemb_id2taxon=dict(enumerate(taxa)), train_taxon2allemb_id={x: i for i, x in enumerate(taxa)}, pseudo_leaf_node=taxa[-1])


anchors = [{'id': x, 'definition': d} for x, d in {
    'CostItem': '비용대상: 문서항목이 표현하는 자재 또는 작업의 비용 항목',
    'WorkTask': '타일 시공 작업 활동; 비용항목이나 재료와 구분',
    'InstallationMethod': '타일 설치 시공방법', 'TileMaterial': '타일 재료 유형',
    'ApplicationSurface': '타일의 적용 부위'}.items()]
records = [seed, anchors + schema['classes']]
datasets = [dataset(x) for x in records]
indices = [{x['id']: i for i, x in enumerate(r)} for r in records]
edges = [[(c['id'], p) for c in seed for p in c['parents'] if p in indices[0]],
         [(c['id'], c['parent']) for c in schema['classes']]]
leaves = sorted({q for q, p in edges[0]} - {p for q, p in edges[0]})
held_queries = set(random.sample(leaves, min(4, len(leaves))))
held = [(q, p) for q, p in edges[0] if q in held_queries]
train_edges = [[(q, p) for q, p in edges[0] if q not in held_queries], edges[1]]
options = read(MOD / 'source/TaxoPro/config_files/food/config.TaxoPro.json')['arch']['args']
options['plm'] = model_path('bert')
options['lora_config'].update(r=8, lora_alpha=16, num_ranks=8, num_tasks=2, target_modules=['query', 'value'])
model = TacoPromptTaxoProCompletion([SimpleNamespace(dataset=x) for x in datasets], **options).cuda()
assert 'tile_case_study/module2/source' in __import__('peft').__file__


def score(task, pairs, return_emb=False):
    dev = 'cuda'
    p = torch.tensor([indices[task][b] for a, b in pairs], device=dev)
    q = [indices[task][a] for a, b in pairs]
    leaf = torch.full_like(p, len(records[task]))
    domain = torch.full_like(p, task)
    return model.scorer(p, q, leaf, domain, requires_emb=return_emb)


def examples(task):
    result = []
    for q, p in train_edges[task]:
        result.append(((q, p), 1.0))
        # No known positive parent or the query itself is used as a negative.
        positive = {b for a, b in edges[task] if a == q}
        negatives = [x for x in indices[task] if x != q and x not in positive]
        result.extend(((q, n), 0.0) for n in random.sample(negatives, min(3, len(negatives))))
    return result

data = [examples(0), examples(1)]
logs = []
params = [p for p in model.parameters() if p.requires_grad]
optimizer = torch.optim.AdamW(params, lr=1e-4, weight_decay=.01)
cosine = torch.nn.CosineEmbeddingLoss(margin=0)
for epoch in range(8):
    model.train()
    for ds in data:
        random.shuffle(ds)
    losses = []
    for step in range(max((len(ds) + 3) // 4 for ds in data)):
        optimizer.zero_grad()
        total = 0
        for task in [0, 1]:
            batch = [data[task][(step * 4 + j) % len(data[task])] for j in range(4)]
            pairs = [x[0] for x in batch]
            labels = torch.tensor([x[1] for x in batch], device='cuda')
            model.plm.set_task_id(task)
            total = total + bce_loss(score(task, pairs).squeeze(1), labels)
            if task == 0:
                # Original TrainerTaxoPro contrast: task-specific vs reversed-specific.
                model.plm.set_task_id(-2)
                _, a = score(task, pairs, True)
                model.plm.set_task_id(-3)
                _, b = score(task, pairs, True)
                total = total + cosine(a, b, -torch.ones(len(pairs), device='cuda'))
                model.plm.set_task_id(0)
        total.backward()
        torch.nn.utils.clip_grad_norm_(params, 1)
        optimizer.step()
        losses.append(total.item())
    logs.append({'epoch': epoch + 1, 'joint_loss': sum(losses) / len(losses)})
    print(logs[-1], flush=True)

model.eval()
rankings = []
with torch.inference_mode():
    for task, queries in [(0, sorted(held_queries)), (1, [c['id'] for c in schema['classes']])]:
        model.plm.set_task_id(task)
        for q in queries:
            parents = [p for p in indices[task] if p != q]
            values = []
            for start in range(0, len(parents), 8):
                values.extend(score(task, [(q, p) for p in parents[start:start + 8]]).flatten().cpu().tolist())
            ranked = sorted([{'parent': p, 'score': s} for p, s in zip(parents, values)], key=lambda x: -x['score'])
            true = {p for a, p in edges[task] if a == q}
            rankings.append({'domain': task, 'query': q, 'ranked': ranked,
                             'reference_rank': min(i + 1 for i, x in enumerate(ranked) if x['parent'] in true)})
checkpoint = MOD / 'checkpoints'; checkpoint.mkdir(exist_ok=True)
torch.save({k: v.cpu() for k, v in model.state_dict().items() if 'lora_' in k or k.startswith('mlp.')}, checkpoint / 'taxopro_adapter_head.pt')
write(MOD / 'outputs/parent_rankings.json', rankings)
write(MOD / 'reports/training.json', {'model_class': 'TacoPromptTaxoProCompletion', 'custom_peft': __import__('peft').__file__,
    'options': options, 'seed': 42, 'epochs': 8, 'batch_per_domain': 4, 'train_edges': train_edges,
    'heldout_seed_edges': held, 'losses': logs, 'heldout_top1': sum(x['reference_rank'] == 1 for x in rankings if x['domain'] == 0),
    'heldout_count': len(held_queries), 'target_supervision': 'LLM provisional initial class hierarchy, not independent ground truth',
    'deviations': ['multilingual BERT for Korean instead of uncased English BERT', 'OWL named subclass edges adapted to leaf insertion; no WBS part-of training labels',
                   'small joint RC/tile pilot instead of original benchmark pretraining; reduced LoRA rank and epochs',
                   'original model/custom LoRA/BCE and specific-reversed cosine preserved; lightweight training loop replaces benchmark trainer'],
    'checkpoint_sha256': sha(checkpoint / 'taxopro_adapter_head.pt')})
print('Module2 complete', flush=True)
