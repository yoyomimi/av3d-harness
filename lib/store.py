import hashlib,json,time
from pathlib import Path

def read(path):return json.loads(Path(path).read_text())
def write(path,data):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(data,indent=2,allow_nan=False,ensure_ascii=False)+'\n');tmp.replace(p)
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()
def event(run,kind,**fields):
    with (Path(run)/'events.jsonl').open('a') as f:f.write(json.dumps({'unix_time':time.time(),'kind':kind,**fields},ensure_ascii=False)+'\n')
