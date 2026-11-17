"""Download the pinned public index model, verifying every file before activation."""
import hashlib,json,urllib.request
from pathlib import Path
from motion_store import root
spec=json.loads((Path(__file__).resolve().parents[1]/'assets/index-model-manifest.json').read_text('utf-8'))
target=root()/'index-model';target.mkdir(exist_ok=True)
for name,expected in spec['files'].items():
 p=target/name
 if p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==expected:continue
 tmp=p.with_suffix(p.suffix+'.part')
 try:
  if name=='revision.txt':tmp.write_text(spec['revision'])
  else:
   remote='onnx/model_quint8_avx2.onnx' if name=='model.onnx' else name
   urllib.request.urlretrieve('https://huggingface.co/'+spec['model']+'/resolve/'+spec['revision']+'/'+remote,tmp)
  if hashlib.sha256(tmp.read_bytes()).hexdigest()!=expected:raise ValueError('Model hash mismatch: '+name)
  tmp.replace(p)
 finally:tmp.unlink(missing_ok=True)
print('Pinned multilingual model ready:',target)
