"""A Wyoming ASR server backed by MLX-Whisper (Apple Silicon GPU).

The transcriber, run natively on macOS so Whisper uses the Apple Silicon GPU via
MLX — far faster and more accurate than the CPU-only Docker Whisper. Home
Assistant's Assist pipeline reaches it over the Wyoming protocol (the hub runs in
Docker, so it connects via host.docker.internal:<port>).

This is host-run code with heavy, Apple-only deps (mlx-whisper), so it lives
outside the conductor's package and CI gate.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from functools import partial

import mlx_whisper
import numpy as np
from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioChunk, AudioChunkConverter, AudioStart, AudioStop
from wyoming.event import Event
from wyoming.info import AsrModel, AsrProgram, Attribution, Describe, Info
from wyoming.server import AsyncEventHandler, AsyncServer

_LOGGER = logging.getLogger("wyoming_mlx_whisper")


def _transcribe(audio: np.ndarray, model: str, language: str | None) -> str:
    result = mlx_whisper.transcribe(audio, path_or_hf_repo=model, language=language)
    return str(result.get("text", "")).strip()


class MlxWhisperEventHandler(AsyncEventHandler):
    def __init__(
        self,
        wyoming_info: Info,
        cli_args: argparse.Namespace,
        model_lock: asyncio.Lock,
        *args: object,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._wyoming_info_event = wyoming_info.event()
        self._args = cli_args
        self._model_lock = model_lock
        self._converter = AudioChunkConverter(rate=16000, width=2, channels=1)
        self._audio = bytearray()
        self._language = cli_args.language

    async def handle_event(self, event: Event) -> bool:
        if Describe.is_type(event.type):
            await self.write_event(self._wyoming_info_event)
            return True

        if Transcribe.is_type(event.type):
            transcribe = Transcribe.from_event(event)
            if transcribe.language:
                # Normalise e.g. "en-US" -> "en" for whisper.
                self._language = transcribe.language.split("-")[0]
            return True

        if AudioStart.is_type(event.type):
            self._audio = bytearray()
            return True

        if AudioChunk.is_type(event.type):
            chunk = self._converter.convert(AudioChunk.from_event(event))
            self._audio.extend(chunk.audio)
            return True

        if AudioStop.is_type(event.type):
            samples = np.frombuffer(bytes(self._audio), dtype=np.int16)
            audio = samples.astype(np.float32) / 32768.0
            async with self._model_lock:
                text = await asyncio.to_thread(
                    _transcribe, audio, self._args.model, self._language
                )
            _LOGGER.info("Transcript: %s", text)
            await self.write_event(Transcript(text=text).event())
            return False

        return True


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", default="tcp://0.0.0.0:10301")
    # medium.en: best accuracy/latency on a base M1 (~2s) for an English assistant.
    # Dial: whisper-small.en-mlx (~0.6s, snappier) or whisper-large-v3-turbo
    # (multilingual, ~3s, most robust). See README.
    parser.add_argument("--model", default="mlx-community/whisper-medium.en-mlx")
    parser.add_argument("--language", default="en", help="default language (HA can override)")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    wyoming_info = Info(
        asr=[
            AsrProgram(
                name="mlx-whisper",
                description="Whisper on Apple Silicon (MLX)",
                attribution=Attribution(
                    name="mlx-examples", url="https://github.com/ml-explore/mlx-examples"
                ),
                installed=True,
                version="0.1.0",
                models=[
                    AsrModel(
                        name=args.model,
                        description=args.model,
                        attribution=Attribution(
                            name="mlx-community", url="https://huggingface.co/mlx-community"
                        ),
                        installed=True,
                        version=None,
                        languages=["en"],
                    )
                ],
            )
        ]
    )

    model_lock = asyncio.Lock()

    _LOGGER.info("Loading model %s (first run downloads it from HuggingFace)...", args.model)
    await asyncio.to_thread(_transcribe, np.zeros(16000, dtype=np.float32), args.model, args.language)
    _LOGGER.info("Model ready")

    server = AsyncServer.from_uri(args.uri)
    _LOGGER.info("Listening on %s", args.uri)
    await server.run(partial(MlxWhisperEventHandler, wyoming_info, args, model_lock))


if __name__ == "__main__":
    asyncio.run(main())
