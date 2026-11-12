import os
"""Build initial schema in bounded semantic groups, with evidence validation."""
import sys
import re
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared'))
from common import *
rows = [r for r in read(T / 'module1/outputs/extracted_rows.json') if r['extraction'][domain_text('in_tile_scope')]]
wbs = read(T / 'shared/wbs.json')
row_ids = {r['id'] for r in rows}
codes = {x['code'] for x in wbs}
classes, rejected = ([], [])
assignments = []
for role, anchor, label in [('material', domain_text('TileMaterialCostItem'), domain_text('타일 자재 비용항목')), ('installation', domain_text('TileInstallationCostItem'), domain_text('타일 설치 비용항목'))]:
    selected = [r for r in rows if r['extraction']['cost_role'] == role]
    classes.append({'id': anchor, 'label': label, 'definition': label + ': 기성서류에서 자재 공급 또는 설치 작업의 비용대상을 표현한다.', 'parent': 'CostItem', 'row_ids': [r['id'] for r in selected], 'wbs_codes': [], 'origin': 'researcher_cost_role_bridge'})
    for r in selected:
        assignments.append({'row_id': r['id'], 'class_id': anchor})
    evidence = [{'row_id': r['id'], 'text': r['name'] + ' / ' + r['specification']} for r in selected]
    prompt = f"""{domain_text('타일 온톨로지의 ')}{label} 아래에 둘 초기 세부 비용항목 클래스 2~4개를 제안하세요.\n부모는 반드시 {anchor}입니다. 재료 자체/시공법 자체와 비용항목을 혼동하지 마세요.\n행 번호는 증거 참조이며 제품 크기마다 클래스를 만들지 마세요. 각 클래스에 제공 행 ID 1~3개만 근거로 쓰세요.\n기존 클래스 ID {anchor}는 출력하지 마세요.\nJSON 형식: {{"classes":[{{"id":"UniqueEnglishCamelCaseCostItem","label":"한국어 비용항목명","definition":"의미 설명","row_ids":["실제 행 ID"]}}]}}\n근거: """ + json.dumps(evidence, ensure_ascii=False)
    result = api('module1', 'bounded_' + role + '_classes', prompt, 2500)
    allowed = {r['id'] for r in selected}
    for c in result['classes']:
        valid = bool(c.get('row_ids')) and set(c['row_ids']) <= allowed and re.fullmatch('[A-Z][A-Za-z0-9]*', c['id']) and (c['id'] not in {x['id'] for x in classes})
        if not valid:
            rejected.append({'proposal': c, 'reason': 'invalid_id_or_source_reference'})
            continue
        classes.append({**c, 'parent': anchor, 'wbs_codes': [], 'origin': 'LLM_document_proposal'})
result = api('module1', 'bounded_work_classes', domain_text('아래 타일 WBS를 근거로 타일 작업의 상위 유형 2~3개를 제안하세요.\n부모 WorkTask 아래의 is-a 작업 유형이어야 합니다. 비용/재료/시공방법과 구분하세요. WBS part-of를 그대로 is-a로 바꾸지 마세요.\nWorkTask 자체는 출력하지 마세요. 작업명 label은 한국어, id는 영문 CamelCase.\nJSON: {"classes":[{"id":"UniqueWorkTaskType","label":"작업유형","definition":"설명","wbs_codes":["실제 코드"]}]}\nWBS: ') + json.dumps(wbs, ensure_ascii=False), 2000)
for c in result['classes']:
    if c.get('wbs_codes') and set(c['wbs_codes']) <= codes and re.fullmatch('[A-Z][A-Za-z0-9]*', c['id']) and (c['id'] not in {x['id'] for x in classes} | {'WorkTask'}):
        classes.append({**c, 'parent': 'WorkTask', 'row_ids': [], 'origin': 'LLM_WBS_proposal'})
    else:
        rejected.append({'proposal': c, 'reason': 'invalid_id_or_WBS_reference'})
labels = {'material': domain_text('타일 재질 표현'), 'surface': domain_text('타일 적용부위 표현'), 'dimensions': domain_text('타일 치수 표현'), 'thickness': domain_text('타일 두께 표현'), 'method': domain_text('타일 시공방법 표현'), 'finish': domain_text('타일 마감 표현'), 'color': domain_text('타일 색상 표현'), 'other': domain_text('기타 타일 특성 표현')}
properties = []
for name, label in labels.items():
    evidence_rows = [r['id'] for r in rows if any((a['name'] == name for a in r['extraction']['attributes']))]
    if evidence_rows:
        properties.append({'id': domain_text('tile') + name.title() + 'Text', 'label': label, 'definition': '원본 품명/규격에 명시된 ' + label + '. 단위나 수치의 추정 변환 없이 보존한다.', 'kind': 'data', 'domain': 'CostItem', 'range': 'string', 'row_ids': evidence_rows, 'wbs_codes': [], 'extracted_attribute': name, 'origin': 'researcher_evidence_field_adapter'})
for r in rows:
    if r['id'] not in {x['row_id'] for x in assignments}:
        assignments.append({'row_id': r['id'], 'class_id': 'CostItem'})
hypotheses = api('module1', 'open_WBS_hypotheses', domain_text('타일 WBS에 명시되지 않았지만 추가 검토할 가치가 있는 작업/개념 3개를 제안하세요.\n이는 LLM 가설이며 제공 문서에서 확인된 사실이라고 주장하면 안 됩니다. 색상 다양성 같은 일반 문장이 아니라 명확한 온톨로지 개념이어야 합니다.\nJSON: {"hypotheses":[{"id":"EnglishCamelCase","label":"한국어 개념명","definition":"의미","parent":"WorkTask","reason":"추가 검토 이유"}]}\nWBS: ') + json.dumps(wbs, ensure_ascii=False), 1800)['hypotheses']
schema = {'classes': classes, 'properties': properties, 'row_classes': assignments, 'hypotheses': hypotheses}
write(T / 'module1/outputs/initial_schema.json', schema)
write(T / 'module1/reports/schema_review.json', {'rejected_bounded_proposals': rejected, 'superseded_global_designs': [domain_text('initial_tile_schema'), domain_text('initial_tile_schema_v2')], 'reason': 'Global generation mixed cost/material/method roles and omitted evidence. Replaced with bounded semantic-group prompts and explicit field adapters.', 'researcher_defined': ['two cost-role bridges', 'datatype properties from extracted source fields'], 'LLM_defined': ['initial cost subclasses', 'initial work-task types', 'open WBS hypotheses']})
write(T / 'module1/reports/extraction_report.json', {'input_rows': len(read(T / 'module1/outputs/raw_rows.json')), 'included_rows': len(rows), 'initial_classes': len(classes), 'initial_properties': len(properties), 'hypotheses': len(hypotheses), 'method_deviation': 'OmEGa-inspired API extraction and schema-guided relation mapping; original trained layout-LoRA/relation classifier not reproduced'})
print('Module1 schema complete:', len(classes), 'classes,', len(properties), 'properties', flush=True)
