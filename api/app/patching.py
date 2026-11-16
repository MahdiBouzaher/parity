from .translation import Hunk, Patch, PatchError, apply_patch


class PatchFailed(Exception):
    pass


def apply(code, patch):
    try:
        model = Patch(
            summary=patch["summary"],
            hunks=[Hunk(h["start"], list(h["remove"]), list(h["add"])) for h in patch["hunks"]],
        )
        text, changed = apply_patch(code, model)
        return text, list(changed)
    except PatchError as exc:
        raise PatchFailed(str(exc))
