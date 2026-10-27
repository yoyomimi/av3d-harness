#!/usr/bin/env python3
"""Encode three same-clock route MP4s from actual RGB replay and fitted binaural audio."""
import argparse,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from lib.store import read,write,sha
p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--fit',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--playback-gain',type=float,default=1.);a=p.parse_args()
if not 0<a.playback_gain<=64:raise ValueError('Explicit shared playback gain must be (0,64]')
a.output.mkdir(parents=True,exist_ok=False);e=read(a.fit/'evaluation.json');v=read(a.inputs/'visual.json');lo,hi=e['config']['interval_s'];rows=[]
if len(e['routes'])!=3:raise ValueError('Exactly three actual fitted routes required')
for r in e['routes']:
 visual=next(x for x in v['routeComparisons'] if x['id']==r['id']);video=a.inputs/v['videos'][visual['videoIndex']];audio=a.fit/r['audio'];output=a.output/('route-'+r['id']+'.mp4')
 cmd=['ffmpeg','-v','warning','-nostdin','-n','-ss',str(lo),'-i',str(video),'-ss',str(lo),'-i',str(audio),'-t',str(hi-lo),'-map','0:v:0','-map','1:a:0','-vf','scale=1080:1080:flags=lanczos','-af','volume='+str(a.playback_gain),'-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-r','30','-c:a','aac','-b:a','192k','-movflags','+faststart',str(output)]
 subprocess.run(cmd,check=True);subprocess.run(['ffmpeg','-v','error','-i',str(output),'-f','null','-'],check=True);rows.append({'id':r['id'],'video_sha256':sha(video),'fitted_audio_sha256':sha(audio),'output':output.name,'output_sha256':sha(output),'command':cmd,'full_decode':'PASS'})
write(a.output/'receipt.json',{'status':'PASS','routes':rows,'interval_s':[lo,hi],'shared_playback_gain':a.playback_gain,'scope':'Actual scene RGB + fitted binaural waveform. Cached RGB is reused unless explicitly replaced by fresh replay output. No independent route normalization.'})
