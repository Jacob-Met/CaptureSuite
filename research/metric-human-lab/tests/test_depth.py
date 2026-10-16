import numpy as np
import pytest
from metric_human.depth import align_relative_depth


def test_relative_depth_calibration_recovers_metric_depth():
    relative=np.array([[1.,2.,3.,4.],[2.,3.,4.,5.],[3.,4.,5.,6.]],dtype=float)
    anchors=[{'u':i,'v':0,'camera_z_m':float(2.5+.3*relative[0,i])} for i in (0,1,2,3)]
    data,cal=align_relative_depth(relative,anchors,max_rmse_m=.00001)
    assert np.allclose(data,2.5+.3*relative)
    assert cal.anchor_rmse_m < 1e-9
    assert cal.n_anchors==4


def test_relative_depth_cannot_determine_metric_units_without_anchors():
    x=np.ones((4,4))
    with pytest.raises(ValueError,match='3 independent'):
        align_relative_depth(x,[])
    with pytest.raises(ValueError,match='Degenerate'):
        align_relative_depth(x,[{'u':i,'v':i,'camera_z_m':1+i*.1} for i in range(3)])


def test_reject_depth_calibration_inconsistent_with_anchors():
    x=np.array([[0,1,2,3,4]],dtype=float)
    obs=[{'u':i,'v':0,'camera_z_m':z} for i,z in enumerate((1.,2.,1.,2.,1.))]
    with pytest.raises(ValueError,match='RMSE'):
        align_relative_depth(x,obs,max_rmse_m=.1)
