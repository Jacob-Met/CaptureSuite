"""Self-contained synthetic benchmark preview (no external javascript/CDN)."""
from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import cv2
import trimesh


def _load_mesh(path):
    mesh=trimesh.load_mesh(path,force='mesh')
    if hasattr(mesh,'geometry'):
        mesh=trimesh.util.concatenate(tuple(mesh.geometry.values()))
    return mesh


def write_demo_viewer(folder, *, name='viewer.html'):
    import plotly.graph_objects as go
    from plotly.offline import plot
    folder=Path(folder)
    truth=_load_mesh(folder/'reference.glb')
    results=[_load_mesh(folder/f'reconstruction_{n}views.glb') for n in (1,2,4,8)]
    benchmark=json.loads((folder/'benchmark.json').read_text())
    traces=[]
    def add(mesh,label,color,opacity,visible):
        v,f=mesh.vertices,mesh.faces
        traces.append(go.Mesh3d(x=v[:,0],y=v[:,1],z=v[:,2],i=f[:,0],j=f[:,1],k=f[:,2],
                                opacity=opacity,color=color,name=label,visible=visible,
                                flatshading=False,lighting=dict(ambient=.5,diffuse=.6,specular=.1),
                                hovertemplate=f'{label}<extra></extra>'))
    add(truth,'Ground truth (procedural)','#b5c4d5',.22,True)
    for n,m in zip((1,2,4,8),results):
        add(m,f'Reconstruction from {n} view(s)','#3f88c5',.72,n==8)
    fig=go.Figure(data=traces)
    buttons=[]
    for idx,n in enumerate((1,2,4,8)):
        row=next(r for r in benchmark['rows'] if r['views']==n)
        label=f'{n} view(s) · IoU {row["synthetic_voxel_iou"]:.3f}'
        visible=[True]+[i==idx for i in range(4)]
        buttons.append(dict(label=label,method='update',args=[{'visible':visible},
                           {'title':f'Synthetic geometric reconstruction · {label}'}]))
    fig.update_layout(title='Synthetic geometric reconstruction · 8 views',
        scene=dict(xaxis_title='Lateral (m)',yaxis_title='Front/back (m)',zaxis_title='Vertical (m)',
                   aspectmode='data',camera=dict(eye=dict(x=1.8,y=-2.2,z=1.25))),
        margin=dict(l=10,r=10,t=95,b=30),height=800,
        updatemenus=[dict(type='dropdown',direction='down',x=.015,y=1.08,
                          buttons=buttons,showactive=True)],
        annotations=[dict(x=.5,y=-.05,xref='paper',yref='paper',showarrow=False,
            text='Synthetic procedurally generated body; known camera poses and metric scale. Not verified RGB-to-human accuracy.')])
    plot(fig,filename=str(folder/name),include_plotlyjs=True,auto_open=False)
    return folder/name


def write_contact_sheet(folder,name='comparison.png'):
    import matplotlib.pyplot as plt
    from .cameras import Camera
    from .synthetic import render_silhouette
    folder=Path(folder)
    truth=_load_mesh(folder/'reference.glb')
    predicted=_load_mesh(folder/'reconstruction_8views.glb')
    poses=[(0,-3),(-3,0),(0,3),(3,0)]
    fig,axs=plt.subplots(2,4,figsize=(11,6),constrained_layout=True)
    for j,(xx,yy) in enumerate(poses):
        cam=Camera.look_at((xx,yy,.96),[0,0,.96],width=220,height=320,focal=135.)
        for k,mesh in enumerate([truth,predicted]):
            mask=render_silhouette(mesh,cam)
            axs[k,j].imshow(mask,cmap='gray_r',vmin=0,vmax=1)
            axs[k,j].axis('off')
            if k==0:axs[k,j].set_title(['Front','Side A','Back','Side B'][j])
    fig.text(.016,.73,'Original\ngeometry',ha='center',va='center',rotation=90,fontsize=9)
    fig.text(.016,.27,'8-view\nreconstruction',ha='center',va='center',rotation=90,fontsize=9)
    fig.suptitle('Synthetic 3D reconstruction: reprojection comparisons',fontsize=14)
    fig.savefig(folder/name,dpi=165,bbox_inches='tight')
    plt.close(fig)
    return folder/name
