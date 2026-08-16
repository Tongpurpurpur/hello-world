// Bring-up sketch for the desk display project.
//
// This does not know what board it is running on, and that is the point. Flash
// it, open the Serial Monitor at 115200, and it reports the chip, the flash,
// the MAC, and every I2C device it can find across the pin pairs these starter
// kits commonly wire an OLED to. If it finds an SSD1306 it draws to it.
//
// Builds in either the Arduino IDE (open this folder's .ino) or PlatformIO
// (`pio run -e esp32dev -t upload` from the repo root). Keep it compiling in
// both -- see docs/ARDUINO_IDE.md.
//
// Requires these libraries (Arduino IDE: Library Manager; PlatformIO: already
// listed in platformio.ini):
//   Adafruit SSD1306
//   Adafruit GFX Library

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#if defined(ARDUINO_ARCH_ESP32)
#include <WiFi.h>
#elif defined(ARDUINO_ARCH_ESP8266)
#include <ESP8266WiFi.h>
#endif

// PlatformIO injects the env name as a build flag. The Arduino IDE has no
// equivalent, so give it a value there rather than failing to compile.
#ifndef PIO_ENV_NAME
#define PIO_ENV_NAME "arduino-ide"
#endif

// ---------------------------------------------------------------------------
// Board-dependent guesses. Overridden at runtime by whatever the I2C scan finds.
// ---------------------------------------------------------------------------

#ifndef STATUS_LED_PIN
#if defined(LED_BUILTIN)
#define STATUS_LED_PIN LED_BUILTIN
#else
#define STATUS_LED_PIN 2
#endif
#endif

// Many ESP8266 boards drive the onboard LED low-active.
#if defined(ARDUINO_ARCH_ESP8266)
#define LED_ON LOW
#define LED_OFF HIGH
#else
#define LED_ON HIGH
#define LED_OFF LOW
#endif

struct PinPair {
  uint8_t sda;
  uint8_t scl;
  const char *label;
};

// Candidate SDA/SCL pairs, in the order worth trying. The first entry is the
// core's own default, the rest cover the wirings these kits ship with.
static const PinPair kCandidatePins[] = {
#if defined(ARDUINO_ARCH_ESP8266)
    {4, 5, "D2/D1 (GPIO4/5) - NodeMCU default"},
    {0, 2, "D3/D4 (GPIO0/2)"},
    {12, 14, "D6/D5 (GPIO12/14)"},
#elif defined(CONFIG_IDF_TARGET_ESP32S3) || defined(CONFIG_IDF_TARGET_ESP32S2)
    {8, 9, "GPIO8/9 - S2/S3 default"},
    {4, 5, "GPIO4/5"},
    {17, 18, "GPIO17/18"},
    {21, 22, "GPIO21/22 - classic ESP32 wiring"},
#elif defined(CONFIG_IDF_TARGET_ESP32C3)
    {8, 9, "GPIO8/9 - C3 default"},
    {4, 5, "GPIO4/5"},
    {5, 6, "GPIO5/6"},
#else  // classic ESP32
    {21, 22, "GPIO21/22 - ESP32 default"},
    {4, 5, "GPIO4/5 - common on OLED-integrated boards"},
    {5, 4, "GPIO5/4 - Heltec/TTGO LoRa boards"},
    {18, 19, "GPIO18/19"},
    {16, 17, "GPIO16/17"},
#endif
};

static const size_t kCandidateCount =
    sizeof(kCandidatePins) / sizeof(kCandidatePins[0]);

// ---------------------------------------------------------------------------
// Discovered at runtime.
// ---------------------------------------------------------------------------

static int8_t g_foundSda = -1;
static int8_t g_foundScl = -1;
static uint8_t g_displayAddr = 0;
static bool g_displayReady = false;

// The 128x32 panels are the same driver, just shorter. We try 64 first and fall
// back, since a 32-row panel driven as 64 shows a squashed top half rather than
// failing outright.
static uint8_t g_displayHeight = 64;
static Adafruit_SSD1306 *g_display = nullptr;

// ---------------------------------------------------------------------------

static void printChipIdentity() {
  Serial.println();
  Serial.println(F("=== chip ==="));

#if defined(ARDUINO_ARCH_ESP32)
  Serial.printf("model:      %s\n", ESP.getChipModel());
  Serial.printf("revision:   %d\n", ESP.getChipRevision());
  Serial.printf("cores:      %d\n", ESP.getChipCores());
  Serial.printf("cpu freq:   %u MHz\n", (unsigned)ESP.getCpuFreqMHz());
  Serial.printf("flash size: %u bytes\n", (unsigned)ESP.getFlashChipSize());
  Serial.printf("free heap:  %u bytes\n", (unsigned)ESP.getFreeHeap());
#if defined(BOARD_HAS_PSRAM)
  Serial.printf("psram:      %u bytes\n", (unsigned)ESP.getPsramSize());
#else
  Serial.println(F("psram:      not enabled in this build"));
#endif
  Serial.printf("mac:        %s\n", WiFi.macAddress().c_str());
#elif defined(ARDUINO_ARCH_ESP8266)
  Serial.printf("chip id:    %08X\n", (unsigned)ESP.getChipId());
  Serial.printf("cpu freq:   %u MHz\n", (unsigned)ESP.getCpuFreqMHz());
  Serial.printf("flash size: %u bytes (real %u)\n",
                (unsigned)ESP.getFlashChipSize(),
                (unsigned)ESP.getFlashChipRealSize());
  Serial.printf("free heap:  %u bytes\n", (unsigned)ESP.getFreeHeap());
  Serial.printf("sdk:        %s\n", ESP.getSdkVersion());
  Serial.printf("mac:        %s\n", WiFi.macAddress().c_str());
#else
  Serial.println(F("unknown architecture - not an ESP core?"));
#endif

  Serial.printf("build env:  %s\n", PIO_ENV_NAME);
  Serial.printf("led pin:    %d\n", STATUS_LED_PIN);
}

// Returns the number of devices answering on the given pair.
static uint8_t scanPair(const PinPair &pair) {
#if defined(ARDUINO_ARCH_ESP32)
  // Release the bus first: on ESP32, begin() on an already-started Wire does
  // not reliably move the peripheral to the new pins, so every pair after the
  // first would silently rescan the first pair's pins. ESP8266's Wire has no
  // end(), but its begin() does reassign pins, so it needs no equivalent.
  Wire.end();
#endif
  Wire.begin(pair.sda, pair.scl);
  // A stuck bus reads as a full house of ACKs; a slow clock is more forgiving
  // of the long dupont jumpers these kits ship with.
  Wire.setClock(100000);

  uint8_t found = 0;
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      found++;
      Serial.printf("  0x%02X  %s\n", addr,
                    (addr == 0x3C || addr == 0x3D)
                        ? "<- SSD1306/SH1106 OLED, almost certainly your screen"
                    : (addr == 0x27 || addr == 0x3F)
                        ? "<- PCF8574 backpack (16x2 character LCD)"
                    : (addr == 0x68) ? "<- DS3231/MPU6050"
                    : (addr == 0x76 || addr == 0x77) ? "<- BME/BMP280 sensor"
                                                     : "");

      if ((addr == 0x3C || addr == 0x3D) && g_displayAddr == 0) {
        g_displayAddr = addr;
        g_foundSda = pair.sda;
        g_foundScl = pair.scl;
      }
    }
  }
  return found;
}

static void scanAllPairs() {
  Serial.println();
  Serial.println(F("=== i2c scan ==="));

  for (size_t i = 0; i < kCandidateCount; i++) {
    const PinPair &pair = kCandidatePins[i];
    Serial.printf("SDA=%u SCL=%u  (%s)\n", pair.sda, pair.scl, pair.label);

    uint8_t found = scanPair(pair);
    if (found == 0) {
      Serial.println(F("  nothing"));
    } else if (found > 8) {
      // Every address ACKing means the lines are floating or shorted, not that
      // you own 100 sensors.
      Serial.println(F("  ^ implausible count - check pullups/wiring, "
                       "these are not real devices"));
    }
  }

  if (g_displayAddr == 0) {
    Serial.println();
    Serial.println(F("No OLED found. That is fine if your kit's screen is SPI "
                     "(more pins, no address) or you have not wired it yet."));
    Serial.println(F("See docs/BRINGUP.md for the wiring table."));
  } else {
    Serial.println();
    Serial.printf("OLED at 0x%02X on SDA=%d SCL=%d\n", g_displayAddr,
                  g_foundSda, g_foundScl);
  }
}

static bool startDisplay() {
  if (g_displayAddr == 0) {
    return false;
  }

  Wire.begin((uint8_t)g_foundSda, (uint8_t)g_foundScl);

  const uint8_t heights[] = {64, 32};
  for (size_t i = 0; i < sizeof(heights) / sizeof(heights[0]); i++) {
    delete g_display;
    g_display = new Adafruit_SSD1306(128, heights[i], &Wire, -1);

    // Adafruit's begin() allocates its buffer and talks to the panel; a false
    // return is usually an allocation failure rather than a wrong geometry, so
    // this loop mostly exists for the 128x32 retry.
    if (g_display->begin(SSD1306_SWITCHCAPVCC, g_displayAddr)) {
      g_displayHeight = heights[i];
      Serial.printf("display init ok, assuming 128x%u\n", g_displayHeight);
      Serial.println(F("If the text looks squashed or doubled, your panel is "
                       "the other height - say so and we pin it."));
      return true;
    }
  }

  Serial.println(F("display responded to the scan but would not init"));
  return false;
}

static void drawBanner() {
  if (!g_displayReady) {
    return;
  }

  g_display->clearDisplay();
  g_display->setTextColor(SSD1306_WHITE);

  g_display->setTextSize(1);
  g_display->setCursor(0, 0);
  g_display->println(F("desk display"));

  g_display->drawFastHLine(0, 10, 128, SSD1306_WHITE);

  g_display->setCursor(0, 14);
  g_display->println(F("bring-up ok"));

  g_display->setCursor(0, 24);
  g_display->printf("i2c 0x%02X", g_displayAddr);

  if (g_displayHeight > 32) {
    g_display->setCursor(0, 34);
    g_display->printf("sda %d scl %d", g_foundSda, g_foundScl);
    g_display->setCursor(0, 44);
    g_display->println(PIO_ENV_NAME);
  }

  g_display->display();
}

void setup() {
  Serial.begin(115200);

  // USB-CDC boards (S2/S3 native USB) drop the first second of output while the
  // host enumerates, which is exactly the banner we care about.
  uint32_t waitStart = millis();
  while (!Serial && (millis() - waitStart) < 2000) {
    delay(10);
  }
  delay(200);

  Serial.println();
  Serial.println(F("################################################"));
  Serial.println(F("#  desk display - hardware bring-up            #"));
  Serial.println(F("#  copy this whole output back into the chat   #"));
  Serial.println(F("################################################"));

  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, LED_OFF);

  printChipIdentity();
  scanAllPairs();

  g_displayReady = startDisplay();
  drawBanner();

  Serial.println();
  Serial.println(F("=== done ==="));
  Serial.println(F("LED should now be blinking. If the LED pin guess is wrong "
                   "for your board, nothing blinks - that is a clue, not a "
                   "failure."));
}

void loop() {
  // A slow, obviously deliberate blink: proof the board is alive and running
  // our code rather than sitting in the bootloader.
  digitalWrite(STATUS_LED_PIN, LED_ON);
  delay(120);
  digitalWrite(STATUS_LED_PIN, LED_OFF);
  delay(1880);

  static uint32_t beats = 0;
  Serial.printf("alive %lu (uptime %lus, heap %u)\n", (unsigned long)++beats,
                (unsigned long)(millis() / 1000), (unsigned)ESP.getFreeHeap());
}
