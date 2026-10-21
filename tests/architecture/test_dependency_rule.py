"""Architecture gate: enforce the inward-only dependency rule.

Layers (from ``plan.md``):

- ``domain/``       imports nothing outside the standard library (+ typing).
- ``application/``  imports only ``domain`` (+ stdlib/typing).
- ``adapters/``     imports only ``domain`` and ``application`` (+ third-party).
- ``gui/``          imports ``domain``/``application``/``adapters`` (+ third-party).

The composition root (``main.py``, ``__init__.py``) may import anything and is
skipped. Any inward→outward import is reported with file, layer and import.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "partiu"

#: layer -> set of layers it MAY import (excluding itself, always allowed).
ALLOWED: dict[str, set[str]] = {
    "domain": set(),
    "application": {"domain"},
    "adapters": {"domain", "application"},
    "gui": {"domain", "application", "adapters"},
}


def _layer_of_import(name: str) -> str | None:
    """Return the layer of a ``partiu.*`` absolute import, or ``None``."""
    if name == "partiu":
        return None
    prefix = "partiu."
    if name.startswith(prefix):
        return name[len(prefix):].split(".")[0]
    return None


def _collect_violations() -> list[str]:
    violations: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC)
        parts = rel.parts
        layer = parts[0] if parts and parts[0] in ALLOWED else "root"
        if layer == "root":
            continue

        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(rel))
        except SyntaxError as exc:
            violations.append(f"{rel}: unparseable ({exc})")
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    _check(violations, rel, layer, name)
            elif isinstance(node, ast.ImportFrom):
                if node.level > 0:  # relative import — trusted within its subtree
                    continue
                if node.module is None:
                    continue
                _check(violations, rel, layer, node.module)

    return violations


def _check(violations: list[str], rel: Path, layer: str, name: str) -> None:
    target = _layer_of_import(name)
    if target is not None:
        allowed = ALLOWED[layer] | {layer}
        if target not in allowed:
            violations.append(
                f"{rel}: layer '{layer}' imports 'partiu.{target}' ({name})"
            )
        return

    if layer == "domain":
        root = name.split(".")[0]
        if root not in sys.stdlib_module_names and root != "__future__":
            violations.append(
                f"{rel}: domain layer imports non-stdlib module '{name}'"
            )


def test_dependency_rule() -> None:
    violations = _collect_violations()
    assert not violations, (
        "Dependency-rule violations found:\n" + "\n".join(f"  - {v}" for v in violations)
    )
