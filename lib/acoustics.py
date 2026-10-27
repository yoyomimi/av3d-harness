"""Explicit acoustic hypotheses and measured RIR diagnostics, never a target RT60 knob."""
import math
import numpy as np

BOOL_FIELDS={'direct','indirect','diffraction','transmission','meshSimplification','temporalCoherence'}
INT_FIELDS={'frequencyBands','indirectRayCount','indirectRayDepth','indirectSHOrder','directSHOrder','directRayCount','sourceRayCount','sourceRayDepth','maxDiffractionOrder','threadCount'}
FLOAT_FIELDS={'maxIRLength','globalVolume','unitScale'}


def validate_settings(settings):
    if not isinstance(settings,dict):raise ValueError('Expected explicit acoustic settings object')
    unknown=set(settings)-BOOL_FIELDS-INT_FIELDS-FLOAT_FIELDS
    if unknown:raise ValueError('Unsupported acoustic setting: '+str(sorted(unknown)))
    for key,value in settings.items():
        if key in BOOL_FIELDS:
            if not isinstance(value,bool):raise ValueError(key+' must be boolean')
        elif key in INT_FIELDS:
            if isinstance(value,bool) or not isinstance(value,int) or value<0:raise ValueError(key+' must be a nonnegative integer')
        elif isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or value<=0:raise ValueError(key+' must be finite and positive')
    if settings.get('unitScale',1)!=1:raise ValueError('Calibrated supplied geometry uses metres; unitScale must remain1')
    if settings.get('maxIRLength',4)>8:raise ValueError('Explicit IR window budget is at most8s')
    if settings.get('temporalCoherence',False):raise ValueError('Independent candidate/source queries cannot reuse temporal acoustic state')
    return dict(settings)


def material_database(absorption,scattering=.5):
    if not 0<=absorption<=1 or not 0<=scattering<=1:raise ValueError('Material coefficients must be in0..1')
    return {'materials':[{'name':'Uniform static-mesh hypothesis','labels':['default'],
        'absorption':[20.,float(absorption),20000.,float(absorption)],
        'scattering':[20.,float(scattering),20000.,float(scattering)],'transmission':[20.,0.,20000.,0.],
        'damping':[20.,0.,20000.,0.],'density':1.225,'speed':343.}]}


def rir_diagnostics(ir,sample_rate):
    ir=np.asarray(ir,dtype=float)
    if ir.ndim!=2 or ir.shape[0]!=2 or not np.isfinite(ir).all() or not ir.shape[1]:raise ValueError('Finite stereo RIR required')
    power=np.sum(ir*ir,axis=0);total=float(power.sum())
    if total<=1e-30:return {'status':'ZERO_IR','rt60_t20_s':None}
    onset=int(np.flatnonzero(power>power.max()*1e-4)[0]);edc=np.cumsum(power[::-1])[::-1]
    db=10*np.log10(np.maximum(edc/total,1e-30));t=np.arange(len(power))/sample_rate
    def fit(lo,hi):
        ids=np.flatnonzero((db<=lo)&(db>=hi)&(np.arange(len(power))>=onset))
        if len(ids)<8 or t[ids[-1]]-t[ids[0]]<.02:return None
        slope,intercept=np.polyfit(t[ids],db[ids],1);prediction=slope*t[ids]+intercept
        r2=1-float(np.sum((db[ids]-prediction)**2)/max(np.sum((db[ids]-db[ids].mean())**2),1e-30))
        return {'rt60_s':float(-60/slope) if slope<0 else None,'r2':r2,'fit_interval_s':[float(t[ids[0]]),float(t[ids[-1]])],'edc_db_range':[lo,hi]}
    t20=fit(-5,-25);edt=fit(0,-10);direct_end=min(len(power),onset+round(.0025*sample_rate));direct=float(power[onset:direct_end].sum())
    def early_late(seconds):
        stop=min(len(power),onset+round(seconds*sample_rate));early=float(power[onset:stop].sum());late=float(power[stop:].sum())
        return float(10*np.log10(max(early,1e-30)/max(late,1e-30)))
    ids=np.unique(np.linspace(0,len(power)-1,200).astype(int))
    return {'status':'PASS','energy':total,'peak':float(abs(ir).max()),'arrival_s':onset/sample_rate,'ir_window_s':len(power)/sample_rate,
        'rt60_t20_s':t20['rt60_s'] if t20 and t20['r2']>=.8 else None,'t20_fit':t20,'edt_fit':edt,
        'drr_proxy_db_2p5ms':float(10*np.log10(max(direct,1e-30)/max(total-direct,1e-30))),
        'c50_db':early_late(.05),'c80_db':early_late(.08),
        'last_100ms_energy_fraction':float(power[-min(len(power),round(.1*sample_rate)):].sum()/total),
        'edc':{'time_s':t[ids].tolist(),'db':db[ids].tolist()},
        'policy':'Schroeder broadband T20 extrapolation when fit spans>=20ms/R2>=.8; IR window is not RT60. Direct-window metric is a proxy, not independently isolated direct sound.'}
