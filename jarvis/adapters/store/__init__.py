"""Store adapters. SQLite ships now; Postgres is a drop-in later (README §11)."""

from jarvis.adapters.store.sqlite import SqliteStore

__all__ = ["SqliteStore"]
