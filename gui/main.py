"""
MelkorS PS5 - Universal PlayStation 5 Runtime & Execution Control Center
Native PKG package detection, metadata parsing, icon extraction, and 1-click PKG installer integration.
"""

import sys
import os
import json
import shutil
import psutil
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTabWidget, QListWidget, QListWidgetItem,
    QTextEdit, QComboBox, QCheckBox, QGroupBox, QFileDialog,
    QMessageBox, QProgressBar, QSplitter, QFrame, QScrollArea, QDialog,
    QSlider
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize, QProcess
from PyQt6.QtGui import QFont, QTextCursor, QPixmap, QIcon

from theme import PS5_STYLESHEET
from game_scanner import GameScanner, PS5Game
from process_runner import ProcessRunner
from log_analyzer import LogAnalyzer
from translations import TRANSLATIONS
from controller_manager import ControllerManager
from game_overlay import GameOverlayBar
from patch_manager import PatchManager

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.abspath(os.path.dirname(sys.executable))
else:
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GAMES_DIR = os.path.join(BASE_DIR, "games")
EMULATOR_DIR = os.path.join(BASE_DIR, "emulator")
DATA_DIR = os.path.join(BASE_DIR, "data")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
TOOLS_DIR = os.path.join(BASE_DIR, "tools")

# MelkorS engine executables (fully rebranded)
PS5_CORE_EXE = os.path.join(EMULATOR_DIR, "melkors_ps5_core.exe")
PS4_CORE_EXE = os.path.join(EMULATOR_DIR, "melkors_ps4_core.exe")
CORE_EXE = PS5_CORE_EXE
PKG_INSTALLER_EXE = os.path.join(EMULATOR_DIR, "melkors_pkg_installer.exe")


class DiagnosisDialog(QDialog):
    def __init__(self, report: dict, lang: str = "tr", parent=None):
        super().__init__(parent)
        self.t = TRANSLATIONS.get(lang, TRANSLATIONS["tr"])
        self.setWindowTitle(self.t["diag_title"])
        self.resize(720, 520)
        self.setStyleSheet(PS5_STYLESHEET)

        layout = QVBoxLayout(self)

        title = QLabel(f"👁️ {self.t['diag_header']}")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #58a6ff; letter-spacing: 1px;")
        layout.addWidget(title)

        status_text = self.t["diag_detected"] if report.get("crashed") else self.t["diag_clear"]
        status_color = "#f85149" if report.get("crashed") else "#58a6ff"
        lbl_status = QLabel(f"<b>Durum:</b> <span style='color: {status_color}; font-weight: bold;'>{status_text}</span>")
        layout.addWidget(lbl_status)

        lbl_cause = QLabel(f"<b>{self.t['diag_root_cause']}</b> <span style='color: #79c0ff;'>{report.get('root_cause')}</span>")
        lbl_cause.setWordWrap(True)
        layout.addWidget(lbl_cause)

        lbl_category = QLabel(f"<b>{self.t['diag_category']}</b> <code style='color: #58a6ff;'>{report.get('category')}</code>")
        layout.addWidget(lbl_category)

        rec_box = QGroupBox(self.t["diag_rec_box"])
        rec_layout = QVBoxLayout(rec_box)
        rec_label = QLabel(report.get("recommended_action", "Bilinmiyor"))
        rec_label.setWordWrap(True)
        rec_label.setStyleSheet("color: #7ee787; font-size: 13px; line-height: 1.4;")
        rec_layout.addWidget(rec_label)
        layout.addWidget(rec_box)

        layout.addWidget(QLabel(f"<b>{self.t['diag_suspicious']}</b>"))
        log_box = QTextEdit()
        log_box.setReadOnly(True)
        lines = report.get("suspicious_lines", [])
        if lines:
            log_box.setText("\n".join(lines))
        else:
            log_box.setText("Şüpheli satır kaydedilmedi.")
        layout.addWidget(log_box)

        btn_close = QPushButton(self.t["close"])
        btn_close.setObjectName("primaryBtn")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

class MelkorSWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.load_config()
        self.lang = self.config.get("language", "tr")
        self.t = TRANSLATIONS.get(self.lang, TRANSLATIONS["tr"])

        self.setWindowTitle("MelkorS PS5")
        self.resize(1180, 780)
        self.setStyleSheet(PS5_STYLESHEET)

        self.scanner = GameScanner(GAMES_DIR)
        self.runner = ProcessRunner(LOGS_DIR)
        self.controller_mgr = ControllerManager()
        self.selected_game = None

        # In-game floating overlay bar
        self.overlay = GameOverlayBar(None)
        self.overlay.return_requested.connect(self.focus_launcher)
        self.overlay.stop_game_requested.connect(self.stop_current_game)

        self.init_ui()
        self.setup_signals()
        self.refresh_games()
        self.refresh_controller_status()

        # Telemetry Timer
        self.telemetry_timer = QTimer(self)
        self.telemetry_timer.timeout.connect(self.update_telemetry)
        self.telemetry_timer.start(1500)

        # Log flush buffer: collect log lines and flush to QTextEdit every 50ms
        # This prevents thousands of individual insertHtml() calls from freezing the GUI
        self._pending_log_lines = []
        self._log_flush_timer = QTimer(self)
        self._log_flush_timer.setInterval(50)
        self._log_flush_timer.timeout.connect(self._flush_log_buffer)
        self._log_flush_timer.start()
        self._MAX_LOG_LINES = 2000  # keep at most this many lines in console

    def load_config(self):
        self.config = {
            "emulator_exe": CORE_EXE,
            "resolution": "1080p (Native)",
            "vsync": True,
            "pipeline_cache": True,
            "verbose_logging": True,
            "jit_optimization": True,
            "audio_backend": "XAudio2 / WASAPI",
            "language": "tr",
            "deadzone": 10,
            "shader_opt": "Performance",
            "present_mode": "Immediate",
            "vblank_hz": "60",
            "readback_bypass": True
        }
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    self.config.update(json.load(f))
            except Exception:
                pass
        # Always force engine path to our emulator/ dir
        self.config["emulator_exe"] = CORE_EXE

    def save_config(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Ayar dosyası kaydedilemedi: {e}")

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 12, 15, 12)
        main_layout.setSpacing(12)

        # Header
        header_layout = QHBoxLayout()
        title_label = QLabel("👁️ MELKORS PS5")
        title_label.setFont(QFont("Segoe UI", 19, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #ff5500; letter-spacing: 2px;")
        header_layout.addWidget(title_label)

        self.sub_label = QLabel(self.t["subtitle"])
        self.sub_label.setStyleSheet("color: #8b9cb4; font-size: 13px; margin-left: 10px; font-weight: 500;")
        header_layout.addWidget(self.sub_label)
        header_layout.addStretch()

        # Language Selector
        self.combo_lang = QComboBox()
        self.combo_lang.addItems(["Türkçe", "English"])
        self.combo_lang.setCurrentText("Türkçe" if self.lang == "tr" else "English")
        self.combo_lang.currentIndexChanged.connect(self.on_language_changed)
        header_layout.addWidget(self.combo_lang)

        # Core Badge
        self.core_status_badge = QLabel("⚡ " + self.t["core_ready"])
        self.core_status_badge.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #002147, stop:1 #003875);"
            "color: #ffffff; padding: 5px 14px; border-radius: 5px; font-weight: bold; border: 1px solid #1f6feb;"
        )
        header_layout.addWidget(self.core_status_badge)
        main_layout.addLayout(header_layout)

        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.tab_library = QWidget()
        self.tab_debug = QWidget()
        self.tab_controller = QWidget()
        self.tab_settings = QWidget()
        self.tab_modules = QWidget()

        self.tabs.addTab(self.tab_library, self.t["tab_library"])
        self.tabs.addTab(self.tab_controller, self.t["tab_controller"])
        self.tabs.addTab(self.tab_settings, self.t["tab_settings"])
        self.tabs.addTab(self.tab_debug, self.t["tab_debug"])
        # Sistem Modülleri sekmesi kullanıcı arayüzünden gizlendi

        self.init_tab_library()
        self.init_tab_controller()
        self.init_tab_settings()
        self.init_tab_debug()
        self.init_tab_modules()

        # Footer
        footer_layout = QHBoxLayout()
        self.status_msg = QLabel(self.t["status_ready"])
        self.status_msg.setStyleSheet("color: #8b9cb4;")
        footer_layout.addWidget(self.status_msg)
        footer_layout.addStretch()

        self.cpu_label = QLabel("CPU: 0%")
        self.cpu_label.setStyleSheet("color: #58a6ff; font-weight: bold;")
        footer_layout.addWidget(self.cpu_label)

        self.ram_label = QLabel("RAM: 0%")
        self.ram_label.setStyleSheet("color: #79c0ff; font-weight: bold; margin-left: 14px;")
        footer_layout.addWidget(self.ram_label)

        main_layout.addLayout(footer_layout)

    # --- TAB 1: Library ---
    def init_tab_library(self):
        layout = QVBoxLayout(self.tab_library)

        top_bar = QHBoxLayout()
        self.btn_refresh = QPushButton(self.t["refresh_lib"])
        self.btn_refresh.clicked.connect(self.refresh_games)
        top_bar.addWidget(self.btn_refresh)

        self.btn_add = QPushButton(self.t["scan_folder"])
        self.btn_add.clicked.connect(self.import_game_folder)
        top_bar.addWidget(self.btn_add)

        self.btn_open_games = QPushButton(self.t["open_games"])
        self.btn_open_games.clicked.connect(lambda: os.startfile(GAMES_DIR) if os.path.exists(GAMES_DIR) else None)
        top_bar.addWidget(self.btn_open_games)

        top_bar.addStretch()
        layout.addLayout(top_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.games_list = QListWidget()
        self.games_list.setIconSize(QSize(48, 48))
        self.games_list.itemClicked.connect(self.on_game_selected)
        splitter.addWidget(self.games_list)

        self.details_widget = QWidget()
        details_layout = QVBoxLayout(self.details_widget)
        details_layout.setContentsMargins(15, 10, 10, 10)

        # Cover banner & icon layout
        self.cover_row = QHBoxLayout()
        self.lbl_cover = QLabel()
        self.lbl_cover.setFixedSize(128, 128)
        self.lbl_cover.setScaledContents(True)
        self.lbl_cover.setStyleSheet("border: 2px solid #1f6feb; border-radius: 10px; background: #0c1320;")
        self.cover_row.addWidget(self.lbl_cover)

        title_box = QVBoxLayout()
        self.detail_title = QLabel(self.t["select_game"])
        self.detail_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.detail_title.setStyleSheet("color: #58a6ff;")
        title_box.addWidget(self.detail_title)

        self.detail_info = QLabel(self.t["game_details_placeholder"])
        self.detail_info.setStyleSheet("color: #c9d1d9; line-height: 1.5; font-size: 13px;")
        self.detail_info.setWordWrap(True)
        title_box.addWidget(self.detail_info)

        self.cover_row.addLayout(title_box)
        self.cover_row.addStretch()
        details_layout.addLayout(self.cover_row)

        details_layout.addStretch()

        actions_box = QHBoxLayout()
        self.btn_launch = QPushButton(self.t["launch_game"])
        self.btn_launch.setObjectName("primaryBtn")
        self.btn_launch.setFixedHeight(44)
        self.btn_launch.setEnabled(False)
        self.btn_launch.clicked.connect(self.launch_selected_game)
        actions_box.addWidget(self.btn_launch)

        self.btn_extract = QPushButton("📦 PKG Paketini Kur / Ayıkla")
        self.btn_extract.setObjectName("primaryBtn")
        self.btn_extract.setFixedHeight(44)
        self.btn_extract.setVisible(False)
        self.btn_extract.clicked.connect(self.extract_selected_pkg)
        actions_box.addWidget(self.btn_extract)

        self.btn_auto_patch = QPushButton(self.t["auto_patch_btn"])
        self.btn_auto_patch.setObjectName("secondaryBtn")
        self.btn_auto_patch.setFixedHeight(44)
        self.btn_auto_patch.setVisible(False)
        self.btn_auto_patch.setToolTip(self.t["auto_patch_tooltip"])
        self.btn_auto_patch.clicked.connect(self.scan_and_patch_selected_game)
        actions_box.addWidget(self.btn_auto_patch)

        self.btn_remove_patch = QPushButton(self.t["remove_patch_btn"])
        self.btn_remove_patch.setObjectName("secondaryBtn")
        self.btn_remove_patch.setFixedHeight(44)
        self.btn_remove_patch.setVisible(False)
        self.btn_remove_patch.setToolTip(self.t["remove_patch_tooltip"])
        self.btn_remove_patch.clicked.connect(self.remove_patch_selected_game)
        actions_box.addWidget(self.btn_remove_patch)

        self.btn_stop = QPushButton(self.t["stop_game"])
        self.btn_stop.setObjectName("stopBtn")
        self.btn_stop.setFixedHeight(44)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_current_game)
        actions_box.addWidget(self.btn_stop)

        details_layout.addLayout(actions_box)
        splitter.addWidget(self.details_widget)
        splitter.setSizes([450, 600])

        layout.addWidget(splitter)

    # --- TAB 2: Debugger ---
    def init_tab_debug(self):
        layout = QVBoxLayout(self.tab_debug)

        bar = QHBoxLayout()
        self.lbl_filter = QLabel(self.t["filter"])
        bar.addWidget(self.lbl_filter)

        self.combo_filter = QComboBox()
        self.combo_filter.addItems([
            self.t["filter_all"], self.t["filter_err"], self.t["filter_warn"],
            self.t["filter_gpu"], self.t["filter_sys"]
        ])
        self.combo_filter.currentTextChanged.connect(self.apply_log_filter)
        bar.addWidget(self.combo_filter)

        self.btn_diagnose = QPushButton(self.t["auto_diagnose"])
        self.btn_diagnose.setObjectName("primaryBtn")
        self.btn_diagnose.clicked.connect(self.run_auto_diagnosis)
        bar.addWidget(self.btn_diagnose)

        bar.addStretch()

        self.btn_clear = QPushButton(self.t["clear_logs"])
        self.btn_clear.clicked.connect(self.clear_logs)
        bar.addWidget(self.btn_clear)

        self.btn_open_logs = QPushButton(self.t["open_logs"])
        self.btn_open_logs.clicked.connect(lambda: os.startfile(LOGS_DIR) if os.path.exists(LOGS_DIR) else None)
        bar.addWidget(self.btn_open_logs)

        layout.addLayout(bar)

        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        layout.addWidget(self.log_console)

        self.all_log_lines = []

    # --- TAB 3: Controller Settings ---
    def init_tab_controller(self):
        layout = QVBoxLayout(self.tab_controller)

        box_ctrl = QGroupBox(self.t["controller_box_title"])
        c_layout = QVBoxLayout(box_ctrl)

        self.lbl_ctrl_status = QLabel(self.t["controller_status_none"])
        self.lbl_ctrl_status.setStyleSheet("color: #58a6ff; font-weight: bold; font-size: 14px; padding: 6px 0;")
        c_layout.addWidget(self.lbl_ctrl_status)

        row_api = QHBoxLayout()
        row_api.addWidget(QLabel(self.t["controller_type"]))
        self.combo_input_api = QComboBox()
        self.combo_input_api.addItems([
            "XInput (Xbox 360 / Xbox One / PS4 / PS5 Generic Mapper)",
            "DualSense Native (Direct USB / Bluetooth libScePad Mode)",
            "DirectInput (Classic Gamepad Mode)"
        ])
        row_api.addWidget(self.combo_input_api)
        c_layout.addLayout(row_api)

        row_dead = QHBoxLayout()
        row_dead.addWidget(QLabel(self.t["deadzone_label"]))
        self.slider_deadzone = QSlider(Qt.Orientation.Horizontal)
        self.slider_deadzone.setRange(0, 30)
        self.slider_deadzone.setValue(self.config.get("deadzone", 10))
        self.slider_deadzone.valueChanged.connect(self.on_deadzone_changed)
        self.lbl_deadzone_val = QLabel(f"{self.slider_deadzone.value()}%")
        self.lbl_deadzone_val.setStyleSheet("color: #58a6ff; font-weight: bold;")
        row_dead.addWidget(self.slider_deadzone)
        row_dead.addWidget(self.lbl_deadzone_val)
        c_layout.addLayout(row_dead)

        btn_vibe = QPushButton(self.t["test_vibration"])
        btn_vibe.setObjectName("primaryBtn")
        btn_vibe.clicked.connect(self.test_controller_vibration)
        c_layout.addWidget(btn_vibe)

        layout.addWidget(box_ctrl)

        box_layout_preview = QGroupBox("🎮 PlayStation 5 DualSense Kontrol Şeması (Controller Layout)")
        prev_layout = QVBoxLayout(box_layout_preview)
        mapping_desc = QLabel(
            "• <b>Kare (Square):</b> XInput: X | Eylem 1 (Action 1 / Attack / Reload)<br>"
            "• <b>Üçgen (Triangle):</b> XInput: Y | Eylem 2 (Action 2 / Secondary / Switch)<br>"
            "• <b>Çarpı (Cross):</b> XInput: A | Onay / Zıplama / Etkileşim (Confirm / Jump / Interact)<br>"
            "• <b>Daire (Circle):</b> XInput: B | İptal / Eğilme / Kaçınma (Cancel / Crouch / Dodge)<br>"
            "• <b>L1 / R1:</b> XInput: LB / RB | Sol / Sağ Üst Tamponlar (Bumper / Shoulder Buttons)<br>"
            "• <b>L2 / R2:</b> XInput: LT / RT | Analog Tetikler (Nişan Alma & Ateş / Gaz & Fren)<br>"
            "• <b>L3 / R3:</b> Sol / Sağ Analog Tıklama (Sprint / Yakın Dövüş / Kamera Sıfırlama)<br>"
            "• <b>D-Pad & Analoglar:</b> Yön Tuşları, Envanter / Karakter Hareketi ve Kamera Kontrolü<br>"
            "• <b>Options & Create:</b> Duraklat / Oyun Menüsü ve Paylaşım Tuşları"
        )
        mapping_desc.setStyleSheet("color: #c9d1d9; line-height: 1.6;")
        prev_layout.addWidget(mapping_desc)
        layout.addWidget(box_layout_preview)

        layout.addStretch()

    # --- TAB 4: Engine Settings ---
    def init_tab_settings(self):
        layout = QVBoxLayout(self.tab_settings)

        self.box_engine = QGroupBox(self.t["core_box_title"])
        engine_layout = QVBoxLayout(self.box_engine)

        row_info1 = QHBoxLayout()
        row_info1.addWidget(QLabel(self.t["arch_label"]))
        self.lbl_arch = QLabel(self.t["arch_val"])
        self.lbl_arch.setStyleSheet("color: #58a6ff; font-weight: bold;")
        row_info1.addWidget(self.lbl_arch)
        row_info1.addStretch()
        engine_layout.addLayout(row_info1)

        row_info2 = QHBoxLayout()
        row_info2.addWidget(QLabel(self.t["gpu_label"]))
        self.lbl_gpu_drv = QLabel(self.t["gpu_val"])
        self.lbl_gpu_drv.setStyleSheet("color: #79c0ff; font-weight: bold;")
        row_info2.addWidget(self.lbl_gpu_drv)
        row_info2.addStretch()
        engine_layout.addLayout(row_info2)

        self.chk_jit = QCheckBox(self.t["jit_opt"])
        self.chk_jit.setChecked(self.config.get("jit_optimization", True))
        engine_layout.addWidget(self.chk_jit)

        self.chk_verbose = QCheckBox(self.t["verbose_opt"])
        self.chk_verbose.setChecked(self.config.get("verbose_logging", True))
        engine_layout.addWidget(self.chk_verbose)

        layout.addWidget(self.box_engine)

        self.box_gfx = QGroupBox(self.t["gfx_box_title"])
        box_layout = QVBoxLayout(self.box_gfx)

        row_res = QHBoxLayout()
        row_res.addWidget(QLabel(self.t["res_label"]))
        self.combo_res = QComboBox()
        self.combo_res.addItems(["720p (Performans)", "1080p (Native)", "1440p (2K)", "2160p (4K UHD)"])
        self.combo_res.setCurrentText(self.config.get("resolution", "1080p (Native)"))
        row_res.addWidget(self.combo_res)
        box_layout.addLayout(row_res)

        # Shader Optimization Level
        row_shader = QHBoxLayout()
        row_shader.addWidget(QLabel(self.t["shader_opt_label"]))
        self.combo_shader_opt = QComboBox()
        self.combo_shader_opt.addItems(["Performance (Maksimum FPS)", "Size (Dengeli)", "None (Kapalı)"])
        cur_opt = self.config.get("shader_opt", "Performance")
        if cur_opt == "Performance":
            self.combo_shader_opt.setCurrentIndex(0)
        elif cur_opt == "Size":
            self.combo_shader_opt.setCurrentIndex(1)
        else:
            self.combo_shader_opt.setCurrentIndex(2)
        row_shader.addWidget(self.combo_shader_opt)
        box_layout.addLayout(row_shader)

        # Present Mode
        row_present = QHBoxLayout()
        row_present.addWidget(QLabel(self.t["present_mode_label"]))
        self.combo_present_mode = QComboBox()
        self.combo_present_mode.addItems([
            "Immediate (V-Sync Kapalı / En Yüksek FPS)",
            "Mailbox (Düşük Gecikmeli Tampon)",
            "Fifo (Standart V-Sync 60 FPS Kilidi)"
        ])
        cur_present = self.config.get("present_mode", "Immediate")
        if cur_present == "Immediate":
            self.combo_present_mode.setCurrentIndex(0)
        elif cur_present == "Mailbox":
            self.combo_present_mode.setCurrentIndex(1)
        else:
            self.combo_present_mode.setCurrentIndex(2)
        row_present.addWidget(self.combo_present_mode)
        box_layout.addLayout(row_present)

        # VBlank / Refresh Rate
        row_vblank = QHBoxLayout()
        row_vblank.addWidget(QLabel(self.t["vblank_label"]))
        self.combo_vblank = QComboBox()
        self.combo_vblank.addItems(["60 Hz (Standart)", "120 Hz (Yüksek Akıcılık)", "144 Hz (Pro)", "30 Hz (Tasarruf)"])
        cur_vblank = str(self.config.get("vblank_hz", "60"))
        vblank_idx = {"60": 0, "120": 1, "144": 2, "30": 3}.get(cur_vblank, 0)
        self.combo_vblank.setCurrentIndex(vblank_idx)
        row_vblank.addWidget(self.combo_vblank)
        box_layout.addLayout(row_vblank)

        # Readback Bypass
        self.chk_readback = QCheckBox(self.t["readback_bypass"])
        self.chk_readback.setChecked(self.config.get("readback_bypass", True))
        box_layout.addWidget(self.chk_readback)

        self.chk_vsync = QCheckBox(self.t["vsync"])
        self.chk_vsync.setChecked(self.config.get("vsync", False))
        box_layout.addWidget(self.chk_vsync)

        self.chk_cache = QCheckBox(self.t["shader_cache"])
        self.chk_cache.setChecked(self.config.get("pipeline_cache", True))
        box_layout.addWidget(self.chk_cache)

        # 1-Click Ultra Performance Profile button
        self.btn_ultra_perf = QPushButton(self.t["ultra_perf_btn"])
        self.btn_ultra_perf.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff4500, stop:1 #ff8c00);"
            "color: white; font-weight: bold; font-size: 13px; padding: 10px; border-radius: 6px; margin: 6px 0;"
        )
        self.btn_ultra_perf.clicked.connect(self.apply_ultra_performance_preset)
        box_layout.addWidget(self.btn_ultra_perf)

        layout.addWidget(self.box_gfx)

        self.btn_save = QPushButton(self.t["save_settings"])
        self.btn_save.setObjectName("primaryBtn")
        self.btn_save.clicked.connect(self.on_save_settings_clicked)
        layout.addWidget(self.btn_save)

        layout.addStretch()

    # --- TAB 5: Modules ---
    def init_tab_modules(self):
        layout = QVBoxLayout(self.tab_modules)

        self.lbl_desc_modules = QLabel(self.t["module_desc"])
        self.lbl_desc_modules.setStyleSheet("color: #8b9cb4; line-height: 1.4;")
        layout.addWidget(self.lbl_desc_modules)

        self.box_modules = QGroupBox(self.t["module_box_title"])
        mod_layout = QVBoxLayout(self.box_modules)

        self.module_labels = {}
        target_modules = [
            ("libSceAgc.sprx", "PS5 Donanım Grafik Arayüzü (RDNA AGC)"),
            ("libSceAgcDriver.sprx", "PS5 GPU Komut Kuyruğu ve Sürücü Katmanı"),
            ("libSceAmpr.sprx", "Gelişmiş Bellek & Resource Yönetimi"),
            ("libScePlayGo.sprx", "Akışkan Veri ve Paket Yükleyici"),
            ("libScePsml.sprx", "PS5 Shader ve Model Çevirici"),
        ]

        for mod_name, desc in target_modules:
            h = QHBoxLayout()
            lbl = QLabel(f"• {mod_name} - {desc}")
            lbl.setStyleSheet("color: #e6edf3;")
            status = QLabel("Checking...")
            status.setStyleSheet("color: #58a6ff; font-weight: bold;")
            h.addWidget(lbl)
            h.addStretch()
            h.addWidget(status)
            mod_layout.addLayout(h)
            self.module_labels[mod_name] = status

        layout.addWidget(self.box_modules)

        self.btn_check_modules = QPushButton(self.t["verify_modules"])
        self.btn_check_modules.setObjectName("primaryBtn")
        self.btn_check_modules.clicked.connect(self.verify_and_repair_modules)
        layout.addWidget(self.btn_check_modules)

        layout.addStretch()

    def setup_signals(self):
        self.runner.log_received.connect(self.on_log_received)
        self.runner.process_started.connect(self.on_process_started)
        self.runner.process_finished.connect(self.on_process_finished)

    def on_language_changed(self):
        new_lang = "tr" if self.combo_lang.currentText() == "Türkçe" else "en"
        self.lang = new_lang
        self.config["language"] = new_lang
        self.save_config()
        self.t = TRANSLATIONS.get(new_lang, TRANSLATIONS["tr"])
        self.update_ui_texts()

    def update_ui_texts(self):
        self.sub_label.setText(self.t["subtitle"])
        self.core_status_badge.setText("⚡ " + self.t["core_ready"])
        self.tabs.setTabText(0, self.t["tab_library"])
        self.tabs.setTabText(1, self.t["tab_controller"])
        self.tabs.setTabText(2, self.t["tab_settings"])
        self.tabs.setTabText(3, self.t["tab_debug"])

        self.btn_refresh.setText(self.t["refresh_lib"])
        self.btn_add.setText(self.t["scan_folder"])
        self.btn_open_games.setText(self.t["open_games"])
        self.btn_launch.setText(self.t["launch_game"])
        self.btn_stop.setText(self.t["stop_game"])
        self.btn_auto_patch.setText(self.t["auto_patch_btn"])
        self.btn_auto_patch.setToolTip(self.t["auto_patch_tooltip"])
        self.btn_remove_patch.setText(self.t["remove_patch_btn"])
        self.btn_remove_patch.setToolTip(self.t["remove_patch_tooltip"])
        self.btn_diagnose.setText(self.t["auto_diagnose"])
        self.btn_clear.setText(self.t["clear_logs"])
        self.btn_open_logs.setText(self.t["open_logs"])
        self.btn_save.setText(self.t["save_settings"])
        self.btn_check_modules.setText(self.t["verify_modules"])

        self.box_engine.setTitle(self.t["core_box_title"])
        self.lbl_arch.setText(self.t["arch_val"])
        self.lbl_gpu_drv.setText(self.t["gpu_val"])
        self.chk_jit.setText(self.t["jit_opt"])
        self.chk_verbose.setText(self.t["verbose_opt"])
        self.box_gfx.setTitle(self.t["gfx_box_title"])
        self.chk_vsync.setText(self.t["vsync"])
        self.chk_cache.setText(self.t["shader_cache"])
        self.box_modules.setTitle(self.t["module_box_title"])
        self.lbl_desc_modules.setText(self.t["module_desc"])

    def refresh_controller_status(self):
        connected = self.controller_mgr.get_connected_controllers()
        if connected:
            self.lbl_ctrl_status.setText(f"✔ DualSense / XInput Uyumlu Kontrollör Bağlı (Port {connected[0]})")
            self.lbl_ctrl_status.setStyleSheet("color: #58a6ff; font-weight: bold; font-size: 14px;")
        else:
            self.lbl_ctrl_status.setText("Oyun Kolu Aranıyor (USB / Bluetooth XInput bekleniyor)...")
            self.lbl_ctrl_status.setStyleSheet("color: #7a889b; font-weight: bold; font-size: 14px;")

    def on_deadzone_changed(self, value):
        self.lbl_deadzone_val.setText(f"{value}%")
        self.config["deadzone"] = value
        self.save_config()

    def test_controller_vibration(self):
        ok = self.controller_mgr.test_vibration(0, 600)
        if ok:
            QMessageBox.information(self, "Titreşim Testi", "Titreşim motorları başarıyla tetiklendi!")
        else:
            QMessageBox.warning(self, "Uyarı", "Bağlı aktif XInput gamepad bulunamadı. Lütfen kolunuzu USB/Bluetooth ile bağlayın.")

    def refresh_games(self):
        self.games_list.clear()
        games = self.scanner.scan()

        if not games:
            item = QListWidgetItem("Henüz oyun eklenmedi (games/ klasörüne atın)")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.games_list.addItem(item)
            self.btn_launch.setEnabled(False)
            self.btn_extract.setVisible(False)
            self.lbl_cover.setVisible(False)
            return

        for game in games:
            item = QListWidgetItem(f"{game.title_name} [{game.title_id}]")
            if game.icon_path and os.path.exists(game.icon_path):
                item.setIcon(QIcon(game.icon_path))
            item.setData(Qt.ItemDataRole.UserRole, game)
            self.games_list.addItem(item)

        self.games_list.setCurrentRow(0)
        self.on_game_selected(self.games_list.item(0))

    def on_game_selected(self, item):
        game: PS5Game = item.data(Qt.ItemDataRole.UserRole)
        if not game:
            return
        self.selected_game = game
        self.detail_title.setText(game.title_name)

        # Set cover icon if available
        if game.icon_path and os.path.exists(game.icon_path):
            pixmap = QPixmap(game.icon_path)
            if not pixmap.isNull():
                self.lbl_cover.setPixmap(pixmap.scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                self.lbl_cover.setVisible(True)
            else:
                self.lbl_cover.setVisible(False)
        else:
            self.lbl_cover.setVisible(False)

        # Check for active XML/JSON patch
        pm = PatchManager(BASE_DIR)
        patch_file = pm.find_patch_for_title(game.title_id)
        if patch_file:
            patch_name = os.path.basename(patch_file)
            patch_status_html = f"<br><b>{self.t.get('patch_label', 'Yama Durumu:')}</b> <span style='color: #2ea44f; font-weight: bold;'>{self.t.get('patch_status_active', '🛡️ Aktif')} ({patch_name})</span>"
        else:
            patch_status_html = f"<br><b>{self.t.get('patch_label', 'Yama Durumu:')}</b> <span style='color: #8b949e;'>{self.t.get('patch_status_none', 'Yama yok')}</span>"

        status_color = "#58a6ff" if (game.has_fakelib or game.is_pkg) else "#f85149"
        info_text = (
            f"<b>Title ID:</b> {game.title_id}<br>"
            f"<b>Sürüm:</b> {game.version}<br>"
            f"<b>Durum:</b> <span style='color: {status_color}; font-weight: bold;'>{game.status}</span>"
            f"{patch_status_html}<br>"
            f"<b>Dosya/Klasör:</b> {game.folder_path}"
        )
        self.detail_info.setText(info_text)

        if game.is_pkg:
            self.btn_launch.setEnabled(False)
            self.btn_extract.setVisible(True)
            self.btn_extract.setEnabled(True)
            self.btn_auto_patch.setVisible(False)
            self.btn_remove_patch.setVisible(False)
        else:
            self.btn_launch.setEnabled(True)
            self.btn_extract.setVisible(False)
            self.btn_auto_patch.setVisible(True)
            self.btn_auto_patch.setEnabled(True)
            has_patch = bool(patch_file)
            has_backup = bool(game.eboot_path and (os.path.exists(game.eboot_path + ".orig") or os.path.exists(game.eboot_path + ".bak")))
            self.btn_remove_patch.setVisible(has_patch or has_backup)
            self.btn_remove_patch.setEnabled(has_patch or has_backup)
            self.update_modules_tab_for_game(game)

    def remove_patch_selected_game(self):
        """Removes active patch for selected game and restores eboot backup if available."""
        if not self.selected_game:
            return

        game = self.selected_game
        confirm_title = self.t.get("patch_remove_confirm_title", "Yamayı Kaldır")
        confirm_msg = self.t.get("patch_remove_confirm_msg", "'{name}' ({id}) için uygulanan tüm yamaları kaldırmak ve varsa orijinal eboot.bin yedeğini geri yüklemek istiyor musunuz?").format(name=game.title_name, id=game.title_id)
        confirm = QMessageBox.question(
            self,
            confirm_title,
            confirm_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        pm = PatchManager(BASE_DIR)
        res = pm.remove_patch_for_title(game.title_id, game.eboot_path)

        details = []
        if res.get("files_deleted"):
            prefix = self.t.get("patch_removed_files", "Silinen yama dosyaları:")
            details.append(f"{prefix} {', '.join(res['files_deleted'])}")
        if res.get("backup_restored"):
            details.append(self.t.get("patch_restored_backup", "Orijinal eboot.bin yedeği geri yüklendi."))

        title = self.t.get("patch_removed_title", "Yama Kaldırıldı")
        if details:
            msg = self.t.get("patch_removed_success", "Yama başarıyla kaldırıldı!") + "\n\n" + "\n".join(details)
        else:
            msg = self.t.get("patch_status_none", "Yama yok")

        QMessageBox.information(self, title, msg)

        # Refresh UI
        if self.games_list.currentItem():
            self.on_game_selected(self.games_list.currentItem())

    def scan_and_patch_selected_game(self):
        """Scans the selected game for UE5 crash patterns and generates an auto-patch file."""
        if not self.selected_game or self.selected_game.is_pkg:
            return

        game = self.selected_game
        eboot_path = game.eboot_path
        if not eboot_path or not os.path.exists(eboot_path):
            QMessageBox.warning(self, "Uyarı", f"Oyun eboot.bin dosyası bulunamadı:\n{eboot_path}")
            return

        self.btn_auto_patch.setEnabled(False)
        self.btn_auto_patch.setText("⏳ ...")
        QApplication.processEvents()

        try:
            from tools.ue5_patch_scanner import UE5PatchScanner
            scanner = UE5PatchScanner(eboot_path, title_id=game.title_id, app_ver=game.version or "01.000.000")
            patches = scanner.scan_all()

            patches_dir = os.path.join(BASE_DIR, "patches")
            json_out = os.path.join(patches_dir, f"{game.title_id}.json")
            xml_out = os.path.join(patches_dir, f"{game.title_id}.xml")
            scanner.export_json(json_out)
            scanner.export_xml(xml_out)

            title = self.t.get("patch_scan_complete_title", "Yama Oluşturuldu")
            msg = self.t.get(
                "patch_scan_complete_msg",
                "UE5 Motor Taraması Başarıyla Tamamlandı!\n\nToplam {count} adet motor çökme açığı tespit edildi.\n\nOluşturulan Yamalar:\n• {json} (MelkorS / GoldHEN Mod)\n• {xml} (shadPS4 XML Mod)\n\nBu yamalar oyun başlatılırken MelkorS Core tarafından bellek üzerinde otomatik olarak uygulanacaktır."
            ).format(count=len(patches), json=os.path.basename(json_out), xml=os.path.basename(xml_out))

            QMessageBox.information(self, title, msg)

            # Refresh details UI
            if self.games_list.currentItem():
                self.on_game_selected(self.games_list.currentItem())

        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Yama taraması sırasında hata oluştu:\n{e}")
        finally:
            self.btn_auto_patch.setEnabled(True)
            self.btn_auto_patch.setText(self.t.get("auto_patch_btn", "⚡ UE5 Yama Tara / Oluştur"))

    def extract_selected_pkg(self):
        if not self.selected_game or not self.selected_game.is_pkg:
            return

        pkg_path = self.selected_game.folder_path

        if not os.path.exists(CORE_EXE):
            QMessageBox.critical(self, "Hata",
                                 "MelkorS çekirdek modülü bulunamadı.\n"
                                 f"Beklenen konum: {CORE_EXE}")
            return

        reply = QMessageBox.question(
            self, "PKG Kurulum",
            f"<b>{self.selected_game.title_name}</b> kurulsun mu?<br><br>"
            f"Kurulum MelkorS içinde gerçekleştirilecek.<br>"
            f"İlerlemeyi <b>Canlı Log</b> sekmesinden takip edebilirsin.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.No:
            return

        # Switch to log tab so user can watch installation progress
        self.tabs.setCurrentWidget(self.tab_debug)
        self.status_msg.setText(f"⚙️ {self.selected_game.title_name} kuruluyor...")
        self.btn_extract.setEnabled(False)
        self.btn_launch.setEnabled(False)
        self.btn_stop.setEnabled(True)

        # Install via MelkorS Core — no external window, streams to log
        self.runner.install_pkg(CORE_EXE, pkg_path, DATA_DIR)

    def _on_installer_finished(self, exit_code: int):
        """Called when PKG install process completes (via on_process_finished)."""
        self.btn_extract.setEnabled(True)
        self.status_msg.setText("🔄 Oyun kütüphanesi güncelleniyor...")
        self.refresh_games()
        if self.selected_game:
            for i in range(self.games_list.count()):
                item = self.games_list.item(i)
                g = item.data(Qt.ItemDataRole.UserRole)
                if g and g.title_id == self.selected_game.title_id and not g.is_pkg:
                    self.status_msg.setText(f"✅ {g.title_name} başarıyla kuruldu!")
                    return
        self.status_msg.setText("✅ Kurulum tamamlandı. Kütüphane güncellendi.")

    def update_modules_tab_for_game(self, game: PS5Game):
        if game.is_pkg:
            return
        fakelib_dir = os.path.join(game.folder_path, "fakelib")
        for mod_name, label in self.module_labels.items():
            mod_path = os.path.join(fakelib_dir, mod_name)
            if os.path.exists(mod_path):
                label.setText("✔ MEVCUT")
                label.setStyleSheet("color: #58a6ff; font-weight: bold;")
            else:
                label.setText("✖ EKSİK")
                label.setStyleSheet("color: #f85149; font-weight: bold;")

    def verify_and_repair_modules(self):
        if not self.selected_game or self.selected_game.is_pkg:
            QMessageBox.information(self, "Bilgi", "Lütfen önce Kütüphane sekmesinden ayıklanmış/kurulmuş bir oyun seçin.")
            return

        fakelib_dir = os.path.join(self.selected_game.folder_path, "fakelib")
        os.makedirs(fakelib_dir, exist_ok=True)
        self.update_modules_tab_for_game(self.selected_game)
        QMessageBox.information(self, "Doğrulama", f"{self.selected_game.title_name} için modül kontrolleri güncellendi.")

    def import_game_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "PS5 Oyun Klasörünü Seçin", BASE_DIR)
        if folder:
            eboot = os.path.join(folder, "eboot.bin")
            if not os.path.exists(eboot):
                QMessageBox.warning(self, "Uyarı", "Seçilen klasörde 'eboot.bin' bulunamadı!\nPS5 oyunlarının decrypted yapıda olması gerekir.")
                return

            dest_folder = os.path.join(GAMES_DIR, os.path.basename(folder))
            if not os.path.exists(dest_folder):
                try:
                    reply = QMessageBox.question(
                        self, "Oyun Ekle",
                        f"Bu oyunu melkorsps5/games/ dizinine kopyalamak istiyor musunuz?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if reply == QMessageBox.StandardButton.Yes:
                        shutil.copytree(folder, dest_folder)
                except Exception as e:
                    QMessageBox.critical(self, "Hata", f"Klasör taşınamadı: {e}")

            self.refresh_games()

    def launch_selected_game(self):
        if not self.selected_game or self.selected_game.is_pkg:
            return

        title_id = getattr(self.selected_game, "title_id", "")
        # PS5 games typically have PPSA IDs; PS4 games have CUSA IDs
        is_ps5 = title_id.startswith("PPSA") or not title_id.startswith("CUSA")
        target_core = PS5_CORE_EXE if is_ps5 else PS4_CORE_EXE
        if not os.path.exists(target_core):
            target_core = CORE_EXE

        if not os.path.exists(target_core):
            QMessageBox.critical(
                self, "MelkorS Çekirdek Hatası",
                f"MelkorS çekirdek modülü bulunamadı.\nBeklenen konum: {target_core}"
            )
            return

        eboot = self.selected_game.eboot_path
        if not os.path.exists(eboot):
            QMessageBox.critical(self, "Hata", f"Oyun dosyası bulunamadı:\n{eboot}")
            return

        target_path = self.selected_game.folder_path if (is_ps5 and os.path.isdir(self.selected_game.folder_path)) else eboot

        core_type = "PS5" if is_ps5 else "PS4"
        self.status_msg.setText(f"▶ MelkorS {core_type} Çekirdeği başlatılıyor: {self.selected_game.title_name}...")
        self.btn_launch.setEnabled(False)
        self.btn_stop.setEnabled(True)

        extra_args = []
        if is_ps5:
            # Resolution scaling
            res = self.config.get("resolution", "1080p (Native)")
            if "720p" in res:
                extra_args.extend(["--screen-width", "1280", "--screen-height", "720"])
            elif "1440p" in res:
                extra_args.extend(["--screen-width", "2560", "--screen-height", "1440"])
            elif "2160p" in res or "4K" in res:
                extra_args.extend(["--screen-width", "3840", "--screen-height", "2160"])
            else:
                extra_args.extend(["--screen-width", "1920", "--screen-height", "1080"])

            # Shader Optimization Level (Performance / Size / None)
            shader_opt = self.config.get("shader_opt", "Performance")
            extra_args.extend(["--shader-optimization-type", shader_opt])
            extra_args.extend(["--shader-log-direction", "Silent"])

            # Frame Presentation Mode (Immediate = No VSync lag, max FPS)
            present_m = self.config.get("present_mode", "Immediate")
            extra_args.extend(["--present-mode", present_m])

            # Refresh rate (VBlank Hz)
            vblank = str(self.config.get("vblank_hz", "60"))
            extra_args.extend(["--vblank-frequency", vblank])

            # Async Readback Bypass (Prevents GPU-CPU stalls)
            if self.config.get("readback_bypass", True):
                extra_args.extend(["--readback-linear-images", "false"])

        self.runner.start_game(target_core, target_path, is_ps5=is_ps5, extra_args=extra_args)

    def stop_current_game(self):
        self._user_stopped_game = True
        self.runner.stop_game()
        self.status_msg.setText("Oyun durduruldu.")
        self.btn_launch.setEnabled(True)
        self.btn_stop.setEnabled(False)
        # Safety watchdog: if finished signal doesn't fire in 3s, reset UI manually
        QTimer.singleShot(3000, self._watchdog_reset_ui)

    def _watchdog_reset_ui(self):
        """Force-reset UI state if the process finished signal was missed."""
        if not self.runner.is_running():
            # Process is gone — make sure UI is clean
            self.overlay.stop_tracking()
            if "Çalışıyor" in self.status_msg.text() or "başlatılıyor" in self.status_msg.text():
                self.status_msg.setText("Hazır.")
            self.btn_launch.setEnabled(True)
            self.btn_stop.setEnabled(False)

    def focus_launcher(self):
        """Close running game and bring MelkorS PS5 main window to front."""
        self.stop_current_game()
        QTimer.singleShot(300, lambda: [self.showNormal(), self.activateWindow(), self.raise_()])

    def on_process_started(self):
        self.status_msg.setText(self.t["status_running"])
        if not getattr(self.runner, "_install_mode", False):
            # Attach overlay to game process
            pid = self.runner.process.processId() if self.runner.process else None
            if pid:
                game_title = self.selected_game.title_name if self.selected_game else "MelkorS PS5"
                game_id = self.selected_game.title_id if self.selected_game else "CUSA41703"
                self.overlay.set_target_process(pid, game_title, game_id)

    def on_process_finished(self, exit_code: int):
        self.overlay.stop_tracking()
        if exit_code == 0:
            self.status_msg.setText("Oyun başarıyla tamamlandı.")
        else:
            self.status_msg.setText(f"Oyun sonlandı (Çıkış kodu: {exit_code}). Log sekmesinden detayları görebilirsiniz.")
        self.btn_launch.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_extract.setEnabled(True)

        if getattr(self.runner, "_install_mode", False):
            self._on_installer_finished(exit_code)
            return

        self._user_stopped_game = False

    def run_auto_diagnosis(self):
        lines = [line for line, _ in self.all_log_lines]
        report = LogAnalyzer.analyze_lines(lines)
        dlg = DiagnosisDialog(report, self.lang, self)
        dlg.exec()

    def on_log_received(self, line: str, level: str):
        self.all_log_lines.append((line, level))
        # Keep maximum 5000 items in history list to prevent unbounded memory growth
        if len(self.all_log_lines) > 5000:
            del self.all_log_lines[:1000]
        # Queue for batched flush
        self._pending_log_lines.append((line, level))

    def _flush_log_buffer(self):
        """Flush queued log lines into the QTextEdit in one batched operation without freezing GUI."""
        if not self._pending_log_lines:
            return

        color_map = {
            "ERROR": "#f85149",
            "WARN":  "#e3b341",
            "GPU":   "#58a6ff",
            "SYS":   "#1f6feb",
            "INFO":  "#8b9cb4",
        }

        # Prevent queue overflow from flooding the DOM
        if len(self._pending_log_lines) > 200:
            self._pending_log_lines = self._pending_log_lines[-100:]

        batch = self._pending_log_lines[:]
        self._pending_log_lines.clear()

        # Build one combined HTML string for the whole batch
        parts = []
        for line, level in batch:
            color = color_map.get(level, "#e6edf3")
            safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            parts.append(f"<span style='color:{color};font-family:Consolas;'>{safe}</span>")

        combined_html = "<br>".join(parts) + "<br>"

        # Fast non-blocking trimming if console exceeds max lines
        doc = self.log_console.document()
        if doc.blockCount() > self._MAX_LOG_LINES:
            block = doc.findBlockByNumber(300)
            if block.isValid():
                cursor = QTextCursor(doc)
                cursor.movePosition(QTextCursor.MoveOperation.Start)
                cursor.setPosition(block.position(), QTextCursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()

        self.log_console.moveCursor(QTextCursor.MoveOperation.End)
        self.log_console.insertHtml(combined_html)
        self.log_console.moveCursor(QTextCursor.MoveOperation.End)

    def _append_colored_line(self, line: str, level: str):
        """Legacy single-line append — routes through buffer for safety."""
        self._pending_log_lines.append((line, level))

    def apply_log_filter(self, filter_text: str):
        self.log_console.clear()
        filter_key = None
        if "Error" in filter_text or "Hata" in filter_text:
            filter_key = "ERROR"
        elif "Warning" in filter_text or "Uyarı" in filter_text:
            filter_key = "WARN"
        elif "GPU" in filter_text:
            filter_key = "GPU"
        elif "Sys" in filter_text or "Sistem" in filter_text:
            filter_key = "SYS"

        for line, level in self.all_log_lines:
            if filter_key is None or level == filter_key:
                self._append_colored_line(line, level)

    def clear_logs(self):
        self.all_log_lines.clear()
        self.log_console.clear()

    def on_save_settings_clicked(self):
        self.config["resolution"] = self.combo_res.currentText()
        self.config["vsync"] = self.chk_vsync.isChecked()
        self.config["pipeline_cache"] = self.chk_cache.isChecked()
        self.config["verbose_logging"] = self.chk_verbose.isChecked()
        self.config["jit_optimization"] = self.chk_jit.isChecked()

        # Map shader optimization selection
        shader_map = {0: "Performance", 1: "Size", 2: "None"}
        self.config["shader_opt"] = shader_map.get(self.combo_shader_opt.currentIndex(), "Performance")

        # Map present mode selection
        present_map = {0: "Immediate", 1: "Mailbox", 2: "Fifo"}
        self.config["present_mode"] = present_map.get(self.combo_present_mode.currentIndex(), "Immediate")

        # Map vblank frequency
        vblank_map = {0: "60", 1: "120", 2: "144", 3: "30"}
        self.config["vblank_hz"] = vblank_map.get(self.combo_vblank.currentIndex(), "60")

        self.config["readback_bypass"] = self.chk_readback.isChecked()

        self.save_config()
        QMessageBox.information(self, "Başarılı", "MelkorS PS5 grafik ve performans ayarları kaydedildi.")

    def apply_ultra_performance_preset(self):
        """1-Click apply the fastest possible profile for low-end / high-FPS setups."""
        self.combo_res.setCurrentText("720p (Performans)")
        self.combo_shader_opt.setCurrentIndex(0)       # Performance
        self.combo_present_mode.setCurrentIndex(0)     # Immediate (No VSync latency)
        self.combo_vblank.setCurrentIndex(0)           # 60 Hz
        self.chk_readback.setChecked(True)             # Readback bypass
        self.chk_vsync.setChecked(False)               # VSync off
        self.chk_cache.setChecked(True)                # Shader cache on
        self.on_save_settings_clicked()
        QMessageBox.information(
            self, "⚡ Ultra Performans Profili",
            "<b>Ultra Performans Profili başarıyla uygulandı!</b><br><br>"
            "• <b>Çözünürlük:</b> 720p (Performans Modu)<br>"
            "• <b>Shader Optimizasyonu:</b> Maksimum Performance Seviyesi<br>"
            "• <b>Kare Sunumu:</b> Immediate (V-Sync Kapalı / Minimum Gecikme)<br>"
            "• <b>GPU Geri Okuma:</b> Readback Bypass Etkin (Async)<br>"
            "• <b>Boru Hattı Önbelleği:</b> Açık (Hızlı Yükleme)<br><br>"
            "Oyununuzu şimdi başlatıp yüksek FPS ile oynayabilirsiniz!"
        )

    def update_telemetry(self):
        try:
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory().percent
            self.cpu_label.setText(f"CPU: {cpu}%")
            self.ram_label.setText(f"RAM: {ram}%")
            self.refresh_controller_status()
        except Exception:
            pass

def main():
    import traceback, datetime
    crash_log = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), "logs", "crash_gui.log")
    try:
        app = QApplication(sys.argv)
        window = MelkorSWindow()
        window.show()
        sys.exit(app.exec())
    except Exception:
        os.makedirs(os.path.dirname(crash_log), exist_ok=True)
        with open(crash_log, "a", encoding="utf-8") as f:
            f.write(f"\n=== CRASH {datetime.datetime.now()} ===\n")
            traceback.print_exc(file=f)
        raise

if __name__ == "__main__":
    main()
