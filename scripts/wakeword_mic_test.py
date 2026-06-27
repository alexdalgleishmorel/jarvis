#!/usr/bin/env python3
"""Tier-2 wake-word test: does Porcupine fire on "jarvis" from your mic?

Streams microphone audio to the running ``wyoming-porcupine`` service (the same one
Home Assistant uses) and prints each detection — so you can validate the wake word
with your own voice and tune sensitivity, no satellite hardware required.

Setup (one-time):
    python3 -m venv scripts/.venv
    scripts/.venv/bin/pip install wyoming sounddevice

Run (the stack must be up; Porcupine is on localhost:10400):
    scripts/.venv/bin/python scripts/wakeword_mic_test.py

Say "jarvis" a few times → each prints a detection (true-accepts). Then talk
normally / play the TV → any detections there are false-accepts. Ctrl-C prints a
summary. If false-accepts are high, lower ``--sensitivity`` on the
wyoming-porcupine service in docker-compose.yml (and re-run `docker compose up -d`).

Validate the plumbing without a mic by streaming a clip instead:
    say "jarvis" -o /tmp/j.aiff && afconvert /tmp/j.aiff /tmp/j.wav -f WAVE -d LEI16@16000
    scripts/.venv/bin/python scripts/wakeword_mic_test.py --file /tmp/j.wav

This is an on-box tool (mic + Wyoming deps), outside the conductor's gate.
"""

from __future__ import annotations

import argparse
import asyncio
import time
import wave

from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.client import AsyncTcpClient
from wyoming.wake import Detect, Detection

RATE, WIDTH, CHANNELS, FRAME = 16000, 2, 1, 512  # 16 kHz mono, Porcupine frame = 512 samples


async def _consume(client: AsyncTcpClient, state: dict) -> None:
    while True:
        event = await client.read_event()
        if event is None:
            return
        if Detection.is_type(event.type):
            state["count"] += 1
            name = Detection.from_event(event).name
            print(f"  ✓ DETECTED {name!r}   (#{state['count']}, t+{time.monotonic() - state['t0']:.0f}s)")


async def run_mic(args: argparse.Namespace) -> None:
    import sounddevice as sd  # imported here so --file mode needs no audio deps

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[bytes] = asyncio.Queue()

    def callback(indata, _frames, _time, status) -> None:  # called from a PortAudio thread
        if status:
            print(f"  (audio status: {status})")
        loop.call_soon_threadsafe(queue.put_nowait, bytes(indata))

    state = {"count": 0, "t0": time.monotonic()}
    async with AsyncTcpClient(args.host, args.port) as client:
        await client.write_event(Detect(names=[args.keyword]).event())
        await client.write_event(AudioStart(rate=RATE, width=WIDTH, channels=CHANNELS).event())
        stream = sd.RawInputStream(
            samplerate=RATE, channels=CHANNELS, dtype="int16", blocksize=FRAME, callback=callback
        )
        stream.start()
        print(f"Listening for {args.keyword!r} on the mic (Ctrl-C to stop). Say it a few times…")

        async def produce() -> None:
            while True:
                data = await queue.get()
                await client.write_event(
                    AudioChunk(audio=data, rate=RATE, width=WIDTH, channels=CHANNELS).event()
                )

        try:
            await asyncio.gather(produce(), _consume(client, state))
        finally:
            stream.stop()
            stream.close()
            dur = time.monotonic() - state["t0"]
            print(
                f"\nSummary: {state['count']} detection(s) in {dur:.0f}s — "
                f"split into the times you said {args.keyword!r} (true) vs not (false)."
            )


async def run_file(args: argparse.Namespace) -> None:
    with wave.open(args.file, "rb") as w:
        if w.getframerate() != RATE or w.getnchannels() != CHANNELS:
            raise SystemExit("need a 16 kHz mono WAV (afconvert ... -d LEI16@16000)")
        pcm = w.readframes(w.getnframes())
    silence = b"\x00\x00" * (RATE // 2)  # 0.5s pad either side
    data = silence + pcm + silence
    count = 0
    async with AsyncTcpClient(args.host, args.port) as client:
        await client.write_event(Detect(names=[args.keyword]).event())
        await client.write_event(AudioStart(rate=RATE, width=WIDTH, channels=CHANNELS).event())
        step = FRAME * WIDTH
        for i in range(0, len(data), step):
            await client.write_event(
                AudioChunk(audio=data[i : i + step], rate=RATE, width=WIDTH, channels=CHANNELS).event()
            )
        await client.write_event(AudioStop().event())
        try:
            while True:
                event = await asyncio.wait_for(client.read_event(), timeout=2)
                if event is None:
                    break
                if Detection.is_type(event.type):
                    count += 1
                    print(f"  ✓ DETECTED {Detection.from_event(event).name!r}")
        except TimeoutError:
            pass
    print(f"file test: {count} detection(s) for {args.file}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Mic wake-word test for the Porcupine service")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=10400)
    parser.add_argument("--keyword", default="jarvis")
    parser.add_argument("--file", help="stream a 16 kHz mono WAV instead of the mic")
    args = parser.parse_args()
    try:
        asyncio.run(run_file(args) if args.file else run_mic(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
