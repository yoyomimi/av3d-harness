#!/usr/bin/env python3
"""SAM original-context peel, capped gain and inverse restoration; no postfilter."""
import argparse,os,sys,subprocess
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from lib.store import write,sha
p=argparse.ArgumentParser();p.add_argument('--audio',type=Path,required=True);p.add_argument('--start',type=float,default=0);p.add_argument('--duration',type=float,default=8);p.add_argument('--cue',required=True);p.add_argument('--model',default='facebook/sam-audio-base');p.add_argument('--device',default='cuda');p.add_argument('--output',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
if not a.execute:print({'cue':a.cue,'context':[a.start,a.start+a.duration],'gain':'min(32, .9 / stereo peak), inverse restore','model':a.model,'execute':False});sys.exit()
if not 0<a.duration<=12 or a.start<0:raise ValueError('Invalid context bounds')
a.output.mkdir(parents=True,exist_ok=False);receipt={'status':'RUNNING','input_sha256':sha(a.audio),'context_s':[a.start,a.start+a.duration],'cue':a.cue,'model':a.model,'script_sha256':sha(__file__),'seed':0,'dry_source':False};write(a.output/'receipt.json',receipt)
try:
 os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
 import torch,soundfile as sf
 from sam_audio import SAMAudio,SAMAudioProcessor
 raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(a.start),'-i',str(a.audio),'-t',str(a.duration),'-ac','2','-ar','48000','-f','f32le','-']);x=np.frombuffer(raw,'<f4').reshape(-1,2).T.copy()
 if abs(x.shape[1]-round(a.duration*48000))>1:raise ValueError('Context exceeds input')
 gain=min(32.,.9/max(float(abs(x).max()),1e-12));model=SAMAudio.from_pretrained(a.model,visual_ranker=None,text_ranker=None,span_predictor=None).eval();processor=SAMAudioProcessor.from_pretrained(a.model)
 for name,module in model.named_children():
  if name not in {'vision_encoder','visual_ranker','text_ranker','span_predictor'}:module.to(a.device)
 torch.manual_seed(0);batch=processor(audios=[torch.from_numpy(x*gain)],descriptions=[a.cue]).to(a.device)
 with torch.inference_mode():result=model.separate(batch,predict_spans=False,reranking_candidates=1)
 waves=[]
 for name,v in [('target',result.target),('residual',result.residual)]:
  w=v[0].detach().float().cpu().numpy().reshape(-1)[:x.shape[1]]/gain;waves.append(w);sf.write(a.output/(name+'.wav'),w,48000,subtype='FLOAT')
 receipt.update(status='PASS_EXECUTION_ONLY',input_gain=gain,inverse_restored=True,closure_error_ratio=float(np.mean((x.mean(0)-sum(waves))**2)/max(np.mean(x.mean(0)**2),1e-20)),outputs={n:sha(a.output/(n+'.wav')) for n in ['target','residual']},quality='Review both outputs. Retaining residual as a speech layer requires explicit quality review; it is not a dry-source claim.')
except Exception as e:receipt.update(status='FAIL',error_type=type(e).__name__);raise
finally:write(a.output/'receipt.json',receipt)
