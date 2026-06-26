"""Services — use-cases that orchestrate the domain and ports.

The request lifecycle (``handle_utterance``) and async jobs (``run_job``) live
here. Services depend on ports and the domain, never on concrete adapters
(README §5, §6).
"""
