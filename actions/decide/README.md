# decide

A shared act/review/escalate decision gate for GitHub Actions workflows across
the qte77 estate. Ask one or more questions about a piece of state against
[TypeSafe's Jev model][typesafe-api] (calibrated probabilities) or, as an
uncalibrated fallback, an OpenAI-compatible chat endpoint such as Cloudflare
Workers AI. Get back a band per question so a workflow can gate on it without
ever auto-acting on an unreliable answer.

Python standard library only — no runtime dependencies. Works on any GitHub
Actions runner with `python3`.

## Question schema

Each question is a dict:

| Field          | Required          | Meaning                                                  |
| --------------- | ------------------ | ---------------------------------------------------------- |
| `name`         | yes                | Key the answer comes back under.                         |
| `type`         | yes                | `"predicate"`, `"choice"`, or `"score"`.                 |
| `instructions` | yes                | The question to ask, as plain text.                      |
| `choices`      | for `"choice"`     | A list of labels, or a `{label: description}` map.       |
| `levels`       | for `"score"`      | An ordered list of level descriptions, low to high.      |

`"predicate"` maps to Jev's `noul` (yes/no) primitive; `"choice"` and
`"score"` map 1:1 to Jev's own primitives of the same name. See
[docs.typesafe.ai/primitives][typesafe-primitives].

## Result shape

`decide()` / the CLI / the action's `result` output all return the same
shape — one entry per question, keyed by `name`:

| Field         | Meaning                                                                          |
| -------------- | ------------------------------------------------------------------------------- |
| `value`       | The answer: a bool (predicate), the chosen label (choice), or a number (score). |
| `probability` | A 0-1 confidence signal — see "Bands" below for what it means per type.         |
| `band`        | `"act"`, `"review"`, or `"escalate"`.                                          |
| `source`      | `"jev"` or `"cf"`.                                                             |
| `error`       | `None` on success, else a short message (never contains a secret).             |

A malformed question, a backend error, a timeout, a missing credential, or a
non-JSON/refused reply all become `{"value": null, "probability": null, "band":
"escalate", "error": "..."}`. **`decide()` never raises for a backend or
network failure** — only for a malformed call (unknown backend, a question
with no `name`, or two questions sharing a `name`).

## Bands

- **`predicate`**: `probability` is Jev's raw `noul` value (0 = confidently
  no, 1 = confidently yes). Both tails are decisive, so the gate is
  symmetric: `probability >= hi` **or** `probability <= 1 - hi` → `"act"`;
  otherwise `"review"`.
- **`choice` / `score`**: `probability` is Jev's own `confidence` statistic —
  how concentrated the answer's probability distribution is (1 = all mass on
  one outcome, 0 = spread evenly across options/levels). It is **not** a
  probability of being correct, and unlike `predicate` it has only one
  decisive tail: low confidence means "the model is unsure," not "confidently
  something else" (there is no single opposite outcome for an argmax over N
  options). The gate is asymmetric: only `probability >= hi` → `"act"`.
  See [docs.typesafe.ai/confidence][typesafe-confidence] and
  [docs.typesafe.ai/patterns/confidence-routing][typesafe-routing] (the
  pattern this gate follows; its own example uses a 0.6 floor and a 0.85
  threshold for auto-approving a high-stakes action — `hi`'s default here).
- **`cf` backend**: never calibrated, so `probability` is always `None` and
  the band is always `"escalate"`. The fallback exists to get *an* answer
  without ever auto-acting on it.

## Secrets

Pass secrets via environment, not as action inputs that end up in a JSON
payload:

| Env var                | Backend | Purpose             |
| ------------------------ | -------- | ---------------------- |
| `TYPESAFE_API_KEY`     | `jev`   | Bearer token for TypeSafe. |
| `CF_WORKERS_AI_TOKEN`  | `cf`    | Bearer token for the CF-compatible endpoint. |
| `LLM_BASE_URL`         | `cf`    | The OpenAI-compatible base URL your deployment exposes. |

`decide()` reads these from `os.environ` when `api_key` / `api_base` aren't
passed explicitly. The composite action (`action.yml`) wires its
`typesafe_api_key`, `cf_api_token`, and `cf_base_url` inputs straight into
these env vars for the one step that calls `decide.py` — they are never
embedded in the JSON payload the action builds.

## Using the composite action

```yaml
- uses: qte77/.github/actions/decide@<SHA>  # pin by commit SHA — this repo has no tags
  id: gate
  with:
    state: ${{ steps.collect.outputs.diff }}
    questions: |
      [{"name": "risky", "type": "predicate", "instructions": "Does this diff touch production credentials?"}]
    backend: jev
    hi: "0.85"
    typesafe_api_key: ${{ secrets.TYPESAFE_API_KEY }}
- run: echo '${{ steps.gate.outputs.result }}' | jq '.risky.band'
```

## Using the library directly

```python
import sys

sys.path.insert(0, "actions/decide")
from decide import decide

result = decide(
    "some state to evaluate",
    [{"name": "risky", "type": "predicate", "instructions": "Is this risky?"}],
    backend="jev",
    api_key="...",
)
```

## CLI

`decide.py` also runs as a script: JSON in on stdin, JSON out on stdout.

```bash
echo '{"state": "...", "questions": [{"name": "q", "type": "predicate", "instructions": "..."}]}' \
  | TYPESAFE_API_KEY=... python3 actions/decide/decide.py
```

## Pinning

This repo has no tags — pin `uses:` to a commit SHA, as `README.md`'s
"Keeping caller SHA pins fresh" section describes (Dependabot bumps it).

## Limitations

- **Jev wire shape**: verified 2026-10-10 against
  [docs.typesafe.ai/api][typesafe-api], [docs.typesafe.ai/models][typesafe-models],
  [docs.typesafe.ai/confidence][typesafe-confidence], and the installed
  `typesafe-sdk==0.7.1` source.
- **The TypeSafe WAF 403 behavior is unverified against TypeSafe's own docs** —
  the only source for "some content gets 403'd by TypeSafe's Cloudflare WAF
  regardless of credentials" is a code comment in a sibling project's caller.
  A 403 still escalates correctly either way (`TypeSafePermissionDeniedError`
  territory per the SDK's exceptions page); only the *cause* is unconfirmed.
- **The `User-Agent: qte77-decide/0.1.0` header is sent on every request, but
  whether it changes WAF behavior one way or the other is unverified** —
  it's cheap insurance against urllib's default (a bot-signature-looking
  `Python-urllib/3.x`), not a confirmed fix for the 403s above.
- **The `cf` backend's request/response shape (`{base}/chat/completions`,
  OpenAI-compatible) was not independently re-verified against Cloudflare's
  own docs this session** — it follows the `LLM_BASE_URL` + `api_base`
  convention already used elsewhere in the qte77 estate.
- No OpenAI `/v1/decisions` or Perplexity adapter — out of scope for now.
- `score` questions pick `probability` from Jev's `confidence` field; there is
  no first-party guidance on using it for a Jev-native "review" threshold
  beyond the `choice`-oriented confidence-routing pattern, so treat the
  `score` gate as this action's own extrapolation of the same idea.

[typesafe-api]: https://docs.typesafe.ai/api
[typesafe-primitives]: https://docs.typesafe.ai/primitives
[typesafe-models]: https://docs.typesafe.ai/models
[typesafe-confidence]: https://docs.typesafe.ai/confidence
[typesafe-routing]: https://docs.typesafe.ai/patterns/confidence-routing
