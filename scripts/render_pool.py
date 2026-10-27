#!/usr/bin/env python3
"""Materialize a bounded candidate×material pool using actual SoundSpaces, never panning."""
import argparse,sys,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from lib.store import read,write,sha
from lib.acoustics import material_database
p=argparse.ArgumentParser();p.add_argument('--pool',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True);p.add_argument('--poses',type=Path,required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--seconds',type=float,required=True);p.add_argument('--profile',type=Path,default=ROOT/'configs/acoustics.json');p.add_argument('--output',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args();pool=read(a.pool)
if not a.execute:print({'pairs':len(pool['candidates'])*len(pool['parameter_pool']['absorption']),'requires':'audio-enabled Habitat + verified material override + clearance.json','execute':False});sys.exit()
# Caller supplies geometry validation bound to exact inputs; no semantic claim is a clearance certificate.
proof=read(a.bundle/'clearance.json')
for key,path in [('pool_sha256',a.pool),('poses_sha256',a.poses),('scene_sha256',a.bundle/'scene.glb')]:
 if proof.get(key)!=sha(path):raise ValueError('Geometry proof mismatch: '+key)
if proof['status']!='PASS':raise ValueError('Geometry proof must pass')
a.output.mkdir(parents=True,exist_ok=False);rows=[]
for c in pool['candidates']:
 for alpha in pool['parameter_pool']['absorption']:
  id=c['id']+'-a'+str(alpha);folder=a.output/id;folder.mkdir();write(folder/'materials.json',material_database(alpha));cfg=read(a.profile);cfg.update(materials_json='materials.json',absorption=alpha);write(folder/'acoustics.json',cfg)
  write(folder/'sources.json',{'scene_sha256':sha(a.bundle/'scene.glb'),'sources':[{'id':c['id'],'wav':str(a.source.resolve()),'wav_sha256':sha(a.source),'start_s':0,'end_s':a.seconds,'gain':1,'trajectory':c['trajectory']}]})
  cmd=[sys.executable,str(ROOT/'scripts/soundspaces_render.py'),'--bundle',str(a.bundle),'--poses',str(a.poses),'--sources',str(folder/'sources.json'),'--output',str(folder/'render'),'--seconds',str(a.seconds),'--ir-step','.25','--mask-fade-ms','0','--rays','5000','--acoustics',str(folder/'acoustics.json'),'--save-all-irs']
  with (folder/'render.log').open('w') as log:subprocess.run(cmd,check=True,stdout=log,stderr=subprocess.STDOUT)
  rows.append({'id':id,'candidate':c['id'],'absorption':alpha,'rir':id+'/render'});write(a.output/'renders.json',{'candidates':rows,'routes':[],'status':'RUNNING'})
write(a.output/'renders.json',{'candidates':rows,'routes':[],'status':'PASS_EXECUTION'})
