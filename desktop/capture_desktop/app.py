# SPDX-License-Identifier: GPL-3.0-only
"""Main window and transport controls for CaptureSuite desktop."""

from __future__ import annotations

from pathlib import Path

from capture_protocol.control_client import ControlClientError
from capture_protocol.generated.capture.v1 import control_pb2
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .daemon_link import DaemonLink
from .persistence import DesktopPersistence
from .screen_capture import CaptureScreen
from .screen_settings import PreferencesDialog
from .screen_setup import SetupScreen, parse_json_object
from .state import CaptureState, fmt_time
from .widgets_preview import PreviewHost
from .widgets_session_header import SessionHeader


class PreflightDialog(QDialog):
    def __init__(self, reply: control_pb2.RunPreflightReply, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preflight")
        self.resize(520, 420)
        layout = QVBoxLayout(self)
        summary = QLabel("PASS" if reply.ok else "FAIL")
        summary.setFont(theme.ui(14, bold=True))
        summary.setStyleSheet(
            f"color: {(theme.GREEN if reply.ok else theme.RED).name()};"
        )
        layout.addWidget(summary)
        body = QTextEdit()
        body.setReadOnly(True)
        body.setFont(theme.mono(9))
        color = {
            "ok": theme.GREEN.name(),
            "warn": theme.ORANGE.name(),
            "fail": theme.RED.name(),
        }
        # Group by source_id when present in check_id / name prefix.
        groups: dict[str, list[str]] = {}
        for check in reply.checks:
            status = check.status.lower()
            mark = {"ok": "OK", "warn": "WARN", "fail": "FAIL"}.get(
                status, check.status.upper()
            )
            c = color.get(status, theme.TEXT_DIM.name())
            cid = check.check_id or ""
            key = cid.split(".", 1)[0] if "." in cid else "session"
            line = (
                f"<span style='color:{c}'>[{mark}]</span> "
                f"<b>{check.name}</b>: {check.message}"
            )
            if check.overridable:
                line += (
                    " <span style='color:"
                    f"{theme.TEXT_FAINT.name()}'>(overridable — no Proceed RPC yet)</span>"
                )
            groups.setdefault(key, []).append(line)
        chunks: list[str] = []
        for key, lines in groups.items():
            chunks.append(f"<p><b>{key}</b><br>" + "<br>".join(lines) + "</p>")
        if reply.error.code:
            chunks.append(
                f"<p style='color:{theme.RED.name()}'>error: "
                f"{reply.error.code}: {reply.error.message}</p>"
            )
        if not chunks:
            chunks.append("<p>(no checks returned)</p>")
        body.setHtml("".join(chunks))
        layout.addWidget(body, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


class MainWindow(QMainWindow):
    def __init__(self, *, auto_connect: bool = True) -> None:
        super().__init__()
        self.setWindowTitle("CaptureSuite")
        self.setMinimumSize(1100, 700)

        self.state = CaptureState()
        self.link = DaemonLink(self)
        self._boot_stage = "idle"
        self._rescan_pending = False
        self.persistence = DesktopPersistence()
        if self.persistence.registry_open.read_only:
            self.state.status_line = self.persistence.registry_open.message
        try:
            self.state.preview_grid_columns = int(
                self.persistence.settings.get("preview_grid_columns") or 0
            )
        except (TypeError, ValueError):
            self.state.preview_grid_columns = 0
        PreviewHost.configure_styles(
            self.persistence.preview_kind_styles(),
            on_changed=self.persistence.set_preview_kind_style,
        )

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_banner())
        layout.addWidget(self._build_transport())
        self._session_header = SessionHeader()
        layout.addWidget(self._session_header)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.capture = CaptureScreen(self.state, persistence=self.persistence)
        self.tabs.addTab(self.capture, "Capture")
        self.setup = SetupScreen(self.state)
        self.tabs.addTab(self.setup, "Setup")
        from .screen_analysis import AnalysisScreen
        from .screen_review import ReviewScreen

        self.review = ReviewScreen(self.state)
        self.tabs.addTab(self.review, "Review")
        self.analysis = AnalysisScreen(self.state, persistence=self.persistence)
        self.tabs.addTab(self.analysis, "Analysis")
        layout.addWidget(self.tabs, 1)
        layout.addWidget(self._build_status_bar())

        self._wire()
        self._restore_geometry()
        self._build_menu()
        self._sync_buttons()

        if auto_connect:
            QTimer.singleShot(0, self._begin_startup)

    def _build_banner(self) -> QWidget:
        banner = QWidget()
        banner.setStyleSheet(
            f"background: {theme.PANEL_ALT.name()};"
            f"border-bottom: 1px solid {theme.BORDER.name()};"
        )
        row = QHBoxLayout(banner)
        row.setContentsMargins(12, 6, 12, 6)
        brand = QLabel("CaptureSuite")
        brand.setFont(theme.ui(11, bold=True))
        tagline = QLabel("Multimodal research capture")
        tagline.setObjectName("Dim")
        tagline.setFont(theme.ui(8))
        row.addWidget(brand)
        row.addSpacing(16)
        row.addWidget(tagline, 1)
        if self.persistence.registry_open.read_only:
            ro = QLabel(
                self.persistence.registry_open.message
                or "Registry is read-only — presets will not persist."
            )
            ro.setObjectName("Dim")
            ro.setFont(theme.ui(8, bold=True))
            ro.setStyleSheet(f"color: {theme.ORANGE.name()};")
            ro.setWordWrap(True)
            row.addWidget(ro, 1)
        return banner

    def _build_menu(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("&File")
        prefs = file_menu.addAction("Preferences…")
        prefs.setShortcut(QKeySequence("Ctrl+,"))
        prefs.triggered.connect(self._open_preferences)
        presets = file_menu.addAction("Preset library…")
        presets.triggered.connect(self._open_preset_library)
        file_menu.addSeparator()
        quit_act = file_menu.addAction("Quit")
        quit_act.setShortcut(QKeySequence.StandardKey.Quit)
        quit_act.triggered.connect(self.close)

    def _open_preferences(self) -> None:
        dlg = PreferencesDialog(
            self.persistence,
            on_theme_changed=self._reapply_theme,
            parent=self,
        )
        dlg.exec()

    def _open_preset_library(self) -> None:
        from .screen_presets import PresetLibraryDialog

        dlg = PresetLibraryDialog(self.persistence, parent=self)
        dlg.exec()

    def _edit_radar_array(self) -> None:
        from .widgets_radar_array import RadarArrayEditorDialog

        radars = [
            s
            for s in self.state.selected_sources()
            if s.modality in ("radar", "radar_doppler") or s.is_hardware_radar
        ]
        if len(radars) < 2:
            return
        dlg = RadarArrayEditorDialog(self.persistence, radars, parent=self)
        if dlg.exec():
            self.state.status_line = "Saved radar array preset"
            self._status.setText(self.state.status_line)

    def _reapply_theme(self) -> None:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return
        setting = str(self.persistence.settings.get("theme") or "system")
        theme.apply_theme(app, setting=setting)
        self._refresh_chrome_styles()

    def _refresh_chrome_styles(self) -> None:
        """Re-apply inline styles that reference theme module colors."""
        self._sync_buttons()
        self.capture.refresh()

    def _build_transport(self) -> QWidget:
        frame = QWidget()
        frame.setStyleSheet(
            f"background: {theme.PANEL.name()};"
            f"border-bottom: 1px solid {theme.BORDER.name()};"
        )
        row = QHBoxLayout(frame)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(7)

        self.btn_create = QPushButton("Create Session")
        self.btn_create.clicked.connect(self._on_create_session)
        self.btn_open = QPushButton("Open Session")
        self.btn_open.clicked.connect(self._on_open_session)
        self.btn_select = QPushButton("Select")
        self.btn_select.clicked.connect(self._on_select)
        self.btn_preflight = QPushButton("Preflight")
        self.btn_preflight.clicked.connect(self._on_preflight)
        self.btn_rescan = QPushButton("Rescan")
        self.btn_rescan.setToolTip(
            "Re-enumerate cameras and radars after unplug/replug "
            "(stops rehearsal; blocked while recording)"
        )
        self.btn_rescan.clicked.connect(self._on_rescan)
        self.btn_rehearse = QPushButton("Rehearse")
        self.btn_rehearse.clicked.connect(self._on_rehearse)
        self.btn_stop_rehearse = QPushButton("Stop Rehearse")
        self.btn_stop_rehearse.clicked.connect(self._on_stop_rehearse)
        self.btn_start = QPushButton("Start Selected")
        self.btn_start.setObjectName("Primary")
        self.btn_start.clicked.connect(self._on_start)
        self.btn_start_all = QPushButton("Start All Ready")
        self.btn_start_all.clicked.connect(self._on_start_all)
        self.btn_checkpoint = QPushButton("Checkpoint")
        self.btn_checkpoint.clicked.connect(self._on_checkpoint)
        self.btn_annotate = QPushButton("Annotation")
        self.btn_annotate.clicked.connect(self._on_annotate)
        self.btn_sync = QPushButton("Sync Event")
        self.btn_sync.clicked.connect(self._on_sync)
        self.btn_logs = QPushButton("Logs")
        self.btn_logs.clicked.connect(self._on_open_logs)

        self._timer_label = QLabel("00:00:00")
        self._timer_label.setFont(theme.mono(19, bold=True))
        self._rec_label = QLabel("IDLE")
        self._rec_label.setFont(theme.ui(8, bold=True))
        self._rec_label.setStyleSheet(f"color: {theme.TEXT_FAINT.name()};")

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setObjectName("Danger")
        self.btn_stop.clicked.connect(self._on_stop)

        for w in (
            self.btn_create,
            self.btn_open,
            self.btn_select,
            self.btn_preflight,
            self.btn_rescan,
            self.btn_rehearse,
            self.btn_stop_rehearse,
            self.btn_start,
            self.btn_start_all,
            self.btn_checkpoint,
            self.btn_annotate,
            self.btn_sync,
            self.btn_logs,
        ):
            row.addWidget(w)
        row.addStretch(1)
        row.addWidget(self._timer_label)
        row.addWidget(self._rec_label)
        row.addSpacing(8)
        row.addWidget(self.btn_stop)
        return frame

    def _build_status_bar(self) -> QWidget:
        frame = QWidget()
        frame.setFixedHeight(34)
        frame.setStyleSheet(
            f"background: {theme.PANEL.name()};"
            f"border-top: 1px solid {theme.BORDER.name()};"
        )
        row = QHBoxLayout(frame)
        row.setContentsMargins(10, 0, 10, 0)
        self._status = QLabel("Starting…")
        self._status.setObjectName("Dim")
        self._status.setFont(theme.ui(8))
        self._session_label = QLabel("")
        self._session_label.setObjectName("Faint")
        self._session_label.setFont(theme.ui(8))
        row.addWidget(self._status, 1)
        row.addWidget(self._session_label)
        return frame

    def _wire(self) -> None:
        self.link.rpc_done.connect(self._on_rpc_done)
        self.link.connected.connect(self._on_connected)
        self.link.disconnected.connect(self._on_disconnected)
        self.link.error.connect(self._on_error)
        self.link.sources_listed.connect(self._on_sources)
        self.link.session_created.connect(self._on_session_created)
        self.link.sources_selected.connect(self._on_sources_selected)
        self.link.session_view.connect(self._on_session_view)
        self.link.preview_frame.connect(self._on_preview)
        self.link.health_snapshot.connect(self._on_health)
        self.link.disk_status.connect(self._on_disk)
        self.link.alert.connect(self._on_alert)
        self.link.gap_event.connect(self._on_gap_event)
        self.link.preflight_done.connect(self._on_preflight_done)
        self.link.checkpoint_created.connect(self._on_checkpoint_created)

        self.capture.focus_changed.connect(self._on_focus)
        self.capture.selection_toggled.connect(self._on_toggle_source)
        self.capture.checkpoint_renamed.connect(self._rename_checkpoint)
        self.capture.view_mode_changed.connect(self._persist_view_mode)
        self.capture.radar_view_changed.connect(self._on_radar_preview_view)
        self.capture.alert_ack_requested.connect(self.link.acknowledge_alert)
        self.capture.alert_show_source.connect(self._on_focus)
        self.capture.radar_array_edit_requested.connect(self._edit_radar_array)
        self.review.export_requested.connect(self._on_review_export)

        self.setup.source_selected.connect(self._load_setup_schema)
        self.setup.refresh_requested.connect(self._load_setup_schema)
        self.setup.apply_requested.connect(self._on_apply_config)
        self.setup.set_preset_handlers(self._save_device_preset, self._load_device_preset)
        self.tabs.currentChanged.connect(self._on_tab_changed)

        for key in (Qt.Key.Key_C, Qt.Key.Key_Space):
            sc = QShortcut(QKeySequence(key), self)
            sc.setContext(Qt.ShortcutContext.ApplicationShortcut)
            sc.activated.connect(self._hotkey_checkpoint)
        ack = QShortcut(QKeySequence(Qt.Key.Key_A), self)
        ack.setContext(Qt.ShortcutContext.ApplicationShortcut)
        ack.activated.connect(self._hotkey_ack_alert)

        self._ui_timer = QTimer(self)
        self._ui_timer.setInterval(100)
        self._ui_timer.timeout.connect(self._refresh_ui)
        self._ui_timer.start()

    # -- settings ------------------------------------------------------------

    def _restore_geometry(self) -> None:
        mode = self.persistence.restore_window(self)
        self.capture.set_view_mode(mode)

    def _persist_view_mode(self, index: int) -> None:
        self.persistence.save_window(self, index)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.persistence.save_window(self, self.capture.view_mode())
        self.persistence.close()
        self.link.stop()
        super().closeEvent(event)

    # -- startup -------------------------------------------------------------

    def _begin_startup(self) -> None:
        if not self.link.daemon_available():
            self.state.status_line = (
                "Daemon not found (LOCALAPPDATA/CaptureSuite/instance.json). "
                "Start capture_daemon.exe, then Create Session."
            )
            self._status.setText(self.state.status_line)
            self._sync_buttons()
            return
        self._boot_stage = "connect"
        self.state.status_line = "Connecting to daemon…"
        self._status.setText(self.state.status_line)
        self.link.start()

    def _on_connected(self, instance_id: str) -> None:
        self.state.connected = True
        self.state.instance_id = instance_id
        self.state.status_line = f"Connected · instance {instance_id[:8]}"
        self._boot_stage = "list_sources"
        self.link.list_sources()

    def _on_disconnected(self, reason: str) -> None:
        self.state.connected = False
        self.state.status_line = f"Disconnected: {reason}"
        self._sync_buttons()

    def _on_error(self, message: str) -> None:
        self.state.status_line = message
        self._status.setText(message)

    def _on_rpc_done(self, tag: str, result: object) -> None:
        self.link.handle_rpc_done(tag, result)
        if tag in ("start_selected", "start_all_ready") and not isinstance(
            result, Exception
        ):
            self.state.session_state = getattr(
                result, "state", control_pb2.SESSION_STATE_RECORDING
            )
            self.link.refresh_session_view()
        elif tag == "acknowledge_alert" and not isinstance(result, Exception):
            alert = getattr(result, "alert", None)
            if alert is not None:
                self.state.apply_alert(alert)
                self.capture.refresh()
            self.link.refresh_session_view()
        elif tag == "open_session" and not isinstance(result, Exception):
            if getattr(result, "error", None) and result.error.code:
                self._on_error(f"open_session: {result.error.message}")
            else:
                recovered = getattr(result, "recovered", False)
                package = getattr(result, "package_path", "") or ""
                session_id = getattr(result, "session_id", "") or ""
                if not package and hasattr(self, "_last_open_path"):
                    package = self._last_open_path
                self.state.review_mode = True
                self.state.status_line = (
                    "Opened session (recovered) — review mode"
                    if recovered
                    else "Opened session — review mode"
                )
                if package:
                    self.state.package_path = package
                    self.state.session_id = session_id or self.state.session_id
                    self.persistence.record_session(
                        package_path=package,
                        session_id=session_id or "unknown",
                        state="finalized_recovered" if recovered else "finalized",
                    )
                    self.review.load_package(package, recovered=recovered)
                    self.analysis.set_package(package)
                    self._refresh_session_header_sealed(package, recovered=recovered)
                    self.tabs.setCurrentWidget(self.review)
                self._sync_buttons()
                self.link.refresh_session_view()
        elif tag == "stop_rehearsal" and not isinstance(result, Exception):
            self.state.rehearsal_active = False
            self.state.status_line = "Rehearsal stopped"
            self._status.setText(self.state.status_line)
            self.link.refresh_session_view()
        elif tag == "stop_session" and not isinstance(result, Exception):
            self.state.session_state = getattr(
                result, "state", control_pb2.SESSION_STATE_FINALIZED
            )
            self.link.refresh_session_view()
        elif tag == "start_rehearsal" and not isinstance(result, Exception):
            if getattr(result, "error", None) and result.error.code:
                self._on_error(f"rehearsal: {result.error.message}")
                self._boot_stage = "ready"
            else:
                self.state.rehearsal_active = True
                if self._boot_stage == "rehearse":
                    self._boot_stage = "ready"
                    self.state.status_line = (
                        f"Session {self.state.session_id} ready · "
                        f"{len(self.state.selected_ids)} sources · rehearsal preview"
                    )
                else:
                    self.state.status_line = "Rehearsal running"
                self._status.setText(self.state.status_line)
                self.link.refresh_session_view()
        elif tag == "start_rehearsal" and isinstance(result, Exception):
            self._on_error(f"rehearsal: {result}")
            self._boot_stage = "ready"
        elif tag == "get_config_schema" and not isinstance(result, Exception):
            self._on_config_schema(result)
            self.state.status_line = "Schema loaded"
            self._status.setText(self.state.status_line)
        elif tag == "get_config_schema" and isinstance(result, Exception):
            self._on_error(f"schema: {result}")
        elif tag == "apply_config" and not isinstance(result, Exception):
            self._on_apply_config_done(result)
        elif tag == "apply_config" and isinstance(result, Exception):
            self.setup.set_applying(False)
            self._on_error(f"apply: {result}")
        elif tag == "rescan_sources" and isinstance(result, Exception):
            self._rescan_pending = False
            self._on_error(f"rescan: {result}")
        elif tag == "select_sources" and not isinstance(result, Exception):
            err = getattr(result, "error", None)
            if err is not None and err.code:
                self._on_error(f"select_sources: {err.message}")
            else:
                self.state.status_line = "Sources selected"
                self._status.setText(self.state.status_line)
        if tag in ("start_selected", "start_all_ready") and not isinstance(
            result, Exception
        ):
            err = getattr(result, "error", None)
            if not (err and err.code):
                self.state.status_line = "Recording"
                self._status.setText(self.state.status_line)
        self._sync_buttons()

    def _on_sources(self, reply: object) -> None:
        err = getattr(reply, "error", None)
        if err is not None and err.code:
            self._on_error(f"sources: {err.message}")
            self._rescan_pending = False
            return
        preserve = bool(getattr(self, "_rescan_pending", False))
        self._rescan_pending = False
        self.state.apply_sources(reply, preserve_selection=preserve)
        self.capture.rebuild_rail()
        self.setup.rebuild_sources()
        for src in reply.sources:
            plugin = src.plugin_id or "unknown"
            for phys in src.physical_devices:
                key = phys.stable_device_key or src.source_id
                self.persistence.registry.upsert_device(
                    stable_device_key=key,
                    plugin_id=plugin,
                    vendor=phys.vendor or None,
                    model=phys.model or None,
                    serial=phys.serial or None,
                    friendly_name=src.alias or phys.model or None,
                    last_source_id=src.source_id,
                )
        if preserve:
            ids = sorted(self.state.selected_ids)
            if ids:
                self.link.select_sources(ids)
            radars = sum(1 for s in self.state.sources if s.source_id.startswith("radar."))
            cams = sum(1 for s in self.state.sources if s.source_type == "camera")
            self.state.status_line = (
                f"Rescan complete · {cams} camera(s), {radars} radar(s)"
            )
            self._status.setText(self.state.status_line)
            # Refresh Setup schema for the current source after Rescan.
            if self.tabs.currentWidget() is self.setup:
                sid = self.setup.current_source_id()
                if sid:
                    self._load_setup_schema(sid)
        if self._boot_stage == "list_sources":
            self._boot_stage = "create_session"
            self.link.create_session()

    def _on_session_created(self, reply: control_pb2.CreateSessionReply) -> None:
        if reply.error.code:
            self._on_error(f"create_session: {reply.error.message}")
            return
        self.state.review_mode = False
        self.state.session_id = reply.session_id
        self.state.package_path = reply.package_path
        self.state.session_state = reply.state
        if reply.package_path:
            self.persistence.record_session(
                package_path=reply.package_path,
                session_id=reply.session_id,
                state="preparing",
            )
        from capture_desktop.state import default_selected_source_ids

        ids = sorted(self.state.selected_ids)
        if not ids:
            ids = default_selected_source_ids(self.state.sources)
        self.state.selected_ids = set(ids)
        for src in self.state.sources:
            src.selected = src.source_id in self.state.selected_ids
        cam = next((s for s in self.state.sources if s.source_id in ids and s.is_real_camera), None)
        if cam is not None:
            self.state.focus_id = cam.source_id
        self._boot_stage = "select_sources"
        self.link.select_sources(ids)

    def _on_sources_selected(self, reply: control_pb2.SelectSourcesReply) -> None:
        if reply.error.code:
            self._on_error(f"select_sources: {reply.error.message}")
            return
        self.state.selected_ids = set(reply.selected_source_ids)
        for src in self.state.sources:
            src.selected = src.source_id in self.state.selected_ids
        if self._boot_stage == "select_sources":
            self._boot_stage = "subscribe"
            self.link.subscribe_status(
                preview_rate_limit_hz=self.persistence.preview_rate_limit_hz()
            )
            self.link.refresh_session_view()
            # Auto-rehearse so Capture tiles show live/sim previews without an
            # extra click (cameras need an active pipeline for frames).
            self._boot_stage = "rehearse"
            self.link.start_rehearsal(sorted(self.state.selected_ids) or None)
            return
        # Operator toggled selection: restart rehearsal so newly selected cameras
        # get a pipeline and deselected ones release the device (LED off).
        if (
            self.state.package_path
            and not self.state.recording
            and self._boot_stage in ("ready", "rehearse")
        ):
            self.link.start_rehearsal(sorted(self.state.selected_ids) or None)
        self.capture.refresh()
        self._sync_buttons()

    def _on_session_view(self, reply: control_pb2.GetSessionViewReply) -> None:
        self.state.apply_session_view(reply)

    def _on_preview(self, frame) -> None:
        self.state.apply_preview(frame)

    def _on_health(self, snap) -> None:
        self.state.apply_health(snap)

    def _on_disk(self, disk) -> None:
        self.state.apply_disk(disk)

    def _on_preflight_done(self, reply: control_pb2.RunPreflightReply) -> None:
        PreflightDialog(reply, self).exec()

    def _on_checkpoint_created(self, reply: control_pb2.CreateCheckpointReply) -> None:
        if reply.error.code:
            self._on_error(f"checkpoint: {reply.error.message}")
            return
        self.state.upsert_checkpoint(reply.checkpoint)
        self.capture.refresh()
        self.capture.focus_checkpoint(reply.checkpoint.checkpoint_id)
        self.link.refresh_session_view()

    def _on_tab_changed(self, index: int) -> None:
        widget = self.tabs.widget(index)
        if widget is self.setup:
            sid = self.setup.current_source_id()
            if not sid and self.state.sources:
                self.setup.rebuild_sources()
                sid = self.setup.current_source_id()
            if sid:
                self._load_setup_schema(sid)
        elif widget is self.analysis:
            self.analysis.refresh_from_state()

    # -- transport actions ---------------------------------------------------

    def _on_review_export(self, package_path: str) -> None:
        from PySide6.QtWidgets import QMessageBox

        from .export_wizard import ExportWizard, run_export

        default = self.persistence.settings.get("last_export_path") or str(
            Path(package_path) / "exports"
        )
        dlg = ExportWizard(package_path, default_out=str(default), parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        opts = dlg.options
        self.persistence.settings.set("last_export_path", opts.out_dir)
        self._set_busy("Exporting session…")
        code, tail = run_export(package_path, opts)
        if code != 0:
            self._on_error(f"export failed: {tail}")
            return
        self.state.status_line = f"Export complete → {opts.out_dir}"
        self._status.setText(self.state.status_line)
        QMessageBox.information(
            self,
            "Export",
            f"Wrote export_manifest.json under:\n{opts.out_dir}\n\n"
            f"Provenance sidecar: provenance_sidecar.json",
        )

    def _on_create_session(self) -> None:
        if not self.state.connected:
            self._begin_startup()
            return
        self.link.create_session()

    def _on_open_session(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        if not self.state.connected:
            self._on_error("Connect to the daemon before opening a session")
            return

        recent = [
            r
            for r in self.persistence.registry.recent_sessions(8)
            if Path(r.get("package_path") or "").exists()
        ]
        if recent:
            labels = [
                f"{r.get('session_id', '?')}  ·  {r.get('state', '?')}  ·  "
                f"{r.get('package_path', '')}"
                for r in recent
            ]
            labels.append("Browse…")
            choice, ok = QInputDialog.getItem(
                self, "Open session", "Recent packages:", labels, 0, False
            )
            if not ok:
                return
            if choice != "Browse…":
                path = recent[labels.index(choice)].get("package_path") or ""
                if path:
                    self._last_open_path = path
                    self.link.open_session(path)
                return

        start = self.persistence.settings.get("last_session_parent_path") or ""
        path = QFileDialog.getExistingDirectory(
            self,
            "Open session package",
            str(start or ""),
            QFileDialog.Option.ShowDirsOnly,
        )
        if path:
            self._last_open_path = path
            parent = str(Path(path).parent)
            self.persistence.settings.set("last_session_parent_path", parent)
            self.link.open_session(path)

    def _set_busy(self, message: str) -> None:
        """Immediate click feedback — do not wait for the daemon reply."""
        self.state.status_line = message
        self._status.setText(message)
        from PySide6.QtWidgets import QApplication

        QApplication.processEvents()

    def _on_select(self) -> None:
        from capture_desktop.state import default_selected_source_ids

        ids = sorted(self.state.selected_ids) or default_selected_source_ids(
            self.state.sources
        )
        self._set_busy(f"Selecting {len(ids)} source(s)…")
        self.link.select_sources(ids)

    def _on_preflight(self) -> None:
        self._set_busy("Running preflight…")
        self.link.run_preflight(sorted(self.state.selected_ids) or None)

    def _on_rescan(self) -> None:
        self._rescan_pending = True
        self._set_busy("Rescanning sources (may take ~20s)…")
        self.btn_rescan.setEnabled(False)
        self.link.rescan_sources()

    def _on_rehearse(self) -> None:
        n = len(self.state.selected_ids)
        self._set_busy(f"Starting rehearsal ({n} source(s); workers may cold-start)…")
        self.link.start_rehearsal(sorted(self.state.selected_ids) or None)

    def _on_stop_rehearse(self) -> None:
        self._set_busy("Stopping rehearsal…")
        self.link.stop_rehearsal()

    def _on_start(self) -> None:
        self._set_busy("Starting recording (arming workers)…")
        self.link.start_selected()

    def _on_start_all(self) -> None:
        self._set_busy("Starting all ready sources…")
        self.link.start_all_ready()

    def _on_alert(self, alert: object) -> None:
        self.state.apply_alert(alert)
        self.capture.refresh()

    def _on_gap_event(self, gap: object) -> None:
        self.state.apply_gap_event(gap)
        self.capture.refresh()

    def _hotkey_ack_alert(self) -> None:
        from PySide6.QtWidgets import QAbstractSpinBox, QComboBox, QLineEdit, QTextEdit

        focus = self.focusWidget()
        if isinstance(focus, (QLineEdit, QTextEdit, QAbstractSpinBox, QComboBox)):
            return
        pending = self.state.highest_unacked_alert()
        if pending is None:
            return
        self.link.acknowledge_alert(pending.alert_id)

    def _on_checkpoint(self) -> None:
        if not self.state.recording and not self.state.rehearsal_active:
            return
        self.link.create_checkpoint(created_via="ui")

    def _hotkey_checkpoint(self) -> None:
        from PySide6.QtWidgets import QAbstractSpinBox, QComboBox, QLineEdit, QTextEdit

        focus = self.focusWidget()
        if isinstance(focus, (QLineEdit, QTextEdit, QAbstractSpinBox, QComboBox)):
            return
        self._on_checkpoint()

    def _on_annotate(self) -> None:
        text, ok = QInputDialog.getText(self, "Annotation", "Timestamped note:")
        if ok and text.strip():
            self.link.annotate(text.strip())

    def _on_sync(self) -> None:
        self.link.add_sync_anchor("ui")

    def _on_open_logs(self) -> None:
        import os
        from pathlib import Path

        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        if self.state.package_path:
            path = Path(self.state.package_path) / "logs"
        else:
            local = os.environ.get("LOCALAPPDATA", "")
            path = Path(local) / "CaptureSuite" / "logs" if local else Path.cwd()
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _on_stop(self) -> None:
        if self.persistence.confirm_stop_always():
            confirm = QMessageBox(self)
            confirm.setWindowTitle("Stop recording")
            confirm.setText("Stop and finalize this session?")
            confirm.setInformativeText(
                "Stop is protected because it ends acquisition for every active source."
            )
            confirm.setIcon(QMessageBox.Icon.Warning)
            confirm.setStandardButtons(
                QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes
            )
            confirm.setDefaultButton(QMessageBox.StandardButton.Cancel)
            if confirm.exec() != QMessageBox.StandardButton.Yes:
                return
        self.link.stop_recording()

    def _on_focus(self, source_id: str) -> None:
        self.state.focus_id = source_id

    def _on_toggle_source(self, source_id: str) -> None:
        if self.state.recording:
            self._on_error("Source selection is locked while recording")
            return
        if source_id in self.state.selected_ids:
            self.state.selected_ids.discard(source_id)
        else:
            self.state.selected_ids.add(source_id)
        for src in self.state.sources:
            src.selected = src.source_id in self.state.selected_ids
        self.link.select_sources(sorted(self.state.selected_ids))
        self.capture.refresh()

    def _rename_checkpoint(self, checkpoint_id: str, name: str) -> None:
        self.link.update_checkpoint(checkpoint_id, name)

    def _load_setup_schema(self, source_id: str) -> None:
        if not source_id or not self.state.connected:
            return
        self._set_busy(f"Loading config schema for {source_id}…")
        self.link.get_config_schema(source_id)

    def _on_config_schema(self, reply: object) -> None:
        err = getattr(reply, "error", None)
        if err is not None and err.code:
            self.setup.show_schema(
                self.setup.current_source_id(),
                {},
                None,
                error=f"{err.code}: {err.message}",
            )
            return
        schema = parse_json_object(getattr(reply, "schema_json", "") or "")
        current = parse_json_object(getattr(reply, "current_json", "") or "")
        if not current:
            # Fall back to defaults embedded in the schema document.
            current = None
        source_id = self.setup.current_source_id()
        # Prefer the source the form asked for; schema title may differ.
        if not source_id:
            return
        self.setup.show_schema(
            source_id,
            schema,
            current,
            schema_revision=getattr(reply, "schema_revision", "") or "",
        )

    def _on_apply_config(self, source_id: str, document: object) -> None:
        if not isinstance(document, dict):
            return
        self._set_busy(f"Applying config to {source_id}…")
        self.setup.set_applying(True)
        self.link.apply_config(source_id, document)

    def _on_radar_preview_view(self, source_id: str, view: str) -> None:
        """Fusion-style preview combo on Focus — ApplyConfig while not recording."""
        if not source_id or not view or not source_id.startswith("radar."):
            return
        self._set_busy(f"Switching radar view → {view}…")
        self.link.apply_config(source_id, {"preview_view": view})

    def _on_apply_config_done(self, reply: object) -> None:
        self.setup.set_applying(False)
        err = getattr(reply, "error", None)
        if err is not None and err.code:
            self.setup.apply_result(effective=None, error=f"{err.code}: {err.message}")
            self.state.status_line = f"Apply failed: {err.message}"
            self._status.setText(self.state.status_line)
            return
        effective = parse_json_object(getattr(reply, "effective_json", "") or "")
        coerced = list(getattr(reply, "coerced_fields", []) or [])
        self.setup.apply_result(
            effective=effective,
            coerced=coerced,
            schema_revision=getattr(reply, "schema_revision", "") or "",
        )
        self.state.status_line = "Config applied"
        self._status.setText(self.state.status_line)
        self.link.refresh_session_view()

    def _save_device_preset(self, source_id: str, form) -> None:
        import json
        import uuid

        from capture_protocol.config_schema import validate_document

        name, ok = QInputDialog.getText(self, "Save device preset", "Preset name:")
        if not ok or not name.strip():
            return
        schema = form.schema
        document = form.values()
        valid = validate_document(schema, document)
        if not valid.ok:
            QMessageBox.warning(self, "Save preset", "\n".join(valid.errors))
            return
        src = next((s for s in self.state.sources if s.source_id == source_id), None)
        content = {
            "schema_revision": self.setup.schema_revision()
            or schema.get("schema_revision", ""),
            "source_type": src.source_type if src else "",
            "configuration": document,
        }
        try:
            self.persistence.registry.put_preset(
                preset_id=f"device-{uuid.uuid4().hex[:12]}",
                preset_type="device",
                name=name.strip(),
                schema_version=str(content["schema_revision"] or "1"),
                content_json=json.dumps(content),
                description=f"Saved from {source_id}",
                compatibility_json=json.dumps(
                    {"source_type": content["source_type"]}
                ),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Save preset", str(exc))
            return
        self.state.status_line = f"Saved device preset “{name.strip()}”"
        self._status.setText(self.state.status_line)

    def _load_device_preset(self, source_id: str, form) -> None:
        import json

        from capture_protocol.config_schema import match_preset_to_schema

        src = next((s for s in self.state.sources if s.source_id == source_id), None)
        want_type = src.source_type if src else ""
        presets = self.persistence.registry.list_presets("device")
        if want_type:
            filtered = []
            for p in presets:
                try:
                    content = json.loads(p.get("content_json") or "{}")
                except json.JSONDecodeError:
                    continue
                if content.get("source_type") == want_type:
                    filtered.append(p)
            presets = filtered
        if not presets:
            QMessageBox.information(
                self,
                "Load preset",
                "No device presets saved yet"
                + (f" for source_type={want_type}." if want_type else "."),
            )
            return
        names = [f"{p['name']}  ({p['schema_version']})" for p in presets]
        choice, ok = QInputDialog.getItem(
            self, "Load device preset", "Preset:", names, 0, False
        )
        if not ok or not choice:
            return
        row = presets[names.index(choice)]
        try:
            content = json.loads(row["content_json"])
        except json.JSONDecodeError:
            QMessageBox.warning(self, "Load preset", "Preset content is not valid JSON.")
            return
        if not isinstance(content, dict):
            QMessageBox.warning(self, "Load preset", "Preset content must be an object.")
            return
        match = match_preset_to_schema(form.schema, content)
        if not match.ok:
            QMessageBox.warning(
                self,
                "Preset incompatible",
                "This preset does not match the device's current schema.\n\n"
                + "\n".join(match.errors),
            )
            return
        # Load into the form as dirty values; Apply pushes to the daemon.
        form.set_values(match.document, as_baseline=False)
        self.state.status_line = (
            f"Loaded preset “{row['name']}” into form — press Apply to send"
        )
        self._status.setText(self.state.status_line)

    def _sync_buttons(self) -> None:
        connected = self.state.connected
        recording = self.state.recording
        rehearse = self.state.rehearsal_active
        for btn in (
            self.btn_create,
            self.btn_open,
            self.btn_select,
            self.btn_preflight,
            self.btn_rescan,
            self.btn_rehearse,
            self.btn_start,
            self.btn_start_all,
        ):
            btn.setEnabled(connected and not recording)
        self.btn_stop_rehearse.setEnabled(connected and rehearse and not recording)
        for btn in (self.btn_checkpoint, self.btn_annotate, self.btn_sync):
            btn.setEnabled(connected and (recording or rehearse))
        self.btn_logs.setEnabled(True)
        self.btn_stop.setEnabled(connected and recording)
        state = self.state.session_state
        if state == control_pb2.SESSION_STATE_ARMING:
            self._rec_label.setText("ARMING…")
            self._rec_label.setStyleSheet(f"color: {theme.ACCENT.name()};")
        elif state == control_pb2.SESSION_STATE_STOPPING:
            self._rec_label.setText("STOPPING…")
            self._rec_label.setStyleSheet(f"color: {theme.ACCENT.name()};")
        elif recording:
            self._rec_label.setText("REC")
            self._rec_label.setStyleSheet(f"color: {theme.RED.name()};")
        elif rehearse:
            self._rec_label.setText("REHEARSE")
            self._rec_label.setStyleSheet(f"color: {theme.ACCENT.name()};")
        else:
            self._rec_label.setText("IDLE")
            self._rec_label.setStyleSheet(f"color: {theme.TEXT_FAINT.name()};")
        locked = state in (
            control_pb2.SESSION_STATE_RECORDING,
            control_pb2.SESSION_STATE_ARMING,
        )
        self.setup.set_locked(locked)
        # Review-mode packages must not start until CreateSession.
        if self.state.review_mode:
            self.btn_start.setEnabled(False)
            self.btn_start_all.setEnabled(False)
            self.btn_rehearse.setEnabled(False)

    def _refresh_ui(self) -> None:
        self._timer_label.setText(fmt_time(self.state.elapsed_s))
        self._status.setText(self.state.status_line)
        path = self.state.package_path or "—"
        self._session_label.setText(
            f"Session: {self.state.session_id or '—'}  ·  {self.state.session_state_name()}"
            f"  ·  {path}"
        )
        if self.state.package_path or self.state.session_id:
            self._session_header.refresh_live(self.state)
        elif not self.state.review_mode:
            self._session_header.clear()
        self.capture.refresh()

    def _refresh_session_header_sealed(self, package_path: str, *, recovered: bool) -> None:
        try:
            from capture_session import load_review_summary

            summary = load_review_summary(package_path)
            self._session_header.refresh_sealed(summary, recovered=recovered)
        except Exception:  # noqa: BLE001
            self._session_header.refresh_live(self.state)


def run_app(*, auto_connect: bool = True) -> int:
    import sys

    from capture_session.settings_store import SettingsStore
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    settings = SettingsStore()
    settings.load()
    theme.apply_theme(app, setting=str(settings.get("theme") or "system"))
    window = MainWindow(auto_connect=auto_connect)
    window.show()
    return app.exec()


# Re-export for tests
__all__ = ["MainWindow", "PreflightDialog", "run_app", "ControlClientError"]
