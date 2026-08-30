#!/usr/bin/env python3
"""Work out which ESP board is plugged into this machine.

Run it with the board connected by USB:

    pip install pyserial esptool
    python3 tools/identify_board.py

It lists serial ports, names the USB-serial bridge chip from its VID/PID, then
asks the ROM bootloader what it is. Paste the whole output back into the chat
and we pin down the firmware target.

Nothing here writes to the board. It only reads.
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys

# USB-serial bridges these boards use. The bridge chip tells you which driver
# you need; it does not tell you which ESP is behind it. The exceptions are the
# 303a entries, which are Espressif's own VID for chips with native USB, and
# those do identify the silicon.
KNOWN_USB_IDS = {
    (0x10C4, 0xEA60): "CP2102 (Silicon Labs) - stock driver on modern macOS/Linux/Win11",
    (0x10C4, 0xEA70): "CP2105 dual (Silicon Labs)",
    (0x1A86, 0x7523): "CH340 (WCH) - needs the WCH driver on macOS, sometimes Windows",
    (0x1A86, 0x7522): "CH340 variant (WCH)",
    (0x1A86, 0x55D4): "CH9102F (WCH) - needs the WCH driver on macOS",
    (0x0403, 0x6001): "FT232R (FTDI)",
    (0x0403, 0x6015): "FT231X (FTDI)",
    (0x303A, 0x1001): "Espressif native USB (ESP32-S2/S3/C3 USB-CDC)",
    (0x303A, 0x0002): "Espressif ESP32-S2 native USB",
    (0x303A, 0x1000): "Espressif USB-JTAG/serial debug unit",
}

# Ports macOS always shows whether or not anything is plugged in. Seeing only
# these means the board is not being detected, however full the menu looks.
NOT_YOUR_BOARD = (
    "Bluetooth-Incoming-Port",
    "BLTH",
    "debug-console",
    "wlan-debug",
)

# Fragments that appear in the device name of a real USB-serial board.
LOOKS_LIKE_A_BOARD = (
    "usbserial",     # CH340 / generic
    "wchusbserial",  # CH340 / CH9102 with the WCH driver
    "SLAB_USBtoUART",  # CP2102 with the Silicon Labs driver
    "usbmodem",      # native-USB chips (S2/S3/C3)
    "ttyUSB",
    "ttyACM",
)


def port_verdict(device: str) -> str:
    """Say whether a port name is plausibly the board."""
    if any(noise in device for noise in NOT_YOUR_BOARD):
        return "built into macOS - NOT your board"
    if any(hint in device for hint in LOOKS_LIKE_A_BOARD):
        return "this looks like your board"
    return "unclear - use --watch to confirm"


# Maps what esptool reports to the platformio.ini env to build.
CHIP_TO_ENV = {
    "ESP32": "esp32dev",
    "ESP32-S2": "esp32-s2-saola-1 (not yet in platformio.ini - ask and I'll add it)",
    "ESP32-S3": "esp32-s3-devkitc-1",
    "ESP32-C3": "esp32-c3-devkitm-1",
    "ESP32-C6": "esp32-c6-devkitc-1 (needs platform espressif32 >= 6.8)",
    "ESP32-H2": "esp32-h2-devkitm-1",
    "ESP8266": "nodemcuv2",
    "ESP8285": "esp8285",
}


def hr(title: str) -> None:
    print()
    print(f"=== {title} ===")


def list_ports() -> list:
    try:
        from serial.tools import list_ports as lp
    except ImportError:
        print("pyserial is not installed, so I cannot read USB VID/PID.")
        print("  pip install pyserial esptool")
        return []
    return sorted(lp.comports(), key=lambda p: p.device)


def describe_ports(ports: list) -> list:
    """Print each port and return the ones that look like an ESP board."""
    if not ports:
        print("No serial ports found at all.")
        print()
        print("Things that cause this, in the order worth checking:")
        print("  1. The USB cable is charge-only. This is the single most")
        print("     common cause. Try a different cable before anything else.")
        print("  2. No driver for the USB-serial bridge (CH340 especially).")
        print("  3. The board is not actually powered - is any LED lit?")
        return []

    candidates = []
    for port in ports:
        vid = port.vid
        pid = port.pid
        ident = ""
        if vid is not None and pid is not None:
            ident = KNOWN_USB_IDS.get((vid, pid), "unrecognised - paste this line into the chat")
            vidpid = f"{vid:04x}:{pid:04x}"
        else:
            vidpid = "no usb id (built-in or virtual port)"

        print(f"{port.device}")
        print(f"    verdict:     {port_verdict(port.device)}")
        print(f"    usb id:      {vidpid}")
        print(f"    description: {port.description}")
        if port.manufacturer:
            print(f"    vendor:      {port.manufacturer}")
        if port.serial_number:
            print(f"    serial:      {port.serial_number}")
        if ident:
            print(f"    -> {ident}")

        if vid is not None and (vid, pid) in KNOWN_USB_IDS:
            candidates.append(port)
        elif vid is not None:
            # Unknown bridge, still worth probing.
            candidates.append(port)

    return candidates


def esptool_cmd() -> list | None:
    """esptool ships as both a console script and a module, and v4 vs v5 differ."""
    for exe in ("esptool.py", "esptool"):
        found = shutil.which(exe)
        if found:
            return [found]
    # Fall back to the module, which is how a pip install into a venv usually lands.
    probe = subprocess.run(
        [sys.executable, "-m", "esptool", "--help"],
        capture_output=True,
        text=True,
    )
    if probe.returncode == 0:
        return [sys.executable, "-m", "esptool"]
    return None


def probe_with_esptool(port: str) -> None:
    base = esptool_cmd()
    if base is None:
        print("esptool is not installed, skipping the ROM probe.")
        print("  pip install esptool")
        return

    # esptool 5 renamed the subcommands to hyphens but kept underscore aliases;
    # esptool 4 only knows underscores. Try the modern spelling, fall back.
    for chip_cmd, flash_cmd in (("chip-id", "flash-id"), ("chip_id", "flash_id")):
        cmd = base + ["--port", port, chip_cmd]
        print(f"$ {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        out = (result.stdout or "") + (result.stderr or "")

        if "invalid choice" in out or "unrecognized arguments" in out:
            continue

        print(out.strip())

        cmd = base + ["--port", port, flash_cmd]
        print()
        print(f"$ {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        print(((result.stdout or "") + (result.stderr or "")).strip())

        interpret(out)
        return

    print("Could not find a working esptool subcommand spelling.")


def interpret(esptool_output: str) -> None:
    hr("what to build")

    # Do this first: a failed connect echoes the chip name it was hoping for
    # ("Failed to connect to ESP32"), which would otherwise read as a positive
    # identification of hardware we never actually reached.
    if "fatal error" in esptool_output.lower() or "failed to connect" in esptool_output.lower():
        print("esptool did not reach the bootloader, so the chip is still unknown.")
        print()
        print("Most boards need a manual bootloader entry:")
        print("  hold BOOT (sometimes labelled IO0), tap EN/RST, release BOOT,")
        print("  then run this script again.")
        print()
        print("If that does not help, the usual culprit is a charge-only USB cable.")
        return

    matched = None
    # Longest names first so ESP32-S3 wins over ESP32.
    for chip in sorted(CHIP_TO_ENV, key=len, reverse=True):
        if chip.lower() in esptool_output.lower():
            matched = chip
            break

    if matched is None:
        print("Could not read a chip name out of the esptool output.")
        print("Paste the output above into the chat and I'll read it.")
        return

    print(f"chip:  {matched}")
    print(f"build: pio run -e {CHIP_TO_ENV[matched]} -t upload")

    if "failed to connect" in esptool_output.lower():
        print()
        print("esptool could not reach the bootloader. On many boards you must")
        print("hold BOOT (sometimes labelled IO0), tap EN/RST, then release BOOT.")


def watch_ports() -> int:
    """Report ports appearing and disappearing, so a replug identifies the board.

    Reading a port list is guesswork; watching one change is proof. Whatever
    shows up when you plug the board in IS the board.
    """
    import time

    try:
        seen = {p.device for p in list_ports()}
    except Exception as exc:  # noqa: BLE001
        print(f"cannot read ports: {exc}")
        return 1

    print("Ports present right now:")
    for device in sorted(seen):
        print(f"  {device}   ({port_verdict(device)})")
    if not seen:
        print("  (none)")

    print()
    print("Now UNPLUG the board, wait two seconds, and PLUG IT BACK IN.")
    print("Press Ctrl-C when you are done.")
    print()

    try:
        while True:
            time.sleep(0.4)
            now = {p.device for p in list_ports()}

            for device in sorted(now - seen):
                print(f"  + APPEARED     {device}")
                print(f"                 ^ THIS IS YOUR BOARD. Select it in "
                      f"Tools > Port.")
            for device in sorted(seen - now):
                print(f"  - disappeared  {device}")
                print(f"                 ^ that was the board being unplugged")

            seen = now
    except KeyboardInterrupt:
        print()
        print("stopped.")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="skip detection and probe this port")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="watch ports appear/disappear as you replug, to identify the board",
    )
    parser.add_argument(
        "--no-probe",
        action="store_true",
        help="list ports only, do not talk to the board",
    )
    args = parser.parse_args()

    if args.watch:
        hr("watching ports")
        return watch_ports()

    hr("host")
    print(f"{platform.system()} {platform.release()} ({platform.machine()})")
    print(f"python {platform.python_version()}")

    hr("serial ports")
    if args.port:
        candidates = [args.port]
        print(f"using {args.port} as given")
    else:
        candidates = [p.device for p in describe_ports(list_ports())]

    if args.no_probe:
        return 0

    if not candidates:
        print()
        print("Nothing to probe.")
        return 1

    for device in candidates:
        hr(f"probing {device}")
        try:
            probe_with_esptool(device)
        except subprocess.TimeoutExpired:
            print("timed out - the board may need BOOT held down while connecting")
        except Exception as exc:  # noqa: BLE001 - a diagnostic tool should not die
            print(f"probe failed: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
