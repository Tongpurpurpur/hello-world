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

### Checking for the port without installing anything (macOS)

Before reaching for any script: open **Terminal** and run

```bash
ls /dev/cu.*
```

Unplug the board, run it again, and compare. The line that disappears is your
board. Plug it back in and run it a third time to confirm it returns.

`/dev/cu.Bluetooth-Incoming-Port` and `/dev/cu.debug-console` are always there
and are never the board.

### If no serial ports are found

There are two quite different causes, and one command separates them. On macOS:

```bash
system_profiler SPUSBDataType
```

This lists every USB device the Mac can see, whether or not a driver exists for
it. Look for an entry like `USB2.0-Serial`, `USB Single Serial`, `CH340`,
`CP2102 USB to UART Bridge Controller`, or `USB JTAG/serial debug unit`.

It can take ten or twenty seconds to print. If it returns *nothing at all*, try
the lower-level view instead:

```bash
ioreg -p IOUSB -w0 -l | grep -i "USB Product Name"
```

On Apple Silicon the built-in keyboard and trackpad are not USB devices, so
genuinely empty output is possible and does not by itself mean the command
failed.

#### Validate the test before trusting it

An empty result is only meaningful if the command works at all. Plug in any
other USB device you own — a phone, a mouse, a memory stick — and run the same
command again:

- **The other device appears, the board does not.** The test works, and the
  board really is not enumerating. Cable first, then the board itself.
- **Nothing appears for either.** The test is not telling you anything. Suspect
  the port, the dongle, or how the command was run, and switch to the GUI:
  **Apple menu → About This Mac → More Info → System Report → USB**.

Checking your instrument against a known-good device before drawing conclusions
from it is worth the thirty seconds, here and generally.

**The board IS listed here, but no `/dev/cu.*` entry exists.**
The cable and the board are fine; macOS just has no driver to expose it as a
serial port. Install the
[CH34x driver from WCH](https://www.wch-ic.com/downloads/CH341SER_MAC_ZIP.html),
reboot, and check again. On recent macOS the install is also blocked until you
approve it under **System Settings → Privacy & Security** — scroll to the
bottom for a message about blocked system software and click **Allow**. Missing
that step is why the driver often appears to install and change nothing.

**The board is NOT listed.** No driver will help, because nothing is arriving.
In order of likelihood:

1. **Charge-only USB cable.** By far the most common. Many cables carry power
   but no data lines at all. The board lights up and looks perfectly healthy.
   A lit power LED is not evidence of a working cable — it is exactly what a
   charge-only cable looks like. Try a different cable, ideally one you know
   has carried data (a phone sync cable that shows up in Finder).
2. **A hub or adapter in the way.** Plug directly into the Mac. Some USB-C
   dongles do not pass through serial devices reliably.
3. **Too much current being drawn** by something on the breadboard, causing the
   port to shut down. Disconnect everything except the board itself.
4. **The board's USB port or bridge chip is faulty.** Rare, but these are cheap
   boards. Suspect this only after trying two known-good cables.

On Linux, a port that exists but is invisible to the IDE is usually permissions:

```bash
sudo usermod -aG dialout $USER    # then log out and back in
```

### If the port is found but esptool cannot connect

Some boards do not enter their bootloader automatically. Do this by hand:

> hold **BOOT** (sometimes labelled **IO0**) → tap **EN**/**RST** → release **BOOT**

Then run the script again.

## Step 3: install the build tool

You need something that can compile code and send it to the board. Use the
**Arduino IDE** — it is the friendliest option and what nearly every ESP-32
tutorial online assumes.

**→ Follow [ARDUINO_IDE.md](ARDUINO_IDE.md) for that, then come back here at
step 4 for the wiring.**

There is also a `platformio.ini` in this repo, which builds the same sketch
from the command line. Both tools read the same source file, so there is one
copy of the code. Use whichever you like; the Arduino IDE is the recommended
starting point.

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

### Your module may not use those exact names

Vendors label the same four pins differently. These are all the same thing:

| Also printed as | Means | Connect to |
| --------------- | ----- | ---------- |
| `VDD`, `VCC`, `3V3`, `+`  | power in | **3V3** |
| `GND`, `VSS`, `-`         | ground   | GND |
| `SCL`, `SCK`, `SCX`, `CLK`| clock    | GPIO21's partner, GPIO22 |
| `SDA`, `SDI`, `DATA`      | data     | GPIO21 |

**Match by name, never by position.** Pin *order* is not standardised — some
modules are `GND VDD SCK SDA`, others are `VDD GND SCL SDA`. Two modules that
look identical from across the desk can have power and ground in opposite
places, and wiring the second like the first is the single most common way to
cook one.

If your wiring differs from the table, do not worry — the sketch scans several
common pin pairs and reports which one your screen actually answered on.

## Step 5: flash the bring-up sketch

In the Arduino IDE: press **→** to upload, then open the **Serial Monitor** at
**115200**. Full walkthrough in [ARDUINO_IDE.md](ARDUINO_IDE.md).

From the command line instead:

```bash
pio run -e esp32dev -t upload
pio device monitor
```

`pio run` compiles, `-t upload` writes it to the board, `pio device monitor`
opens the serial output so you can read what the board says.

Either way, the first build downloads a compiler — expect a few minutes once,
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

## If something gets hot, or smells

**Unplug immediately.** Heat means current is going somewhere it should not,
and the damage is cumulative — a component that gets hot for five seconds
usually survives, one left powered for a minute often does not.

Then work through this before reconnecting.

### A hot OLED

In order of likelihood:

1. **VCC and GND are swapped.** This is the overwhelmingly common cause. The
   module is powered backwards, and reverse polarity turns it into a heater.
   Check the labels on the screen itself, not the position of the wires —
   pin order is *not* consistent between modules. Plenty are `GND VCC SCL SDA`,
   plenty of others are `VCC GND SCL SDA`. Two modules that look identical can
   differ here.

2. **VCC is on 5V or VIN instead of 3V3.** Some modules tolerate it, some do
   not. Use the **3V3** pin.

3. **A short across the breadboard.** The two long rails down the sides are
   continuous strips; the short rows in the middle are connected in groups of
   five. If VCC and GND end up in the same row, they are shorted together. A
   wire whose stripped end is a little too long can also bridge two rows.

Feel the screen after five seconds with power on. Warm is acceptable. Hot
enough that you want to let go is not.

### Is the screen dead?

Possibly, but often not — these panels survive brief reverse polarity more
often than you would expect. Rewire it correctly and run the bring-up sketch:
if the I2C scan reports a device at `0x3C`, the controller is alive.

If it stays silent, the module is likely gone. They cost a few dollars and the
rest of the project is unaffected — the ESP-32 itself is almost certainly fine,
since the fault was on the module side.

### Red LED on the ESP-32

Not a fault. Nearly every ESP32 devkit has a red power LED that is on solid
whenever the board has power. It means the board is powered, nothing more.

### Overheating can also hide your board

Worth knowing, because it links two symptoms that look unrelated: a miswired
module draws more current than the USB port will supply, and the host responds
by cutting power to the port. macOS may show a "USB device disabled" notice, or
nothing at all. The board then does not appear under **Tools → Port**, or
appears and vanishes.

So if the screen was hot *and* the port would not show up, fix the wiring
first and re-check the port afterwards. One cause, two symptoms.

## Safety notes, briefly

- Power the board from USB only, at this stage.
- 3.3V for everything. Not 5V.
- Never connect a pin directly to GND or 3V3 without knowing what it does.
- **Unplug before rewiring.** Every time.
- Check polarity twice before applying power. It is the one mistake that
  reliably destroys parts.

None of this is dangerous to you — it is 5V over USB, which cannot hurt you.
The risk is to the components, and it is real but cheap.
