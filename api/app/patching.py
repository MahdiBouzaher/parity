try:
    from .translation import PatchError as _PatchError
    from .translation import apply_patch as _apply_patch
    from .translation.types import Hunk, Patch
except Exception:
    _apply_patch = None
    _PatchError = None


class PatchFailed(Exception):
    pass


def _apply_local(code, patch):
    lines = code.split("\n")
    trailing = lines[-1] == ""
    if trailing:
        lines = lines[:-1]
    result = []
    changed = []
    cursor = 0
    for hunk in sorted(patch["hunks"], key=lambda h: h["start"]):
        start = hunk["start"] - 1
        if start < cursor or start > len(lines):
            raise PatchFailed("hunk out of range")
        remove = hunk["remove"]
        existing = [line.rstrip() for line in lines[start : start + len(remove)]]
        if existing != [line.rstrip() for line in remove]:
            raise PatchFailed("hunk does not match")
        result.extend(lines[cursor:start])
        first = len(result) + 1
        result.extend(hunk["add"])
        changed.extend(range(first, first + len(hunk["add"])))
        cursor = start + len(remove)
    result.extend(lines[cursor:])
    text = "\n".join(result) + ("\n" if trailing else "")
    return text, changed


def apply(code, patch):
    if _apply_patch is None:
        return _apply_local(code, patch)
    try:
        model = Patch(
            summary=patch["summary"],
            hunks=[Hunk(h["start"], list(h["remove"]), list(h["add"])) for h in patch["hunks"]],
        )
        text, changed = _apply_patch(code, model)
        return text, list(changed)
    except _PatchError as exc:
        raise PatchFailed(str(exc))
