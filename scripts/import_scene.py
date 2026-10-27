#!/usr/bin/env python3
"""Package an already calibrated, Y-up meter-scale static GLB for Habitat."""
import argparse
import shutil
import sys
from pathlib import Path
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.store import sha, write


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mesh', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--fps', default=10., type=float)
    a = p.parse_args()
    if a.mesh.suffix.lower() != '.glb':
        p.error('Export a self-contained static GLB first; Blender projects are not mesh bundles.')
    if not np.isfinite(a.fps) or a.fps <= 0:
        p.error('fps must be finite and positive')
    scene = trimesh.load(a.mesh, force='scene', process=False)
    if not scene.geometry or any(not isinstance(g, trimesh.Trimesh) or
        len(g.faces) == 0 or not np.isfinite(g.vertices).all() for g in scene.geometry.values()):
        p.error('Scene must contain finite triangle meshes')
    bounds = scene.bounds
    if bounds is None or not np.isfinite(bounds).all():
        p.error('Invalid world bounds')
    a.output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(a.mesh, a.output / 'scene.glb')
    write(a.output / 'scene.stage_config.json', {
        'render_asset': 'scene.glb', 'collision_asset': 'scene.glb',
        'up': [0, 1, 0], 'front': [0, 0, -1], 'units_to_meters': 1.0,
    })
    write(a.output / 'config.json', {'fps': a.fps})
    write(a.output / 'build.json', {
        'status': 'PASS_PACKAGE_ONLY',
        'files': {n: sha(a.output / n) for n in
                  ('scene.glb', 'scene.stage_config.json', 'config.json')},
        'input_sha256': sha(a.mesh), 'bounds_m': bounds.tolist(),
        'assumptions': ['Input is static, meters, +Y up; no coordinate transform applied.'],
        'not_validated': ['Habitat engine loading', 'metric registration',
                          'navmesh', 'acoustic materials', 'source/listener poses'],
    })
    print('PASS_PACKAGE_ONLY:', a.output)


if __name__ == '__main__':
    main()
