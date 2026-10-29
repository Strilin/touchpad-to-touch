# Touchpad logger: reads the raw HID reports of a Windows Precision Touchpad via
# Raw Input (usage page 0x0D, usage 0x05, RIDEV_INPUTSINK) and writes the device
# capabilities and every finger (contact id, tip, confidence, x, y, contact count)
# to touchpad_log.txt. Shows no window and does not read the keyboard.
# Also used as a module by touchpad_to_touch.py.
#
# Usage:  python touchpad_logger.py [seconds]      (default: 30)

import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
hid = ctypes.WinDLL("hid")

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)

WM_DESTROY = 0x0002
WM_INPUT = 0x00FF
WM_TIMER = 0x0113
RID_INPUT = 0x10000003
RIM_TYPEHID = 2
RIDEV_INPUTSINK = 0x00000100
RIDI_PREPARSEDDATA = 0x20000005
RIDI_DEVICENAME = 0x20000007
HIDP_INPUT = 0
HIDP_STATUS_SUCCESS = 0x00110000

PAGE_GENERIC = 0x01
PAGE_DIGITIZER = 0x0D
PAGE_BUTTON = 0x09
USAGE_TOUCHPAD = 0x05
USAGE_X = 0x30
USAGE_Y = 0x31
USAGE_TIP = 0x42
USAGE_CONFIDENCE = 0x47
USAGE_CONTACT_ID = 0x51
USAGE_CONTACT_COUNT = 0x54
USAGE_SCAN_TIME = 0x56


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", wt.UINT), ("style", wt.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON), ("hCursor", wt.HANDLE),
                ("hbrBackground", wt.HBRUSH), ("lpszMenuName", wt.LPCWSTR),
                ("lpszClassName", wt.LPCWSTR), ("hIconSm", wt.HICON)]


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [("usUsagePage", wt.USHORT), ("usUsage", wt.USHORT),
                ("dwFlags", wt.DWORD), ("hwndTarget", wt.HWND)]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [("dwType", wt.DWORD), ("dwSize", wt.DWORD),
                ("hDevice", wt.HANDLE), ("wParam", wt.WPARAM)]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [("Usage", wt.USHORT), ("UsagePage", wt.USHORT),
                ("InputReportByteLength", wt.USHORT), ("OutputReportByteLength", wt.USHORT),
                ("FeatureReportByteLength", wt.USHORT), ("Reserved", wt.USHORT * 17),
                ("NumberLinkCollectionNodes", wt.USHORT),
                ("NumberInputButtonCaps", wt.USHORT), ("NumberInputValueCaps", wt.USHORT),
                ("NumberInputDataIndices", wt.USHORT),
                ("NumberOutputButtonCaps", wt.USHORT), ("NumberOutputValueCaps", wt.USHORT),
                ("NumberOutputDataIndices", wt.USHORT),
                ("NumberFeatureButtonCaps", wt.USHORT), ("NumberFeatureValueCaps", wt.USHORT),
                ("NumberFeatureDataIndices", wt.USHORT)]


class HIDP_VALUE_CAPS(ctypes.Structure):
    _fields_ = [("UsagePage", wt.USHORT), ("ReportID", ctypes.c_ubyte),
                ("IsAlias", ctypes.c_ubyte), ("BitField", wt.USHORT),
                ("LinkCollection", wt.USHORT), ("LinkUsage", wt.USHORT),
                ("LinkUsagePage", wt.USHORT), ("IsRange", ctypes.c_ubyte),
                ("IsStringRange", ctypes.c_ubyte), ("IsDesignatorRange", ctypes.c_ubyte),
                ("IsAbsolute", ctypes.c_ubyte), ("HasNull", ctypes.c_ubyte),
                ("Reserved", ctypes.c_ubyte), ("BitSize", wt.USHORT),
                ("ReportCount", wt.USHORT), ("Reserved2", wt.USHORT * 5),
                ("UnitsExp", wt.ULONG), ("Units", wt.ULONG),
                ("LogicalMin", wt.LONG), ("LogicalMax", wt.LONG),
                ("PhysicalMin", wt.LONG), ("PhysicalMax", wt.LONG),
                ("UsageMin", wt.USHORT), ("UsageMax", wt.USHORT),  # NotRange: UsageMin == Usage
                ("_rest", wt.USHORT * 6)]


class HIDP_BUTTON_CAPS(ctypes.Structure):
    _fields_ = [("UsagePage", wt.USHORT), ("ReportID", ctypes.c_ubyte),
                ("IsAlias", ctypes.c_ubyte), ("BitField", wt.USHORT),
                ("LinkCollection", wt.USHORT), ("LinkUsage", wt.USHORT),
                ("LinkUsagePage", wt.USHORT), ("IsRange", ctypes.c_ubyte),
                ("IsStringRange", ctypes.c_ubyte), ("IsDesignatorRange", ctypes.c_ubyte),
                ("IsAbsolute", ctypes.c_ubyte), ("ReportCount", wt.USHORT),
                ("Reserved2", wt.USHORT), ("Reserved", wt.ULONG * 9),
                ("UsageMin", wt.USHORT), ("UsageMax", wt.USHORT),
                ("_rest", wt.USHORT * 6)]


assert ctypes.sizeof(HIDP_VALUE_CAPS) == 72 and ctypes.sizeof(HIDP_BUTTON_CAPS) == 72

user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.RegisterClassExW.restype = wt.ATOM
user32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.HWND, wt.HMENU,
                                   wt.HINSTANCE, wt.LPVOID]
user32.CreateWindowExW.restype = wt.HWND
user32.RegisterRawInputDevices.argtypes = [ctypes.POINTER(RAWINPUTDEVICE), wt.UINT, wt.UINT]
user32.RegisterRawInputDevices.restype = wt.BOOL
user32.GetRawInputData.argtypes = [wt.HANDLE, wt.UINT, wt.LPVOID, ctypes.POINTER(wt.UINT), wt.UINT]
user32.GetRawInputData.restype = wt.UINT
user32.GetRawInputDeviceInfoW.argtypes = [wt.HANDLE, wt.UINT, wt.LPVOID, ctypes.POINTER(wt.UINT)]
user32.GetRawInputDeviceInfoW.restype = wt.UINT
user32.SetTimer.argtypes = [wt.HWND, ctypes.c_size_t, wt.UINT, wt.LPVOID]
user32.SetTimer.restype = ctypes.c_size_t
user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]
user32.TranslateMessage.argtypes = [ctypes.POINTER(wt.MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]
user32.DestroyWindow.argtypes = [wt.HWND]
kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
kernel32.GetModuleHandleW.restype = wt.HMODULE

hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
hid.HidP_GetValueCaps.argtypes = [ctypes.c_int, ctypes.POINTER(HIDP_VALUE_CAPS),
                                  ctypes.POINTER(wt.USHORT), ctypes.c_void_p]
hid.HidP_GetButtonCaps.argtypes = [ctypes.c_int, ctypes.POINTER(HIDP_BUTTON_CAPS),
                                   ctypes.POINTER(wt.USHORT), ctypes.c_void_p]
hid.HidP_GetUsageValue.argtypes = [ctypes.c_int, wt.USHORT, wt.USHORT, wt.USHORT,
                                   ctypes.POINTER(wt.ULONG), ctypes.c_void_p,
                                   ctypes.c_void_p, wt.ULONG]
hid.HidP_GetUsages.argtypes = [ctypes.c_int, wt.USHORT, wt.USHORT, ctypes.POINTER(wt.USHORT),
                               ctypes.POINTER(wt.ULONG), ctypes.c_void_p, ctypes.c_void_p, wt.ULONG]
hid.HidP_MaxUsageListLength.argtypes = [ctypes.c_int, wt.USHORT, ctypes.c_void_p]
hid.HidP_MaxUsageListLength.restype = wt.ULONG
for f in (hid.HidP_GetCaps, hid.HidP_GetValueCaps, hid.HidP_GetButtonCaps,
          hid.HidP_GetUsageValue, hid.HidP_GetUsages):
    f.restype = wt.LONG


def ok(status):
    return (status & 0xFFFFFFFF) == HIDP_STATUS_SUCCESS


def unit_exp(e):
    e &= 0xF
    return e - 16 if e >= 8 else e


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(SCRIPT_DIR, "touchpad_log.txt")
log_file = None  # opened by main() or by the importing program
t0 = time.perf_counter()


def log(line):
    if log_file:
        log_file.write(line + "\n")


class Device:
    """Preparsed HID descriptor of one touchpad and its finger collections."""

    def __init__(self, handle, index):
        self.index = index
        size = wt.UINT(0)
        user32.GetRawInputDeviceInfoW(handle, RIDI_DEVICENAME, None, ctypes.byref(size))
        name = ctypes.create_unicode_buffer(size.value + 1)
        user32.GetRawInputDeviceInfoW(handle, RIDI_DEVICENAME, name, ctypes.byref(size))
        self.name = name.value
        size = wt.UINT(0)
        user32.GetRawInputDeviceInfoW(handle, RIDI_PREPARSEDDATA, None, ctypes.byref(size))
        self.pp = ctypes.create_string_buffer(size.value)
        user32.GetRawInputDeviceInfoW(handle, RIDI_PREPARSEDDATA, self.pp, ctypes.byref(size))
        self.caps = HIDP_CAPS()
        hid.HidP_GetCaps(self.pp, ctypes.byref(self.caps))
        self.max_usages = hid.HidP_MaxUsageListLength(HIDP_INPUT, 0, self.pp) or 1

        n = wt.USHORT(self.caps.NumberInputValueCaps)
        vcaps = (HIDP_VALUE_CAPS * max(n.value, 1))()
        hid.HidP_GetValueCaps(HIDP_INPUT, vcaps, ctypes.byref(n), self.pp)
        self.vcaps = list(vcaps)[:n.value]
        n = wt.USHORT(self.caps.NumberInputButtonCaps)
        bcaps = (HIDP_BUTTON_CAPS * max(n.value, 1))()
        hid.HidP_GetButtonCaps(HIDP_INPUT, bcaps, ctypes.byref(n), self.pp)
        self.bcaps = list(bcaps)[:n.value]

        # Finger collections: the link collections that contain an X value.
        self.fingers = sorted({c.LinkCollection for c in self.vcaps
                               if c.UsagePage == PAGE_GENERIC and c.UsageMin == USAGE_X})
        self.xcap = self.find_value(PAGE_GENERIC, USAGE_X)
        self.ycap = self.find_value(PAGE_GENERIC, USAGE_Y)
        self.cc_cap = self.find_value(PAGE_DIGITIZER, USAGE_CONTACT_COUNT)
        self.describe()

    def find_value(self, page, usage):
        return next((c for c in self.vcaps if c.UsagePage == page and c.UsageMin == usage), None)

    def describe(self):
        c = self.caps
        log(f"=== Device #{self.index}: {self.name}")
        log(f"    TLC usage page 0x{c.UsagePage:02X} usage 0x{c.Usage:02X}, input report "
            f"{c.InputReportByteLength} bytes, link collections: {c.NumberLinkCollectionNodes}")
        log("    Value caps (usage page/usage, link collection, report id, logical and physical range):")
        for v in self.vcaps:
            usage = f"0x{v.UsageMin:02X}" + (f"-0x{v.UsageMax:02X}" if v.IsRange else "")
            log(f"      page 0x{v.UsagePage:02X} usage {usage:11} lc={v.LinkCollection:2} rid={v.ReportID:3} "
                f"bits={v.BitSize:2}x{v.ReportCount} log=[{v.LogicalMin}..{v.LogicalMax}] "
                f"phys=[{v.PhysicalMin}..{v.PhysicalMax}] unit=0x{v.Units:X} exp={unit_exp(v.UnitsExp)}")
        log("    Button caps:")
        for b in self.bcaps:
            usage = f"0x{b.UsageMin:02X}" + (f"-0x{b.UsageMax:02X}" if b.IsRange else "")
            log(f"      page 0x{b.UsagePage:02X} usage {usage:11} lc={b.LinkCollection:2} rid={b.ReportID:3}")
        log(f"    Finger collections (lc): {self.fingers}")
        for name, cap in (("X", self.xcap), ("Y", self.ycap)):
            if cap:
                e = unit_exp(cap.UnitsExp)
                unit = {0x11: "cm", 0x13: "inch"}.get(cap.Units, f"unit 0x{cap.Units:X}")
                size = (cap.PhysicalMax - cap.PhysicalMin) * (10 ** e)
                log(f"    {name}: logical {cap.LogicalMin}..{cap.LogicalMax}, physical size about {size:.2f} {unit}")
        log("")

    def value(self, page, lc, usage, report):
        v = wt.ULONG(0)
        st = hid.HidP_GetUsageValue(HIDP_INPUT, page, lc, usage, ctypes.byref(v), self.pp,
                                    report, len(report))
        return v.value if ok(st) else None

    def usages(self, page, lc, report):
        buf = (wt.USHORT * self.max_usages)()
        n = wt.ULONG(self.max_usages)
        st = hid.HidP_GetUsages(HIDP_INPUT, page, lc, buf, ctypes.byref(n), self.pp,
                                report, len(report))
        return set(buf[:n.value]) if ok(st) else set()

    def contact_count(self, report):
        if not self.cc_cap:
            return None
        return self.value(PAGE_DIGITIZER, self.cc_cap.LinkCollection, USAGE_CONTACT_COUNT, report)

    def contacts(self, report):
        """The finger slots of one report as a list of (contact id, tip, confidence, x, y)."""
        result = []
        for lc in self.fingers:
            x = self.value(PAGE_GENERIC, lc, USAGE_X, report)
            y = self.value(PAGE_GENERIC, lc, USAGE_Y, report)
            if x is None:
                continue
            flags = self.usages(PAGE_DIGITIZER, lc, report)
            tip = USAGE_TIP in flags
            if not tip and not x and not y:
                continue  # empty slot
            cid = self.value(PAGE_DIGITIZER, lc, USAGE_CONTACT_ID, report)
            result.append((cid, tip, USAGE_CONFIDENCE in flags, x, y))
        return result


devices = {}


def read_reports(lparam):
    """Yields the touchpad reports of one WM_INPUT message as (Device, report buffer) pairs."""
    size = wt.UINT(0)
    hdr_size = ctypes.sizeof(RAWINPUTHEADER)
    user32.GetRawInputData(lparam, RID_INPUT, None, ctypes.byref(size), hdr_size)
    buf = ctypes.create_string_buffer(size.value)
    if user32.GetRawInputData(lparam, RID_INPUT, buf, ctypes.byref(size), hdr_size) != size.value:
        return
    hdr = RAWINPUTHEADER.from_buffer(buf)
    if hdr.dwType != RIM_TYPEHID:
        return
    key = hdr.hDevice
    if key not in devices:
        devices[key] = Device(hdr.hDevice, len(devices) + 1)
    dev = devices[key]
    size_hid, count = ctypes.cast(ctypes.byref(buf, hdr_size), ctypes.POINTER(wt.DWORD * 2)).contents
    data = buf.raw[hdr_size + 8:hdr_size + 8 + size_hid * count]
    for i in range(count):
        yield dev, ctypes.create_string_buffer(data[i * size_hid:(i + 1) * size_hid], size_hid)


def create_input_window(class_name, wndproc):
    """Creates a hidden (never shown) top-level window and registers it for touchpad raw input."""
    hinst = kernel32.GetModuleHandleW(None)
    wc = WNDCLASSEXW()
    wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
    wc.lpfnWndProc = wndproc
    wc.hInstance = hinst
    wc.lpszClassName = class_name
    if not user32.RegisterClassExW(ctypes.byref(wc)):
        raise ctypes.WinError(ctypes.get_last_error())
    hwnd = user32.CreateWindowExW(0, class_name, class_name, 0, 0, 0, 0, 0, None, None, hinst, None)
    if not hwnd:
        raise ctypes.WinError(ctypes.get_last_error())
    rid = RAWINPUTDEVICE(PAGE_DIGITIZER, USAGE_TOUCHPAD, RIDEV_INPUTSINK, hwnd)
    if not user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(rid)):
        raise ctypes.WinError(ctypes.get_last_error())
    return hwnd


def message_loop():
    msg = wt.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


stats = {"reports": 0, "max_tips": 0, "max_cc": 0, "minx": None, "maxx": None,
         "miny": None, "maxy": None, "ids": set()}


def on_report(dev, report):
    stats["reports"] += 1
    t = time.perf_counter() - t0
    cc = dev.contact_count(report)
    scan = dev.value(PAGE_DIGITIZER, 0, USAGE_SCAN_TIME, report)
    buttons = dev.usages(PAGE_BUTTON, 0, report)
    parts = []
    tips = 0
    for cid, tip, conf, x, y in dev.contacts(report):
        tips += tip
        parts.append(f"id={cid} tip={int(tip)} conf={int(conf)} x={x} y={y}")
        if tip:
            stats["ids"].add(cid)
            for k, val in (("x", x), ("y", y)):
                lo, hi = "min" + k, "max" + k
                stats[lo] = val if stats[lo] is None else min(stats[lo], val)
                stats[hi] = val if stats[hi] is None else max(stats[hi], val)
    stats["max_tips"] = max(stats["max_tips"], tips)
    if cc is not None:
        stats["max_cc"] = max(stats["max_cc"], cc)
    btn = f" button={sorted(buttons)}" if buttons else ""
    log(f"{t:8.3f} #{dev.index} rid={report.raw[0]} count={cc} scan={scan}{btn} | " + " | ".join(parts))


@WNDPROC
def wndproc(hwnd, msg, wparam, lparam):
    if msg == WM_INPUT:
        try:
            for dev, report in read_reports(lparam):
                on_report(dev, report)
        except Exception as e:  # one bad report must not stop the logging
            log(f"ERROR: {e!r}")
    elif msg == WM_TIMER:
        user32.DestroyWindow(hwnd)
        return 0
    elif msg == WM_DESTROY:
        user32.PostQuitMessage(0)
        return 0
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def main():
    global log_file
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
    log_file = open(LOG_PATH, "w", encoding="utf-8")
    hwnd = create_input_window("TouchpadLogger", wndproc)
    log(f"Touchpad logger started, listening for {seconds:g} seconds. ({time.strftime('%Y-%m-%d %H:%M:%S')})")
    log("")
    log_file.flush()
    print(f"Listening for {seconds:g} seconds, move your fingers on the touchpad... Log: {LOG_PATH}", flush=True)
    user32.SetTimer(hwnd, 1, int(seconds * 1000), None)
    message_loop()

    log("")
    log("=== Summary")
    if not stats["reports"]:
        log("No raw touchpad report arrived.")
    else:
        log(f"Reports: {stats['reports']}, devices: {len(devices)}")
        log(f"Most simultaneous touching fingers: {stats['max_tips']} (highest reported count: {stats['max_cc']})")
        log(f"Contact ids seen: {sorted(i for i in stats['ids'] if i is not None)}")
        log(f"Measured X: {stats['minx']}..{stats['maxx']}, measured Y: {stats['miny']}..{stats['maxy']}")
    log_file.close()
    print(f"Done. Reports: {stats['reports']}. Log: {LOG_PATH}", flush=True)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    main()
