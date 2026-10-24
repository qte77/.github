"""decide: a minimal, conservative decision gate for GitHub Actions workflows.

Asks one or more questions about a piece of state against TypeSafe's Jev model
(calibrated noul/choice/score probabilities, verified against docs.typesafe.ai
and the `typesafe-sdk==0.7.1` source, 2026-10-10) or, as an uncalibrated
fallback, an OpenAI-compatible chat endpoint (e.g. Cloudflare Workers AI).
Returns one of three bands per question so a caller can gate CI behavior on it:

- "act":      confident enough to proceed automatically.
- "review":   not confident enough; a human should look before anything acts.
- "escalate": no usable signal at all (error, timeout, missing credential,
              refusal, or an uncalibrated answer) — never upgraded to a verdict.

Standard library only — no runtime dependencies, so this can run on any GitHub
Actions runner with nothing but `python3`.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

TYPESAFE_BASE_URL = "https://api.typesafe.ai"
TYPESAFE_SYSTEM_ONE_PATH = "/v1/systemone"
CF_CHAT_COMPLETIONS_PATH = "/chat/completions"

# Verified 2026-10-10 against docs.typesafe.ai/models and docs.typesafe.ai/api,
# and against the installed typesafe-sdk==0.7.1 source
# (_core/constants.py DEFAULT_MODEL, _core/endpoints.py, _core/transport.py):
# POST https://api.typesafe.ai/v1/systemone, Authorization: Bearer <key>, body
# {"state", "model", "questions"}, "jev-1.13.0" is a valid (non-alias) request
# value. The SDK itself defaults to the "jev-latest" alias; we pin the version
# instead so behavior doesn't shift under us when TypeSafe moves the alias.
DEFAULT_JEV_MODEL = "jev-1.13.0"

# NOT independently re-verified against Cloudflare's own docs this session —
# this is the OpenAI-compatible `{base}/chat/completions` convention already in
# use elsewhere across the qte77 estate (e.g. gha-rxiv-paper-eval's LLM_BASE_URL
# + api_base pattern). Treat the exact CF request/response shape as unverified.
DEFAULT_CF_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"

# TypeSafe's own confidence-routing pattern doc (docs.typesafe.ai/patterns/
# confidence-routing) uses 0.6 as a floor and 0.85 to auto-approve a high-stakes
# action; 0.85 is the same conservative default used here.
DEFAULT_HI = 0.85
DEFAULT_TIMEOUT = 10.0

# urllib's default User-Agent ("Python-urllib/3.x") reads as a bot signature.
# TypeSafe sits behind a Cloudflare WAF (per the feelings repo's jev_gate.py
# comment) and the official SDK sends its own UA; sending one here too is
# cheap insurance. UNVERIFIED: whether this affects WAF behavior either way.
USER_AGENT = "qte77-decide/0.1.0"

_MAX_ERROR_BODY = 200

# Maps our question "type" to the wire's "type". Our "predicate" is TypeSafe's
# "noul" (yes/no); "choice" and "score" pass through unchanged.
_JEV_TYPE_FOR = {"predicate": "noul", "choice": "choice", "score": "score"}


class DecideError(Exception):
    """A malformed *call* (bad backend name, a question with no name, a duplicate
    name). Never raised for a backend/network failure — those always escalate
    instead; see `_escalate`.
    """


class _QuestionShapeError(Exception):
    """A malformed single *question* dict (unknown type, missing instructions,
    missing choices/levels). Caught internally and turned into an escalate
    verdict for that question only — other questions in the same call still get
    answered.
    """


def _escalate(error: str, source: str) -> dict[str, Any]:
    return {"value": None, "probability": None, "band": "escalate", "source": source, "error": error}


def _band(probability: float | None, hi: float, symmetric: bool) -> str:
    """Band a 0-1 value into act/review/escalate.

    symmetric=True (predicate/noul): the raw noul probability. A value near 0 is
    "confidently false," just as actionable as a value near 1 near "confidently
    true" — so both tails act.

    symmetric=False (choice/score): TypeSafe's `confidence` statistic (how
    concentrated the probability distribution is — 0 spread evenly, 1 all on one
    outcome; see docs.typesafe.ai/confidence). It is NOT a probability of being
    correct, and it has only one decisive tail: low confidence means "the model
    is unsure," not "confidently something else" (there is no single "opposite"
    outcome for an argmax over N options). Only the high tail acts.
    """
    if probability is None:
        return "escalate"
    if probability >= hi:
        return "act"
    if symmetric and probability <= 1 - hi:
        return "act"
    return "review"


def _redact(message: str, *secrets: str) -> str:
    for secret in secrets:
        if secret:
            message = message.replace(secret, "***")
    return message


def _post_json(url: str, body: dict[str, Any], headers: dict[str, str], timeout: float, secret: str) -> dict[str, Any]:
    """POST a JSON body and return the parsed JSON response, or raise RuntimeError.

    The raised message is truncated and scrubbed of `secret` — callers turn it
    into an escalate verdict's `error` field, which may end up in CI logs.
    """
    # Explicit scheme allowlist before urlopen() (addresses Bandit B310: urlopen
    # on an unvalidated scheme could open file:/ or other unexpected handlers).
    # `url` is built from a hardcoded default or an operator-supplied api_base /
    # LLM_BASE_URL, never from request/question content, but validating costs
    # nothing and turns a misconfigured base into a clear escalate instead of
    # a surprising open.
    scheme = urllib.parse.urlsplit(url).scheme
    if scheme not in ("http", "https"):
        raise RuntimeError(f"unsupported URL scheme: {scheme!r} (expected http or https)")

    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310 - scheme allowlisted above
            raw = response.read()
    except urllib.error.HTTPError as error:
        error_body = error.read()[:_MAX_ERROR_BODY].decode("utf-8", "replace")
        raise RuntimeError(_redact(f"HTTP {error.code}: {error_body}", secret)) from None
    except TimeoutError:
        raise RuntimeError("request timed out") from None
    except urllib.error.URLError as error:
        raise RuntimeError(_redact(f"connection error: {error.reason}", secret)) from None
    except Exception as error:
        # Reason: never-raise contract (see decide()'s docstring) — anything the three
        # excepts above don't name (ConnectionResetError, ssl.SSLError,
        # http.client.IncompleteRead/RemoteDisconnected, ...) must still become an
        # escalate verdict in the caller, not propagate out of decide().
        raise RuntimeError(_redact(f"{type(error).__name__}: {error}", secret)) from None

    if not raw:
        raise RuntimeError("empty response body")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise RuntimeError("response body was not valid UTF-8") from None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        raise RuntimeError("response body was not valid JSON") from None
    if not isinstance(parsed, dict):
        raise RuntimeError("response body was not a JSON object")
    return parsed


# --- Jev backend -------------------------------------------------------------


def _jev_question_payload(question: dict[str, Any]) -> dict[str, Any]:
    """Build one wire-format question dict, or raise _QuestionShapeError."""
    qtype = question.get("type")
    jev_type = _JEV_TYPE_FOR.get(qtype)
    if jev_type is None:
        raise _QuestionShapeError(f"unknown question type: {qtype!r}")
    instructions = question.get("instructions")
    if not instructions:
        raise _QuestionShapeError("'instructions' is required")
    payload: dict[str, Any] = {"type": jev_type, "instructions": instructions}
    if jev_type == "choice":
        choices = question.get("choices")
        if not choices:
            raise _QuestionShapeError("'choices' is required for type 'choice'")
        payload["criteria"] = choices if isinstance(choices, dict) else {label: None for label in choices}
    elif jev_type == "score":
        levels = question.get("levels")
        if not levels:
            raise _QuestionShapeError("'levels' is required for type 'score'")
        payload["criteria"] = list(levels)
    return payload


def _answer_from_jev(answer: Any, hi: float) -> dict[str, Any]:
    if not isinstance(answer, dict):
        return _escalate("missing answer in Jev response", "jev")
    kind = answer.get("type")
    if kind == "noul":
        probability = answer.get("noul")
        if not isinstance(probability, (int, float)):
            return _escalate("malformed noul answer: 'noul' missing or not a number", "jev")
        probability = float(probability)
        return {
            "value": probability >= 0.5,
            "probability": probability,
            "band": _band(probability, hi, symmetric=True),
            "source": "jev",
            "error": None,
        }
    if kind == "choice":
        choice = answer.get("choice")
        confidence = answer.get("confidence")
        confidence = float(confidence) if isinstance(confidence, (int, float)) else None
        return {
            "value": choice,
            "probability": confidence,
            "band": _band(confidence, hi, symmetric=False),
            "source": "jev",
            "error": None,
        }
    if kind == "score":
        score = answer.get("score")
        confidence = answer.get("confidence")
        confidence = float(confidence) if isinstance(confidence, (int, float)) else None
        return {
            "value": score,
            "probability": confidence,
            "band": _band(confidence, hi, symmetric=False),
            "source": "jev",
            "error": None,
        }
    return _escalate(f"unrecognized Jev answer type: {kind!r}", "jev")


def _decide_jev(
    state: str,
    questions: list[dict[str, Any]],
    model: str | None,
    api_key: str | None,
    api_base: str | None,
    timeout: float,
    hi: float,
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    batch: dict[str, dict[str, Any]] = {}
    for question in questions:
        name = question["name"]
        try:
            batch[name] = _jev_question_payload(question)
        except _QuestionShapeError as error:
            results[name] = _escalate(str(error), "jev")

    if not batch:
        return results

    key = api_key if api_key is not None else os.environ.get("TYPESAFE_API_KEY", "")
    key = key.strip()
    if not key:
        for name in batch:
            results[name] = _escalate("missing TYPESAFE_API_KEY", "jev")
        return results

    base = api_base if api_base is not None else os.environ.get("TYPESAFE_BASE_URL") or TYPESAFE_BASE_URL
    body = {"state": state, "model": model or DEFAULT_JEV_MODEL, "questions": batch}
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }

    try:
        parsed = _post_json(base.rstrip("/") + TYPESAFE_SYSTEM_ONE_PATH, body, headers, timeout, key)
    except RuntimeError as error:
        for name in batch:
            results[name] = _escalate(str(error), "jev")
        return results

    answers = parsed.get("answers")
    if not isinstance(answers, dict):
        for name in batch:
            results[name] = _escalate("malformed Jev response: missing 'answers'", "jev")
        return results

    for name in batch:
        results[name] = _answer_from_jev(answers.get(name), hi)
    return results


# --- Cloudflare Workers AI fallback ------------------------------------------


def _cf_prompt(state: str, question: dict[str, Any]) -> str:
    """Build a prompt asking for a strict `{"value": ...}` JSON reply, or raise
    _QuestionShapeError. Unverified against Cloudflare's own docs — see the
    module docstring and DEFAULT_CF_MODEL comment.
    """
    qtype = question.get("type")
    if qtype not in _JEV_TYPE_FOR:
        raise _QuestionShapeError(f"unknown question type: {qtype!r}")
    instructions = question.get("instructions")
    if not instructions:
        raise _QuestionShapeError("'instructions' is required")
    hint = ""
    if qtype == "choice":
        choices = question.get("choices")
        if not choices:
            raise _QuestionShapeError("'choices' is required for type 'choice'")
        labels = list(choices.keys()) if isinstance(choices, dict) else list(choices)
        hint = f" Answer with exactly one of: {labels}."
    elif qtype == "score":
        levels = question.get("levels")
        if not levels:
            raise _QuestionShapeError("'levels' is required for type 'score'")
        hint = f" Answer with the zero-based index into this ordered list of levels: {list(levels)}."
    return (
        f"State:\n{state}\n\nQuestion: {instructions}{hint}\n\n"
        'Reply with ONLY a JSON object of the shape {"value": <answer>} and nothing else.'
    )


def _answer_from_cf(parsed: dict[str, Any]) -> dict[str, Any]:
    try:
        content = parsed["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return _escalate("malformed CF response: no message content", "cf")
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        content = content.split("\n", 1)[1] if "\n" in content else content
    try:
        value_obj = json.loads(content)
    except json.JSONDecodeError:
        return _escalate("CF response was not valid JSON (refusal or free text)", "cf")
    if not isinstance(value_obj, dict) or "value" not in value_obj:
        return _escalate("CF response JSON missing 'value'", "cf")
    # CF is never calibrated: no probability, so _band() always returns
    # "escalate" here. This is intentional — an uncalibrated fallback must
    # never be upgraded to "act".
    return {"value": value_obj["value"], "probability": None, "band": "escalate", "source": "cf", "error": None}


def _decide_cf(
    state: str,
    questions: list[dict[str, Any]],
    model: str | None,
    api_key: str | None,
    api_base: str | None,
    timeout: float,
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    key = (api_key if api_key is not None else os.environ.get("CF_WORKERS_AI_TOKEN", "")).strip()
    base = (api_base if api_base is not None else os.environ.get("LLM_BASE_URL", "")).strip()

    for question in questions:
        name = question["name"]
        try:
            prompt = _cf_prompt(state, question)
        except _QuestionShapeError as error:
            results[name] = _escalate(str(error), "cf")
            continue
        if not key:
            results[name] = _escalate("missing CF_WORKERS_AI_TOKEN", "cf")
            continue
        if not base:
            results[name] = _escalate("missing LLM_BASE_URL", "cf")
            continue
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": USER_AGENT}
        body = {"model": model or DEFAULT_CF_MODEL, "messages": [{"role": "user", "content": prompt}]}
        try:
            parsed = _post_json(base.rstrip("/") + CF_CHAT_COMPLETIONS_PATH, body, headers, timeout, key)
        except RuntimeError as error:
            results[name] = _escalate(str(error), "cf")
            continue
        results[name] = _answer_from_cf(parsed)
    return results


# --- Public API ---------------------------------------------------------------


def decide(
    state: str,
    questions: list[dict[str, Any]],
    backend: str = "jev",
    hi: float = DEFAULT_HI,
    model: str | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, dict[str, Any]]:
    """Answer each question about `state` and band the result.

    questions: a list of {"name", "type": "predicate"|"choice"|"score",
    "instructions", "choices"? (for "choice"), "levels"? (for "score")}.

    Returns {name: {"value", "probability", "band", "source", "error"}}. A
    question whose shape is malformed, or whose backend call fails for any
    reason (HTTP error, timeout, missing credential, refusal, malformed
    response), gets `"band": "escalate"` and never a verdict.

    Raises DecideError only for a malformed *call* — an unknown backend, or a
    question with no "name" / a name reused by another question in the same
    call. Never raises for a backend or network failure.
    """
    if backend not in ("jev", "cf"):
        raise DecideError(f"unknown backend: {backend!r} (expected 'jev' or 'cf')")

    seen: set[str] = set()
    for question in questions:
        if not isinstance(question, dict) or not question.get("name"):
            raise DecideError("each question must be a dict with a non-empty 'name'")
        name = question["name"]
        if name in seen:
            raise DecideError(f"duplicate question name: {name!r}")
        seen.add(name)

    if backend == "jev":
        return _decide_jev(state, questions, model, api_key, api_base, timeout, hi)
    return _decide_cf(state, questions, model, api_key, api_base, timeout)


# --- CLI -----------------------------------------------------------------------

_CLI_OPTIONAL_KEYS = ("backend", "hi", "model", "api_key", "api_base", "timeout")


def main(argv: list[str] | None = None) -> int:
    """JSON in on stdin, JSON out on stdout.

    Input: {"state": str, "questions": [...], "backend"?, "hi"?, "model"?,
    "api_key"?, "api_base"?, "timeout"?}. Secrets are normally left out of this
    payload entirely and picked up from TYPESAFE_API_KEY / CF_WORKERS_AI_TOKEN /
    LLM_BASE_URL instead — see actions/decide/README.md.
    """
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        print(json.dumps({"error": f"invalid JSON on stdin: {error}"}), file=sys.stderr)
        return 2
    if not isinstance(payload, dict):
        print(json.dumps({"error": "stdin JSON must be an object"}), file=sys.stderr)
        return 2
    try:
        state = payload["state"]
        questions = payload["questions"]
    except KeyError as error:
        print(json.dumps({"error": f"missing required field: {error}"}), file=sys.stderr)
        return 2

    kwargs = {key: payload[key] for key in _CLI_OPTIONAL_KEYS if payload.get(key) is not None}
    try:
        result = decide(state, questions, **kwargs)
    except DecideError as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 2

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
