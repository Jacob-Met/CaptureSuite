# SPDX-License-Identifier: GPL-3.0-only
"""Native presentation receiving on synthetic media; no source edits."""
from __future__ import annotations
import hashlib, json, os, pathlib, subprocess, sys, time, types
ROOT=pathlib.Path(__file__).resolve().parents[3]; OUT=pathlib.Path(__file__).resolve().parent
RUNTIME=pathlib.Path(r"C:\Users\minec\hamon-0378a7b6-capture-runtime")
os.environ["QT_QPA_PLATFORM"]="offscreen"
for key,suffix in [("LOCALAPPDATA","local"),("APPDATA","roaming"),("XDG_CONFIG_HOME","config"),("XDG_DATA_HOME","data"),("XDG_CACHE_HOME","cache")]:
    path=RUNTIME/"presentation-state"/suffix;path.mkdir(parents=True,exist_ok=True);os.environ[key]=str(path)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QPushButton
from capture_desktop import theme
from capture_desktop.state import CaptureState
from capture_desktop.screen_review import ReviewScreen
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def wait(predicate,description):
    end=time.monotonic()+12
    while time.monotonic()<end:
        app.processEvents()
        if predicate():return
        QTest.qWait(15)
    raise AssertionError(description)
def color(video,index):
    frame=video._video.videoSink().videoFrame()
    if not frame.isValid():return False
    image=frame.toImage()
    if image.isNull():return False
    rgb=image.pixelColor(80,60).getRgb()[:3]
    return rgb[index]>200 and all(v<45 for i,v in enumerate(rgb) if i!=index)
source_paths=["desktop/capture_desktop/review_video.py","desktop/capture_desktop/widgets_review_video.py","desktop/capture_desktop/screen_review.py","tests/test_review_video_model.py","tests/ui/test_review_video.py"]
before={p:sha(ROOT/p) for p in source_paths}
package=RUNTIME/"synthetic-video.mmsession"
raw_before={str(p.relative_to(package)):sha(p) for p in package.rglob("*") if p.is_file()}
app=QApplication([])
fonts={}
for name in ["segoeui.ttf","segoeuib.ttf"]:
    path=pathlib.Path("C:/Windows/Fonts")/name
    handle=QFontDatabase.addApplicationFont(str(path));assert handle>=0
    fonts[name]={"sha256":sha(path),"families":QFontDatabase.applicationFontFamilies(handle)}
theme.apply_theme(app,setting="dark")
old_source=subprocess.check_output(["git","-C",str(ROOT),"show","HEAD:desktop/capture_desktop/screen_review.py"])
old=types.ModuleType("capture_desktop.original_review_receiving");old.__package__="capture_desktop"
exec(compile(old_source,"original-screen_review.py","exec"),old.__dict__)
original=old.ReviewScreen(CaptureState());original.resize(1160,760);original.load_package(str(package));original.show()
app.processEvents();QTest.qWait(80)
assert original._streams.count()==2
assert [b.text() for b in original.findChildren(QPushButton)]==["Export…"]
assert original.grab().save(str(OUT/"baseline-fonts.png"))
original.close()
screen=ReviewScreen(CaptureState());screen.resize(1160,900);screen.load_package(str(package));screen.show()
viewer=screen._recorded_video
QTest.mouseClick(viewer._toggle,Qt.MouseButton.LeftButton);viewer._choice.setCurrentIndex(1)
wait(lambda:viewer._ready,"native decoder ready")
QTest.mouseClick(viewer._play,Qt.MouseButton.LeftButton);wait(lambda:color(viewer,0),"actual red frame")
QTest.mouseClick(viewer._play,Qt.MouseButton.LeftButton)
viewer._seek.setValue(7500);wait(lambda:color(viewer,2),"actual blue frame after seek")
assert viewer._player.position()==1500
assert viewer._video.videoSink().videoFrame().toImage().save(str(OUT/"decoded-blue-frame.png"))
app.processEvents();assert screen.grab().save(str(OUT/"candidate-dark.png"))
theme.apply_theme(app,setting="light");app.processEvents();assert screen.grab().save(str(OUT/"candidate-light.png"))
screen.resize(760,900);app.processEvents();assert screen.grab().save(str(OUT/"candidate-compact.png"))
baseline=json.loads((OUT/"baseline.json").read_text())
changed_original=[p for p,h in baseline["sourceHashes"].items() if sha(ROOT/p)!=h]
assert changed_original==["desktop/capture_desktop/screen_review.py"],changed_original
assert before=={p:sha(ROOT/p) for p in source_paths}
assert raw_before=={str(p.relative_to(package)):sha(p) for p in package.rglob("*") if p.is_file()}
receipt={"at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"python":sys.version,"sourcePins":before,"nativeMedia":{"decoderReady":True,"actualRedFrame":True,"actualBlueFrameAfterSeek":True,"positionMs":viewer._player.position(),"durationMs":viewer._player.duration(),"clockText":viewer._clock.text()},"fontsLoadedOnlyInReceiver":fonts,"screenshots":["baseline-fonts.png","candidate-dark.png","candidate-light.png","candidate-compact.png","decoded-blue-frame.png"],"unchangedOriginalLeaves":len(baseline["sourceHashes"])-1,"changedOriginalLeaves":changed_original,"packagePreserved":True,"sourceStableDuringReceiving":True,"boundary":"Actual Windows native Qt offscreen decoder/widget receiving with synthetic FFV1 MKV. Fonts were explicitly loaded from existing Windows files into this test application after initial offscreen screenshots showed missing glyphs. No installed font, theme or production dependency was changed."}
(OUT/"presentation.json").write_text(json.dumps(receipt,indent=2)+"\n")
screen.close();screen.deleteLater();app.processEvents()
print(json.dumps(receipt))
