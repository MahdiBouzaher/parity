from .types import Patch


class PatchError(Exception):
    pass


def apply_patch(code, patch):
    lines = code.split("\n")
    hunks = sorted(patch.hunks, key=lambda h: h.start)
    prev_end = 1
    for h in hunks:
        if h.start < 1 or h.start > len(lines) + 1:
            raise PatchError(f"Line {h.start} is outside the code.")
        if h.start < prev_end:
            raise PatchError(f"The change at line {h.start} overlaps another change.")
        end = h.start - 1 + len(h.remove)
        if end > len(lines):
            raise PatchError(f"The change at line {h.start} runs past the end of the code.")
        for k, expected in enumerate(h.remove):
            actual = lines[h.start - 1 + k]
            if actual.rstrip() != expected.rstrip():
                raise PatchError(f"Line {h.start + k} does not match the expected text.")
        prev_end = end + 1 if h.remove else h.start
    out = []
    changed = []
    cursor = 0
    for h in hunks:
        idx = h.start - 1
        out.extend(lines[cursor:idx])
        first = len(out) + 1
        out.extend(h.add)
        changed.extend(range(first, first + len(h.add)))
        cursor = idx + len(h.remove)
    out.extend(lines[cursor:])
    return "\n".join(out), changed
