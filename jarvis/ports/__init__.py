"""Ports — the interfaces (Protocols / ABCs) the conductor depends on.

Everything that touches the outside world (the hub, brain, voice, messenger,
store, speaker ID) sits behind one of these ports. Ports import only from
``jarvis.domain`` (README §3.1, §5).
"""
