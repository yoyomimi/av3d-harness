#!/usr/bin/env python3
"""One-time migration of licensed local demo artifacts; never needed by the runtime."""
import argparse,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from lib.store import read,write,sha
from lib.dsp import load,save
p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output;out.mkdir(parents=True,exist_ok=False)
h=a.workspace/'real2sim/harness';case=h/'runs/nymeria-four-v1/corey';base=h/'runs/nymeria-four-v1/review/real2sim-demo-v12';d=read(base/'data.json')
for key in ['votes','perception','caption_evidence','decision_trace']:d.pop(key,None)
d['sources']={f'asset_{i:02d}':d['sources'][f'vote_person_{i:02d}'] for i in range(1,4)}
assets=[]
for v in d['avatars']:
 id=f'asset_{v["number"]:02d}';assets.append({'id':id,'number':v['number'],'kind':'person','sound_categories':['speech'],'trajectory':d['sources'][id],'raw_head_trajectory':[{'time_s':i/10,'position_m':f['head']} for i,f in enumerate(v['frames'])],'geometry':'Previously checked continuous head-proxy trajectory; not physical speaker GT'})
write(out/'assets.json',{'frame':'Habitat world meters, +Y up','assets':assets})
answer=read(case/'ownership-av-v4/answer.json');write(out/'gemini-answer.json',answer)
write(out/'semantic.json',{'provider':'Gemini','answer_sha256':sha(out/'gemini-answer.json'),'event':{'category':'speech','start_s':.5,'end_s':4.,'caption':answer['sources'][0]['caption'],'role':'external','visual_identity':None},'scope':'Cached Gemini audio/video answer. Visual asset class compatibility is a harness proposal, not Gemini-confirmed identity.'})
original=h/'inputs/nymeria-four-targets-v1/nymeria_four_targets/clips/corey/binaural.wav';save(out/'original.wav',load(original))
import subprocess,numpy as np
raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(case/'selected-speech-v1/source.wav'),'-ac','1','-ar','48000','-f','f32le','-']);save(out/'source-stereo.wav',np.repeat(np.frombuffer(raw,'<f4')[:,None],2,axis=1))
shutil.copy2(case/'selected-speech-v1/receipt.json',out/'source-review.json')
for key in ['room','ownership']:
 path=(base/d[key]).resolve();name=key+path.suffix;shutil.copy2(path,out/name);d[key]=name
for key in ['videos']:
 for i,value in enumerate(d[key]):
  name=f'video-{i}.mp4';shutil.copy2((base/value).resolve(),out/name);d[key][i]=name
for i,v in enumerate(d['avatars']):
 name=f'avatar-{i}.glb';shutil.copy2((base/v['asset']).resolve(),out/name);v['asset']=name
# Keep only geometry/timing/presentation metadata, not prior model proposals or scores.
for key in ['trials','best','fit_sha256','audio','envelopes','evidence']:d.pop(key,None)
d['caption_tracks']=d['caption_tracks'][:1];write(out/'visual.json',d)
rows=[{'id':f'asset-{n}-a{alpha}','candidate':f'asset_{n:02d}','absorption':alpha,'rir':f'irs/trial_{i:02d}'} for i,(n,alpha) in enumerate([(1,.8),(2,.8),(3,.8),(3,.1)])]
routes=[{'id':key,'candidate':'asset_03','absorption':alpha,'rir':f'irs/{key}-a{alpha}'} for alpha in [.1,.8] for key in 'ABC']
write(out/'renders.json',{'candidates':rows,'routes':routes,'missing_combinations':['asset_01 absorption .1','asset_02 absorption .1'],'scope':'Actual saved SoundSpaces IRs. Geometry determined by visual asset head proxies; old perception votes are not imported or used. These cached IRs originated in earlier experiments.'})
write(out/'import-receipt.json',{'status':'PASS','script_sha256':sha(__file__),'semantic_sha256':sha(out/'semantic.json'),'assets_sha256':sha(out/'assets.json'),'note':'IR folders must be supplied separately; weights/recordings are not part of the code license.'})
print(out)
