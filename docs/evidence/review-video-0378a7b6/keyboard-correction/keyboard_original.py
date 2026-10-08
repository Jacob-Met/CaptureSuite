# SPDX-License-Identifier: GPL-3.0-only
import hashlib,json,os,pathlib,sys,time
rt=pathlib.Path(r"C:\Users\minec\hamon-0378a7b6-capture-runtime")
root=rt/"published-source"
os.environ["QT_QPA_PLATFORM"]="offscreen"
for key,suffix in [("LOCALAPPDATA","local"),("APPDATA","roaming"),("XDG_CONFIG_HOME","config"),("XDG_DATA_HOME","data"),("XDG_CACHE_HOME","cache")]:
    p=rt/"keyboard-original-state"/suffix;p.mkdir(parents=True,exist_ok=True);os.environ[key]=str(p)
sys.path[:0]=[str(root/"desktop")]+[str(p) for p in (root/"libs/python").iterdir() if p.is_dir()]
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest
from capture_desktop.app import MainWindow
app=QApplication([])
window=MainWindow(auto_connect=False);window.resize(1280,1000)
hits=[]
window._on_checkpoint=lambda:hits.append("checkpoint")
window.state.package_path=str(root/"tests/fixtures/review_video")
window.state.review_mode=True
window.review.load_package(window.state.package_path)
window.tabs.setCurrentWidget(window.review)
window.show();window.activateWindow();app.setActiveWindow(window)
view=window.review._recorded_video
view._toggle.setChecked(True);view._choice.setCurrentIndex(1)
deadline=time.monotonic()+8
while not view._ready and time.monotonic()<deadline:app.processEvents();time.sleep(.01)
assert view._ready
view._play.setFocus();QTest.qWait(30)
assert app.focusWidget() is view._play
QTest.keyClick(view._play,Qt.Key.Key_Space);QTest.qWait(50)
receipt={"at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"source":"e9728100b7c27b175b04e0fc776f8d9984713698","actual_main_window":True,"focused_play":app.focusWidget() is view._play,"playback":view._player.playbackState().name,"checkpoint_hits":len(hits),"video_source_sha256":hashlib.sha256((root/"desktop/capture_desktop/widgets_review_video.py").read_bytes()).hexdigest()}
(rt/"keyboard-original.json").write_text(json.dumps(receipt,indent=2)+"\n");print(json.dumps(receipt))
window.close();app.processEvents()
assert receipt["playback"]=="PlayingState" and not hits,"Focused Play Space was intercepted by existing application shortcut"
