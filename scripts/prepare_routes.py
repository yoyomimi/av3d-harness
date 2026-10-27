#!/usr/bin/env python3
"""Build smooth, explicitly configured counterfactual listening paths and cameras."""
import argparse,sys
from pathlib import Path
import numpy as np,trimesh
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from lib.store import read,write,sha
from lib.mesh_clearance import SurfaceIndex
from soundspaces_render import basis
p=argparse.ArgumentParser();p.add_argument('--scene',type=Path,required=True);p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();cfg=read(a.config);a.output.mkdir(parents=True,exist_ok=False);surface=SurfaceIndex(trimesh.load(a.scene,force='mesh',process=False));records=[]
for r in cfg['routes']:
 start,end=np.array(r['start_m']),np.array(r['end_m']);lo,hi=cfg['movement_interval_s'];speed=float(np.linalg.norm(end-start)*1.875/(hi-lo));target=np.array(cfg['look_at_m'])
 def points(t):
  u=np.clip((np.asarray(t)-lo)/(hi-lo),0,1);f=6*u**5-15*u**4+10*u**3;return start+f[...,None]*(end-start)
 dense=np.linspace(0,cfg['duration_s'],round(cfg['duration_s']*50)+1);audit=surface.audit(points(dense),dense,speed)
 if speed>cfg['max_speed_m_s'] or audit['status']!='PASS':write(a.output/'failed-route.json',{'route':r,'audit':audit,'speed':speed});raise ValueError('Route fails bound; revise configuration in a fresh run')
 folder=a.output/r['id'];folder.mkdir();times=np.unique(np.r_[np.arange(0,cfg['duration_s'],.1),cfg['duration_s']]);pos=points(times);rows=[{'time_s':float(t),'position_m':v.tolist(),'heading':((target-v)/np.linalg.norm(target-v)).tolist(),'segment':0,'reliable':True} for t,v in zip(times,pos)];write(folder/'listener.json',rows)
 cameras=[]
 for t in np.arange(round(cfg['duration_s']*10))/10:
  v=points(t);m=np.eye(4);m[:3,:3]=basis(target-v);m[:3,3]=v;cameras.append(m)
 np.savez(folder/'camera.npz',T_habitat_camera=np.array(cameras));records.append({'route':r,'audit':audit,'speed_bound_m_s':speed})
write(a.output/'receipt.json',{'status':'PASS','scene_sha256':sha(a.scene),'config_sha256':sha(a.config),'routes':records,'scope':'Surface clearance, not full-body navigation. Look-at camera, uncalibrated ear extrinsics.'})
