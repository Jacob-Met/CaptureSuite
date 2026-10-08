# SPDX-License-Identifier: GPL-3.0-only
"""Original native Review witness; authored before the video viewer."""
from __future__ import annotations
import hashlib, json, os, pathlib, subprocess, sys, time
ROOT = pathlib.Path(__file__).resolve().parents[3]
OUT = pathlib.Path(__file__).resolve().parent
RUNTIME = pathlib.Path(r"C:\Users\minec\hamon-0378a7b6-capture-runtime")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
for key, suffix in [("LOCALAPPDATA", "local"), ("APPDATA", "roaming"), ("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"), ("XDG_CACHE_HOME", "cache")]:
    path = RUNTIME / "baseline-state" / suffix
    path.mkdir(parents=True, exist_ok=True)
    os.environ[key] = str(path)
import av, numpy as np, PySide6
from PySide6.QtWidgets import QApplication, QPushButton, QComboBox, QSlider
from capture_desktop import theme
from capture_desktop.screen_review import ReviewScreen
from capture_desktop.state import CaptureState
from capture_analysis.discover import discover_streams
from capture_session import load_review_summary
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def manifest(path): return {str(p.relative_to(path)).replace("\\","/"): sha(p) for p in path.rglob("*") if p.is_file()}
tracked = subprocess.check_output(["git","-C",str(ROOT),"ls-files","-z"]).decode().split("\0")
before = {p:sha(ROOT/p) for p in tracked if p}
package = RUNTIME / "synthetic-video.mmsession"
package.mkdir(exist_ok=False)
(package/"manifest.json").write_text(json.dumps({"schemaId":"capture.session/1","sessionId":"synthetic-video-0378","state":"finalized"}))
(package/"events").mkdir()
(package/"events"/"checkpoints.json").write_text(json.dumps([{"checkpointId":"cp-1","name":"Synthetic start","effectiveTimestampNs":1000000000}]))
def video(source, stream_id, name, colors):
    stream_dir = package/"sources"/source/"streams"/stream_id
    seg = stream_dir/"segments"; seg.mkdir(parents=True,exist_ok=True)
    (stream_dir/"stream.json").write_text(json.dumps({"sourceId":source+" <literal>","streamId":stream_id+" & camera","dataSchemaId":"video.frame/1","modality":"video","nominalRateHz":10,"dimensions":[160,120],"units":""}))
    path=seg/name
    with av.open(str(path),"w") as mux:
        stream=mux.add_stream("ffv1",rate=10); stream.width=160; stream.height=120; stream.pix_fmt="yuv420p"
        for index in range(20):
            rgb=np.zeros((120,160,3),dtype=np.uint8); rgb[:]=colors[index//10]
            frame=av.VideoFrame.from_ndarray(rgb,format="rgb24")
            for packet in stream.encode(frame):mux.mux(packet)
        for packet in stream.encode():mux.mux(packet)
    return path
video("sim.left","front","0001.mkv",[(255,0,0),(0,0,255)])
video("sim.left","front","0002.mkv",[(255,255,0),(255,255,0)])
video("sim.right","front","0001.mkv",[(0,255,0),(0,255,0)])
bad=package/"sources"/"sim.right"/"streams"/"front"/"segments"/"invalid.mkv"
bad.write_bytes(b"synthetic intentionally invalid media\n")
summary=load_review_summary(package); refs=discover_streams(package)
assert summary.session_id=="synthetic-video-0378" and sum(len(r.mkv_paths) for r in refs)==4
raw_before=manifest(package)
app=QApplication([]); theme.apply_theme(app,setting="dark")
screen=ReviewScreen(CaptureState()); screen.resize(1160,760); screen.load_package(str(package)); screen.show()
for _ in range(8):app.processEvents(); time.sleep(.04)
assert screen._streams.count()==2
labels=[w.text() for w in screen.findChildren(QPushButton)]
missing=not any("play" in t.casefold() for t in labels) and not screen.findChildren(QComboBox) and not screen.findChildren(QSlider)
assert missing, "Original video capability was unexpectedly present; do not claim missing baseline"
assert screen.grab().save(str(OUT/"baseline.png"))
after={p:sha(ROOT/p) for p in before}
assert before==after and raw_before==manifest(package)
receipt={"schema":"capturesuite.review-video.baseline/1","at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"head":subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip(),"python":sys.version,"qt":PySide6.__version__,"av":av.__version__,"syntheticPackage":str(package),"streamCount":2,"listedMediaSegments":4,"existingReviewPositiveControl":True,"recordedVideoCapabilityAbsent":True,"originalButtons":labels,"sourceHashes":before,"packageHashes":raw_before,"sourcePreserved":True,"packagePreserved":True,"platform":"Native Windows Qt offscreen; actual ReviewScreen, no daemon or hardware","screenshot":"baseline.png"}
(OUT/"baseline.json").write_text(json.dumps(receipt,indent=2)+"\n")
screen.close();screen.deleteLater();app.processEvents()
print(json.dumps({k:v for k,v in receipt.items() if k not in ["sourceHashes","packageHashes"]}))
