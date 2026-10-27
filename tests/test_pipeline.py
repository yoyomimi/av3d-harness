import unittest,tempfile
from pathlib import Path
import numpy as np
from lib.pipeline import metrics,propose,convolve
from lib.store import write
class PipelineTests(unittest.TestCase):
 def setUp(self):
  t=np.arange(24000)/48000;self.x=np.column_stack([np.sin(2*np.pi*437*t)*.1,np.sin(2*np.pi*437*t)*.05])
 def test_reference_identity(self):
  m=metrics(self.x,self.x);self.assertAlmostEqual(m['channel_energy_mae_db'],0);self.assertAlmostEqual(m['ild_mae_db'],0)
 def test_gain_and_ear_swap(self):
  m=metrics(self.x,self.x*2);self.assertAlmostEqual(m['level_delta_db'],6.0206,places=3);self.assertAlmostEqual(m['ild_mae_db'],0)
  self.assertGreater(metrics(self.x,self.x[:,::-1])['ild_mae_db'],10)
 def test_silence_shape_nonfinite_rejected(self):
  for x in [self.x*0,self.x[:-1],self.x*np.nan]:
   with self.assertRaises(ValueError):metrics(self.x,x)
 def test_semantics_preserve_all_compatible_assets(self):
  assets={'assets':[{'id':k,'number':i,'kind':kind,'sound_categories':tags,'trajectory':[{'time_s':0,'position_m':[0,1,0]},{'time_s':1,'position_m':[0,1,0]}]} for i,(k,kind,tags) in enumerate([('a','person',['speech']),('b','person',['speech']),('c','table',['impact'])])]}
  p=propose({'event':{'category':'speech'}},assets,{'parameter_pool':{},'budget':{'max_candidates':3}});self.assertEqual([c['id'] for c in p['candidates']],['a','b'])
 def test_real_ir_partition_and_invalid_ir(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);x=np.arange(24000,dtype=float)/24000;ir=np.array([[1.],[.5]])
   np.savez(p/'ir.npz',ir=ir);write(p/'receipt.json',{'skipped_pose_gaps':0,'support_masks':[]});write(p/'ir_manifest.json',[{'status':'PASS','input_start_sample':start,'ir_file':'ir.npz'} for start in [0,0,12000]])
   y,_=convolve(x,p);np.testing.assert_allclose(y[:,0],(x-x.mean()).astype(np.float32),atol=1e-7);np.testing.assert_allclose(y[:,1],y[:,0]*.5,atol=1e-7)
   np.savez(p/'ir.npz',ir=ir*0)
   with self.assertRaises(ValueError):convolve(x,p)
if __name__=='__main__':unittest.main()
