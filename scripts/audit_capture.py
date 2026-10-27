#!/usr/bin/env python3
"""Check each captured ear against its chapter source after AAC timestamp recovery."""
import argparse,json,subprocess,sys
from pathlib import Path
import numpy as np
from scipy.signal import correlate
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from lib.store import read,write,sha
p=argparse.ArgumentParser();p.add_argument('--demo',type=Path,required=True);p.add_argument('--video',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
if a.output.exists():raise FileExistsError(a.output)
def audio(path):return np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-vn','-af','aresample=async=1:first_pts=0','-ar','48000','-ac','2','-f','f32le','-']),'<f4').reshape(-1,2)
x=audio(a.video);d=read(a.demo/'data.json');checks=[]
for c in d['chapters']:
 if not c['audio']:continue
 y=audio(a.demo/d['audio'][c['audio']]);ref=y[round((c['clip_start']+.5)*48000):round((c['clip_start']+1.5)*48000)];expected=c['start']+.5;lo=max(0,round((expected-.8)*48000));hi=min(len(x),round((expected+1.8)*48000))
 for ear in range(2):
  seg=x[lo:hi,ear].astype(float);r=ref[:,ear].astype(float);dots=correlate(seg,r,mode='valid',method='fft');energy=np.r_[0,np.cumsum(seg.astype(float)**2)];norm=np.sqrt(np.maximum((energy[len(r):]-energy[:-len(r)])*np.sum(r.astype(float)**2),1e-30));scores=np.where(norm>1e-10,dots/norm,-1);j=int(np.argmax(scores));checks.append({'audio':c['audio'],'ear':['L','R'][ear],'correlation':float(scores[j]),'offset_s':(lo+j)/48000-expected})
result={'status':'PASS' if checks and all(c['correlation']>.9 for c in checks) else 'FAIL','checks':checks,'video_sha256':sha(a.video),'method':'Each ear, middle1s of actual chapter, +/- .8s timing search. Timestamped silence restored; no audio replacement.'};write(a.output,result);print(result['status'],len(checks),'ear/chapter comparisons',min(c['correlation'] for c in checks))
if result['status']!='PASS':sys.exit(1)
