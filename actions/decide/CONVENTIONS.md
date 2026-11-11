# Decision models in qte77 actions: conventions

How qte77 GitHub Actions ask a model a question. The [`decide` README](README.md) documents the
gate itself: question schema, result shape, bands, secrets, pinning. This page covers when to use
it, which defaults to start from, and how to roll it out.

## Decision first, free text last

- A question with a fixed answer goes to `decide()`: yes/no (`predicate`), one of a list
  (`choice`), or a level on a scale (`score`). Relevance filters, labels, triage fields and
  go/no-go gates are all decisions.
- A generative LLM (an OpenAI-compatible chat endpoint, Cloudflare Workers AI in this estate) is
  used only for free text, and as the fallback for answers the gate does not act on.
- Model free text never goes into a public comment, label or commit. Issue and PR text can steer
  what a model writes, so public output carries only fixed-list values and numbers.

## Acting on an answer

- `act`: use the answer.
- `review`: don't act automatically. Fall back to the chat call, a human, or a no-op, whichever
  the action documents.
- `escalate` (error, timeout, missing key, refusal, WAF block): never a verdict. Treat it like
  `review` and count it in the run summary.
- A run where every call failed, or that loaded no input at all, exits non-zero. A green run
  that did nothing hides an outage.

## Defaults

| Use case                     | Backend / model | `hi`   | Status                       |
| ---------------------------- | --------------- | ------ | ---------------------------- |
| Paper relevance (yes/no)     | `clef` / `clef` | `0.75` | Calibrated on 100 papers     |
| Issue triage fields          | `clef` / `clef` | `0.75` | Shadow mode only             |
| Anything new                 | `clef` / `clef` | `0.85` | `decide()`'s own default `hi` |

- The paper threshold comes from one in-sample run (2026-11) on 100 agent-labelled papers. It is
  the smallest `hi` whose acted answers were wrong at most 5% of the time. On those papers, Clef
  (27B) and TypeSafe's Jev 1.13.0 scored within each other's bootstrap intervals. Clef-flash
  (9B) was cheaper but scored lower. Re-measure before relying on the number for another topic.
- `clef` needs no extra key: it uses the same Workers AI token as the chat fallback. `jev` needs
  `TYPESAFE_API_KEY` and is a per-repo opt-in.
- Thresholds don't transfer between repos or question wordings. A threshold belongs to one
  question asked against one kind of input.

## Rolling out a new decision

1. **Shadow.** Ask the question next to the existing logic and report value, probability and
   band in fixed format, without acting on them.
2. **Measure.** Once enough real cases carry the shadow output, sweep `hi` against the outcomes
   you trust and pick the smallest value that meets an error budget fixed in advance.
3. **Act.** Turn on acting at that `hi`, keep the fallback for `review` and `escalate`, and keep
   counting both.

## Secrets and wiring

- Secret names are fixed across the estate: `CF_WORKERS_AI_TOKEN`, `LLM_BASE_URL` and
  `TYPESAFE_API_KEY`. The README's Secrets section says which backend reads which.
- `LLM_BASE_URL` is a secret, not a repository variable: the URL contains the Cloudflare account id.
- A reusable workflow's `with:` block can't read the `secrets` context. Pass the base URL through
  the callee's `secrets:` block instead.
- An action must send each backend only its own credentials: the Cloudflare token goes to `clef`
  and `cf`, the TypeSafe key to `jev`.
- Callers load `decide.py` from a checkout of this repo pinned to a commit SHA (this repo has no
  tags). Never copy `decide.py` into another repo.

## Where it is used

- [gha-rxiv-paper-eval](https://github.com/qte77/gha-rxiv-paper-eval): paper relevance through
  `decide()`, chat fallback for the uncertain band (opt-in, `decide_enabled`).
- [gha-issue-triage](https://github.com/qte77/gha-issue-triage): the six triage fields in shadow
  mode (opt-in, `decide-shadow`).
