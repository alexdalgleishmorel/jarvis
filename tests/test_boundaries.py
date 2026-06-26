"""Architecture guard: the pure domain core depends on nothing external.

README §3.1 / §13 make this load-bearing. We assert it statically by parsing
every module under ``jarvis/domain`` and checking each import is either the
standard library or another ``jarvis.domain`` module — never an adapter, app,
port, service, or third-party package.
"""

import ast
import pathlib
import sys

import jarvis.domain

DOMAIN_DIR = pathlib.Path(jarvis.domain.__file__).parent
STDLIB = sys.stdlib_module_names


def _imports(path: pathlib.Path) -> list[tuple[str, int]]:
    """Return (top-level-or-dotted module, relative-level) for each import."""
    tree = ast.parse(path.read_text(), filename=str(path))
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name, 0) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            # Relative imports (level > 0) stay within the domain package.
            found.append((node.module or "", node.level))
    return found


def _is_allowed(module: str, level: int) -> bool:
    if level > 0:  # relative import within jarvis.domain
        return True
    top = module.split(".")[0]
    if top == "jarvis":
        return module.startswith("jarvis.domain")
    return top in STDLIB


def test_domain_imports_are_stdlib_or_domain_only():
    offenders: list[str] = []
    for path in sorted(DOMAIN_DIR.rglob("*.py")):
        for module, level in _imports(path):
            if not _is_allowed(module, level):
                offenders.append(f"{path.relative_to(DOMAIN_DIR.parent.parent)} -> {module}")
    assert not offenders, "domain core must import only stdlib + jarvis.domain:\n" + "\n".join(
        offenders
    )
