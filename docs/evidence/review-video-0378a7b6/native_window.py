# SPDX-License-Identifier: GPL-3.0-only
"""Native Windows presentation qualification, restricted to this synthetic test window."""
from __future__ import annotations
import hashlib,json,os,pathlib,time
ROOT=pathlib.Path(__file__).resolve().parents[3];OUT=pathlib.Path(__file__).resolve().parent
RUNTIME=pathlib.Path(r"C:\Users\minec\hamon-0378a7b6-capture-runtime")
os.environ["QT_QPA_PLATFORM"]="windows"
for key,suffix in [("LOCALAPPDATA","local"),("APPDATA","roaming"),("XDG_CONFIG_HOME","config"),("XDG_DATA_HOME","data"),("XDG_CACHE_HOME","cache")]:
    p=RUNTIME/"window-state"/suffix;p.mkdir(parents=True,exist_ok=True);os.environ[key]=str(p)
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from capture_desktop import theme
from capture_desktop.screen_review import ReviewScreen
from capture_desktop.state import CaptureState
app=QApplication([]);theme.apply_theme(app,setting="dark")
screen=ReviewScreen(CaptureState());screen.setWindowTitle("CaptureSuite receiving - synthetic video")
screen.resize(1120,860);screen.load_package(str(RUNTIME/"synthetic-video.mmsession"));screen.show()
viewer=screen._recorded_video;QTest.mouseClick(viewer._toggle,Qt.MouseButton.LeftButton);viewer._choice.setCurrentIndex(1)
def wait(test):
    end=time.monotonic()+12
    while time.monotonic()<end:
        app.processEvents();QTest.qWait(20)
        if test():return
    raise AssertionError(viewer._status.text())
wait(lambda:viewer._ready)
QTest.mouseClick(viewer._play,Qt.MouseButton.LeftButton)
wait(lambda:viewer._video.videoSink().videoFrame().isValid())
QTest.mouseClick(viewer._play,Qt.MouseButton.LeftButton);viewer._seek.setValue(7500)
def blue():
    frame=viewer._video.videoSink().videoFrame()
    if not frame.isValid():return False
    image=frame.toImage()
    return not image.isNull() and image.pixelColor(80,60).blue()>200 and image.pixelColor(80,60).red()<45
wait(blue)
QTest.qWait(300);app.processEvents()
pix=screen.screen().grabWindow(int(screen.winId()))
assert not pix.isNull()
assert pix.save(str(OUT/"candidate-windows-dark.png"))
bounds=viewer._video.geometry()
origin=viewer._video.mapTo(screen,viewer._video.rect().center())
color=pix.toImage().pixelColor(origin.x(),origin.y()).getRgb()
assert color[2]>180 and color[0]<60,("Rendered video pixel not blue",color)
theme.apply_theme(app,setting="light");QTest.qWait(120);app.processEvents()
assert screen.screen().grabWindow(int(screen.winId())).save(str(OUT/"candidate-windows-light.png"))
receipt={"at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"platform":app.platformName(),"actualWindow":True,"capture":"Only this owned synthetic ReviewScreen HWND; no other window or desktop screenshot","decodedBlue":True,"renderedWindowBluePixel":list(color),"mediaPositionMs":viewer._player.position(),"windowSize":[pix.width(),pix.height()],"sourcePins":{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ["desktop/capture_desktop/review_video.py","desktop/capture_desktop/widgets_review_video.py","desktop/capture_desktop/screen_review.py"]}}
(OUT/"native-window.json").write_text(json.dumps(receipt,indent=2)+"\n")
screen.close();screen.deleteLater();app.processEvents();print(json.dumps(receipt))
