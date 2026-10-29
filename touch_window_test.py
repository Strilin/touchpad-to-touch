# Touch receiver test: a full-screen window that logs the touch input it gets, to compare
# how Windows delivers touches in different registration modes.
#
# Usage:  python touch_window_test.py <mode> [seconds, default 60]
#   mode "palm":    RegisterTouchWindow without TWF_WANTPALM (palm rejection on) -> WM_TOUCH
#   mode "nopalm":  RegisterTouchWindow with TWF_WANTPALM (palm rejection off)   -> WM_TOUCH
#   mode "pointer": no RegisterTouchWindow, handles WM_POINTERDOWN/UPDATE/UP
# Writes touch_window_<mode>.txt. Escape or the time limit closes the window.

import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

import touchpad_logger as tp

user32 = tp.user32
kernel32 = tp.kernel32

WM_KEYDOWN = 0x0100
WM_TOUCH = 0x0240
WM_POINTERUPDATE, WM_POINTERDOWN, WM_POINTERUP = 0x0245, 0x0246, 0x0247
VK_ESCAPE = 0x1B
TWF_FINETOUCH, TWF_WANTPALM = 0x1, 0x2
TOUCHEVENTF_MOVE, TOUCHEVENTF_DOWN, TOUCHEVENTF_UP = 0x1, 0x2, 0x4
WS_POPUP, WS_VISIBLE, WS_EX_TOPMOST = 0x80000000, 0x10000000, 0x00000008


class TOUCHINPUT(ctypes.Structure):
    _fields_ = [("x", wt.LONG), ("y", wt.LONG), ("hSource", wt.HANDLE), ("dwID", wt.DWORD),
                ("dwFlags", wt.DWORD), ("dwMask", wt.DWORD), ("dwTime", wt.DWORD),
                ("dwExtraInfo", ctypes.c_size_t), ("cxContact", wt.DWORD), ("cyContact", wt.DWORD)]


user32.RegisterTouchWindow.argtypes = [wt.HWND, wt.ULONG]
user32.GetTouchInputInfo.argtypes = [wt.HANDLE, wt.UINT, ctypes.POINTER(TOUCHINPUT), ctypes.c_int]
user32.CloseTouchInputHandle.argtypes = [wt.HANDLE]
user32.SetForegroundWindow.argtypes = [wt.HWND]

mode = sys.argv[1] if len(sys.argv) > 1 else "nopalm"
seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
lines = []
moved = set()
t0 = time.perf_counter()
screen_w = screen_h = 1


def log(text):
    lines.append(f"{(time.perf_counter() - t0) * 1000:9.0f} ms {text}")


def frac(x, y):
    return f"x={x / (screen_w - 1):.3f} y={y / (screen_h - 1):.3f}"


def on_touch(wparam, lparam):
    n = wparam & 0xFFFF
    buf = (TOUCHINPUT * n)()
    if user32.GetTouchInputInfo(lparam, n, buf, ctypes.sizeof(TOUCHINPUT)):
        for ti in buf:
            pos = frac(ti.x / 100, ti.y / 100)  # WM_TOUCH coordinates are in 1/100 pixel
            if ti.dwFlags & TOUCHEVENTF_DOWN:
                log(f"DOWN id={ti.dwID} {pos}")
            elif ti.dwFlags & TOUCHEVENTF_UP:
                log(f"UP   id={ti.dwID} {pos}")
                moved.discard(ti.dwID)
            elif ti.dwFlags & TOUCHEVENTF_MOVE and ti.dwID not in moved:
                moved.add(ti.dwID)
                log(f"MOVE id={ti.dwID} {pos} (first move)")
    user32.CloseTouchInputHandle(lparam)


def on_pointer(msg, wparam, lparam):
    pid = wparam & 0xFFFF
    x, y = ctypes.c_short(lparam & 0xFFFF).value, ctypes.c_short((lparam >> 16) & 0xFFFF).value
    if msg == WM_POINTERDOWN:
        log(f"DOWN id={pid} {frac(x, y)}")
    elif msg == WM_POINTERUP:
        log(f"UP   id={pid} {frac(x, y)}")
        moved.discard(pid)
    elif pid not in moved:
        moved.add(pid)
        log(f"MOVE id={pid} {frac(x, y)} (first move)")


@tp.WNDPROC
def wndproc(hwnd, msg, wparam, lparam):
    if msg == WM_TOUCH:
        on_touch(wparam, lparam)
        return 0
    if mode == "pointer" and msg in (WM_POINTERDOWN, WM_POINTERUPDATE, WM_POINTERUP):
        on_pointer(msg, wparam, lparam)
        return 0
    if (msg == WM_KEYDOWN and wparam == VK_ESCAPE) or msg == tp.WM_TIMER:
        user32.DestroyWindow(hwnd)
        return 0
    if msg == tp.WM_DESTROY:
        user32.PostQuitMessage(0)
        return 0
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def main():
    global screen_w, screen_h
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except AttributeError:
        pass
    screen_w, screen_h = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    hinst = kernel32.GetModuleHandleW(None)
    wc = tp.WNDCLASSEXW()
    wc.cbSize = ctypes.sizeof(tp.WNDCLASSEXW)
    wc.lpfnWndProc = wndproc
    wc.hInstance = hinst
    wc.lpszClassName = "TouchWindowTest"
    user32.RegisterClassExW(ctypes.byref(wc))
    title = f"Touch window test {mode}"
    hwnd = user32.CreateWindowExW(WS_EX_TOPMOST, wc.lpszClassName, title, WS_POPUP | WS_VISIBLE,
                                  0, 0, screen_w, screen_h, None, None, hinst, None)
    if mode == "palm":
        user32.RegisterTouchWindow(hwnd, TWF_FINETOUCH)
    elif mode == "nopalm":
        user32.RegisterTouchWindow(hwnd, TWF_FINETOUCH | TWF_WANTPALM)
    user32.keybd_event(0x12, 0, 0, 0)
    user32.keybd_event(0x12, 0, 2, 0)
    user32.SetForegroundWindow(hwnd)
    user32.SetTimer(hwnd, 1, int(seconds * 1000), None)
    log(f"start mode={mode} screen {screen_w}x{screen_h}")
    print(f"{title} open for {seconds:g} s", flush=True)
    tp.message_loop()
    with open(os.path.join(tp.SCRIPT_DIR, f"touch_window_{mode}.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
