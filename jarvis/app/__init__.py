"""Application wiring — the composition root.

FastAPI routes (the hub ingress endpoint and the config API), the in-process
event bus, runtime config, and ``main`` live here. This is the only layer that
instantiates adapters and injects them into use-cases (README §5).
"""
