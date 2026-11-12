"""Synthetic sanity controls for the evidence gate; not research accuracy data."""
import sys,json
from pathlib import Path
MOD=Path(__file__).resolve().parent
sys.path.insert(0,str(MOD.parent/'shared'))
from common import *
from pydantic import BaseModel,ConfigDict
from typing import Literal
class Result(BaseModel):
    model_config=ConfigDict(extra='forbid')
    id:str
    relation:Literal['is_a','part_of','related','unclear']
    source_supports:bool
    reason:str
class Results(BaseModel):
    model_config=ConfigDict(extra='forbid')
    results:list[Result]
cases=[
 {'id':'positive_task','query':'FloorPaintingWork: floor painting activity','selected_parent':'WorkTask: construction work activity','source':'WBS: Floor painting'},
 {'id':'positive_cost','query':'RoofTilePurchaseCost: cost of purchasing roof tiles','selected_parent':'TileMaterialPurchaseCost: cost of purchasing tile materials, excluding installation costs','source':'Priced row: roof tiles; quantity 10 m2, unit purchase price 100'},
 {'id':'negative_role','query':'PaintCan: a physical container of paint','selected_parent':'PaintingCost: a monetary cost of painting work','source':'A paint can is a physical container'},
 {'id':'negative_part','query':'SurfacePreparation: cleaning the surface before installation','selected_parent':'TileInstallation: fixing tiles to a surface','source':'Clean the surface before fixing the tiles'}]
instruction=(MOD/'reports/evidence_gate_instruction.txt').read_text()
obj=api('module5','evidence_gate_synthetic_controls',instruction+'\nThese are four synthetic logic controls, not observed research data. Evaluate each, using its id. Return results with id, relation, source_supports and reason.\n'+json.dumps(cases),1800,response_schema=Results.model_json_schema())
results=Results.model_validate(obj).results
actual={r.id:r for r in results}
passed=set(actual)=={c['id'] for c in cases} and all(actual[k].relation=='is_a' and actual[k].source_supports for k in ['positive_task','positive_cost']) and all(actual[k].relation!='is_a' for k in ['negative_role','negative_part'])
write(MOD/'reports/evidence_gate_calibration.json',{'passed':passed,'synthetic_controls':cases,'responses':obj,'not_a_benchmark':True})
print('Evidence gate synthetic controls passed:',passed,flush=True)
if not passed:raise SystemExit(1)
