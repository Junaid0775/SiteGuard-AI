"""Static code map (spec §2.1): definitions, internal imports and call sites per module.

    .venv/bin/python scripts/engineering/code_map.py <out.json>

Parses the real source with `ast`, so the architecture is traced from code rather than old reports.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
FILES = [PROJECT / "app.py"] + sorted((PROJECT / "src").rglob("*.py")) + sorted((PROJECT / "scripts").rglob("*.py"))


def module_name(p: Path) -> str:
    rel = p.relative_to(PROJECT).with_suffix("")
    return ".".join(rel.parts)


def analyse(p: Path) -> dict:
    tree = ast.parse(p.read_text(encoding="utf-8"))
    defs, imports, calls = [], [], set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            defs.append({"kind": "class", "name": node.name, "line": node.lineno, "methods": methods})
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defs.append({"kind": "function", "name": node.name, "line": node.lineno})
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("src"):
            imports.append({"from": node.module, "names": [a.name for a in node.names], "line": node.lineno})
        elif isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else None)
            if name:
                calls.add(name)
    return {"path": p.relative_to(PROJECT).as_posix(), "lines": len(p.read_text(encoding="utf-8").splitlines()),
            "definitions": defs, "internal_imports": imports, "called_names": sorted(calls)}


def main(out: Path) -> None:
    mods = {module_name(p): analyse(p) for p in FILES if p.name != "__init__.py"}
    # reverse index: which modules import each internal module / name
    for name, m in mods.items():
        m["imported_by"] = sorted({other for other, o in mods.items() for imp in o["internal_imports"] if imp["from"] == name})
    out.write_text(json.dumps(mods, indent=2), encoding="utf-8")
    for name, m in mods.items():
        print(f"{m['path']:45s} {m['lines']:4d} lines  defs={len(m['definitions']):2d}  imported_by={m['imported_by']}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
