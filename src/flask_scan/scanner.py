"""Static scan of Flask source: find routes and flag what needs care in a FastAPI port.

Uses only the standard library (ast). It never imports or runs the scanned code.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

HTTP_SHORTCUTS = {"get", "post", "put", "delete", "patch"}
CONVERTERS = {"int": "int", "float": "float", "string": "str", "path": "str", "uuid": "UUID"}
PARAM_RE = re.compile(r"<(?:(\w+)(?:\([^)]*\))?:)?(\w+)>")

# Flask names grouped by how much work they are in a port.
# "manual": no one-line FastAPI equivalent, needs a design decision.
# "review": has an equivalent, but the shape changes.
MANUAL = {"g", "session", "render_template", "make_response", "send_file",
          "redirect", "url_for", "current_app", "flash", "stream_with_context"}
REVIEW = {"request", "abort"}
HOOKS = {"before_request", "after_request", "teardown_request", "errorhandler",
         "before_first_request", "context_processor"}
REQUEST_HINTS = {
    "json": "body: declare a Pydantic model instead of request.json",
    "get_json": "body: declare a Pydantic model instead of request.get_json()",
    "form": "form: use Form(...) parameters",
    "files": "files: use UploadFile",
    "args": "query: declare query parameters in the signature",
    "headers": "headers: use Header(...)",
    "cookies": "cookies: use Cookie(...)",
}


@dataclass
class Route:
    file: str
    line: int
    function: str
    path: str
    fastapi_path: str
    methods: list[str]
    params: dict[str, str]
    owner: str
    uses: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    effort: str = "easy"


@dataclass
class Hook:
    file: str
    line: int
    function: str
    kind: str


def convert_path(rule: str) -> tuple[str, dict[str, str]]:
    """'/users/<int:id>' -> ('/users/{id}', {'id': 'int'})"""
    params: dict[str, str] = {}

    def repl(m: re.Match) -> str:
        conv, name = m.group(1), m.group(2)
        params[name] = CONVERTERS.get(conv or "string", "str")
        suffix = ":path" if conv == "path" else ""
        return "{" + name + suffix + "}"

    return PARAM_RE.sub(repl, rule), params


def _str(node: ast.AST | None) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _methods(call: ast.Call, attr: str) -> list[str]:
    if attr in HTTP_SHORTCUTS:
        return [attr.upper()]
    for kw in call.keywords:
        if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple, ast.Set)):
            found = [_str(e) for e in kw.value.elts]
            return sorted(m.upper() for m in found if m)
    return ["GET"]


def _owners(tree: ast.Module) -> dict[str, str]:
    """Names assigned from Flask(...) or Blueprint(...) -> url_prefix ('' for app)."""
    owners: dict[str, str] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)):
            continue
        f = node.value.func
        name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
        if name not in {"Flask", "Blueprint"}:
            continue
        prefix = ""
        for kw in node.value.keywords:
            if kw.arg == "url_prefix":
                prefix = _str(kw.value) or ""
        for t in node.targets:
            if isinstance(t, ast.Name):
                owners[t.id] = prefix
    return owners


def _usage(func: ast.AST) -> tuple[list[str], list[str]]:
    used: set[str] = set()
    hints: list[str] = []
    for n in ast.walk(func):
        if isinstance(n, ast.Name) and n.id in (MANUAL | REVIEW | {"jsonify"}):
            used.add(n.id)
        if (isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                and n.value.id == "request" and n.attr in REQUEST_HINTS):
            h = REQUEST_HINTS[n.attr]
            if h not in hints:
                hints.append(h)
    return sorted(used), hints


def scan_source(source: str, filename: str = "<string>") -> list[Route]:
    tree = ast.parse(source, filename=filename)
    owners = _owners(tree)
    routes: list[Route] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
                    and isinstance(dec.func.value, ast.Name)):
                continue
            owner, attr = dec.func.value.id, dec.func.attr
            if owner not in owners or (attr != "route" and attr not in HTTP_SHORTCUTS):
                continue
            rule = _str(dec.args[0]) if dec.args else None
            if rule is None:
                continue
            full = owners[owner].rstrip("/") + rule
            fpath, params = convert_path(full)
            uses, hints = _usage(node)
            effort = ("manual" if set(uses) & MANUAL
                      else "review" if (set(uses) & REVIEW or hints) else "easy")
            if isinstance(node, ast.AsyncFunctionDef):
                hints.append("already async")
            routes.append(Route(filename, node.lineno, node.name, full, fpath,
                                _methods(dec, attr), params, owner, uses, hints, effort))
    return sorted(routes, key=lambda r: (r.file, r.line))


def find_hooks(source: str, filename: str = "<string>") -> list[Hook]:
    """App-level hooks (before_request, errorhandler...) have no 1:1 FastAPI route equivalent."""
    tree = ast.parse(source, filename=filename)
    owners = _owners(tree)
    hooks: list[Hook] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            d = dec.func if isinstance(dec, ast.Call) else dec
            if (isinstance(d, ast.Attribute) and isinstance(d.value, ast.Name)
                    and d.value.id in owners and d.attr in HOOKS):
                hooks.append(Hook(filename, node.lineno, node.name, d.attr))
    return sorted(hooks, key=lambda h: (h.file, h.line))


def scan_hooks(path: str | Path) -> list[Hook]:
    out: list[Hook] = []
    for f in _py_files(path):
        try:
            out += find_hooks(f.read_text(encoding="utf-8"), str(f))
        except (SyntaxError, UnicodeDecodeError):
            continue
    return out


def _py_files(path: str | Path) -> list[Path]:
    p = Path(path)
    files = [p] if p.is_file() else sorted(p.rglob("*.py"))
    return [f for f in files
            if not any(part in {".venv", "venv", "node_modules", "__pycache__"} for part in f.parts)]


def scan_path(path: str | Path) -> list[Route]:
    routes: list[Route] = []
    for f in _py_files(path):
        try:
            routes += scan_source(f.read_text(encoding="utf-8"), str(f))
        except (SyntaxError, UnicodeDecodeError):
            continue  # skip files that do not parse; do not fail the whole scan
    return routes
