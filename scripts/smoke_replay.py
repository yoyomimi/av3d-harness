#!/usr/bin/env python3
"""Execute the standalone CPU path in a fresh run using an explicit input pack."""
import argparse,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from lib.store import write,sha
p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--run',type=Path,required=True);a=p.parse_args();commands=[]
def execute(argv):
 cmd=[sys.executable,str(ROOT/'scripts'/argv[0]),*map(str,argv[1:])];subprocess.run(cmd,check=True);commands.append(cmd)
execute(['harness.py','init','--inputs',a.inputs,'--run',a.run])
for stage in ['propose','fit','label']:execute(['harness.py',stage,'--run',a.run])
execute(['validate_ir_geometry.py','--pool',a.run/'candidates/pool.json','--renders',a.inputs/'renders.json','--output',a.run/'ir-geometry.json'])
execute(['export_routes.py','--inputs',a.inputs,'--fit',a.run/'fit','--output',a.run/'final-routes','--playback-gain','32'])
write(a.run/'smoke.json',{'status':'PASS','commands':commands,'scope':'Fresh execution using supplied actual saved IR/RGB input pack; no new engine/API calls','outputs':{f'route-{k}.mp4':sha(a.run/f'final-routes/route-{k}.mp4') for k in 'ABC'}})
