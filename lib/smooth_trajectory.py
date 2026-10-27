"""Whole-interval C2 cubic trajectories; observations are evidence, never audio gates."""
import numpy as np


def evaluate(curve,t):
    if curve['kind']=='piecewise_cubic_C2':
        times=np.asarray(t,dtype=float);flat=times.reshape(-1);positions=[];velocities=[]
        ends=np.array([s['interval_s'][1] for s in curve['segments']])
        for value in flat:
            segment=curve['segments'][min(len(ends)-1,np.searchsorted(ends,value,side='right'))]
            p,v=evaluate(segment,value);positions.append(p);velocities.append(v)
        return np.array(positions).reshape(times.shape+(3,)),np.array(velocities).reshape(times.shape+(3,))
    start,end=curve['interval_s'];duration=end-start
    u=np.asarray((np.asarray(t,dtype=float)-start)/duration)
    c=np.asarray(curve['control_points_m'],float)
    b=np.stack(((1-u)**3,3*u*(1-u)**2,3*u*u*(1-u),u**3),axis=-1)
    db=np.stack((-3*(1-u)**2,3*(1-u)**2-6*u*(1-u),6*u*(1-u)-3*u*u,3*u*u),axis=-1)/duration
    return b@c,db@c


def fit(path,start,end,pose_frames,max_speed=1.5,max_acceleration=1.0):
    """Fit ONE global cubic to raw proposed observations, with analytic motion bounds.

    Constant/linear motion is included in the cubic family. Curvature is penalized;
    scaling control-point deviations bounds the entire continuous curve, not just
    sampled differences. Missing locations become explicit inferred render poses.
    Never interpolate a coordinate reset or absent listener pose.
    """
    if not end>start or max_speed<=0 or max_acceleration<=0:raise ValueError('Invalid smooth interval/limits')
    if any(not f.get('listener_pose') for f in pose_frames):raise ValueError('Listener gap; cannot render a continuous hypothesis')
    if len({f['listener_pose'].get('segment',0) for f in pose_frames})!=1:raise ValueError('Coordinate reset; split source interval before fitting')
    obs=path['trajectory'];times=np.array([p['time_s'] for p in obs]);points=np.array([p.get('raw_position_m',p['position_m']) for p in obs],float)
    if len(points)<2 or not np.isfinite(points).all():raise ValueError('Insufficient finite trajectory observations')
    duration=end-start;u=(times-start)/duration
    design=np.stack(((1-u)**3,3*u*(1-u)**2,3*u*u*(1-u),u**3),axis=1)
    # Penalize changes of velocity in normalized time, equally per observation.
    curvature=np.array([[1.,-2.,1.,0.],[0.,1.,-2.,1.]])
    center=points.mean(axis=0)
    controls=np.linalg.solve(design.T@design/len(points)+.2*curvature.T@curvature+1e-6*np.eye(4),
                             design.T@points/len(points)+1e-6*np.tile(center,(4,1)))
    speed_bound=float(np.linalg.norm(3*np.diff(controls,axis=0)/duration,axis=1).max())
    accel_bound=float(np.linalg.norm(6*np.diff(controls,n=2,axis=0)/duration**2,axis=1).max())
    scale=min(1.,max_speed/max(speed_bound,1e-12),max_acceleration/max(accel_bound,1e-12))
    controls=center+scale*(controls-center)
    curve={'kind':'cubic_bezier_C2','interval_s':[start,end],'control_points_m':controls.tolist(),
           'max_speed_m_s':max_speed,'max_acceleration_m_s2':max_acceleration,'constraint_scale':scale,
           'speed_bound_m_s':speed_bound*scale,'acceleration_bound_m_s2':accel_bound*scale,
           'interpretation':'continuous render hypothesis; inferred poses do not create observed evidence'}
    prediction,_=evaluate(curve,times)
    errors=np.linalg.norm(prediction-points,axis=1)
    curve.update(observation_fit_rms_m=float(np.sqrt(np.mean(errors**2))),observation_fit_max_m=float(errors.max()))
    grid=np.unique(np.r_[start,[f['time_s'] for f in pose_frames],end])
    positions,velocities=evaluate(curve,grid);lookup={round(p['time_s'],8):p for p in obs};knots=[]
    for t,position,velocity in zip(grid,positions,velocities):
        evidence=lookup.get(round(float(t),8))
        knots.append({'time_s':float(t),'position_m':position.tolist(),'velocity_m_s':velocity.tolist(),
                      'segment':0,'reliable':True,'geometry_validated':False,'evidence_kind':'smooth_render_hypothesis',
                      'observed_support':evidence is not None,'candidate_id':None if evidence is None else evidence['candidate_id'],
                      'cluster_id':None if evidence is None else evidence['cluster_id'],
                      'member_slots':[] if evidence is None else evidence['member_slots'],
                      'raw_position_m':None if evidence is None else evidence.get('raw_position_m',evidence['position_m'])})
    result={**path,'raw_observation_trajectory':obs,'trajectory':knots,'smooth_curve':curve,
            'inferred_times_s':[p['time_s'] for p in knots if not p['observed_support']]}
    validate(result,start,end)
    return result


def fit_object_path(path,start,end,pose_frames,max_speed=1.5,max_acceleration=1.0):
    """Constrained cubic B-spline fit for supplied objects that turn during a clip.

    Derivative control polygons bound speed/acceleration everywhere; conversion to
    C2 Bezier segments keeps the renderer's existing exact Hermite interpolation.
    """
    from scipy.interpolate import BSpline
    from scipy.optimize import minimize
    obs=path['trajectory'];times=np.array([r['time_s'] for r in obs]);points=np.array([r['position_m'] for r in obs],float)
    if len(times)<2 or not end>start or not np.isfinite(points).all():raise ValueError('Invalid object observations')
    if any(not f.get('listener_pose') for f in pose_frames) or len({f['listener_pose'].get('segment',0) for f in pose_frames})!=1:raise ValueError('Listener discontinuity')
    breaks=np.linspace(start,end,max(2,int(np.ceil((end-start)/1.0))+1));knots=np.r_[np.repeat(start,3),breaks,np.repeat(end,3)];n=len(knots)-4
    basis=BSpline(knots,np.eye(n),3);design=basis(times)
    d1=basis.derivative(1).c[:n-1];d2=basis.derivative(2).c[:n-2]
    def objective(flat):
        c=flat.reshape(n,3);error=design@c-points;acc=d2@c
        return float(np.mean(error**2)+.01*np.mean(acc**2))
    def jac(flat):
        c=flat.reshape(n,3)
        return (2*design.T@(design@c-points)/points.size+.02*d2.T@(d2@c)/((n-2)*3)).ravel()
    constraints={'type':'ineq','fun':lambda z:np.r_[max_speed**2-np.sum((d1@z.reshape(n,3))**2,axis=1),max_acceleration**2-np.sum((d2@z.reshape(n,3))**2,axis=1)]}
    initial=np.tile(points.mean(axis=0),(n,1));result=minimize(objective,initial.ravel(),jac=jac,constraints=constraints,method='SLSQP',options={'ftol':1e-9,'maxiter':300})
    if not result.success or min(constraints['fun'](result.x)) < -1e-6:raise ValueError('Constrained object spline fit failed: '+result.message)
    spline=BSpline(knots,result.x.reshape(n,3),3);segments=[]
    for a,b in zip(breaks,breaks[1:]):
        pa,pb=spline([a,b]);va,vb=spline([a,b],nu=1);dt=b-a
        segments.append({'kind':'cubic_bezier_C2','interval_s':[float(a),float(b)],'control_points_m':np.array([pa,pa+va*dt/3,pb-vb*dt/3,pb]).tolist()})
    speed=max(float(np.linalg.norm(3*np.diff(np.array(s['control_points_m']),axis=0)/(s['interval_s'][1]-s['interval_s'][0]),axis=1).max()) for s in segments)
    acceleration=max(float(np.linalg.norm(6*np.diff(np.array(s['control_points_m']),n=2,axis=0)/(s['interval_s'][1]-s['interval_s'][0])**2,axis=1).max()) for s in segments)
    errors=np.linalg.norm(spline(times)-points,axis=1)
    curve={'kind':'piecewise_cubic_C2','interval_s':[start,end],'segments':segments,'max_speed_m_s':max_speed,'max_acceleration_m_s2':max_acceleration,
        'speed_bound_m_s':speed,'acceleration_bound_m_s2':acceleration,'observation_fit_rms_m':float(np.sqrt(np.mean(errors**2))),'observation_fit_max_m':float(errors.max()),
        'optimizer':'Constrained cubic B-spline least squares +0.01 acceleration regularization; derivative polygon constraints','iterations':int(result.nit)}
    grid=np.unique(np.round(np.r_[start,[f['time_s'] for f in pose_frames],breaks,end],10));positions,velocities=evaluate(curve,grid)
    rows=[{'time_s':float(t),'position_m':p.tolist(),'velocity_m_s':v.tolist(),'segment':0,'reliable':True,'observed_support':False,'evidence_kind':'smooth object render hypothesis','geometry_validated':False} for t,p,v in zip(grid,positions,velocities)]
    fitted={**path,'raw_observation_trajectory':obs,'trajectory':rows,'smooth_curve':curve};validate(fitted,start,end);return fitted


def validate(path,start,end):
    curve=path.get('smooth_curve');rows=path['trajectory']
    if not curve or curve.get('kind') not in ('cubic_bezier_C2','piecewise_cubic_C2'):raise ValueError('Smooth C2 curve required before rendering')
    if not np.allclose(curve['interval_s'],[start,end],atol=1e-8,rtol=0):raise ValueError('Curve interval mismatch')
    times=np.array([p['time_s'] for p in rows]);segments=curve.get('segments',[curve])
    for segment in segments:
        controls=np.asarray(segment['control_points_m'],float)
        if controls.shape!=(4,3) or not np.isfinite(controls).all():raise ValueError('Invalid cubic controls')
    if abs(segments[0]['interval_s'][0]-start)>1e-8 or abs(segments[-1]['interval_s'][1]-end)>1e-8:raise ValueError('Segment coverage mismatch')
    for a,b in zip(segments,segments[1:]):
        ta=a['interval_s'][1];tb=b['interval_s'][0]
        if abs(ta-tb)>1e-8 or np.min(abs(times-ta))>1e-8:raise ValueError('Missing segment boundary knot')
        pa,va=evaluate(a,ta);pb,vb=evaluate(b,tb);ca=np.array(a['control_points_m']);cb=np.array(b['control_points_m'])
        aa=6*(ca[3]-2*ca[2]+ca[1])/(ta-a['interval_s'][0])**2;ab=6*(cb[2]-2*cb[1]+cb[0])/(b['interval_s'][1]-tb)**2
        if not all(np.allclose(x,y,atol=1e-6,rtol=0) for x,y in [(pa,pb),(va,vb),(aa,ab)]):raise ValueError('Piecewise trajectory is not C2')
    if len(times)<2 or abs(times[0]-start)>1e-8 or abs(times[-1]-end)>1e-8 or np.any(np.diff(times)<=0) or np.max(np.diff(times))>.250001:
        raise ValueError('Render curve must cover the whole interval at <=250ms spacing')
    if len({p.get('segment',0) for p in rows})!=1:raise ValueError('Render curve cannot contain segment breaks')
    points,velocity=evaluate(curve,times)
    if not np.allclose(points,[p['position_m'] for p in rows],atol=1e-7,rtol=0) or not np.allclose(velocity,[p.get('velocity_m_s') for p in rows],atol=1e-7,rtol=0):
        raise ValueError('Knots/tangents differ from the certified cubic')
    speed=max(float(np.linalg.norm(3*np.diff(np.array(s['control_points_m']),axis=0)/(s['interval_s'][1]-s['interval_s'][0]),axis=1).max()) for s in segments)
    acceleration=max(float(np.linalg.norm(6*np.diff(np.array(s['control_points_m']),n=2,axis=0)/(s['interval_s'][1]-s['interval_s'][0])**2,axis=1).max()) for s in segments)
    if speed>curve['max_speed_m_s']+1e-7 or acceleration>curve['max_acceleration_m_s2']+1e-7:raise ValueError('Continuous motion limits exceeded')
    return {'status':'PASS','coverage':'whole source interval','continuity':'C2 analytic cubic, exact Hermite evaluation',
            'speed_bound_m_s':speed,'acceleration_bound_m_s2':acceleration,'internal_audio_gaps':0}
