"""Provider-neutral proposals and auditable, bounded energy fitting."""
import itertools
from pathlib import Path
import numpy as np
from scipy.signal import fftconvolve
from .store import read, write, sha
from .dsp import load, save, compare

def propose(semantic, assets, config):
    category=semantic['event']['category']
    pool=[]
    for asset in assets['assets']:
        if category not in asset['sound_categories'] and asset['kind'] not in semantic['event'].get('compatible_visual_classes',[]): continue
        track=asset['trajectory']; times=np.array([p['time_s'] for p in track])
        xyz=np.array([p['position_m'] for p in track])
        if len(times)<2 or np.any(np.diff(times)<=0) or not np.isfinite(xyz).all(): raise ValueError('Invalid asset trajectory')
        pool.append({'id':asset['id'],'number':asset['number'],'trajectory':track,'reason':f'{category} compatible with {asset["kind"]}; identity unverified','geometry':asset.get('geometry','NOT CHECKED')})
    if len(pool)>config['budget']['max_candidates']: raise ValueError('Candidate budget exceeded; refine semantic class or increase explicit budget')
    if not pool: raise ValueError('No semantically compatible visual assets; supply more assets or mark source offscreen')
    return {'status':'PROPOSED','provider':'semantic-to-visual-asset compatibility','candidates':pool,'parameter_pool':config['parameter_pool'],'policy':'All compatible assets retained. No audio-direction model, no confidence-count ranking. Geometry must pass before live rendering.'}

def metrics(reference, rendered):
    if reference.shape!=rendered.shape or reference.ndim!=2 or reference.shape[1]!=2: raise ValueError('Exact stereo clock required')
    if not np.isfinite(reference).all() or not np.isfinite(rendered).all(): raise ValueError('Nonfinite audio')
    if min(np.mean(reference**2),np.mean(rendered**2))<1e-14: raise ValueError('Silent/near-empty audio is not a valid fit')
    m,_=compare(reference,rendered)
    m['channel_level_error_db']=(10*np.log10(np.maximum(np.mean(rendered**2,axis=0),1e-20)/np.maximum(np.mean(reference**2,axis=0),1e-20))).tolist()
    m['channel_energy_mae_db']=float(np.mean(np.abs(m['channel_level_error_db'])))
    if m['ild_mae_db'] is None: raise ValueError('No valid stereo-energy windows')
    return m

def convolve(source, folder):
    """Replay real saved IRs; 250ms triangular overlap, unchanged full source clock."""
    folder=Path(folder); x=np.asarray(source,dtype=float); x=(x-x[0])-np.mean(x-x[0]);x=x.astype(np.float32)
    records=read(folder/'ir_manifest.json');receipt=read(folder/'receipt.json')
    if receipt.get('skipped_pose_gaps',0) or any(r['masked_nonzero_samples'] for r in receipt.get('support_masks',[])): raise ValueError('Incomplete historical render')
    blocks=[]
    for center in range(0,len(x)+12000,12000):
        start=max(0,center-12000);end=min(len(x),center+12000)
        if end>start: blocks.append((start,x[start:end]*np.maximum(0.,1-abs(np.arange(start,end)-center)/12000)))
    if len(records)!=len(blocks): raise ValueError('IR/source clock mismatch')
    out=np.zeros((len(x),2)); hashes=[]
    for (start,block),r in zip(blocks,records):
        if r['status']!='PASS' or r['input_start_sample']!=start: raise ValueError('Invalid IR receipt')
        f=folder/r['ir_file'];ir=np.load(f)['ir']
        if ir.shape[0]!=2 or not np.isfinite(ir).all() or np.sum(ir**2)<=1e-20: raise ValueError('Invalid binaural IR')
        hashes.append(sha(f))
        for ch in range(2):
            y=fftconvolve(block,ir[ch]);n=min(len(y),len(x)-start);out[start:start+n,ch]+=y[:n]
    return out,{'manifest_sha256':sha(folder/'ir_manifest.json'),'ir_sha256':hashes,'queries':len(records),'scope':'Actual saved RIR replay; no new simulator query. Output retains recording-length clock.'}

def fit(inputs, pool, output, config, render_manifest=None):
    root=Path(inputs);out=Path(output);out.mkdir(parents=True,exist_ok=False)
    render_manifest=Path(render_manifest) if render_manifest else root/'renders.json';manifest=read(render_manifest);rir_root=render_manifest.parent;gt=load(root/'original.wav');source=load(root/'source-stereo.wav')[:,0]
    lo,hi=[round(v*48000) for v in config['interval_s']];ref=gt[lo:hi]
    allowed={c['id'] for c in pool['candidates']}; rows=[]; waves={}; placement=[]
    for item in manifest['candidates']:
        if item['candidate'] not in allowed or item['absorption'] not in pool['parameter_pool']['absorption']:continue
        wave,receipt=convolve(source,rir_root/item['rir']);waves[item['id']]=wave
        if item['absorption']==pool['parameter_pool']['absorption'][0]:
            pm=metrics(ref,wave[lo:hi]*4.);placement.append({**item,'gain':4.,'metrics':pm,'objective':pm['channel_energy_mae_db']+pm['ild_mae_db']})
        gain=float(np.clip(np.sqrt(np.mean(ref**2)/np.mean(wave[lo:hi]**2)),*pool['parameter_pool']['source_gain_bounds']))
        m=metrics(ref,wave[lo:hi]*gain)
        # Fixed public objective. No spectral/model score participates in selection.
        objective=m['channel_energy_mae_db']+m['ild_mae_db']
        row={**item,'gain':gain,'metrics':m,'objective':objective,'rir':receipt};rows.append(row)
    if not rows: raise ValueError('No rendered candidate in pool')
    rows.sort(key=lambda r:r['objective']);best=rows[0]
    for i,row in enumerate(rows):
        name=f'candidate-{i:02d}.wav';save(out/name,waves[row['id']]*row['gain']);row['audio']=name;row['audio_sha256']=sha(out/name)
    for i,row in enumerate(placement):
        name=f'placement-{i:02d}.wav';save(out/name,waves[row['id']]*row['gain']);row['audio']=name;row['audio_sha256']=sha(out/name)
    routes=[]
    for item in manifest['routes']:
        if item['candidate']!=best['candidate'] or item['absorption']!=best['absorption']: continue
        w,receipt=convolve(source,rir_root/item['rir']);name='route-'+item['id']+'.wav';save(out/name,w*best['gain']);routes.append({**item,'audio':name,'gain':best['gain'],'receipt':receipt})
    result={'status':'PASS_EXECUTION','objective':'channel_energy_mae_db + 250ms ild_mae_db; lower is better','selected':best,'candidates':rows,'placement_controls':placement,'routes':routes,'config':config,'source_sha256':sha(root/'source-stereo.wav'),'reference_sha256':sha(root/'original.wav'),'quality':'Wet speech layer; physical identity unverified. Fit reference is not held-out GT.'}
    write(out/'evaluation.json',result);return result
