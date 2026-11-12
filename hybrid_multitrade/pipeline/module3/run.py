import os
"""Original MILA retrieval/bidirectional matching with verified HCB matches."""
import sys
import json
from pathlib import Path
MOD = Path(os.environ['HYBRID_CASE_ROOT']) / 'module3'
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared'))
from common import *
sys.path.insert(0, str(MOD / 'source'))
import pandas as pd
from sentence_transformers import SentenceTransformer
from modules.identify_correspondences.retrieve_identify_prompt import retrieve_identify_prompt
rc = {'RebarCostItem', 'RebarMaterialCostItem', 'RebarFabricationAssemblyCostItem', 'ConcreteCostItem', 'ReadyMixedConcreteMaterialCostItem', 'ConcretePlacementCostItem', 'FormworkCostItem', 'ShoringCostItem'}
seed = [x for x in read(T / 'shared/seed_elements.json') if x['type'] == 'Class']
schema = read(T / 'module1/outputs/initial_schema.json')
source = [{'id': domain_text('tile:') + x['id'], 'label': ' '.join(x['labels']), 'definition': domain_text('타일 기성업무에서 재사용할 공통 문서/정보 역할: ') + ' '.join(x['comments'])} for x in seed if x['id'] not in rc]
source += [{'id': domain_text('tile:') + x['id'], 'label': x['label'], 'definition': x['definition']} for x in schema['classes']]
target = [{'id': 'rc:' + x['id'], 'label': ' '.join(x['labels']), 'definition': ' '.join(x['comments'])} for x in seed]

def text(x):
    return (x['id'] + ' ' + x['label'] + ': ' + x['definition']).replace('|', '/')
encoder = SentenceTransformer(model_path('embedding'), device='cpu')
import torch
torch.set_num_threads(4)
a = encoder.encode(['query: ' + text(x) for x in source], normalize_embeddings=True)
b = encoder.encode(['query: ' + text(x) for x in target], normalize_embeddings=True)
similarity = a @ b.T

def frame(left, right, matrix):
    records = []
    for i, x in enumerate(left):
        top = sorted(range(len(right)), key=lambda j: -float(matrix[i, j]))[:3]
        records.append({'Query Class': x['id'], 'Query Preferred Term': text(x), 'Candidate List': '|'.join((right[j]['id'] for j in top)), 'Score': '|'.join((str(float(matrix[i, j])) for j in top))})
    return pd.DataFrame(records)
forward, reverse = (frame(source, target, similarity), frame(target, source, similarity.T))
forward.to_json(MOD / 'outputs/forward_candidates.json', orient='records', force_ascii=False, indent=2)
reverse.to_json(MOD / 'outputs/reverse_candidates.json', orient='records', force_ascii=False, indent=2)
template = MOD / 'adapters/matching_prompt.txt'
template.write_text(domain_text('Source ontology: {}\nTarget ontology: {}\nSource entity: {}\nTarget entity: {}\nDecide whether these entities have the SAME ontological meaning/structural role and can be reused across trades. Common document and information roles can match. Distinct RC and tile cost types must not be equated. Relatedness, similar wording, shared parent or same material/work role alone is not equivalence. Return JSON with equivalent:boolean and reason:string.'))
calls = []

def callback(prompt, temperature=None, LLM_model=None):
    result = api('module3', 'semantic_equivalence', prompt, 450)
    assert type(result['equivalent']) is bool
    calls.append({'prompt': prompt, **result})
    return result['equivalent']
retrieve_identify_prompt(domain_text('Tile OWL2'), 'RC OWL2', [x['id'] for x in source], forward, reverse, str(MOD / 'outputs/mila_correspondences.xlsx'), str(template), pd.DataFrame(), pd.DataFrame([{'Entity': x['id'], 'Term': x['id'] + '|' + text(x)} for x in target]), callback, 0, 'gpt-4o-mini-2024-07-18')
matched = pd.read_excel(MOD / 'outputs/mila_correspondences.xlsx').fillna('').to_dict('records')
write(MOD / 'outputs/alignment.json', matched)
write(MOD / 'reports/semantic_verification.json', calls)
write(MOD / 'reports/metrics.json', {'source_classes': len(source), 'target_classes': len(target), 'matched': sum((bool(x['Correspondence']) for x in matched)), 'llm_checks': len(calls), 'deviation': 'Original bidirectional candidate traversal preserved; HCB auto-accept replaced with same semantic callback; multilingual E5 and OpenAI callback replace sample encoder/Ollama setup.'})
print('Module3 complete', flush=True)
