"""Speaker-identity adapters. The null adapter ships today; a voice-embedding
adapter lands in M4 (README §7)."""

from jarvis.adapters.speaker_id.null import NullSpeakerIdentifier

__all__ = ["NullSpeakerIdentifier"]
