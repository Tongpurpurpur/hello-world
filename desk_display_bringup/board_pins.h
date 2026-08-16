// Candidate I2C pin pairs to probe, per chip family.
//
// This lives in a header rather than in the .ino on purpose. The Arduino IDE
// preprocesses .ino files to auto-generate function prototypes, and it inserts
// them after what it believes is the last top-level declaration. The #if/#elif
// chain below defeats that heuristic: the prototypes land in the middle of the
// array initialiser and the sketch fails to compile with a syntax error that
// points at the wrong line. Files with a .h extension are passed through
// untouched, which sidesteps the whole problem.

#pragma once

#include <Arduino.h>

struct PinPair {
  uint8_t sda;
  uint8_t scl;
  const char *label;
};

// The first entry in each list is the core's own default; the rest cover the
// wirings these starter kits ship with.
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
