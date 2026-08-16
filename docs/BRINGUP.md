# Bring-up: getting the board to say hello

"Bring-up" is the embedded word for the first stage of any hardware project:
prove the board powers on, prove your computer can talk to it, prove you can
run your own code on it. Nothing about oil prices happens here. If bring-up is
shaky, everything built on top of it is shaky, so it is worth doing properly
once.

You do not need to know what your board is before starting. Working that out
is step 2.

---

## The plan, so the steps make sense

The finished thing looks like this:

```
   Claude Code on your laptop
        |  hooks fire on session events
        v
   broker  (a small program on your laptop)
        |  holds current prices + session state
        |  ESP asks it "what should I show?" every few seconds
        v
   ESP board on your desk  ->  screen
```

The board never calls a price API itself and never holds an API key. It asks
one thing on your own network for a small blob of JSON and draws it. That keeps
the firmware simple, which matters because reflashing a board is slower than
restarting a program on your laptop.

We are building the bottom box first.

---

## Step 1: plug it in

Connect the board to your computer with a USB cable.

**The cable matters more than you would think.** Many USB cables are
charge-only: they carry power but no data. A board on a charge-only cable
lights up and looks perfectly healthy while your computer cannot see it at all.
If nothing is detected later, suspect the cable first — before drivers, before
the board.

A power LED should light up. Some boards also blink, because they ship with a
demo program.

## Step 2: find out what you have

Boards are labelled inconsistently and Amazon listings are vague, so rather
than guess, we ask the board directly.

```bash
pip install pyserial esptool
python3 tools/identify_board.py
```

This prints two things:

- **The USB-to-serial bridge chip** (CP2102, CH340, ...). Your board's main
  chip cannot speak USB directly on most models, so a second small chip
  translates. This is the one that sometimes needs a driver.
- **The ESP chip itself** — ESP32, ESP32-S3, ESP8266, and so on — read out of
  the chip's built-in bootloader, along with its flash size and MAC address.

The script only reads. It cannot modify or damage the board.

**Copy the whole output into the chat.** That is what tells me which firmware
target to keep and which of the candidate configs to delete.

### If no serial ports are found

In order of likelihood:

1. Charge-only USB cable. Try another cable.
2. Missing driver for the bridge chip:
   - CH340/CH9102: install the WCH driver (needed on macOS, sometimes Windows).
   - CP2102: built into modern macOS, Linux, and Windows 11.
3. On Linux, your user may not be allowed to open serial ports:
   ```bash
   sudo usermod -aG dialout $USER    # then log out and back in
   ```

### If the port is found but esptool cannot connect

Some boards do not enter their bootloader automatically. Do this by hand:

> hold **BOOT** (sometimes labelled **IO0**) → tap **EN**/**RST** → release **BOOT**

Then run the script again.

## Step 3: install the build tool

We use PlatformIO, which downloads the compiler for your specific chip and
builds from a config file checked into this repo — so the build is reproducible
rather than depending on menu settings you have to remember.

Easiest route: install the **PlatformIO IDE** extension in VS Code.

Command line alternative:

```bash
pip install platformio
```

> Already comfortable with the Arduino IDE from your kit's instructions? That
> works too — `firmware/src/main.cpp` is ordinary Arduino code. Install the
> ESP32 board support package, install the **Adafruit SSD1306** and **Adafruit
> GFX** libraries from Library Manager, and paste the file in as a sketch.

## Step 4: wire up the screen (if your kit has an I2C OLED)

Only if your kit included a small screen with **four** pins labelled roughly
`GND VCC SCL SDA`. Four pins means I2C, which is what the bring-up sketch
scans for. If your screen has seven or eight pins it is SPI — say so and I will
adjust.

**Unplug the board from USB before wiring.** Wiring a live board is how pins
get destroyed.

| OLED pin | ESP32 | ESP8266 (NodeMCU) |
| -------- | ----- | ----------------- |
| GND      | GND   | GND               |
| VCC      | 3V3   | 3V3               |
| SDA      | GPIO21| D2 (GPIO4)        |
| SCL      | GPIO22| D1 (GPIO5)        |

Use **3V3, not 5V**. The ESP's pins are 3.3V parts and 5V can damage them.

If your wiring differs from the table, do not worry — the sketch scans several
common pin pairs and reports which one your screen actually answered on.

## Step 5: flash the bring-up sketch

Substitute the env the identify script recommended:

```bash
cd firmware
pio run -e esp32dev -t upload
pio device monitor
```

`pio run` compiles, `-t upload` writes it to the board, `pio device monitor`
opens the serial output so you can read what the board says.

The first build downloads a compiler toolchain — expect a few minutes once,
then seconds thereafter.

## Step 6: read the output

You should see a banner, then the chip details, then an I2C scan, then a
repeating `alive` heartbeat. The onboard LED should blink once every two
seconds.

Three things are worth knowing about how to read this:

- **`0x3C` in the I2C scan is your OLED.** Nearly all of these panels are at
  `0x3C`, occasionally `0x3D`.
- **A scan that reports dozens of devices found nothing.** It means the data
  lines are floating rather than that you own a lot of hardware. Check wiring.
- **No blink is a clue, not a failure.** It means this board puts its LED on a
  different pin than the sketch guessed. Everything else still holds.

Paste the output back into the chat and we move on to WiFi and the broker.

---

## Safety notes, briefly

- Power the board from USB only, at this stage.
- 3.3V for everything. Not 5V.
- Never connect a pin directly to GND or 3V3 without knowing what it does.
- Unplug before rewiring.

None of this is dangerous to you — it is 5V over USB. The risk is to the board,
and it is modest. These boards are cheap and hard to kill by miswiring a screen.
