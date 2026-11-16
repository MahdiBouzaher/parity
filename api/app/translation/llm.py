import json
import os
import re
import time

from . import prompts
from .fixes import rule_explanation, rule_fix
from .patch import PatchError, apply_patch
from .types import Explanation, Hunk, Patch, TranslateError

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-4o-mini"
TAGS = ("rounding", "missing values", "sort order", "integer division", "dates")


def is_configured():
    return bool(os.environ.get("OPENROUTER_API_KEY", "").strip())


def _client():
    from openai import OpenAI

    return OpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"].strip(),
        base_url=os.environ.get("OPENROUTER_BASE_URL", "").strip() or DEFAULT_BASE_URL,
        timeout=60,
        max_retries=1,
    )


def _model():
    return os.environ.get("OPENROUTER_MODEL", "").strip() or DEFAULT_MODEL


def _complete(messages, max_tokens=1500):
    resp = _client().chat.completions.create(model=_model(), messages=messages, temperature=0, max_tokens=max_tokens)
    return resp.choices[0].message.content or ""


def _fallback(analysis):
    text = analysis.draft_python
    sizes = (3, 2, 4)
    i = k = 0
    while i < len(text):
        step = sizes[k % 3]
        yield text[i : i + step]
        i += step
        k += 1
        time.sleep(0.012)


def _clean(pieces):
    state, buf = "head", ""
    for piece in pieces:
        if not piece:
            continue
        buf += piece
        if state == "head":
            stripped = buf.lstrip()
            if not stripped:
                continue
            if stripped.startswith("`"):
                if "\n" not in stripped:
                    continue
                if stripped.startswith("```"):
                    stripped = stripped.split("\n", 1)[1]
            buf = stripped
            state = "body"
        cut = buf.rfind("\n")
        complete, partial = buf[: cut + 1], buf[cut + 1 :]
        out = ""
        for line in complete.splitlines(keepends=True):
            if line.strip().startswith("```"):
                if out:
                    yield out
                return
            out += line
        if partial.lstrip().startswith("`"):
            buf = partial
        else:
            out += partial
            buf = ""
        if out:
            yield out
    if buf and not buf.lstrip().startswith("`"):
        yield buf


def _raw_pieces(stream):
    for event in stream:
        if event.choices and event.choices[0].delta and event.choices[0].delta.content:
            yield event.choices[0].delta.content


def stream_translate(code, lang, analysis, ctx, on_fallback=None):
    if not is_configured():
        yield from _fallback(analysis)
        return
    sent = False
    try:
        stream = _client().chat.completions.create(
            model=_model(),
            messages=prompts.translate_messages(code, lang, analysis, ctx),
            stream=True,
            temperature=0,
        )
        for piece in _clean(_raw_pieces(stream)):
            sent = True
            yield piece
        if not sent:
            raise TranslateError("The translation model returned no code.")
    except Exception as exc:
        if sent:
            raise TranslateError(str(exc) or "The translation model stopped early.") from exc
        if on_fallback is not None:
            on_fallback(str(exc) or "The translation model did not answer.")
        yield from _fallback(analysis)


def _parse_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no json")
    return json.loads(text[start : end + 1])


def _clean_text(text):
    text = text.replace(" \u2014 ", ", ").replace("\u2014", ", ")
    text = re.sub(r"!(?=\s|$)", ".", text)
    return re.sub(r"\s+", " ", text).strip()


def _explanation_from(data, total):
    if not isinstance(data, dict):
        raise ValueError("shape")
    tag = data.get("tag")
    if tag is not None and tag not in TAGS:
        raise ValueError("tag")
    title = data.get("title")
    paras = data.get("paragraphs")
    if not isinstance(title, str) or not title.strip() or len(title) > 120:
        raise ValueError("title")
    if not isinstance(paras, list) or len(paras) > 2 or not all(isinstance(p, str) and p.strip() for p in paras):
        raise ValueError("paragraphs")
    note = data.get("note")
    body = data.get("fixed_body")
    count = f"All {total} checks match." if total else "All checks match."
    return Explanation(
        "model",
        tag,
        _clean_text(title),
        [_clean_text(p) for p in paras],
        _clean_text(note) if isinstance(note, str) and note.strip() else "Applying the fix changes the translation and runs it again.",
        _clean_text(body) if isinstance(body, str) and body.strip() else f"{count} The translation now follows the same rule as the original.",
    )


def explain(code, lang, python, failing_checks, analysis, ctx, total=None):
    rules = rule_explanation(failing_checks, python, analysis, ctx, total)
    if not is_configured() or not failing_checks:
        return rules
    try:
        text = _complete(prompts.explain_messages(code, lang, python, failing_checks, analysis, ctx))
        return _explanation_from(_parse_json(text), total)
    except Exception:
        return rules


def _patch_from(data):
    if not isinstance(data, dict) or not isinstance(data.get("hunks"), list) or not data["hunks"]:
        raise PatchError("The patch has no hunks.")
    hunks = []
    for h in data["hunks"]:
        try:
            start = int(h["start"])
            remove = [str(x) for x in h.get("remove", [])]
            add = [str(x) for x in h.get("add", [])]
        except (KeyError, TypeError, ValueError, AttributeError):
            raise PatchError("A hunk has the wrong format.")
        hunks.append(Hunk(start, remove, add))
    summary = data.get("summary")
    return Patch(_clean_text(summary) if isinstance(summary, str) and summary.strip() else "Fix the translation.", hunks)


def _improves(python, patch, score, baseline):
    if score is None:
        return True, None
    patched, _ = apply_patch(python, patch)
    result = score(patched)
    if result is None:
        return False, None
    matched, failing = result
    return matched > baseline, failing


def propose_fix(code, lang, python, failing_checks, analysis, explanation, score=None, baseline=0):
    tag = explanation.tag if explanation is not None else None
    if is_configured() and failing_checks:
        messages = prompts.fix_messages(code, lang, python, failing_checks, explanation)
        for _ in range(2):
            text = ""
            try:
                text = _complete(messages, 2500)
                patch = _patch_from(_parse_json(text))
                better, still_failing = _improves(python, patch, score, baseline)
                if better:
                    return patch
                messages = prompts.retry_messages(messages, text, still_failing)
            except PatchError as exc:
                messages = prompts.repair_messages(messages, text, str(exc))
            except ValueError:
                messages = prompts.repair_messages(messages, text, "The reply was not valid JSON.")
            except Exception:
                break
    try:
        patch = rule_fix(python, analysis, failing_checks, tag)
        if patch is None:
            return None
        better, _ = _improves(python, patch, score, baseline)
        return patch if better else None
    except Exception:
        return None
