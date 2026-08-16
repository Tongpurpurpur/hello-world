# Arduino IDE setup

The path to a running board, using the Arduino IDE. This is the friendlier of
the two options and what almost every ESP-32 tutorial you find online assumes,
so it is worth starting here.

You need to do steps 1–3 exactly once, ever. After that, flashing is one button.

> Everything below is a one-time toolchain setup. If it feels like a lot for a
> blinking LED — it is, and it is also the entire setup for every ESP project
> you ever do afterwards.

---

## 1. Install the Arduino IDE

Download version 2.x from [arduino.cc/en/software](https://www.arduino.cc/en/software).
The download page offers a donation first — "Just Download" is free and is the
same software.

**macOS.** Open the `.dmg`, drag Arduino IDE to Applications. On first launch
macOS may refuse to open it because it came from the internet: right-click the
app and choose **Open**, then confirm. (Right-click → Open works where a normal
double-click is blocked.)

Your board will most likely also need a USB driver — macOS is the OS most
likely to need one. If no port appears in step 5, install the
[CH34x driver from WCH](https://www.wch-ic.com/downloads/CH341SER_MAC_ZIP.html)
and reboot.

**Windows.** Run the `.exe` installer and accept the driver-installation
prompts that appear during it — those are the USB-serial drivers, and skipping
them is the usual reason no COM port shows up later. Your board appears as
`COM3`, `COM4`, or similar.

**Linux.** Download the AppImage, then make it executable:

```bash
chmod +x arduino-ide_*.AppImage
./arduino-ide_*.AppImage
```

There is one extra step, and without it the board will not appear even though
it is plugged in and working — your user needs permission to open serial ports:

```bash
sudo usermod -aG dialout $USER
```

Then **log out and back in** for it to take effect.

## 2. Teach it about ESP-32 boards

The IDE ships knowing only about Arduino's own boards. The ESP-32 is made by a
different company, so you point the IDE at Espressif's catalogue.

1. **File → Preferences** (on macOS, **Arduino IDE → Settings**)
2. Find the **Additional Board Manager URLs** field
3. Paste in:

   ```
   https://espressif.github.io/arduino-esp32/package_esp32_index.json
   ```

4. **OK**
5. **Tools → Board → Boards Manager**, search `esp32`
6. Install **"esp32 by Espressif Systems"**

That download is around a gigabyte — it contains a complete compiler for the
chip. Expect several minutes. It only happens once.

> Careful: a separate entry named "Arduino ESP32 Boards" may also appear. You
> want the **Espressif Systems** one.

## 3. Install the two display libraries

Only needed if your kit has a small screen, but installing them anyway is
harmless and the sketch expects them either way.

1. **Tools → Manage Libraries** (or the books icon in the left sidebar)
2. Search `Adafruit SSD1306`, install it
3. It will offer to **"Install all"** dependencies — accept. That pulls in
   Adafruit GFX and Adafruit BusIO, which SSD1306 needs.

## 4. Open the sketch

**File → Open**, and select:

```
desk_display_bringup/desk_display_bringup.ino
```

The Arduino IDE requires a sketch to sit in a folder of the same name, which is
why that folder exists and why neither it nor the file should be renamed.

## 5. Pick the board and port

- **Tools → Board → esp32 → ESP32 Dev Module**

  "Dev Module" is the generic ESP-32 profile. It is the right choice for a
  board simply labelled ESP-32.

- **Tools → Port →** pick the port that appears when the board is plugged in.

  Unsure which it is? Unplug the board, look at the list, plug it back in, look
  again. The one that appeared is yours.

  - macOS: `/dev/cu.usbserial-…` or `/dev/cu.SLAB_USBtoUART`
  - Linux: `/dev/ttyUSB0`
  - Windows: `COM3`, `COM4`, …

  **No port listed at all?** Do not fight the IDE — see
  [BRINGUP.md](BRINGUP.md#if-no-serial-ports-are-found). The usual answer is a
  charge-only USB cable.

## 6. Upload

Press the **→** (right arrow) button in the toolbar. It compiles, then writes
to the board.

The first compile is slow — a minute or two. Later ones are quick.

## 7. Watch it run

Open **Tools → Serial Monitor**, and set the baud dropdown to **115200**.

Press the **EN**/**RST** button on the board to restart it so you see the
banner from the beginning.

You should get: a banner, the chip details, an I2C scan, and then a repeating
`alive` heartbeat. The onboard LED should blink once every two seconds.

**Copy that whole output into the chat.**

---

## When it does not work

**`A fatal error occurred: Failed to connect to ESP32`**

The board did not enter its bootloader on its own. Do it manually: hold
**BOOT** (sometimes labelled **IO0**), tap **EN**/**RST**, release **BOOT**,
then hit upload again. Some boards need this on every single upload — annoying,
but normal, and not a sign of a fault.

**The Serial Monitor shows garbage characters**

The baud rate is wrong. Set it to 115200.

A short burst of garbage at boot before the banner is normal and expected —
that is the chip's own bootloader talking at a different speed.

**`Adafruit_SSD1306.h: No such file or directory`**

Step 3 did not complete. Reinstall the library and accept the dependencies.

**The port vanishes mid-upload**

Usually a power issue: an unpowered USB hub or a marginal cable. Plug directly
into the computer.

---

## About the other tool

This repo also has a `platformio.ini`, which builds the exact same file from
the command line. That is what I use to check builds; you do not need it.

Both tools read the same `desk_display_bringup.ino`, so there is one copy of
the code and no chance of the two drifting apart.

---

Sources for the install steps:
[Espressif Arduino-ESP32 installation docs](https://docs.espressif.com/projects/arduino-esp32/en/latest/installing.html),
[Random Nerd Tutorials](https://randomnerdtutorials.com/installing-the-esp32-board-in-arduino-ide-windows-instructions/)
