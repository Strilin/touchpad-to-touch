# TouchpadToTouch

Turn a laptop's touchpad into a touchscreen on Windows.

The whole touchpad surface is mapped to the whole screen: the top-left corner of the pad is
the top-left corner of the screen, the middle of the pad is the middle of the screen, and so on.
Every finger on the pad is sent to Windows as a real touch at the matching screen position, so
File Explorer, browsers, games and any other program behave exactly as if you were touching a
touchscreen. Multiple fingers work too (drags, two-finger gestures, pinch to zoom).

## Why?

- Use touch-only apps and games on a laptop that has no touchscreen.
- Test and develop touch interfaces without touch hardware.
- Accessibility: blind and low-vision users can explore and practise touch interaction with the
  touchpad, whose physical edges make it easy to find the corners and the middle of the screen.
  It started as a helper for audio games and a handwriting trainer written in
  [NVGT](https://nvgt.gg), but it works with any Windows program.

## Requirements

- Windows 10 or 11.
- A **Precision Touchpad** (most modern laptops; listed under Settings > Bluetooth & devices >
  Touchpad). Older touchpads with vendor-only drivers are not supported.
- No installation and no administrator rights. Pure Python 3 + `ctypes`, no dependencies.

## Usage

Download `TouchpadToTouch.zip` from the [Releases](../../releases) page and run
`TouchpadToTouch.exe` (no Python needed), or run the script:

```
python touchpad_to_touch.py [seconds] [--keep-aspect] [--log]
```

It runs invisibly in the background (no window).

- `seconds`: quit after this many seconds (default `0` = run until stopped).
- `--keep-aspect`: keep the pad's aspect ratio (centered on the screen) instead of stretching
  the pad over the whole screen.
- `--log`: write finger down / up events to `inject_log.txt`.
- Stop with **Ctrl+Alt+Shift+Q**, or end the process in Task Manager.
  (Not Ctrl+Alt+Q: that is AltGr+Q, which types `\` on many keyboard layouts.)

### Sounds

| Sound | Meaning |
|---|---|
| one high beep | started |
| one low beep | stopped |
| two short beeps | already running, the second copy quits |
| three low beeps | error, e.g. no Precision Touchpad (reason in `touchpad_to_touch_error.txt`) |

To start it with Windows, put a shortcut to the .exe into the folder opened by
Win+R `shell:startup`.

## Good to know

- The touchpad keeps working as a mouse at the same time: the pointer still moves and a tap
  still clicks.
- **Screen readers:** JAWS intercepts all touch input (from real touchscreens as well) before
  programs see it. While JAWS runs, a touch that does not move (tap, press and hold) reaches the
  program only when the finger is lifted, and stationary two-finger touches can be lost, even
  when JAWS passes gestures through to Windows. Without JAWS every touch arrives immediately.
  This was measured with the self-test below; it is not specific to this tool.
- Injecting into windows of elevated (administrator) programs is blocked by Windows.
- Privacy: it only reads the local touchpad, does not read the keyboard, and sends nothing
  anywhere.

## How it works

1. `RegisterRawInputDevices` with usage page `0x0D` (digitizer), usage `0x05` (touchpad) and
   `RIDEV_INPUTSINK`, on a hidden window.
2. Each `WM_INPUT` report is parsed with `HidP_GetUsageValue` / `HidP_GetUsages`
   (contact id `0x51`, X `0x30`, Y `0x31`, tip switch `0x42`, contact count `0x54`).
   The coordinate range comes from the pad's own HID descriptor, so pads of any size and
   resolution work, including ones that split a frame over several reports ("hybrid mode").
3. The touching fingers are mapped to screen pixels (DPI aware) and sent with
   `InjectTouchInput` (down / update / up per finger).

## Diagnostic tools

- `touchpad_logger.py [seconds]`: writes the touchpad's HID capabilities (logical range,
  physical size, finger slots) and every raw report to `touchpad_log.txt`. Use it to check
  whether a touchpad is supported.
- `inject_selftest.py [delay]`: injects a fixed sequence of touches (taps, press and hold,
  drags, flicks, two-finger taps / holds / drags) without the touchpad, to see which gestures
  reach a program.
- `touch_window_test.py <palm|nopalm|pointer> [seconds]`: a full-screen window that logs the
  touches it receives (`WM_TOUCH` with or without palm rejection, or `WM_POINTER`).

## Building the .exe

```
python -m PyInstaller --onefile --noconsole --name TouchpadToTouch touchpad_to_touch.py
```

## License

MIT, see [LICENSE](LICENSE).
