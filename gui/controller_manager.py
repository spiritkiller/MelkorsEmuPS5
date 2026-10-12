"""
MelkorS PS5 - Native Controller & Gamepad Manager (XInput / DualSense)
"""

import ctypes
from ctypes import Structure, c_ushort, c_ubyte, c_short, c_ulong, byref

class XINPUT_GAMEPAD(Structure):
    _fields_ = [
        ("wButtons", c_ushort),
        ("bLeftTrigger", c_ubyte),
        ("bRightTrigger", c_ubyte),
        ("sThumbLX", c_short),
        ("sThumbLY", c_short),
        ("sThumbRX", c_short),
        ("sThumbRY", c_short),
    ]

class XINPUT_STATE(Structure):
    _fields_ = [
        ("dwPacketNumber", c_ulong),
        ("Gamepad", XINPUT_GAMEPAD),
    ]

class XINPUT_VIBRATION(Structure):
    _fields_ = [
        ("wLeftMotorSpeed", c_ushort),
        ("wRightMotorSpeed", c_ushort),
    ]

class ControllerManager:
    def __init__(self):
        self.xinput = None
        for dll in ["xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll"]:
            try:
                self.xinput = ctypes.windll.LoadLibrary(dll)
                break
            except Exception:
                continue

    def get_connected_controllers(self):
        if not self.xinput:
            return []

        connected = []
        state = XINPUT_STATE()
        for i in range(4):
            res = self.xinput.XInputGetState(i, byref(state))
            if res == 0:  # ERROR_SUCCESS
                connected.append(i)
        return connected

    def test_vibration(self, user_index: int = 0, duration_ms: int = 500):
        if not self.xinput:
            return False

        vib = XINPUT_VIBRATION(32000, 32000)
        res = self.xinput.XInputSetState(user_index, byref(vib))
        if res == 0:
            import threading, time
            def stop():
                time.sleep(duration_ms / 1000.0)
                zero_vib = XINPUT_VIBRATION(0, 0)
                self.xinput.XInputSetState(user_index, byref(zero_vib))
            threading.Thread(target=stop, daemon=True).start()
            return True
        return False
