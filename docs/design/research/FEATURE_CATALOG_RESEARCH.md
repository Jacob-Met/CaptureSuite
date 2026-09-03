# Feature catalog research

Research date: **2026-09-01**  
Legend: **implemented** | **planned** | **provisional** (needs real hardware data)

---

## EMG (`emg.batch/1`)

| Feature id | Description | Status |
|------------|-------------|--------|
| `emg.rms.v1` | Windowed RMS per channel | implemented |
| `emg.mav.v1` | Mean absolute value | implemented |
| `emg.wl.v1` | Waveform length | implemented |
| `emg.zc.v1` | Zero crossings | implemented |
| `emg.ssc.v1` | Slope sign changes | implemented |
| `emg.envelope.v1` | Rectified low-pass envelope | planned |
| `emg.median_freq.v1` | MNF / MDF fatigue | provisional |
| `emg.coherence.v1` | Pairwise channel coherence | provisional |
| `emg.onset.v1` | Activity onset latency | provisional |
| `emg.fatigue_index.v1` | Composite fatigue | provisional |

**Citations:** standard EMG processing (Merletti & Parker); mark provisional until Delsys soak.

---

## IMU (`imu.frame/1`)

| Feature id | Description | Status |
|------------|-------------|--------|
| `imu.accel_mag.v1` | \|a\| mean/std | implemented |
| `imu.gyro_mag.v1` | \|ω\| mean/std | implemented |
| `imu.orientation_euler.v1` | Roll/pitch/yaw series | planned |
| `imu.jerk.v1` | d|a|/dt | planned |
| `imu.still.v1` | Stillness detector | provisional |
| `imu.segment_velocity.v1` | Integrated velocity (uncalibrated) | provisional |

---

## Radar FMCW (`radar.frame/1`)

| Feature id | Description | Status |
|------------|-------------|--------|
| `radar.motion_energy.v1` | Frame motion energy | implemented |
| `radar.peak_range.v1` | Strongest range bin | implemented |
| `radar.rd_tensor.v1` | RD map `.npy` shard | implemented (derived) |
| `radar.micro_doppler.v1` | Short-time Doppler signature | planned |
| `radar.peak_track.v1` | Range peak tracker | planned |
| `radar.multi_radar_stack.v1` | Array stack per arrays.json | planned |

---

## Radar Doppler (`radar.doppler/1`)

| Feature id | Description | Status |
|------------|-------------|--------|
| `radar_doppler.mag_stats.v1` | Mean/max magnitude | implemented |
| `radar_doppler.peak_bin.v1` | Peak bin index | implemented |
| `radar_doppler.spectrogram.v1` | STFT features | planned |

---

## Video timing (`video.*`)

| Feature id | Description | Status |
|------------|-------------|--------|
| `video.timing_qc.v1` | fps, dt percentiles | implemented |
| `video.frame_grab.v1` | Thumbnail at scope points | planned |

---

## Pose / video (Phase D)

| Feature id | Description | Status |
|------------|-------------|--------|
| `pose.landmarks.v1` | Canonical parquet | planned |
| `pose.conf_mask.v1` | Per-joint confidence | planned |
| `pose.joint_angles.v1` | Tier A angles | planned (kinematics) |
| `pose.path_length.v1` | Wrist path length | planned |
| `hand.landmarks_21.v1` | Native 21-pt per hand | planned (D+) |
| `face.landmarks.v1` | Face mesh subset | planned (D+) |

---

## Kinematics (Phase D2)

| Feature id | Description | Status |
|------------|-------------|--------|
| `kinematics.tier_a.v1` | Registry columns | planned |
| `kinematics.kobayashi.v1` | ATD/MS/MA/MR/AFR | planned (Tier B) |

See [kinematics_columns.registry.json](../../../schemas/kinematics/kinematics_columns.registry.json).

---

## Cross-modal

| Feature id | Description | Status |
|------------|-------------|--------|
| `coupling.emg_angle.v1` | EMG vs joint angle correlation | provisional |
| `ml.window_radar_kinematics.v1` | Aligned X/y windows | planned (Phase E) |
| `sync.anchor_quality.v1` | Residual after anchor apply | planned |

---

## Graph / plot types (linked)

| plot_id | Feature inputs |
|---------|----------------|
| `plot.emg.channels` | emg features / raw materialized |
| `plot.imu.accel` | imu features |
| `plot.radar.energy` | radar frame features |
| `plot.sync.dashboard` | multi-stream |
| `plot.rd.heatmap` | derived RD |
| `plot.pose.overlay` | pose + video |
| `plot.kinematics.angle` | kinematics tier A |
| `plot.ml.residual` | eval Phase F |

---

## Provisional flag policy

Features marked **provisional** must:
- Set `calibrated: false` or explicit units in column meta
- Appear with badge in Analysis UI
- Fail CI if claimed as validated without fixture tagged `hardware_validated`

---

## References

- [ANALYSIS_PLUGIN_ARCHITECTURE.md](ANALYSIS_PLUGIN_ARCHITECTURE.md)
- [MODALITY_DEPTH_*.md](README.md)
