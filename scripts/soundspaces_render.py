#!/usr/bin/env python3
"""Render moving mono sources through actual SoundSpaces 2 binaural impulse responses.

Requires an audio-enabled Habitat-Sim build. There is deliberately no panning
fallback. Input poses share the visual bundle's scene coordinates and video clock.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import time
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def basis(heading):
    forward=np.asarray(heading,dtype=float)
    forward/=max(np.linalg.norm(forward),1e-12)
    up=np.array([0.,1.,0.])
    if abs(forward@up)>.999:up=np.array([0.,0.,1.])
    right=np.cross(forward,up);right/=np.linalg.norm(right)
    return np.column_stack((right,np.cross(right,forward),-forward))


def is_valid(row):
    return not row.get('missing',False) and row.get('reliable',True)


def pose_at(rows, t, max_gap=.6):
    """Offline interpolation within valid segments; singleton is static only explicitly."""
    times=np.array([p['time_s'] for p in rows])
    if len(rows)==1:
        row=rows[0]
        return row if is_valid(row) and (row.get('static',False) or abs(t-times[0])<1e-7) else None
    if t<times[0]-1e-6 or t>times[-1]+1e-6:return None
    i=min(len(rows)-1,max(0,int(np.searchsorted(times,t,side='right')-1)))
    a=rows[i]
    if not is_valid(a):return None
    if i==len(rows)-1 or abs(t-times[i])<1e-7:return a
    b=rows[i+1]
    if b['time_s']-a['time_s']>max_gap or a.get('segment',0)!=b.get('segment',0):return None
    if not is_valid(b):return None
    f=(t-a['time_s'])/(b['time_s']-a['time_s'])
    value=dict(a)
    value['position_m']=(np.asarray(a['position_m'])*(1-f)+np.asarray(b['position_m'])*f).tolist()
    if 'velocity_m_s' in a and 'velocity_m_s' in b:
        # Exact cubic Hermite interpolation for certified smooth source curves.
        # Ordinary listener/legacy observations retain their prior interpolation.
        dt=b['time_s']-a['time_s']
        value['position_m']=((2*f**3-3*f*f+1)*np.asarray(a['position_m'])+
            (f**3-2*f*f+f)*dt*np.asarray(a['velocity_m_s'])+
            (-2*f**3+3*f*f)*np.asarray(b['position_m'])+
            (f**3-f*f)*dt*np.asarray(b['velocity_m_s'])).tolist()
    if 'rotation_matrix' in a or 'rotation_matrix' in b:
        if 'rotation_matrix' not in a or 'rotation_matrix' not in b:
            raise ValueError('Incomplete calibrated rotation interval')
        from scipy.spatial.transform import Rotation, Slerp
        rotation=Slerp([0.,1.],Rotation.from_matrix([a['rotation_matrix'],b['rotation_matrix']]))([f]).as_matrix()[0]
        value['rotation_matrix']=rotation.tolist()
        value['heading']=(-rotation[:,2]).tolist()
    elif 'heading' in a:
        h=np.asarray(a['heading'])*(1-f)+np.asarray(b['heading'])*f
        if np.linalg.norm(h)<1e-6:return None
        value['heading']=(h/np.linalg.norm(h)).tolist()
    return value


def support_mask(rows,count,sample_rate,max_gap):
    """Sample support of valid continuous segments; no future/gap extrapolation."""
    mask=np.zeros(count,dtype=bool)
    if len(rows)==1 and rows[0].get('static',False) and is_valid(rows[0]):
        mask[:]=True
        return mask
    for a,b in zip(rows,rows[1:]):
        if (is_valid(a) and is_valid(b) and a.get('segment',0)==b.get('segment',0)
            and b['time_s']-a['time_s']<=max_gap):
            start=max(0,int(math.ceil(a['time_s']*sample_rate)))
            stop=min(count,int(math.floor(b['time_s']*sample_rate))+1)
            mask[start:stop]=True
    return mask


def remove_dc(waveform):
    """Remove the whole valid source waveform mean before any temporal masking."""
    waveform=np.asarray(waveform,dtype=np.float64)
    if waveform.size==0 or not np.isfinite(waveform).all():
        raise ValueError('Empty or nonfinite waveform')
    reference=float(waveform.flat[0])
    shifted=waveform-reference
    centered_mean=float(np.mean(shifted,dtype=np.float64))
    return shifted-centered_mean,reference+centered_mean


def support_envelope(mask,fade_samples):
    """Raised-cosine fades entirely INSIDE each supported interval."""
    mask=np.asarray(mask,dtype=bool)
    envelope=mask.astype(np.float32)
    if fade_samples<=0:return envelope
    changes=np.diff(np.r_[False,mask,False].astype(np.int8))
    for start,stop in zip(np.flatnonzero(changes==1),np.flatnonzero(changes==-1)):
        length=stop-start
        distance=np.minimum(np.arange(length),np.arange(length)[::-1])
        phase=np.minimum(1.,distance/float(fade_samples))
        envelope[start:stop]=(.5-.5*np.cos(np.pi*phase)).astype(np.float32)
    return envelope


def validate_trajectory(rows, heading=False):
    if not rows:raise ValueError('Empty trajectory')
    times=np.array([r['time_s'] for r in rows],float)
    if not np.isfinite(times).all() or np.any(np.diff(times)<=0):raise ValueError('Invalid trajectory clock')
    for row in rows:
        for key in ('position_m','heading') if heading else ('position_m',):
            v=np.asarray(row[key],float)
            if v.shape!=(3,) or not np.isfinite(v).all():raise ValueError('Invalid '+key)
            if key=='heading' and np.linalg.norm(v)<1e-6:raise ValueError('Zero heading')
        if 'rotation_matrix' in row:
            r=np.asarray(row['rotation_matrix'],float)
            if r.shape!=(3,3) or not np.isfinite(r).all() or not np.allclose(r.T@r,np.eye(3),atol=2e-5) or abs(np.linalg.det(r)-1)>2e-5:
                raise ValueError('Invalid calibrated rotation')
            if heading and not np.allclose(-r[:,2],np.asarray(row['heading'])/np.linalg.norm(row['heading']),atol=2e-5):
                raise ValueError('Heading disagrees with calibrated rotation')


def windowed_blocks(signal,hop):
    """Triangular partition of unity: smoothly blend adjacent IR contributions."""
    for center in range(0,len(signal)+hop,hop):
        start=max(0,center-hop);end=min(len(signal),center+hop)
        if end<=start:continue
        weights=np.maximum(0.,1-np.abs(np.arange(start,end)-center)/hop)
        yield center,start,signal[start:end]*weights


def overlap_add(output,block,ir,start):
    from scipy.signal import fftconvolve
    for channel in range(2):
        convolved=fftconvolve(block,ir[channel],mode='full')
        length=min(len(convolved),len(output)-start)
        if length>0:output[start:start+length,channel]+=convolved[:length]


def create_sim(stage,sample_rate,rays,indirect,acoustics=None,effective=None):
    # Upstream documents import order as a workaround for invalid pointer errors.
    import quaternion
    import habitat_sim
    spec=habitat_sim.AudioSensorSpec()
    if not hasattr(spec,'acousticsConfig'):
        raise RuntimeError('Habitat was built without audio. Use the isolated audio_env / --audio build; no panning fallback.')
    cfg=habitat_sim.SimulatorConfiguration();cfg.scene_id=str(stage.resolve())
    cfg.enable_physics=False;cfg.create_renderer=False
    if hasattr(cfg,'load_semantic_mesh'):cfg.load_semantic_mesh=False
    ag=habitat_sim.agent.AgentConfiguration()
    spec.uuid='audio_sensor';spec.enableMaterials=False
    spec.channelLayout.type=habitat_sim.sensor.RLRAudioPropagationChannelLayoutType.Binaural
    spec.channelLayout.channelCount=2
    spec.position=[0.,0.,0.]
    ac=spec.acousticsConfig
    ac.sampleRate=sample_rate;ac.threadCount=2;ac.indirect=indirect
    ac.indirectRayCount=rays;ac.sourceRayCount=200;ac.temporalCoherence=False
    if acoustics:
        from lib.acoustics import validate_settings
        for key,value in validate_settings(acoustics.get('settings',{})).items():
            if not hasattr(ac,key):raise RuntimeError('Installed audio ABI does not expose '+key)
            setattr(ac,key,value)
    # Temporal coherence cannot reuse history across independently evaluated sources.
    ag.sensor_specifications=[spec]
    sim=habitat_sim.Simulator(habitat_sim.Configuration(cfg,[ag]))
    sensor=sim.get_agent(0)._sensors['audio_sensor']
    if acoustics and acoustics.get('materials_json'):
        if not hasattr(sensor,'supportsNonSemanticMaterials') or not sensor.supportsNonSemanticMaterials():
            sim.close();raise RuntimeError('This audio build cannot apply material JSON to non-semantic meshes; no silent ignored material fitting')
        sensor.setAudioMaterialsJSON(str(acoustics['materials_json']))
    if effective is not None:
        effective.update({name:getattr(ac,name) for name in dir(ac) if not name.startswith('_') and isinstance(getattr(ac,name),(float,int,bool,str))})
        effective['materials_json_sha256']=sha(acoustics['materials_json']) if acoustics and acoustics.get('materials_json') else None
        effective['material_scope']='uniform default category on unchanged static mesh' if effective['materials_json_sha256'] else 'legacy generic material'
        import habitat_sim._ext.habitat_sim_bindings as bindings
        effective['native_binary_sha256']=sha(Path(bindings.__file__))
    return sim,sensor


def render(args):
    import soundfile as sf
    import quaternion
    import habitat_sim
    bundle=args.bundle.resolve();output=args.output.resolve()
    stage=bundle/'scene.stage_config.json'
    build=read(bundle/'build.json')
    for name,expected in build.get('files',{}).items():
        if sha(bundle/name)!=expected:raise ValueError('Bundle hash mismatch: '+name)
    listeners=read(args.poses);validate_trajectory(listeners,heading=True)
    data=read(args.sources)
    if isinstance(data,dict) and data.get('scene_sha256') and sha(bundle/'scene.glb')!=data['scene_sha256']:
        raise ValueError('Source trajectories were assembled for a different scene hash')
    sources=data['sources'] if isinstance(data,dict) else data
    if not sources:raise ValueError('No sources supplied')
    excluded=[s['id'] for s in sources if not s.get('renderable',True) or s.get('exclude_world_render',False)]
    sources=[s for s in sources if s['id'] not in excluded]
    if not sources:raise ValueError('No renderable world sources after wearer/validity exclusions')
    fps=read(bundle/'config.json')['fps']
    timeline_duration=listeners[-1]['time_s']+1/fps
    if args.seconds>timeline_duration+1e-6:raise ValueError('Requested duration exceeds listener timeline')
    duration=args.seconds or timeline_duration
    hop=round(args.ir_step*args.sample_rate)
    count=round(duration*args.sample_rate)
    if hop<1 or count<1:raise ValueError('Invalid duration/hop')
    output.mkdir(parents=True,exist_ok=False)
    sim=None
    try:
        prepared=[]
        conditioning=[]
        listener_support=support_mask(listeners,count,args.sample_rate,args.max_pose_gap)
        support_records=[]
        for source in sources:
            validate_trajectory(source['trajectory'])
            wav=(args.sources.parent/source['wav']).resolve()
            if source.get('wav_sha256') and sha(wav)!=source['wav_sha256']:
                raise ValueError('Source WAV hash mismatch: '+source['id'])
            x,sr=sf.read(wav,dtype='float32',always_2d=True)
            if not np.isfinite(x).all():raise ValueError('Nonfinite source audio')
            if x.shape[1]!=1:raise ValueError(f"{source['id']}: expected mono dry/proxy stem, not recorded binaural mix")
            if sr!=args.sample_rate:
                from scipy.signal import resample_poly
                divisor=math.gcd(sr,args.sample_rate)
                x=resample_poly(x,args.sample_rate//divisor,sr//divisor,axis=0)
            x,removed_dc=remove_dc(x)
            conditioning.append({'source_id':source['id'],'removed_dc':removed_dc,
                'mean_policy':'whole source waveform after resampling, before temporal masking or gain'})
            start_s=float(source.get('start_s',0));end_s=float(source.get('end_s',start_s+len(x)/args.sample_rate))
            if not math.isfinite(end_s) or not 0<=start_s<end_s:raise ValueError('Invalid source interval')
            if not math.isfinite(float(source.get('gain',1.))):raise ValueError('Invalid source gain')
            full=np.zeros(count,dtype=np.float32)
            start=round(start_s*args.sample_rate);n=min(len(x),round((end_s-start_s)*args.sample_rate),count-start)
            if n>0:full[start:start+n]=x[:n,0]*float(source.get('gain',1.))
            support=listener_support & support_mask(source['trajectory'],count,args.sample_rate,args.max_pose_gap)
            masked_nonzero=int(np.count_nonzero((abs(full)>1e-8)&~support))
            full*=support_envelope(support,round(args.mask_fade_ms*args.sample_rate/1000))
            support_records.append({'source_id':source['id'],'masked_nonzero_samples':masked_nonzero,
                'supported_samples':int(np.count_nonzero(support))})
            prepared.append((source,full,wav))
        save_all=getattr(args,'save_all_irs',False)
        budget=sum(sum(save_all or np.max(np.abs(block),initial=0)>1e-8 for _,_,block in windowed_blocks(x,hop)) for _,x,_ in prepared)
        if budget>args.max_ir_queries:raise ValueError(f'{budget} IR queries exceed limit {args.max_ir_queries}; increase explicitly or use a shorter preview')
        acoustics=read(args.acoustics) if getattr(args,'acoustics',None) else None
        if acoustics and acoustics.get('materials_json'):
            acoustics['materials_json']=str((args.acoustics.parent/acoustics['materials_json']).resolve())
        effective={};sim,sensor=create_sim(stage,args.sample_rate,args.rays,not args.direct_only,acoustics,effective)
        actor=sim.get_agent(0)
        mixed=np.zeros((count,2),dtype=np.float64);records=[];started=time.monotonic()
        (output/'irs').mkdir()
        for source,x,wav in prepared:
            for center,start,block in windowed_blocks(x,hop):
                if not save_all and np.max(np.abs(block),initial=0)<1e-8:continue
                t=min(center/args.sample_rate,max(0,duration-1/args.sample_rate))
                # Last video pose covers the remaining frame interval only.
                listener=pose_at(listeners,min(t,listeners[-1]['time_s']),max_gap=args.max_pose_gap)
                position=pose_at(source['trajectory'],t,max_gap=args.max_pose_gap)
                record={'source_id':source['id'],'time_s':t,'input_start_sample':start}
                if listener is None or position is None:
                    records.append(dict(record,status='SKIP',reason='pose gap/outside source trajectory'));continue
                state=habitat_sim.AgentState();state.position=np.array(listener['position_m'])
                state.rotation=quaternion.from_rotation_matrix(np.asarray(listener['rotation_matrix']) if 'rotation_matrix' in listener else basis(listener['heading']))
                actor.set_state(state)
                sensor.setAudioSourceTransform(np.asarray(position['position_m'],dtype=np.float32))
                ir=np.asarray(sim.get_sensor_observations()['audio_sensor'],dtype=np.float32)
                if ir.ndim!=2 or ir.shape[0]!=2 or not np.isfinite(ir).all():raise RuntimeError(f'Invalid binaural IR {ir.shape}')
                if ir.shape[1]==0:raise RuntimeError('Empty IR')
                name=f'{len(records):06d}.npz';np.savez_compressed(output/'irs'/name,ir=ir)
                overlap_add(mixed,block,ir,start)
                records.append(dict(record,status='PASS',ir_file='irs/'+name,ir_samples=ir.shape[1],
                    listener_position=listener['position_m'],source_position=position['position_m'],
                    ir_peak=float(np.max(abs(ir))),listener_reliable=listener.get('reliable',True)))
                if len(records)%20==0:print(f'IR {len(records)}/{budget}',flush=True)
        peak=float(np.max(np.abs(mixed),initial=0));gain=min(1.,.98/max(peak,1e-12))
        sf.write(output/'binaural.wav',(mixed*gain).astype(np.float32),args.sample_rate,subtype='FLOAT')
        write(output/'ir_manifest.json',records)
        write(output/'support_masks.json',support_records)
        if getattr(args,'acoustics',None):
            from lib.acoustics import rir_diagnostics
            diagnostics=[]
            for record in records:
                if record['status']=='PASS':diagnostics.append({'time_s':record['time_s'],**rir_diagnostics(np.load(output/record['ir_file'])['ir'],args.sample_rate)})
            write(output/'rir_diagnostics.json',diagnostics)
            representative=next(r for r in records if r['status']=='PASS' and abs(r['time_s']-duration/2)==min(abs(k['time_s']-duration/2) for k in records if k['status']=='PASS'))
            sf.write(output/'representative_rir.wav',np.load(output/representative['ir_file'])['ir'].T,args.sample_rate,subtype='FLOAT')
        receipt={'status':'PASS','backend':'SoundSpaces 2 / RLRAudioPropagation via Habitat audio sensor',
            'channel_layout':'Binaural HRTF, 2 channels','sample_rate':args.sample_rate,'duration_s':duration,
            'source_count':len(sources),'excluded_sources':excluded,'ir_queries':sum(r['status']=='PASS' for r in records),
            'skipped_pose_gaps':sum(r['status']=='SKIP' for r in records),'ir_step_s':args.ir_step,
            'gap_policy':'sample-level source/listener support with inward raised-cosine fades before convolution; valid reverberation tails preserved',
            'source_conditioning':conditioning,'mask_fade_ms':args.mask_fade_ms,
            'support_masks':support_records,
            'crossfade':'triangular input partition of unity + overlap-add full IR tails; no blockwise truncation',
            'elapsed_s':time.monotonic()-started,'peak_before_attenuation':peak,'global_output_gain':gain,
            'indirect_enabled':bool(effective['indirect']),'indirect_ray_count':effective['indirectRayCount'],
            'max_pose_gap_s':args.max_pose_gap,'renderer_sha256':sha(Path(__file__)),
            'material_policy':effective['material_scope'],'acoustics_effective':effective,
            'acoustic_profile_sha256':sha(args.acoustics) if getattr(args,'acoustics',None) else None,'save_all_ir_queries':save_all,
            'listener_poses_sha256':sha(args.poses),'sources_sha256':sha(args.sources),'scene_sha256':sha(bundle/'scene.glb'),
            'source_files':[{ 'id':s['id'],'sha256':sha(w),'signal_kind':s.get('signal_kind',s.get('waveform_origin','unspecified proxy'))} for s,_,w in prepared],
            'audio_sha256':sha(output/'binaural.wav'),'api_calls':0,
            'limitations':['Estimated geometry and source trajectories; not measured room acoustics.',
                'Separated recorded stems may retain original room/reverb/HRTF and are not true dry signals.',
                'Quasi-static time-varying IR approximation; finite duration trims final reverberation tail; no Doppler.',
                'Monte Carlo acoustic tracing is stochastic; saved IR files are the exact rendering evidence.',
                'Per-route safety attenuation can differ; use global_output_gain when comparing route levels.']}
        receipt['nonzero_ir_queries']=sum(r.get('ir_peak',0)>0 for r in records)
        if receipt['ir_queries']==0:raise RuntimeError('No valid IR queries were rendered')
        if receipt['nonzero_ir_queries']==0:raise RuntimeError('All rendered binaural IRs were zero')
        write(output/'receipt.json',receipt);print('PASS:',output/'binaural.wav')
    except Exception as exc:
        write(output/'failure.json',{'status':'FAIL','error_type':type(exc).__name__,'reason':str(exc)})
        raise
    finally:
        if sim is not None:sim.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('bundle','poses','sources','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--sample-rate',type=int,default=48000)
    p.add_argument('--ir-step',type=float,default=.25)
    p.add_argument('--max-pose-gap',type=float,default=.35)
    p.add_argument('--mask-fade-ms',type=float,default=10.,help='Raised-cosine fade inside valid support only')
    p.add_argument('--seconds',type=float,default=0)
    p.add_argument('--rays',type=int,default=2000)
    p.add_argument('--max-ir-queries',type=int,default=4000)
    p.add_argument('--direct-only',action='store_true')
    p.add_argument('--acoustics',type=Path,help='Explicit validated acoustic/material profile; runtime ABI and binary hashes recorded')
    p.add_argument('--save-all-irs',action='store_true',help='Query actual RIR at every4Hz center, including zero source blocks, for exact component reuse')
    args=p.parse_args()
    if not 8000<=args.sample_rate<=48000 or not .05<=args.ir_step<=2 or not 0<=args.seconds<=3600 or args.max_pose_gap<=0 or not 0<=args.mask_fade_ms<=100:
        p.error('Invalid sample rate, time step, pose gap or duration')
    render(args)


if __name__=='__main__':main()
