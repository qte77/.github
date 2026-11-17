# Plan 2026-11-17-0001 — Maintenance backlog

**Status:** OPEN, opened 2026-11-17 from the qte77 estate maintenance sweep. That sweep ranks open issues, alerts and
TODOs by value and effort; this plan lists this repo's rows above its cut, each checked live on 2026-11-17. Nothing
has shipped under this plan yet. The sweep found no open PRs, alerts or TODO markers here, only issues. Lower-value
open issues (#22, #29, #37) are not part of this arc and stay in GitHub Issues.

## Start here

**What's next, in order:**

1. **Owner decisions (rows 1-5).** Each has evidence on the issue or a recommended default below. They are closes and
   settings, not code.
2. **Row 6, callers on tagged pins (#44 step 2).** Re-pin each caller of this repo's reusable workflows to
   `@<sha>  # v<tag>` so Dependabot can bump them. One PR per caller repo, then cut a new tag and watch for the first
   Dependabot bump PR.
3. **Row 7, Dependabot `github-actions` updates in callers (#18).** After row 6, add or extend `.github/dependabot.yml`
   in callers that lack it.
4. **Row 8 (#19)** waits for the owner's call (see the default below).

**The loop:** one topic per branch and PR. Changes to `.github/workflows/` here affect every caller, so check the
callers before changing an input or a filename. Strike the row in the same PR that ships it. Merge once CI is green and the owner has given the
go-ahead for the session.

**Owner gates:** rows 1-5 and 8. Row 3 needs a GitHub App and secrets set up by the owner.

**Watch-outs:**

- Caller PRs touch workflow files in other repos. Those repos' own rulesets and required checks apply.
- Bump PRs opened with `GITHUB_TOKEN` start no `pull_request` workflows (row 3), so a required check may not report on
  them until the PR is closed and reopened by a person.

## Source map

| Row | Files and refs |
|---|---|
| 1 | `.github/workflows/lint-md-links.yml` `notify` job (upsert and auto-close shipped in #50, 2026-10-31); lychee step has no `GITHUB_TOKEN`. Evidence comment on #35, 2026-11-17. |
| 2 | `.github/workflows/lint-md-links.yml` uses `DavidAnson/markdownlint-cli2-action` and `lycheeverse/lychee-action`; callers allow-list both today (e.g. gha-sbom-action, green since 2026-11-13). Evidence comment on #63, 2026-11-17. |
| 3 | `.github/workflows/bump-version.yml` inputs `app_client_id` / `app_private_key` (added in #54); issue #70. |
| 4 | `.github/workflows/lint-actions.yml` (`workflow_call`: actionlint, yamllint, zizmor) is on `main`; issue #34. |
| 5 | `.github/workflows/bump-version.yml` (reusable bump, shipped in #24); issue #23 chose a reusable workflow over a Marketplace repo. |
| 6 | Issue #44 (steps 1-3, done-when). `v0.1.1` tagged and released 2026-11-13 by `bump.yml` / `release.yml`. Callers pin bare SHA `a32769a` with a date comment (14 repos re-pinned 2026-11-13). |
| 7 | Issue #18 (caller list and the `dependabot.yml` snippet). |
| 8 | Issue #19; `.github/workflows/lint-md-links.yml` and every caller's `uses:` line. |

## Decisions (with defaults)

- **Row 2 (#63).** Callers already work through the allow-list. Default: keep the issue open as low priority; do it
  only if a new caller should not need the allow-list step.
- **Row 5 (#23).** Its chosen form (a reusable workflow) shipped in #24 and runs in callers. Default: close it; caller
  adoption of the reusable release workflows is tracked in the estate maintenance plan, not here.
- **Row 8 (#19).** A rename breaks every caller's `uses:` line, and Dependabot can't migrate a filename. Default: do it
  only together with row 6's re-pin PRs (one caller PR does both), or close it.

## Remaining work

| # | Item | Value / effort | Gate | Done when |
|---|---|---|---|---|
| 1 | Close #35 (notify upsert shipped in #50), or narrow it to the optional lychee token point | hygiene / S | owner | #35 closed or retitled |
| 2 | Decide #63 (pinned run steps so callers need no allow-list) | hygiene / S | owner | Kept with a priority, or closed |
| 3 | Bump PRs run their required checks: create the estate GitHub App, store its credentials, pass them from callers (#70) | broken automation / M | owner | A bump PR opened by the reusable workflow runs every required check without a manual reopen |
| 4 | Close #34 (reusable `lint-actions.yml` is on `main`) | hygiene / S | owner | #34 closed |
| 5 | Close #23 per the default | hygiene / S | owner | #23 closed |
| 6 | Re-pin callers to `@<sha>  # v<tag>` and confirm a Dependabot bump (#44 steps 2-3) | automation / M | agent | Every caller pins the tag-commented form; after a new tag, at least one caller gets a Dependabot bump PR for its `qte77/.github` pin |
| 7 | Dependabot `github-actions` updates in every caller (#18) | automation / S | agent | Each caller listed in #18 has a `github-actions` Dependabot entry; #18 closed |
| 8 | Rename `lint-md-links.yml` to `lint-md-and-links.yaml` (#19) | hygiene / M | owner | Owner decision applied: renamed with all callers migrated, or #19 closed |
