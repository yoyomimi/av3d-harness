#!/usr/bin/env python3
"""Fresh Habitat RGB + SoundSpaces RIRs for three routes using the selected fit."""
import argparse,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from lib.store import read,write,sha
from lib.acoustics import material_database
from lib.dsp import load,save
p=argparse.ArgumentParser();p.add_argument('--fit',type=Path,required=True);p.add_argument('--pool',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True);p.add_argument('--routes',type=Path,required=True);p.add_argument('--dataset',type=Path,required=True);p.add_argument('--clip',required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--visual-python',required=True);p.add_argument('--audio-python',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--seconds',type=float,default=7.6);p.add_argument('--execute',action='store_true');a=p.parse_args();e=read(a.fit/'evaluation.json');selected=e['selected'];pool=read(a.pool);source=next(c for c in pool['candidates'] if c['id']==selected['candidate'])
if not a.execute:print({'routes':['A','B','C'],'source':selected['candidate'],'absorption':selected['absorption'],'source_gain':selected['gain'],'fresh':'3 visual replays + 3 actual RIR sequences'});sys.exit()
a.output.mkdir(parents=True,exist_ok=False);rows=[]
for key in 'ABC':
 folder=a.output/key;folder.mkdir();write(folder/'sources.json',{'scene_sha256':sha(a.bundle/'scene.glb'),'sources':[{'id':source['id'],'wav':str(a.source.resolve()),'wav_sha256':sha(a.source),'start_s':0,'end_s':a.seconds,'gain':1,'trajectory':source['trajectory']}]});write(folder/'materials.json',material_database(selected['absorption']));profile=read(ROOT/'configs/acoustics.json');profile.update(materials_json='materials.json',absorption=selected['absorption']);write(folder/'acoustics.json',profile)
 visual=[a.visual_python,str(ROOT/'scripts/render_target_replay.py'),'--dataset',str(a.dataset),'--clip',a.clip,'--camera-override',str(a.routes/key/'camera.npz'),'--silent-only','--output',str(folder/'visual')]
 acoustic=[a.audio_python,str(ROOT/'scripts/soundspaces_render.py'),'--bundle',str(a.bundle),'--poses',str(a.routes/key/'listener.json'),'--sources',str(folder/'sources.json'),'--output',str(folder/'audio'),'--seconds',str(a.seconds),'--ir-step','.25','--mask-fade-ms','0','--rays','5000','--acoustics',str(folder/'acoustics.json'),'--save-all-irs']
 for name,cmd in [('visual',visual),('audio',acoustic)]:
  with (folder/(name+'.log')).open('w') as log:subprocess.run(cmd,check=True,stdout=log,stderr=subprocess.STDOUT)
 rec=read(folder/'audio/receipt.json')
 if rec['skipped_pose_gaps'] or any(v['masked_nonzero_samples'] for v in rec['support_masks']):raise ValueError('Incomplete audio route')
 save(folder/'fitted.wav',load(folder/'audio/binaural.wav')*selected['gain']);lo,hi=e['config']['interval_s'];cmd=['ffmpeg','-v','error','-nostdin','-n','-ss',str(lo),'-i',str(folder/'visual/rgb_silent.mp4'),'-ss',str(lo),'-i',str(folder/'fitted.wav'),'-t',str(hi-lo),'-map','0:v:0','-map','1:a:0','-c:v','libx264','-preset','fast','-crf','18','-r','30','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(folder/'final.mp4')];subprocess.run(cmd,check=True);subprocess.run(['ffmpeg','-v','error','-i',str(folder/'final.mp4'),'-f','null','-'],check=True)
 rows.append({'id':key,'status':'PASS','video_sha256':sha(folder/'final.mp4'),'visual_receipt_sha256':sha(folder/'visual/receipt.json'),'audio_receipt_sha256':sha(folder/'audio/receipt.json'),'commands':[visual,acoustic,cmd]});write(a.output/'receipt.json',{'status':'RUNNING','routes':rows});print(key,'PASS',flush=True)
write(a.output/'receipt.json',{'status':'PASS','routes':rows,'fit_sha256':sha(a.fit/'evaluation.json'),'source_sha256':sha(a.source),'scope':'Fresh visual+acoustic simulation, existing installed engines and supplied scene. No model training.'})
