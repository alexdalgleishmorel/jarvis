#!/usr/bin/env python3
"""#19 — Measure the ``hey_jarvis`` wake word from the laptop mic.

The most controlled way to test the wake word without the full HA satellite: run
openWakeWord against the mic, count detections, and tune the threshold.

Setup (on the box):
    # macOS needs portaudio for pyaudio:
    brew install portaudio
    pip install openwakeword pyaudio numpy

Run:
    python scripts/wakeword_test.py --threshold 0.5

How to read it:
  * True-accepts  — say "hey jarvis" ~20 times (vary distance/volume/background);
    count how many DETECTED lines you intended.
  * False-accepts — let it run during normal talking / TV / silence and try
    near-misses ("hey jervis", "okay jarvis"); the detections you did NOT intend
    are false-accepts.
Raise --threshold if there are too many false-accepts; lower it if it misses you.
Ctrl-C prints a summary. This script is run on the box; it's not part of the
conductor's package or CI.
"""

from __future__ import annotations

import argparse
import time

import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(description="hey_jarvis wake-word mic test (#19)")
    parser.add_argument("--model", default="hey_jarvis")
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()

    import openwakeword
    import pyaudio
    from openwakeword.model import Model

    openwakeword.utils.download_models()  # pretrained set incl. hey_jarvis
    model = Model(wakeword_models=[args.model])

    rate, chunk = 16000, 1280  # 80 ms frames of 16 kHz mono PCM
    audio = pyaudio.PyAudio()
    stream = audio.open(
        rate=rate, channels=1, format=pyaudio.paInt16, input=True, frames_per_buffer=chunk
    )

    print(f"Listening for '{args.model}' (threshold {args.threshold}). Ctrl-C to stop.\n")
    detections = 0
    armed = True
    start = time.monotonic()
    try:
        while True:
            frame = np.frombuffer(stream.read(chunk, exception_on_overflow=False), dtype=np.int16)
            score = float(model.predict(frame)[args.model])
            if score >= args.threshold and armed:
                detections += 1
                armed = False  # debounce: one count per utterance
                print(f"  DETECTED #{detections}  score={score:.2f}  t=+{time.monotonic() - start:.0f}s")
            elif score < args.threshold * 0.5:
                armed = True
    except KeyboardInterrupt:
        elapsed = time.monotonic() - start
        print(f"\nSummary: {detections} detection(s) in {elapsed:.0f}s at threshold {args.threshold}.")
        print("Split these into the 'hey jarvis' you said (true-accepts) vs the rest (false-accepts).")
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()


if __name__ == "__main__":
    main()
