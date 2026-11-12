from pathlib import Path
import requests,json,hashlib,tarfile
root=Path(__file__).resolve().parents[1]/'runtime';p=root/'java.lock.json'
if p.exists():a=json.loads(p.read_text())
else:
 a=requests.get('https://api.adoptium.net/v3/assets/latest/17/hotspot',params={'architecture':'x64','image_type':'jre','os':'linux'},timeout=60).json()[0];p.write_text(json.dumps(a,indent=2))
pkg=a['binary']['package'];dest=root/pkg['name']
if not dest.exists():
 with requests.get(pkg['link'],stream=True,timeout=60) as r:
  r.raise_for_status()
  with dest.open('wb') as f:
   for b in r.iter_content(1048576):f.write(b)
assert hashlib.sha256(dest.read_bytes()).hexdigest()==pkg['checksum']
with tarfile.open(dest) as t:t.extractall(root/'java',filter='data')
print('Java ready',a['version']['semver'])
