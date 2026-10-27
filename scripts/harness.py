#!/usr/bin/env python3
"""Small JSON-first harness. Fresh runs, explicit stages, replaceable providers."""
import argparse,sys,shutil,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from lib.store import read,write,sha,event
from lib.pipeline import propose,fit

def main():
 p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='cmd',required=True)
 i=s.add_parser('init');i.add_argument('--inputs',type=Path,required=True);i.add_argument('--run',type=Path,required=True);i.add_argument('--config',type=Path,default=ROOT/'configs/demo.json')
 for command in ['propose','fit','label','status']:
  q=s.add_parser(command);q.add_argument('--run',type=Path,required=True)
  if command=='fit':q.add_argument('--renders',type=Path)
 a=p.parse_args();run=a.run
 if a.cmd=='init':
  run.mkdir(parents=True,exist_ok=False);(run/'receipts').mkdir();(run/'candidates').mkdir()
  files=['semantic.json','assets.json','original.wav','source-stereo.wav']
  if (a.inputs/'renders.json').exists():files.append('renders.json')
  write(run/'manifest.json',{'schema_version':1,'inputs':str(a.inputs.resolve()),'input_hashes':{f:sha(a.inputs/f) for f in files},'config':read(a.config),'script_sha256':sha(__file__)})
  event(run,'init');print(run);return
 m=read(run/'manifest.json');inputs=Path(m['inputs'])
 if a.cmd=='status': print({'run':str(run),'proposed':(run/'candidates/pool.json').exists(),'fit':(run/'fit/evaluation.json').exists(),'label':(run/'candidate-label.json').exists()});return
 for f,h in m['input_hashes'].items():
  if sha(inputs/f)!=h:raise ValueError('Input changed: start a fresh run')
 dest=run/'receipts'/f'{a.cmd}.json'
 if dest.exists():raise FileExistsError('Stage already attempted; preserve receipt and start a fresh run')
 receipt={'stage':a.cmd,'status':'RUNNING','command':sys.argv,'code_sha256':sha(ROOT/'lib/pipeline.py')};write(dest,receipt)
 try:
  if a.cmd=='propose':result=propose(read(inputs/'semantic.json'),read(inputs/'assets.json'),m['config']);write(run/'candidates/pool.json',result)
  elif a.cmd=='fit':result=fit(inputs,read(run/'candidates/pool.json'),run/'fit',m['config'],a.renders)
  else:
   e=read(run/'fit/evaluation.json');c=next(x for x in read(run/'candidates/pool.json')['candidates'] if x['id']==e['selected']['candidate'])
   result={'status':'CANDIDATE_REQUIRES_VALIDATION','training_status':'NOT TRAINED','candidate':c,'fit_sha256':sha(run/'fit/evaluation.json'),'gates':['Independent source-quality review','Geometry/head registration','Held-out training evaluation']};write(run/'candidate-label.json',result)
  receipt['status']='PASS_EXECUTION';print({'status':result['status'],'selected':result.get('selected',{}).get('id')})
 except Exception as e:receipt.update(status='FAIL',error_type=type(e).__name__);raise
 finally:write(dest,receipt);event(run,a.cmd,status=receipt['status'])
if __name__=='__main__':main()
