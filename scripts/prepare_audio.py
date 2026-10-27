#!/usr/bin/env python3
"""Put a reviewed mono crop back on the original clock; preserve source gain."""
import argparse,sys,subprocess
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from lib.dsp import load,save
from lib.store import write,sha
p=argparse.ArgumentParser();p.add_argument('--original',type=Path,required=True);p.add_argument('--stem',type=Path,required=True);p.add_argument('--offset',type=float,required=True);p.add_argument('--fade-ms',type=float,default=20);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);original=load(a.original)
info=__import__('json').loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(a.stem)]));stream=next(s for s in info['streams'] if s['codec_type']=='audio')
if stream['channels']!=1:raise ValueError('Expected reviewed mono stem; do not silently fold original stereo')
x=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(a.stem),'-ar','48000','-f','f32le','-']),'<f4').copy();start=round(a.offset*48000)
if start<0 or start+len(x)>len(original) or not np.isfinite(x).all():raise ValueError('Invalid source clock')
n=min(round(a.fade_ms*48),len(x)//2)
if n>0:
 ramp=(.5-.5*np.cos(np.linspace(0,np.pi,n)));x[:n]*=ramp;x[-n:]*=ramp[::-1]
full=np.zeros(len(original),np.float32);full[start:start+len(x)]=x
save(a.output/'original.wav',original);save(a.output/'source-stereo.wav',np.repeat(full[:,None],2,axis=1))
subprocess.run(['ffmpeg','-v','error','-n','-f','f32le','-ar','48000','-ac','1','-i','pipe:0','-c:a','pcm_f32le',str(a.output/'source-mono.wav')],input=full.tobytes(),check=True)
write(a.output/'audio-receipt.json',{'status':'PASS_EXECUTION','original_sha256':sha(a.original),'stem_sha256':sha(a.stem),'offset_s':a.offset,'edge_fade_ms':a.fade_ms,'stereo_duplication_gain':1,'quality':'Caller-reviewed stem; no purity certification'})
