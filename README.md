# Desk display

A small screen for my desk that shows oil and natural gas prices, plus live
status from my Claude Code sessions.

Hardware: an ESP-32 development board.

## How it fits together

```
   Claude Code on the laptop
        |  hooks fire on session events (start, notification, stop)
        v
   broker  (small local service)
        |  caches commodity prices + current session state
        |  serves one JSON blob
        v
   ESP-32 on the desk  ->  screen
```

The board polls the broker over the LAN and draws the result. It never calls a
price API directly and holds no API keys — that keeps the firmware small and
means changing what is displayed rarely requires reflashing.

## Status

| Piece | State |
| ----- | ----- |
| Bring-up firmware (chip ID, I2C scan, blink, OLED hello) | written, not yet flashed |
| Board identification tool | written, tested |
| WiFi + broker polling | not started |
| Broker service | not started |
| Claude Code hooks | not started |
| Price feed | not started — data source still to be chosen |

## Layout

```
desk_display_bringup/
  desk_display_bringup.ino   the sketch; opens in the Arduino IDE as-is
platformio.ini               command-line build of that same sketch
tools/
  identify_board.py          reports which board and USB bridge are attached
docs/
  ARDUINO_IDE.md             Arduino IDE setup, start here
  BRINGUP.md                 wiring and first-run walkthrough
```

The sketch lives in an Arduino sketch folder and PlatformIO points at it, so
both toolchains build one copy of the source rather than two that drift.

## Getting started

New to this? Read [docs/ARDUINO_IDE.md](docs/ARDUINO_IDE.md), then
[docs/BRINGUP.md](docs/BRINGUP.md).

Command-line route, if you prefer it:

```bash
pip install pyserial esptool platformio

# Confirm what is plugged in.
python3 tools/identify_board.py

# Build and flash.
pio run -e esp32dev -t upload
pio device monitor
```

## Note on the price feed

Commodity price sources have not been chosen or tested yet. The sandbox this
was developed in blocks outbound access to finance APIs, so that piece needs to
be built and verified on a machine with real network access.
