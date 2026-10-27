"""Same-clock binaural diagnostics; residual is unexplained signal, not ambient truth."""
import subprocess,json
import numpy as np

def load(path,start=0.,duration=None):
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(path)]))
    audio=next(s for s in info['streams'] if s['codec_type']=='audio')
    if int(audio['channels'])!=2:raise ValueError('Expected original/reconstructed binaural stereo, not upmixed mono')
    cmd=['ffmpeg','-v','error','-nostdin','-ss',str(start),'-i',str(path)]
    if duration is not None:cmd+=['-t',str(duration)]
    cmd+=['-map','0:a:0','-ar','48000','-f','f32le','-']
    x=np.frombuffer(subprocess.check_output(cmd),'<f4').reshape(-1,2).astype(np.float64)
    if len(x)<2048 or not np.isfinite(x).all():raise ValueError('Audio too short or nonfinite')
    return x

def save(path,x):
    subprocess.run(['ffmpeg','-v','error','-nostdin','-n','-f','f32le','-ar','48000','-ac','2','-i','pipe:0','-c:a','pcm_f32le',str(path)],input=np.asarray(x,dtype='<f4').tobytes(),check=True)

def spatial(x):
    power=np.mean(x*x,axis=0)
    if power.min()<1e-12:return {'ild_db':None,'itd_ms':None,'valid':False}
    # Positive lag convention is explicitly diagnostic, not a world azimuth.
    n=1<<(2*len(x)-1).bit_length();spec=np.fft.rfft(x[:,0],n)*np.conj(np.fft.rfft(x[:,1],n))
    corr=np.fft.irfft(spec/np.maximum(abs(spec),1e-15),n)
    lag=48;local=np.r_[corr[-lag:],corr[:lag+1]];offset=int(np.argmax(abs(local)))-lag
    return {'ild_db':float(10*np.log10(power[0]/power[1])),'itd_ms':offset/48.,'valid':True}

def compare(x,y):
    if x.shape!=y.shape:raise ValueError('Comparison requires exact same shape/clock; no silent time stretch or truncation')
    nfft=2048;hop=512;window=np.hanning(nfft)
    def spectrum(v):return abs(np.fft.rfft(np.lib.stride_tricks.sliding_window_view(v,nfft,axis=0)[::hop]*window,axis=-1))
    a,b=spectrum(x),spectrum(y);floor=max(float(a.max())*1e-4,1e-10)
    log_mae=float(np.mean(abs(20*np.log10(np.maximum(a,floor))-20*np.log10(np.maximum(b,floor)))))
    reference=float(np.mean(x*x));residual=x-y
    windows=[]
    for start in range(0,len(x)-12000+1,12000):
        sx,sy=spatial(x[start:start+12000]),spatial(y[start:start+12000]);windows.append({'time_s':start/48000,'original':sx,'reconstruction':sy})
    valid=[w for w in windows if w['original']['valid'] and w['reconstruction']['valid']]
    result={'status':'PASS measured','sample_rate':48000,'samples':len(x),'duration_s':len(x)/48000,
      'log_spectral_mae_db':log_mae,'residual_energy_ratio':float(np.mean(residual**2)/max(reference,1e-20)),
      'level_delta_db':float(10*np.log10(max(float(np.mean(y*y)),1e-20)/max(reference,1e-20))),
      'ild_mae_db':float(np.mean([abs(w['original']['ild_db']-w['reconstruction']['ild_db']) for w in valid])) if valid else None,
      'itd_mae_ms':float(np.mean([abs(w['original']['itd_ms']-w['reconstruction']['itd_ms']) for w in valid])) if valid else None,
      'spatial_windows':windows,'semantic_match':'NOT RUN','noise_only_residual':'UNVERIFIED',
      'interpretation':'No level fitting, phase alignment or time stretch. RIR phase differences can dominate subtraction; residual is not a verified new source. Spatial metrics characterize mixtures, not source geometry.'}
    return result,residual

def stopping(history,max_rounds,min_improvement):
    if not history:return {'stop':False,'reason':'No evaluated round'}
    if len(history)>=max_rounds:return {'stop':True,'converged':False,'reason':'Round budget exhausted'}
    if len(history)<2:return {'stop':False,'reason':'Need another controlled comparison'}
    old,new=history[-2]['log_spectral_mae_db'],history[-1]['log_spectral_mae_db']
    gain=(old-new)/max(old,1e-9)
    if gain<min_improvement:return {'stop':True,'converged':False,'reason':'No sufficient spectral improvement; semantic/spatial acceptance still required','relative_improvement':gain}
    return {'stop':False,'reason':'Improved spectral metric; semantic/spatial review still required','relative_improvement':gain}
