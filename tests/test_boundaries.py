"""Architecture guards: enforce the hexagonal import boundaries statically.

README §3.1 / §13 make these load-bearing. We parse every module in a layer and
check each import is the standard library or an allowed ``jarvis.*`` layer:

* ``jarvis/domain`` may import only stdlib + ``jarvis.domain``.
* ``jarvis/ports``  may import only stdlib + ``jarvis.domain`` + ``jarvis.ports``.
"""

import ast
import pathlib
import sys

import jarvis

REPO_ROOT = pathlib.Path(jarvis.__file__).parent.parent
# stdlib module names, used to distinguish standard library from third-party.
STDLIB = sys.stdlib_module_names


def _imports(path: pathlib.Path) -> list[tuple[str, int]]:
    """Return (module, relative-level) for each import statement in a file."""
    tree = ast.parse(path.read_text(), filename=str(path))
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name, 0) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.append((node.module or "", node.level))
    return found


def _offenders(package: str, allowed_prefixes: tuple[str, ...]) -> list[str]:
    package_dir = REPO_ROOT / package.replace(".", "/")
    bad: list[str] = []
    for path in sorted(package_dir.rglob("*.py")):
        for module, level in _imports(path):
            if level > 0:  # relative import — stays within this package
                continue
            top = module.split(".")[0]
            if top == "jarvis":
                if not module.startswith(allowed_prefixes):
                    bad.append(f"{path.relative_to(REPO_ROOT)} -> {module}")
            elif top and top not in STDLIB:
                bad.append(f"{path.relative_to(REPO_ROOT)} -> {module} (third-party)")
    return bad


def test_domain_imports_only_stdlib_and_domain():
    offenders = _offenders("jarvis/domain", ("jarvis.domain",))
    assert not offenders, "domain core boundary violated:\n" + "\n".join(offenders)


def test_ports_import_only_stdlib_domain_and_ports():
    offenders = _offenders("jarvis/ports", ("jarvis.domain", "jarvis.ports"))
    assert not offenders, "ports boundary violated:\n" + "\n".join(offenders)


def test_adapters_do_not_import_app_services_or_sibling_adapters():
    """Adapters depend on ports, never on each other / on app / on services
    (README §13). Third-party imports are allowed here."""
    adapters_dir = REPO_ROOT / "jarvis" / "adapters"
    offenders: list[str] = []
    for path in sorted(adapters_dir.rglob("*.py")):
        rel = path.relative_to(adapters_dir)
        # The adapter's own subpackage (e.g. "speaker_id"); None for adapters/__init__.py.
        own = rel.parts[0] if len(rel.parts) > 1 else None
        for module, level in _imports(path):
            if level > 0:
                continue
            if module == "jarvis.app" or module.startswith("jarvis.app."):
                offenders.append(f"{path.relative_to(REPO_ROOT)} -> {module} (app)")
            elif module == "jarvis.services" or module.startswith("jarvis.services."):
                offenders.append(f"{path.relative_to(REPO_ROOT)} -> {module} (services)")
            elif module.startswith("jarvis.adapters."):
                other = module.split(".")[2]
                if own is not None and other != own:
                    offenders.append(f"{path.relative_to(REPO_ROOT)} -> {module} (sibling adapter)")
    assert not offenders, "adapters boundary violated:\n" + "\n".join(offenders)
