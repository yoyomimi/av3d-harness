#!/usr/bin/env python3
"""Build a self-contained review from a completed run; no model inference in the UI."""
import argparse,copy,shutil,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from lib.store import read,write,sha
from lib.dsp import load,save
p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output;out.mkdir(parents=True,exist_ok=False);(out/'audio').mkdir();m=read(a.run/'manifest.json');inputs=Path(m['inputs']);D=read(inputs/'visual.json');E=read(a.run/'fit/evaluation.json');pool=read(a.run/'candidates/pool.json');chosen=E['selected'];number={c['id']:c['number'] for c in pool['candidates']}
# Stage order follows observed fit, never a hardcoded winning identity.
baseline=next(c for c in E['placement_controls'] if c['candidate']==pool['candidates'][0]['id'] and c['absorption']==.8)
placement=next(c for c in E['placement_controls'] if c['candidate']==chosen['candidate'] and c['absorption']==.8)
rows=[]
for i,r in enumerate([baseline,placement,chosen]):rows.append({'iteration':i,'path':r['candidate'],'candidate_number':number[r['candidate']],'absorption':r['absorption'],'global_source_gain':r['gain'],'diagnostics':r['metrics'],'accepted':i==0 or r['objective']<rows[-1]['objective'],'objective':r['objective']})
D.update(trials=rows,best=2,physics_trial=2,winner_number=number[chosen['candidate']],candidate_pool={'candidates':pool['candidates'],'windows':[]})
D['caption_tracks']=D['caption_tracks'][:1]
D['caption_tracks'][0]['provider']='Perception'
for key in ['room','ownership']:
 shutil.copy2(inputs/D[key],out/D[key])
for value in D['videos']:shutil.copy2(inputs/value,out/value)
for v in D['avatars']:shutil.copy2(inputs/v['asset'],out/v['asset'])
raw={'original':load(inputs/'original.wav'),'external':load(inputs/'source-stereo.wav')}
for i,r in enumerate([baseline,placement,chosen]):raw[f'trial{i}']=load(a.run/'fit'/r['audio'])
for r in E['routes']:raw['route'+r['id']]=load(a.run/'fit'/r['audio'])
if len(E['routes'])!=3:raise ValueError('Three actual route renders required; no invented finale')
gain=min(64,.88/max(float(abs(x).max()) for x in raw.values()));D['audio']={};D['envelopes']={}
for k,x in raw.items():
 save(out/'audio'/f'{k}.wav',x*gain);D['audio'][k]=f'audio/{k}.wav';D['envelopes'][k]=np.sqrt(np.mean(x.reshape(-1,480,2)**2,axis=(1,2))).tolist()
D['audition_gain']=gain
D['rejected_absorption']=next((c['absorption'] for c in E['candidates'] if c['candidate']==chosen['candidate'] and c['absorption']!=chosen['absorption']),None)
for c in D['chapters']:
 if c['kind']=='caption':c['tool']='Perception · semantic events';c['stage']='Perception'
 if c['kind'] in ['perceive','candidates']:c.update(stage='Propose Candidates',tool='Semantic events → visual assets',note='Speech → person assets → trajectories')
 if c['kind']=='peel':c.update(stage='Semantic Audio Peel',tool='Semantics → separated audio tracks',note='Semantic target · speech / cutting-board phrase')
 if c['kind']=='match':c['note']='Test perception target '+str(rows[c['trial']]['candidate_number']).zfill(2)
 if c.get('stage')=='Fit Physics' or c['kind']=='benchmark':c.update(stage='Fit to GT',tool='Test → Render → Compare GT → Auto-adjust')
# One held overview: semantic target and all compatible assets appear together.
combined=[];overview=None
for c in D['chapters']:
 if c['kind']=='perceive':
  overview={**c,'kind':'candidates','freeze':True,'clip_start':1.9,'note':'Semantic target · Speech'};combined.append(overview)
 elif c['kind']=='candidates' and overview is not None:overview['duration']+=c['duration']
 else:combined.append(c)
D['chapters']=combined
# Deliberate chapter cards: the active tool and one plain-language purpose.
transitions={'peel':(1,'Use semantic descriptions to separate the recording into audio tracks.'),'candidates':(2,'Match the speech event to possible people in the 3D scene.'),'match':(3,'Test perception targets and room-physics candidates.'),'label':(4,'Save the fitted source and a candidate label for review.'),'routes':(5,'Keep the source fixed. Hear three different listening paths.')}
chapters=[{'stage':'Original · silent opening','kind':'coldopen','closing':False,'duration':4.0,'audio':None,'clip_start':.7,'trial':0,'freeze':False,'tool':''}];seen=set();clock=0.
for c in D['chapters']:
 if c['kind'] in transitions and c['kind'] not in seen:
  module,note=transitions[c['kind']];seen.add(c['kind']);chapters.append({'stage':'Next · '+['Perception','Semantic Audio Peel','Candidates','Fit to GT','Merge Trajectory','Rerender'][module],'kind':'transition','module':module,'note':note,'duration':4.0 if module==3 else 1.8,'audio':None,'clip_start':.7,'trial':0,'freeze':True,'tool':''})
 chapters.append(c)
chapters.append({'stage':'AV3D-Harness · finale','kind':'brand','closing':True,'duration':3.,'audio':None,'clip_start':3.8,'trial':2,'freeze':True,'tool':''})
for c in chapters:c['start']=clock;clock+=c['duration']
D['chapters']=chapters;D['duration']=clock
D['evidence']='Default pipeline: cached Gemini semantics → visual asset class compatibility → candidate locations/trajectories → actual saved SoundSpaces RIR replay → energy + left/right energy benchmark. No learned spatial perception is used. All three person assets remain eligible. RIRs were queried in earlier experiments; this run recomputes source convolution and selection. Missing candidate/material pairs remain NOT RUN. Caption/source-review models are fallible; retained speech has room background. Candidate labels are pending validation; no model training performed.'
D['fit_sha256']=sha(a.run/'fit/evaluation.json');D['source_sha256']=sha(inputs/'source-stereo.wav')
for r in D['routeComparisons']:
 r.pop('route_receipt',None);r.pop('audio_receipt',None)
write(out/'data.json',D);write(out/'evaluation.json',E);write(out/'candidate-pool.json',pool);shutil.copy2(a.run/'candidate-label.json',out/'candidate-label.json');shutil.copytree(ROOT/'vendor',out/'vendor');shutil.copy2(ROOT/'templates/demo.html',out/'index.html');write(out/'build.json',{'status':'PASS','duration_s':D['duration'],'code_sha256':sha(__file__),'data_sha256':sha(out/'data.json'),'template_sha256':sha(out/'index.html'),'scope':'Review; runtime has no dependency on unreleased perception tools'})
print(out)
