#!/usr/bin/env python3
"""Verify cached RIR query source positions match proposed visual trajectories."""
import argparse,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from lib.store import read,write,sha
from soundspaces_render import pose_at
p=argparse.ArgumentParser();p.add_argument('--pool',type=Path,required=True);p.add_argument('--renders',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
if a.output.exists():raise FileExistsError(a.output)
pool={c['id']:c for c in read(a.pool)['candidates']};manifest=read(a.renders);checks=[]
for item in manifest['candidates']+manifest['routes']:
 records=read(a.renders.parent/item['rir']/'ir_manifest.json');rows=pool[item['candidate']]['trajectory'];errors=[]
 for r in records:
  t=r['time_s']
  if t<rows[0]['time_s']-.25 or t>rows[-1]['time_s']+.25:raise ValueError('IR query outside trajectory support')
  row=pose_at(rows,min(max(t,rows[0]['time_s']),rows[-1]['time_s']))
  if row is None:raise ValueError('IR query in missing trajectory')
  errors.append(float(np.linalg.norm(np.array(row['position_m'])-r['source_position'])))
 checks.append({'id':item['id'],'max_position_error_m':max(errors),'status':'PASS' if max(errors)<1e-5 else 'FAIL'})
result={'status':'PASS' if all(c['status']=='PASS' for c in checks) else 'FAIL','pool_sha256':sha(a.pool),'renders_sha256':sha(a.renders),'checks':checks};write(a.output,result)
if result['status']!='PASS':raise ValueError('Cached IR source position mismatch')
print(result['status'],len(checks),'IR sequences')
