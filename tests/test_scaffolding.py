"""Smoke tests for the package scaffolding.

These exist so the suite is green from the first commit and so the layout
boundaries are asserted rather than assumed.
"""

import importlib

import jarvis


def test_version_is_exposed() -> None:
    assert jarvis.__version__


def test_all_layers_import() -> None:
    for module in (
        "jarvis.domain",
        "jarvis.ports",
        "jarvis.adapters",
        "jarvis.services",
        "jarvis.app",
    ):
        assert importlib.import_module(module) is not None
