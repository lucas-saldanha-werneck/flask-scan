from __future__ import annotations

from collections import Counter

from .scanner import Hook, Route

ORDER = ["easy", "review", "manual"]


def to_markdown(routes: list[Route], hooks: list[Hook] | None = None) -> str:
    counts = Counter(r.effort for r in routes)
    out = [f"# Flask route inventory\n",
           f"{len(routes)} routes: " + ", ".join(f"{counts.get(e, 0)} {e}" for e in ORDER) + "\n",
           "| Methods | FastAPI path | Function | Effort | Flask features used |",
           "|---|---|---|---|---|"]
    for r in routes:
        feats = ", ".join(r.uses) or "-"
        out.append(f"| {','.join(r.methods)} | `{r.fastapi_path}` | `{r.function}` "
                   f"({r.file}:{r.line}) | {r.effort} | {feats} |")
    hinted = [r for r in routes if r.hints]
    if hinted:
        out.append("\n## Hints\n")
        for r in hinted:
            out.append(f"- `{r.function}`: " + "; ".join(r.hints))
    if hooks:
        out.append("\n## App-level hooks (no route-level equivalent)\n")
        for h in hooks:
            out.append(f"- `@{h.kind}` `{h.function}` ({h.file}:{h.line}): "
                       "port as middleware, a dependency, or an exception handler")
    return "\n".join(out) + "\n"


def to_stubs(routes: list[Route]) -> str:
    """FastAPI skeleton: one stub per route and method. Bodies are left as TODO."""
    lines = ["from uuid import UUID", "from fastapi import APIRouter", "", "router = APIRouter()", ""]
    for r in routes:
        for m in r.methods:
            if m in {"HEAD", "OPTIONS"}:
                continue
            args = ", ".join(f"{n}: {t}" for n, t in r.params.items())
            lines += [f'@router.{m.lower()}("{r.fastapi_path}")',
                      f"def {r.function}_{m.lower()}({args}):",
                      f"    # TODO ported from {r.file}:{r.line} (effort: {r.effort})",
                      "    raise NotImplementedError", ""]
    return "\n".join(lines)
