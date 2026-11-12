import sys,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shared'))
from common import *
import xlrd
from rdflib import Graph,OWL,RDFS,URIRef
wbsfile=next(ROOT.glob('*타일*.md'));rules=[]
for line in wbsfile.read_text().splitlines():
 m=re.match(r'^(?:#{2,3}\s+|-\s+)(3(?:\.\d+)*)(?:\.)?\s+(.+)$',line)
 if m:rules.append({'code':m[1],'label':m[2].strip(),'parent':m[1].rsplit('.',1)[0] if '.' in m[1] else None})
assert len({x['code'] for x in rules})==len(rules)
write(TEST/'shared/wbs.json',rules)
f=next((ROOT/'documents/Documents_2').glob('*.xls'));w=xlrd.open_workbook(str(f));rows=[];excluded=[]
fields={'contractQuantity':3,'contractUnitPrice':10,'contractAmount':11,'previousCumulativeQuantity':12,'previousCumulativeAmount':20,'currentQuantity':21,'currentAmount':29,'cumulativeQuantity':30,'cumulativeAmount':38,'remainingQuantity':39,'remainingAmount':47}
for sn,shift in [('건내',0),('건(인)내',2)]:
 sh=w.sheet_by_name(sn);section=''
 for i in range(5,sh.nrows):
  name=str(sh.cell_value(i,shift)).strip();spec=str(sh.cell_value(i,shift+1)).strip();unit=str(sh.cell_value(i,shift+2)).strip()
  if re.match(r'^\d{6}\s',name):section=name;continue
  in_section='타일공사' in section.replace(' ','')
  mentions=bool(re.search(r'타일|TILE',name+' '+spec,re.I))
  if not unit or not name:continue
  if not (in_section and mentions):
   if in_section or mentions:excluded.append({'sheet':sn,'row':i+1,'name':name,'spec':spec,'section':section,'reason':'outside_tile_section' if not in_section else 'adjacent_non_tile_work'})
   continue
  rawnums={};cellcoords={}
  for k,c in fields.items():
   cell=sh.cell(i,c+shift);rawnums[k]=cell.value if cell.ctype==xlrd.XL_CELL_NUMBER else None;cellcoords[k]={'row':i+1,'column':c+shift+1,'cell_type':cell.ctype,'raw':cell.value}
  # Stair tread is deliberately unresolved; no external rule silently equates it with floor.
  surface='wall' if re.search(r'(^|,)\s*벽',spec) else 'floor' if '바닥' in spec else 'ceiling' if '천장' in spec else 'unknown'
  method='adhesive' if '접착' in name else 'improved_press' if '개량압착' in name else 'press' if '압착' in name else None
  kind='installation' if '붙임' in name or '붙이기' in name else 'material'
  parent={'wall':'3.2','floor':'3.3','ceiling':'3.4'}.get(surface)
  exact={('wall','press'):'3.2.2',('wall','improved_press'):'3.2.3',('wall','adhesive'):'3.2.5',('floor','press'):'3.3.2',('floor','improved_press'):'3.3.3',('floor','adhesive'):'3.3.4'}.get((surface,method)) if kind=='installation' else None
  # Mosaic material alone never establishes the installation method in 3.2.7.
  normalized=re.sub(r'\([^)]*\)','',name.split('/')[0]).strip().replace('타일타일','타일')
  concept=normalized+' | '+surface
  rows.append({'id':f'{sn}:{i+1}','file':f.name,'sheet':sn,'excel_row':i+1,'section':section,'name':name,'specification':spec,'unit':unit,'numbers':rawnums,'cells':cellcoords,'concept_key':concept,'rule':{'surface':surface,'kind':kind,'method':method,'wbs':exact or parent,'wbs_role':'installation_task' if kind=='installation' else 'material_for_work','evidence':'name+specification','unresolved':surface=='unknown'}})
concepts={}
for r in rows:
 if r['concept_key'] not in concepts:
  cid='concept_'+str(len(concepts)+1).zfill(3);concepts[r['concept_key']]={'id':cid,'label':r['concept_key'],'name':re.sub(r'\([^)]*\)','',r['name'].split('/')[0]).strip().replace('타일타일','타일'),'rows':[],'examples':[],'rule':r['rule']}
 c=concepts[r['concept_key']];c['rows'].append(r['id']);c['examples'].append({'name':r['name'],'specification':r['specification']});r['concept_id']=c['id']
g=Graph().parse(ROOT/'KO/OWL2/rcpp-owl-final.ttl');classes=[]
for s in sorted(set(g.subjects(__import__('rdflib').RDF.type,OWL.Class))):
 if isinstance(s,URIRef):classes.append({'iri':str(s),'id':str(s).split('#')[-1],'labels':[str(v) for v in g.objects(s,RDFS.label)],'parents':[str(v).split('#')[-1] for v in g.objects(s,RDFS.subClassOf) if isinstance(v,URIRef)]})
write(TEST/'shared/seed_classes.json',classes);write(TEST/'module1/rows.json',rows);write(TEST/'module1/concepts.json',list(concepts.values()));write(TEST/'module1/excluded_rows.json',excluded)
write(TEST/'module1/preparation.json',{'rows':len(rows),'concepts':len(concepts),'wbs_nodes':len(rules),'excluded_architecture_rows':len(excluded),'missing_CBS':True,'numeric_missing':sum(v is None for r in rows for v in r['numbers'].values()),'file_sha256':digest(f),'wbs_sha256':digest(wbsfile),'seed_sha256':digest(ROOT/'KO/OWL2/rcpp-owl-final.ttl')})
print('Prepared',len(rows),'rows',len(concepts),'concepts',len(rules),'WBS nodes')
