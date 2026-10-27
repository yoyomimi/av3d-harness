#!/usr/bin/env python3
"""Render supplied Habitat target geometry/poses to RGB and metric depth, in a new run."""
import argparse,json,math,subprocess,sys,time
from pathlib import Path
import numpy as np
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE))
from lib.store import read,write,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset',type=Path,required=True);p.add_argument('--clip',required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--limit',type=int,default=0);p.add_argument('--camera-override',type=Path);p.add_argument('--silent-only',action='store_true');p.add_argument('--hfov',type=float);a=p.parse_args()
    import habitat_sim,magnum as mn,trimesh
    from scipy.spatial.transform import Rotation
    from habitat_sim.utils.common import quat_from_coeffs
    from PIL import Image
    root=a.dataset.resolve();folder=root/'clips'/a.clip;c=read(folder/'replay_config.json');clip=read(folder/'clip.json')
    camera_path=a.camera_override or folder/c['camera'];poses=np.load(camera_path)['T_habitat_camera'];count=min(len(poses),a.limit) if a.limit else len(poses)
    if len(c['objects'])!=len(poses) or len(poses)!=clip['frames']:raise ValueError('Object/camera clock mismatch')
    if a.hfov is not None:
        if not 30<=a.hfov<=140:raise ValueError('Unsupported editorial field of view')
        c['hfov_deg']=a.hfov
    out=a.output;out.mkdir(parents=True,exist_ok=False)
    for name in ('depth','rgb','config'):(out/name).mkdir()
    W,H,fps=c['width'],c['height'],c['fps'];focal=W/(2*math.tan(math.radians(c['hfov_deg'])/2))
    K=np.array([[focal,0,(W-1)/2],[0,focal,(H-1)/2],[0,0,1]])
    stage=out/'config/environment.stage_config.json';write(stage,dict(render_asset=str(root/c['environment']),collision_asset=str(root/c['environment']),up=[0,1,0],front=[0,0,-1],is_collidable=False,shader_type='pbr'))
    pbr=out/'config/replay.pbr_config.json';write(pbr,dict(enable_ibl=True,enable_direct_lights=True,map_mat_txtr_to_linear=True,map_output_to_srgb=True,use_direct_tonemap=True,use_ibl_tonemap=True))
    scene=out/'config/replay.scene_instance.json';write(scene,dict(stage_instance=dict(template_name=str(stage.resolve()),shader_type='pbr'),default_pbr_shader_config=str(pbr.resolve())))
    backend=habitat_sim.SimulatorConfiguration();backend.scene_id=str(scene.resolve());backend.enable_physics=False;backend.enable_hbao=True;backend.requires_textures=True;backend.gpu_device_id=0;backend.override_scene_light_defaults=True;backend.scene_light_setup=habitat_sim.gfx.DEFAULT_LIGHTING_KEY
    specs=[]
    for name,kind in [('rgb',habitat_sim.SensorType.COLOR),('depth',habitat_sim.SensorType.DEPTH)]:
        spec=habitat_sim.CameraSensorSpec();spec.uuid=name;spec.sensor_type=kind;spec.sensor_subtype=habitat_sim.SensorSubType.PINHOLE;spec.resolution=[H,W];spec.position=mn.Vector3(0);spec.hfov=c['hfov_deg'];spec.near=.01;spec.far=1000.;specs.append(spec)
    ac=habitat_sim.agent.AgentConfiguration();ac.sensor_specifications=specs
    sim=None;encoders={};start=time.monotonic();frames=[];actual=[];bounds={}
    receipt={'status':'RUNNING','clip':a.clip,'habitat_version':habitat_sim.__version__,'provided_renderer_version':'0.3.1',
        'physics':'Disabled: supplied transforms are assigned directly, no dynamics simulation',
        'replay_config_sha256':sha(folder/'replay_config.json'),'camera_sha256':sha(camera_path), 'camera_override':str(a.camera_override) if a.camera_override else None,
        'scene_sha256':sha(root/c['environment']),'script_sha256':sha(__file__),'command':sys.argv,'partial':bool(a.limit)}
    write(out/'receipt.json',receipt)
    try:
        sim=habitat_sim.Simulator(habitat_sim.Configuration(backend,[ac]));agent=sim.initialize_agent(0)
        tm=sim.get_object_template_manager();om=sim.get_rigid_object_manager();templates={};active={}
        for kind in ('rgb','depth'):
            cmd=['ffmpeg','-nostdin','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(fps),'-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-threads','2',str(out/(kind+'_silent.mp4'))]
            encoders[kind]=subprocess.Popen(cmd,stdin=subprocess.PIPE)
        for i in range(count):
            desired={key:v for key,v in c['objects'][i].items() if v['visible']}
            for key in list(active):
                if key not in desired:om.remove_object_by_id(active.pop(key).object_id)
            objects=[]
            for key,obj in desired.items():
                asset=obj['asset']
                if asset not in templates:
                    attr=habitat_sim.attributes.ObjectAttributes(asset);attr.render_asset_handle=str(root/asset);attr.collision_asset_handle=str(root/asset);attr.compute_COM_from_shape=False;attr.com=mn.Vector3(0);attr.is_collidable=False;attr.shader_type='pbr';attr.orient_up=mn.Vector3(0,1,0);attr.orient_front=mn.Vector3(0,0,-1);templates[asset]=tm.register_template(attr)
                    bounds[asset]=np.asarray(trimesh.load(root/asset,force='scene').bounds).tolist()
                if key not in active:
                    instance=om.add_object_by_template_id(templates[asset]);instance.motion_type=habitat_sim.physics.MotionType.KINEMATIC;instance.collidable=False;active[key]=instance
                matrix=np.asarray(obj['matrix'],float);active[key].transformation=mn.Matrix4(matrix)
                lo,hi=np.asarray(bounds[asset]);center=(lo+hi)/2;head=center.copy();head[1]=lo[1]+.88*(hi[1]-lo[1]);anchor=(matrix@np.r_[head,1])[:3]
                objects.append({'id':key,'asset':asset,'matrix':matrix.tolist(),'local_bounds':bounds[asset],
                    'head_proxy_world_m':anchor.tolist(),'anchor_policy':'88% local mesh height; mouth/head proxy, not a measured joint'})
            state=habitat_sim.AgentState();state.position=poses[i,:3,3];state.rotation=quat_from_coeffs(Rotation.from_matrix(poses[i,:3,:3]).as_quat());agent.set_state(state,reset_sensors=True)
            cameras={name:np.asarray(sim._sensors[name]._sensor_object.node.absolute_transformation()) for name in ('rgb','depth')}
            if any(not np.allclose(m,poses[i],atol=2e-5) for m in cameras.values()):raise ValueError('Actual sensor camera differs from supplied replay pose')
            actual.append(cameras['rgb']);obs=sim.get_sensor_observations();rgb=np.asarray(obs['rgb'])[...,:3].copy();depth=np.asarray(obs['depth'],np.float32)
            if depth.shape!=(H,W) or not np.isfinite(depth).all():raise ValueError('Invalid depth sensor output')
            valid=(depth>.01)&(depth<999.);v=np.clip(np.log1p(depth)/math.log(11),0,1)
            colour=np.stack((255*(1-v),180*(1-abs(2*v-1)),255*v),axis=-1).astype(np.uint8);colour[~valid]=0
            np.savez_compressed(out/'depth'/f'{i:04d}.npz',depth_m=depth,intrinsics=K,camera_to_world=cameras['depth'])
            Image.fromarray(rgb).save(out/'rgb'/f'{i:04d}.jpg',quality=90)
            encoders['rgb'].stdin.write(rgb.tobytes());encoders['depth'].stdin.write(colour.tobytes())
            frames.append({'index':i,'time_s':i/fps,'depth':f'depth/{i:04d}.npz','rgb':f'rgb/{i:04d}.jpg',
                'valid_depth_fraction':float(valid.mean()),'rgb_std':float(rgb.std()),'objects':objects})
            if i%25==0:print(a.clip,'frame',i,'of',count,flush=True)
        for process in encoders.values():process.stdin.close()
        for process in encoders.values():
            if process.wait()!=0:raise RuntimeError('Video encoder failed')
        encoders={}
        for kind in (() if a.silent_only else ('rgb','depth')):
            subprocess.run(['ffmpeg','-nostdin','-v','error','-n','-i',str(out/(kind+'_silent.mp4')),'-i',str(folder/'binaural.wav'),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-t',str(count/fps),'-movflags','+faststart',str(out/(kind+'_replay.mp4'))],check=True)
        np.savez_compressed(out/'rendered_camera.npz',T_habitat_camera=np.array(actual))
        write(out/'frames.json',{'frames':frames,'intrinsics':K.tolist(),'depth_convention':'positive optical-axis metres; camera -Z forward, +Y up',
            'rgb_registration':'Supplied reconstructed scene/camera; original RGB matching remains approximate',
            'camera_source':str(camera_path),'objects_status':'Supplied provisional rigid avatars; no new identity/pose certification'})
        receipt.update(status='PASS',frames=count,duration_s=count/fps,width=W,height=H,hfov_deg=c['hfov_deg'],
            camera_matrix_max_error=float(np.max(abs(np.array(actual)-poses[:count]))),
            min_valid_depth_fraction=min(f['valid_depth_fraction'] for f in frames),
            min_rgb_std=min(f['rgb_std'] for f in frames),elapsed_s=time.monotonic()-start,
            audio='NONE: silent render for separate acoustic synthesis' if a.silent_only else 'Recorded original binaural audio, not RIR reconstruction',geometry='Supplied static mesh + exact provided per-frame avatar matrices; no inferred actors',
            frames_sha256=sha(out/'frames.json'),rgb_video_sha256=sha(out/('rgb_silent.mp4' if a.silent_only else 'rgb_replay.mp4')),depth_video_sha256=sha(out/('depth_silent.mp4' if a.silent_only else 'depth_replay.mp4')))
    except Exception as error:
        receipt.update(status='FAIL',error_type=type(error).__name__,reason=str(error));raise
    finally:
        for process in encoders.values():
            if process.stdin and not process.stdin.closed:process.stdin.close()
            process.wait()
        if sim is not None:sim.close()
        write(out/'receipt.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('command',)},indent=2))


if __name__=='__main__':main()
