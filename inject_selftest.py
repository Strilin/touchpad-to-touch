# Injection self-test: injects a fixed, scripted sequence of touches (no touchpad needed)
# so we can check which kinds of gestures reach the target program and which get lost.
# Each gesture is logged with its start time to selftest_log.txt; compare it with the
# target program's own log.
#
# Usage:  python inject_selftest.py [start delay in seconds, default 5]
# Keep your hands off the touchpad and mouse while it runs (about 30 seconds).

import sys
import time
import winsound

import touchpad_logger as tp
import touchpad_to_touch as tt

FRAME = 0.008  # seconds between injected frames (about the touchpad's report rate)
log_lines = []


def log(line):
    t = time.perf_counter() - t_start
    log_lines.append(f"{t:8.3f} {line}")
    print(log_lines[-1], flush=True)


def px(fx, fy):
    return int(fx * (screen_w - 1)), int(fy * (screen_h - 1))


def inject(frame):
    """frame: list of (pointer id, (fx, fy), flags)."""
    infos = [tt.Injector.info(pid, px(*pos), flags) for pid, pos, flags in frame]
    arr = (tt.POINTER_TOUCH_INFO * len(infos))(*infos)
    if not tt.user32.InjectTouchInput(len(infos), arr):
        log(f"  ERROR: InjectTouchInput failed, Windows error code {tt.ctypes.get_last_error()}")
    time.sleep(FRAME)


DOWN = tt.POINTER_FLAG_DOWN | tt.POINTER_FLAG_INRANGE | tt.POINTER_FLAG_INCONTACT
MOVE = tt.POINTER_FLAG_UPDATE | tt.POINTER_FLAG_INRANGE | tt.POINTER_FLAG_INCONTACT
UP = tt.POINTER_FLAG_UP


def gesture(name, paths, seconds):
    """paths: one (start, end) pair of screen fractions per finger; fingers move linearly."""
    log(f"{name}: fingers={len(paths)} start={[p[0] for p in paths]} end={[p[1] for p in paths]} "
        f"duration={seconds:g}s")
    steps = max(1, round(seconds / FRAME))

    def at(i):
        k = i / steps
        return [((s[0] + (e[0] - s[0]) * k), (s[1] + (e[1] - s[1]) * k)) for s, e in paths]

    inject([(pid, pos, DOWN) for pid, pos in enumerate(at(0))])
    for i in range(1, steps + 1):
        inject([(pid, pos, MOVE) for pid, pos in enumerate(at(i))])
    inject([(pid, pos, UP) for pid, pos in enumerate(at(steps))])
    time.sleep(1.0)


def main():
    global t_start, screen_w, screen_h
    delay = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0
    try:
        tt.user32.SetProcessDpiAwarenessContext(tt.ctypes.c_void_p(-4))
    except AttributeError:
        pass
    screen_w = tt.user32.GetSystemMetrics(tt.SM_CXSCREEN)
    screen_h = tt.user32.GetSystemMetrics(tt.SM_CYSCREEN)
    if not tt.user32.InitializeTouchInjection(tt.MAX_CONTACTS, tt.TOUCH_FEEDBACK_DEFAULT):
        raise tt.ctypes.WinError(tt.ctypes.get_last_error())
    print(f"Self-test starts in {delay:g} seconds, hands off the touchpad and mouse.", flush=True)
    time.sleep(delay)
    t_start = time.perf_counter()
    log(f"start {time.strftime('%Y-%m-%d %H:%M:%S')}, screen {screen_w}x{screen_h}")
    winsound.Beep(1200, 120)
    time.sleep(1.0)

    for i, x in enumerate((0.2, 0.4, 0.6, 0.8)):
        gesture(f"tap {i + 1}", [((x, 0.3), (x, 0.3))], 0.05)
    for i in range(2):
        gesture(f"long press {i + 1}", [((0.5, 0.5), (0.5, 0.5))], 0.8)
    for i in range(3):
        gesture(f"slow drag {i + 1}", [((0.3, 0.6), (0.7, 0.6))], 1.5)
    for i in range(3):
        gesture(f"fast flick left {i + 1}", [((0.7, 0.45), (0.35, 0.5))], 0.2)
    for i in range(3):
        gesture(f"two-finger tap {i + 1}", [((0.4, 0.4), (0.4, 0.4)), ((0.55, 0.45), (0.55, 0.45))], 0.08)
    for i in range(2):
        gesture(f"two-finger hold {i + 1}", [((0.4, 0.4), (0.42, 0.42)), ((0.55, 0.45), (0.57, 0.47))], 0.8)
    for i in range(2):
        gesture(f"two-finger drag {i + 1}", [((0.3, 0.3), (0.6, 0.3)), ((0.3, 0.5), (0.6, 0.5))], 1.0)

    log("end")
    winsound.Beep(600, 200)
    with open(tp.os.path.join(tp.SCRIPT_DIR, "selftest_log.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines) + "\n")


if __name__ == "__main__":
    main()
