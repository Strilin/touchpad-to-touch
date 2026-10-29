# Touchpad -> touchscreen: reads the fingers of a Windows Precision Touchpad (Raw Input,
# see touchpad_logger.py) and injects them into Windows as real touch input
# (InjectTouchInput), so every program sees a touchscreen. The pad's range is taken
# from the device's own HID descriptor, so any size / resolution of Precision Touchpad works.
#
# Runs invisibly (no window). Usage:
#   python touchpad_to_touch.py [seconds] [--keep-aspect] [--log]
#   seconds:        quit after this many seconds (default 0 = run until stopped)
#   --keep-aspect:  keep the pad's aspect ratio (centered) instead of stretching it to the screen
#   --log:          write finger down / up events to inject_log.txt
# Sounds: one high beep = started; one low beep = stopped (Ctrl+Alt+Shift+Q or time limit);
# two short beeps = already running; three low beeps = error (e.g. no Precision Touchpad).
# Can also be stopped from Task Manager (then without a sound).

import ctypes
import ctypes.wintypes as wt
import os
import sys
import time
import winsound

import touchpad_logger as tp

user32 = tp.user32
kernel32 = tp.kernel32

PT_TOUCH = 2
POINTER_FLAG_INRANGE = 0x00000002
POINTER_FLAG_INCONTACT = 0x00000004
POINTER_FLAG_DOWN = 0x00010000
POINTER_FLAG_UPDATE = 0x00020000
POINTER_FLAG_UP = 0x00040000
TOUCH_MASK_CONTACTAREA = 0x1
TOUCH_MASK_ORIENTATION = 0x2
TOUCH_MASK_PRESSURE = 0x4
TOUCH_FEEDBACK_DEFAULT = 0x1
MAX_CONTACTS = 10
CONTACT_RADIUS = 4

WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x4000
HOTKEY_ID = 1
SM_CXSCREEN, SM_CYSCREEN = 0, 1
RIDI_DEVICEINFO = 0x2000000B
ERROR_ALREADY_EXISTS = 183
MUTEX_NAME = "Local\\TouchpadToTouch"


class POINTER_INFO(ctypes.Structure):
    _fields_ = [("pointerType", wt.DWORD), ("pointerId", ctypes.c_uint32),
                ("frameId", ctypes.c_uint32), ("pointerFlags", ctypes.c_uint32),
                ("sourceDevice", wt.HANDLE), ("hwndTarget", wt.HWND),
                ("ptPixelLocation", wt.POINT), ("ptHimetricLocation", wt.POINT),
                ("ptPixelLocationRaw", wt.POINT), ("ptHimetricLocationRaw", wt.POINT),
                ("dwTime", wt.DWORD), ("historyCount", ctypes.c_uint32),
                ("InputData", ctypes.c_int32), ("dwKeyStates", wt.DWORD),
                ("PerformanceCount", ctypes.c_uint64), ("ButtonChangeType", ctypes.c_int)]


class POINTER_TOUCH_INFO(ctypes.Structure):
    _fields_ = [("pointerInfo", POINTER_INFO), ("touchFlags", ctypes.c_uint32),
                ("touchMask", ctypes.c_uint32), ("rcContact", wt.RECT),
                ("rcContactRaw", wt.RECT), ("orientation", ctypes.c_uint32),
                ("pressure", ctypes.c_uint32)]


assert ctypes.sizeof(POINTER_TOUCH_INFO) == (144 if ctypes.sizeof(ctypes.c_void_p) == 8 else 136)

user32.InitializeTouchInjection.argtypes = [ctypes.c_uint32, wt.DWORD]
user32.InitializeTouchInjection.restype = wt.BOOL
user32.InjectTouchInput.argtypes = [ctypes.c_uint32, ctypes.POINTER(POINTER_TOUCH_INFO)]
user32.InjectTouchInput.restype = wt.BOOL
user32.RegisterHotKey.argtypes = [wt.HWND, ctypes.c_int, wt.UINT, wt.UINT]
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetRawInputDeviceList.argtypes = [ctypes.c_void_p, ctypes.POINTER(wt.UINT), wt.UINT]
user32.GetRawInputDeviceList.restype = wt.UINT
kernel32.CreateMutexW.argtypes = [wt.LPVOID, wt.BOOL, wt.LPCWSTR]
kernel32.CreateMutexW.restype = wt.HANDLE

# Next to the .exe when packaged with PyInstaller, next to the script otherwise.
APP_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else tp.SCRIPT_DIR
LOG_PATH = os.path.join(APP_DIR, "inject_log.txt")
ERROR_PATH = os.path.join(APP_DIR, "touchpad_to_touch_error.txt")
log = tp.log


class RAWINPUTDEVICELIST(ctypes.Structure):
    _fields_ = [("hDevice", wt.HANDLE), ("dwType", wt.DWORD)]


class RID_DEVICE_INFO_HID(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("dwType", wt.DWORD), ("dwVendorId", wt.DWORD),
                ("dwProductId", wt.DWORD), ("dwVersionNumber", wt.DWORD),
                ("usUsagePage", wt.USHORT), ("usUsage", wt.USHORT), ("_pad", wt.DWORD * 2)]


assert ctypes.sizeof(RID_DEVICE_INFO_HID) == 32  # sizeof(RID_DEVICE_INFO)


def has_precision_touchpad():
    count = wt.UINT(0)
    user32.GetRawInputDeviceList(None, ctypes.byref(count), ctypes.sizeof(RAWINPUTDEVICELIST))
    devices = (RAWINPUTDEVICELIST * max(count.value, 1))()
    n = user32.GetRawInputDeviceList(devices, ctypes.byref(count), ctypes.sizeof(RAWINPUTDEVICELIST))
    for d in devices[:n if n != 0xFFFFFFFF else 0]:
        if d.dwType != tp.RIM_TYPEHID:
            continue
        info = RID_DEVICE_INFO_HID(cbSize=ctypes.sizeof(RID_DEVICE_INFO_HID))
        size = wt.UINT(ctypes.sizeof(info))
        if (user32.GetRawInputDeviceInfoW(d.hDevice, RIDI_DEVICEINFO, ctypes.byref(info), ctypes.byref(size))
                and info.usUsagePage == tp.PAGE_DIGITIZER and info.usUsage == tp.USAGE_TOUCHPAD):
            return True
    return False


def say(text):
    if sys.stdout:  # there is no console in the windowed .exe
        print(text, flush=True)


def beeps(freq, ms, count):
    for _ in range(count):
        winsound.Beep(freq, ms)
        time.sleep(0.08)


def pad_aspect(dev):
    """The pad's physical aspect ratio if the descriptor gives one, else that of the logical range."""
    xc, yc = dev.xcap, dev.ycap
    pw, ph = xc.PhysicalMax - xc.PhysicalMin, yc.PhysicalMax - yc.PhysicalMin
    if pw > 0 and ph > 0 and tp.unit_exp(xc.UnitsExp) == tp.unit_exp(yc.UnitsExp):
        return pw / ph
    lw, lh = xc.LogicalMax - xc.LogicalMin, yc.LogicalMax - yc.LogicalMin
    return lw / lh if lw > 0 and lh > 0 else None


class Mapper:
    """Maps pad coordinates (each device with its own logical range) to screen pixels."""

    def __init__(self, keep_aspect):
        self.w = user32.GetSystemMetrics(SM_CXSCREEN)
        self.h = user32.GetSystemMetrics(SM_CYSCREEN)
        self.keep_aspect = keep_aspect
        self.aspects = {}

    def __call__(self, dev, x, y):
        xc, yc = dev.xcap, dev.ycap
        fx = (x - xc.LogicalMin) / max(1, xc.LogicalMax - xc.LogicalMin)
        fy = (y - yc.LogicalMin) / max(1, yc.LogicalMax - yc.LogicalMin)
        fx, fy = min(max(fx, 0.0), 1.0), min(max(fy, 0.0), 1.0)
        w, h, ox, oy = self.w, self.h, 0, 0
        if self.keep_aspect:
            if dev not in self.aspects:
                self.aspects[dev] = pad_aspect(dev)
            aspect = self.aspects[dev]
            if aspect and aspect > w / h:
                h = int(w / aspect)
                oy = (self.h - h) // 2
            elif aspect:
                w = int(h * aspect)
                ox = (self.w - w) // 2
        return ox + int(fx * (w - 1)), oy + int(fy * (h - 1))


class Injector:
    def __init__(self, mapper):
        self.mapper = mapper
        self.active = {}   # (device, contact id) -> pointer id
        self.pos = {}      # pointer id -> (px, py)
        self.frames = {}   # device -> [expected contact count, collected contacts]
        self.errors = 0

    def on_report(self, dev, report):
        contacts = dev.contacts(report)
        cc = dev.contact_count(report)
        # Hybrid mode: when more fingers touch than the report has slots, one frame is split
        # over several reports; the first carries the contact count, the rest carry 0.
        frame = self.frames.setdefault(dev, [0, []])
        if cc is None:
            frame[:] = [len(contacts), []]
        elif cc > 0:
            frame[:] = [cc, []]
        frame[1].extend(contacts)
        if len(frame[1]) < frame[0]:
            return
        self.apply(dev, frame[1])
        frame[:] = [0, []]

    def free_id(self):
        used = set(self.active.values())
        return next((i for i in range(MAX_CONTACTS) if i not in used), None)

    def apply(self, dev, contacts):
        touching = {}
        for cid, tip, conf, x, y in contacts:
            if tip:
                touching[cid] = self.mapper(dev, x, y)
        t = time.perf_counter() - tp.t0
        infos = []
        for key in [k for k in self.active if k[0] is dev and k[1] not in touching]:
            pid = self.active.pop(key)
            pos = self.pos.pop(pid)
            infos.append(self.info(pid, pos, POINTER_FLAG_UP))
            log(f"{t:8.3f} up    finger={key[1]} pointer={pid} at {pos}")
        for cid, pos in touching.items():
            key = (dev, cid)
            if key in self.active:
                flags = POINTER_FLAG_UPDATE | POINTER_FLAG_INRANGE | POINTER_FLAG_INCONTACT
            else:
                pid = self.free_id()
                if pid is None:
                    continue
                self.active[key] = pid
                flags = POINTER_FLAG_DOWN | POINTER_FLAG_INRANGE | POINTER_FLAG_INCONTACT
                log(f"{t:8.3f} down  finger={cid} pointer={pid} at {pos}")
            pid = self.active[key]
            self.pos[pid] = pos
            infos.append(self.info(pid, pos, flags))
        self.inject(infos)

    def release_all(self):
        infos = [self.info(pid, self.pos.pop(pid), POINTER_FLAG_UP) for pid in self.active.values()]
        self.active.clear()
        self.inject(infos)

    @staticmethod
    def info(pid, pos, flags):
        t = POINTER_TOUCH_INFO()
        t.pointerInfo.pointerType = PT_TOUCH
        t.pointerInfo.pointerId = pid
        t.pointerInfo.pointerFlags = flags
        x, y = pos
        t.pointerInfo.ptPixelLocation = wt.POINT(x, y)
        t.touchMask = TOUCH_MASK_CONTACTAREA | TOUCH_MASK_ORIENTATION | TOUCH_MASK_PRESSURE
        t.rcContact = wt.RECT(x - CONTACT_RADIUS, y - CONTACT_RADIUS, x + CONTACT_RADIUS, y + CONTACT_RADIUS)
        t.orientation = 90
        t.pressure = 32000
        return t

    def inject(self, infos):
        if not infos:
            return
        arr = (POINTER_TOUCH_INFO * len(infos))(*infos)
        if not user32.InjectTouchInput(len(infos), arr):
            self.errors += 1
            if self.errors <= 20:
                log(f"ERROR: InjectTouchInput failed, Windows error code {ctypes.get_last_error()}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    seconds = float(args[0]) if args else 0.0
    keep_aspect = "--keep-aspect" in sys.argv

    mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        say("Already running.")
        beeps(1000, 70, 2)
        return
    if not has_precision_touchpad():
        raise RuntimeError("No Precision Touchpad found.")

    # Work in physical pixels, otherwise display scaling would shift the coordinates.
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
    except AttributeError:
        pass
    if "--log" in sys.argv:
        tp.log_file = open(LOG_PATH, "w", encoding="utf-8")
    mapper = Mapper(keep_aspect)
    injector = Injector(mapper)
    log(f"Injector started ({time.strftime('%Y-%m-%d %H:%M:%S')}), screen {mapper.w}x{mapper.h}, "
        f"mapping: {'keep aspect' if keep_aspect else 'stretch'}, time limit: {seconds:g} s (0 = none)")
    if not user32.InitializeTouchInjection(MAX_CONTACTS, TOUCH_FEEDBACK_DEFAULT):
        raise ctypes.WinError(ctypes.get_last_error())

    @tp.WNDPROC
    def wndproc(hwnd, msg, wparam, lparam):
        if msg == tp.WM_INPUT:
            try:
                for dev, report in tp.read_reports(lparam):
                    injector.on_report(dev, report)
            except Exception as e:
                log(f"ERROR: {e!r}")
        elif msg in (tp.WM_TIMER, WM_HOTKEY):
            user32.DestroyWindow(hwnd)
            return 0
        elif msg == tp.WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    hwnd = tp.create_input_window("TouchpadToTouch", wndproc)
    if not user32.RegisterHotKey(hwnd, HOTKEY_ID, MOD_CONTROL | MOD_ALT | MOD_SHIFT | MOD_NOREPEAT, ord("Q")):
        raise RuntimeError("Ctrl+Alt+Shift+Q is already used by another program.")
    if seconds > 0:
        user32.SetTimer(hwnd, 1, int(seconds * 1000), None)
    if tp.log_file:
        tp.log_file.flush()
    limit = f" for {seconds:g} seconds" if seconds > 0 else ""
    say(f"Touchpad -> touch running{limit}. Stop: Ctrl+Alt+Shift+Q.")
    winsound.Beep(1200, 150)
    try:
        tp.message_loop()
    finally:
        injector.release_all()  # never leave a stuck finger on the screen
        log(f"Exit. Injection errors: {injector.errors}")
        if tp.log_file:
            tp.log_file.close()
        winsound.Beep(600, 250)
    say("Stopped.")


if __name__ == "__main__":
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    try:
        main()
    except Exception as e:
        try:
            with open(ERROR_PATH, "w", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {e!r}\n")
        except OSError:
            pass
        say(f"Error: {e}")
        beeps(300, 200, 3)
        sys.exit(1)
