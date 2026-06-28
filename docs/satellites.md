# Satellites (per-room mic + speaker)

A **satellite** is the box in each room that listens, detects the wake word, and
plays replies — it streams to the hub (Home Assistant on the Mac Mini) over the
LAN. This guide covers the **MVP test device** (M5Stack Atom Echo) and the
**production** per-room devices.

> **Where the wake word runs.** "jarvis" is configured on the **hub** (the
> `wyoming-porcupine` service). Small ESP32 satellites like the **Atom Echo**
> can't run wake word on-device, so they **stream audio to the hub** and HA
> detects "jarvis" with Porcupine — exactly what we set up. Bigger devices (Voice
> PE) do wake word **on-device**; see [Production](#production) for getting
> "jarvis" there.

---

## MVP — M5Stack Atom Echo (~$13)

Cheap, officially supported, perfect for proving the full hands-free loop. Basic
mic/speaker — great for testing and quiet/small rooms.

### Flash it (5 minutes, in Chrome or Edge)

1. Plug the Atom Echo into your computer with a USB-C cable.
2. Open the official installer: **https://www.home-assistant.io/voice_control/thirteen-usd-voice-remote/**
3. Scroll to the install step → **Connect** → pick the serial port → **Install
   "Atom Echo Voice Assistant"**. Wait for the flash to finish.
4. When prompted, give it your **2.4 GHz Wi-Fi** SSID + password.

### Adopt it in Home Assistant

5. HA auto-discovers it (ESPHome). **Settings → Devices & Services → Discovered →
   Configure** to add it.
6. **Assign its Area** to the room (e.g. *Office*) — that's the `area` the
   conductor uses to route the reply back to the right room.
7. **Pick the assistant + wake word.** The Atom Echo uses an Assist pipeline; make
   sure it's the **Jarvis** pipeline (the preferred one), and set its **wake word
   to "jarvis"** (Settings → Voice assistants → the device's wake-word selector;
   the options come from the Porcupine provider).

### Test

8. Say **"jarvis"** → the LED shows it's listening → ask a question → hear the
   reply in your ElevenLabs voice. 🎉
   - **Fallback:** the Atom Echo also supports **press-to-talk** (the front
     button) — handy if continuous wake-word streaming is flaky on the tiny
     ESP32-PICO. Press → speak → release; this still exercises STT → brain → TTS.

---

## Production

Once the MVP is proven, put one good satellite per room. Plan: **main floor** +
**office**.

- **Home Assistant Voice Preview Edition (~$60)** — recommended for the main
  floor: far-field dual-mic array, a real speaker, mute switch, 3.5mm out to wire
  a louder speaker. Polished and plug-and-play.
- The office can be a second Voice PE, or keep the Atom Echo there if it's a quiet
  room.

**Wake word on the Voice PE.** It runs wake word **on-device** (microWakeWord),
so it doesn't use the hub Porcupine. To get "jarvis" there, choose one:
1. Use the built-in **"hey jarvis"** model (zero effort), or
2. Flash a community/trained **microWakeWord "jarvis"** model, or
3. Configure the device to **stream to the hub** and use the Porcupine "jarvis"
   (consistent with the Atom Echo, at some battery/bandwidth cost).

We'll pick one when the hardware arrives.

---

## Troubleshooting

- **Not discovered in HA** → confirm it's on the same LAN/2.4 GHz Wi-Fi; add the
  **ESPHome** integration; re-plug to re-provision Wi-Fi.
- **Wakes but no answer** → check the device's pipeline is **Jarvis** and the
  conductor is running (`curl http://localhost:8000/healthz`).
- **Too many false "jarvis" triggers** → lower `--sensitivity` on
  `wyoming-porcupine` in `docker-compose.yml`; validate with
  `scripts/wakeword_mic_test.py`.
- **Reply plays in the wrong room** → fix the device's **Area** in HA.
