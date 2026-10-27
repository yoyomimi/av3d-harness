"""Conservative surface clearance of continuous paths against supplied triangles.

No watertight-room or solid-occupancy claim follows for reconstructed open meshes.
Radius buckets keep the exact point/triangle narrow phase bounded without rtree.
"""
import numpy as np

class SurfaceIndex:
    def __init__(self, mesh):
        from scipy.spatial import cKDTree
        triangles=np.asarray(mesh.triangles)
        keep=np.linalg.norm(np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0]),axis=1)>1e-12
        self.triangles=triangles[keep];self.degenerate_faces=int((~keep).sum())
        centers=self.triangles.mean(axis=1);radii=np.linalg.norm(self.triangles-centers[:,None,:],axis=2).max(axis=1)
        self.buckets=[]
        edges=[0,.05,.1,.25,.5,1,2,5,10,np.inf]
        for low,high in zip(edges,edges[1:]):
            ids=np.flatnonzero((radii>low)&(radii<=high))
            if len(ids):self.buckets.append((cKDTree(centers[ids]),ids,float(radii[ids].max())))

    def distances_capped(self, points, cap):
        from trimesh.triangles import closest_point
        result=np.full(len(points),cap,dtype=float)
        for tree,ids,radius in self.buckets:
            neighbours=tree.query_ball_point(points,cap+radius)
            for i,local in enumerate(neighbours):
                if not local:continue
                tri=self.triangles[ids[local]];q=np.broadcast_to(points[i],(len(tri),3))
                closest=closest_point(tri,q);distance=np.linalg.norm(closest-q,axis=1)
                if not np.isfinite(distance).all():raise ValueError('Nonfinite point/triangle clearance')
                result[i]=min(result[i],float(distance.min()))
        return result

    def audit(self, points, times, speed_bound, margin=.08):
        times=np.asarray(times,float);points=np.asarray(points,float)
        if len(times)<2 or np.any(np.diff(times)<=0):raise ValueError('Invalid clearance sampling')
        # Every continuous point is within v_max*dt/2 of one sampled endpoint.
        travel=float(speed_bound*np.max(np.diff(times))/2)
        distances=self.distances_capped(points,margin+travel+.02)
        lower=float(distances.min()-travel)
        return {'status':'PASS' if lower>=margin else 'FAIL','surface_clearance_lower_bound_m':lower,
            'required_margin_m':margin,'sample_min_distance_capped_m':float(distances.min()),
            'between_sample_travel_bound_m':travel,'speed_bound_m_s':float(speed_bound),'samples':len(times),
            'scope':'Continuous path versus static mesh SURFACES; open mesh solid occupancy and real-world registration unverified',
            'degenerate_faces_excluded':self.degenerate_faces}
