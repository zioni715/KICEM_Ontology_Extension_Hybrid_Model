import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shared'))
from common import *
cs=read(TEST/'module1/concepts.json');wbs=read(TEST/'shared/wbs.json');llm=LocalLLM('module1')
prompts=[]
for c in cs:
 prompts.append('아래 Excel 행들은 하나의 타일 비용 개념의 예시입니다. 전체 예시를 통합하여 JSON 객체를 정확히 하나만 반환하세요. 수량/금액을 생성하지 마세요.\n'
 'kind는 material, installation, unknown 중 하나만 선택하세요. material=타일 자재 공급. installation=타일을 붙이는 시공비. 이름의 붙임/붙이기는 시공을 뜻합니다. 접착제붙임도 시공비입니다.\n'
 'surface는 wall, floor, ceiling, unknown 중 하나만 선택하세요. 규격의 벽=wall, 바닥/외부바닥=floor, 천장=ceiling. 디딤만 있으면 unknown. 이름에 있는 사용장소보다 규격의 명시적인 부위를 우선하세요.\n'
 'method는 press, improved_press, adhesive, unknown 중 하나만 선택하세요. 압착붙임=press, 개량압착=improved_press, 접착제붙임=adhesive. 자재만 있으면 unknown.\n'
 'wbs_code는 아래 WBS에서 증거로 확인되는 코드 또는 null. 자재 공급만 있으면 부위 수준(벽 3.2, 바닥 3.3)까지만 배정하고 시공법을 추정하지 마세요. 모자이크 자재라고 시공법을 추정하지 마세요.\n'
 'WBS: '+json.dumps(wbs,ensure_ascii=False)+'\n'
 '실제 행: '+json.dumps(c['examples'],ensure_ascii=False)+'\n'
 '출력 키는 kind, surface, method, wbs_code, material입니다. material에는 원문에 있는 짧은 재료명을 넣으세요. 선택지 문자열을 복사하지 말고 각 필드에 값 하나만 넣으세요. 설명/배열/추가 JSON 없이 객체 하나만 반환하세요.')
outs=llm.objects(prompts,160);traces=[]
for c,o in zip(cs,outs):
 d=o.get('data',{});r=c['rule'];valid=o['valid'] and d.get('kind') in ['material','installation','unknown'] and d.get('surface') in ['wall','floor','ceiling','unknown'] and d.get('method') in ['press','improved_press','adhesive','unknown'] and (d.get('wbs_code') is None or d['wbs_code'] in {x['code'] for x in wbs})
 matches={k:d.get(k)==r[k] for k in ['kind','surface']};matches['wbs']=d.get('wbs_code')==r['wbs']
 c['omega']=d if valid else None;c['llm_valid']=valid;c['rule_llm_agreement']=matches;c['final_semantics']=r;c['decision']='rule_grounded; LLM proposals retained for audit'
 traces.append({'concept_id':c['id'],'schema_valid':valid,'proposal':o,'agreement':matches})
write(TEST/'module1/extracted_concepts.json',cs);write(TEST/'module1/extraction_audit.json',traces)
write(TEST/'module1/metrics.json',{'concepts':len(cs),'schema_valid':sum(c['llm_valid'] for c in cs),'kind_agreement_with_rules':sum(c['rule_llm_agreement']['kind'] for c in cs),'surface_agreement_with_rules':sum(c['rule_llm_agreement']['surface'] for c in cs),'wbs_agreement_with_rules':sum(c['rule_llm_agreement']['wbs'] for c in cs),'independent_gold':False,'trained_OmEGa_layout_LoRA':False,'deviation':'OmEGa-inspired ontology-conditioned extraction on exact spreadsheet cells; local Qwen, no OCR/layout embedding/relation fine-tuning'})
print('Module1 complete')
