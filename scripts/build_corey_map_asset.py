#!/usr/bin/env python3
"""Lightweight, texture-free display mesh; never used for acoustic simulation."""
import argparse,json,hashlib,time
from pathlib import Path
import numpy as np,trimesh
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
s=trimesh.load(a.input,force='scene',process=False);out=trimesh.Scene();rows=[]
for i,node in enumerate(s.graph.nodes_geometry):
 transform,name=s.graph[node];mesh=s.geometry[name];original=len(mesh.faces);welded=mesh.copy();welded.merge_vertices(merge_tex=True,merge_norm=True);new=welded.simplify_quadric_decimation(face_count=max(100,min(original,round(original*.035))),aggression=7) if original>300 else welded
 material=getattr(mesh.visual,'material',None);color=getattr(material,'baseColorFactor',None)
 if color is None:color=np.array([194,189,176,255])
 texture=getattr(material,'baseColorTexture',None)
 if texture is not None:
  pixels=np.asarray(texture.convert('RGB').resize((32,32)),float);color=np.r_[pixels.mean(axis=(0,1)),255].astype(np.uint8)
 color=np.asarray(color).copy();color[3]=255;new.visual=trimesh.visual.ColorVisuals(mesh=new,face_colors=color);out.add_geometry(new,node_name=node,geom_name=node,transform=transform);rows.append({'node':node,'original_faces':original,'display_faces':len(new.faces)})
print('export',len(rows),sum(r['display_faces'] for r in rows),flush=True);out.export(a.output/'room.glb')
(a.output/'receipt.json').write_text(json.dumps({'status':'PASS','source_sha256':hashlib.sha256(a.input.read_bytes()).hexdigest(),'display_sha256':hashlib.sha256((a.output/'room.glb').read_bytes()).hexdigest(),'scope':'Display-only decimation and removal of textures. Original world transforms retained. Actual acoustic geometry remains unchanged.','original_faces':sum(r['original_faces'] for r in rows),'display_faces':sum(r['display_faces'] for r in rows),'bounds':out.bounds.tolist(),'objects':rows},indent=2));print(a.output/'room.glb')
