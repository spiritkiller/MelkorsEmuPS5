"""
MelkorS PS5 - In-Game Title Bar & Process Monitor
No floating HUD overlay, no hook conflicts, no taskbar freeze.
Directly updates the native Windows game window title:
"Pocket Bravery | [F1] Ana Ekrana Dön | [F10] FPS | [F11] Tam Ekran"
"""

import sys
import os
import ctypes
from ctypes import wintypes
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

user32 = ctypes.windll.user32

VK_F1 = 0x70

class GameOverlayBar(QObject):
    return_requested = pyqtSignal()
    stop_game_requested = pyqtSignal()

    def __init__(self, parent=None, game_title: str = "Pocket Bravery"):
        super().__init__(parent)
        self.game_title = game_title
        self.game_id = "CUSA41703"
        self.target_pid = None
        self.target_hwnd = None
        self._title_applied = False

        self._prev_f1 = False

        # Periodic timer: sets game window title once window appears & polls F1
        self.monitor_timer = QTimer(self)
        self.monitor_timer.setInterval(100)
        self.monitor_timer.timeout.connect(self._monitor_tick)

    def set_target_process(self, pid: int, game_title: str = "MelkorS PS5", game_id: str = "CUSA41703"):
        self.target_pid = pid
        self.game_title = game_title or "Pocket Bravery"
        self.game_id = game_id or "CUSA41703"
        self.target_hwnd = None
        self._title_applied = False
        self._prev_f1 = False
        self.monitor_timer.start()

    def stop_tracking(self):
        self.monitor_timer.stop()
        self.target_pid = None
        self.target_hwnd = None
        self._title_applied = False

    def _monitor_tick(self):
        if not self.target_pid:
            return

        # Check if process is still running
        try:
            import psutil
            if not psutil.pid_exists(self.target_pid):
                self.stop_tracking()
                return
        except Exception:
            pass

        # Poll F1 as safety fallback to return to launcher
        f1_down = bool(user32.GetAsyncKeyState(VK_F1) & 0x8000)
        if f1_down and not self._prev_f1:
            self.return_requested.emit()
        self._prev_f1 = f1_down

        # Find HWND and apply window title
        if not self.target_hwnd or not user32.IsWindow(self.target_hwnd):
            self.target_hwnd = self._find_hwnd_for_pid(self.target_pid)
            self._title_applied = False

        if self.target_hwnd and not self._title_applied:
            formatted_title = f"{self.game_title} | [F1] Ana Ekrana Dön | [F10] FPS | [F11] Tam Ekran"
            user32.SetWindowTextW(self.target_hwnd, formatted_title)
            self._title_applied = True

    def _find_hwnd_for_pid(self, target_pid):
        found_hwnds = []

        def enum_cb(hwnd, lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == target_pid:
                rect = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                w = rect.right - rect.left
                h = rect.bottom - rect.top
                if w > 200 and h > 200:
                    found_hwnds.append(hwnd)
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        return found_hwnds[0] if found_hwnds else None
