#!/usr/bin/env python3
"""Select one reviewed Gemini event and prepare full-clock source for fitting."""
import argparse,sys,subprocess
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from lib.store import read,write,sha
from lib.dsp import load,save
p=argparse.ArgumentParser();p.add_argument('--caption',type=Path,required=True);p.add_argument('--event',type=int,default=0);p.add_argument('--output',type=Path,required=True);a=p.parse_args();answer=read(a.caption);row=answer['events'][a.event]
if a.output.exists():raise FileExistsError(a.output)
write(a.output,{'provider':'Gemini','answer_sha256':sha(a.caption),'event':row,'status':'SELECTED_HYPOTHESIS'})
