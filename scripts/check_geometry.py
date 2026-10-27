#!/usr/bin/env python3
"""Continuous surface-clearance bound for source Hermite paths and linear listener."""
import argparse,sys
from pathlib import Path
import numpy as np,trimesh
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from lib.store import read,write,sha
from lib.mesh_clearance import SurfaceIndex
from soundspaces_render import pose_at,validate_trajectory
p=argparse.ArgumentParser();p.add_argument('--pool',type=Path,required=True);p.add_argument('--poses',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True);a=p.parse_args();dest=a.bundle/'clearance.json'
if dest.exists():raise FileExistsError('Use fresh bundle; retain previous proof')
surface=SurfaceIndex(trimesh.load(a.bundle/'scene.glb',force='mesh',process=False));pool=read(a.pool);listener=read(a.poses);paths=[('listener',listener)]+[(c['id'],c['trajectory']) for c in pool['candidates']];checks=[]
for name,rows in paths:
 validate_trajectory(rows,heading=name=='listener');speed=0.
 for left,right in zip(rows,rows[1:]):
  dt=right['time_s']-left['time_s'];v=(np.array(right['position_m'])-left['position_m'])/dt
  controls=[v]
  if 'velocity_m_s' in left and 'velocity_m_s' in right:controls=[np.array(left['velocity_m_s']),3*v-np.array(left['velocity_m_s'])-right['velocity_m_s'],np.array(right['velocity_m_s'])]
  speed=max(speed,max(float(np.linalg.norm(v)) for v in controls))
 t=np.linspace(rows[0]['time_s'],rows[-1]['time_s'],int((rows[-1]['time_s']-rows[0]['time_s'])*50)+2);poses=[pose_at(rows,x) for x in t]
 if any(x is None for x in poses):raise ValueError('Trajectory gap')
 check=surface.audit(np.array([x['position_m'] for x in poses]),t,speed);checks.append({'id':name,'speed_bound_m_s':speed,**check})
write(dest,{'status':'PASS' if all(x['status']=='PASS' for x in checks) else 'FAIL','pool_sha256':sha(a.pool),'poses_sha256':sha(a.poses),'scene_sha256':sha(a.bundle/'scene.glb'),'checks':checks,'scope':'Triangle surface distance only, not solid occupancy/full-body navigation or physical registration.'});print(read(dest)['status'])
