# qte77/.github

Default community health files for repositories owned by
[@qte77](https://github.com/qte77). Files here are inherited by any
`qte77/*` repository that does not define its own.

## Cascading files

| File | Purpose |
|---|---|
| `CODE_OF_CONDUCT.md` | Conduct rules across all qte77 projects |
| `CONTRIBUTING.md` | How to contribute |
| `GOVERNANCE.md` | Decision-making and maintainer roles |
| `SECURITY.md` | Vulnerability reporting |
| `SUPPORT.md` | Where to ask questions |
| `.github/DISCUSSION_TEMPLATE/*.yml` | Discussion category forms (ideas, q-and-a, show-and-tell) |
| `.github/ISSUE_TEMPLATE/*.yml` | Bug report, feature request, chooser config |
| `.github/PULL_REQUEST_TEMPLATE.md` | PR description template |

The cascade applies to GitHub-rendered surfaces only (Security tab, issue chooser, profile sidebar). Files do not materialize in consuming repos, so filesystem references like `[security](SECURITY.md)`, `[ -f SECURITY.md ]`, or `cat CONTRIBUTING.md` still 404. For cross-doc links use:

- `https://github.com/qte77/<repo>/security/policy` (renders cascaded content)
- `https://github.com/qte77/.github/blob/main/<file>` (canonical source)

## Templates (not cascadable)

These must live in each repo individually — copy from here when bootstrapping a new repo.

| File | Purpose |
|---|---|
| `LICENSE` | Canonical Apache-2.0 text |
| `NOTICE` | Attribution template with `{PROJECT_NAME}` and `{YEAR}` placeholders |

## Reusable workflows

Workflows downstream `qte77/*` repos can call directly. Configs (`.markdownlint.jsonc`, `lychee.toml`) are picked up from the caller's repo if present, otherwise fetched from this repo's `main` branch as fallback.

| Workflow | Purpose |
|---|---|
| `.github/workflows/lint-md-links.yml` | Markdown + link checking (markdownlint-cli2 + lychee) |

Caller usage:

```yaml
jobs:
  lint:
    uses: qte77/.github/.github/workflows/lint-md-links.yml@main
```

The actions inside the workflow are SHA-pinned. The workflow's runtime config fetch (`.markdownlint.jsonc`, `lychee.toml`) tracks `main`, so lint rule updates propagate to all callers automatically. Override locally by committing a `.markdownlint.jsonc` or `lychee.toml` at the caller repo root.

For stricter reproducibility, callers can pin the `uses:` ref to a SHA instead of `@main` (this is what `qte77/*` repos do internally — not a requirement for external callers):

```yaml
uses: qte77/.github/.github/workflows/lint-md-links.yml@<SHA>  # bump on .github updates
```

### Scheduled monitoring (opt-in)

The reusable workflow accepts a `notify_on_failure` input. Use a **single caller file** that handles PR-blocking and cron monitoring together — `notify_on_failure` derives from the trigger so an issue is only created on scheduled failures, never on PR failures:

```yaml
name: Lint MD and Links
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: "0 0 * * 0"  # weekly Sunday 00:00 UTC
  workflow_dispatch:
permissions:
  contents: read
  issues: write
jobs:
  lint:
    uses: qte77/.github/.github/workflows/lint-md-links.yml@<SHA>
    with:
      notify_on_failure: ${{ github.event_name == 'schedule' }}
    permissions:
      contents: read
      issues: write
```

One caller file, one job — never two files. The `schedule:` trigger must live in the caller because reusable workflows cannot propagate `schedule:` to callers (see [GitHub docs](https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#workflow_call)).

Repos that don't need cron monitoring can omit the `schedule:` trigger and the `issues: write` permission.

### Keeping caller SHA pins fresh

Each caller pins `uses:` to a specific `qte77/.github` commit. To get notified about updates without manual SHA chasing, enable Dependabot for GitHub Actions in the caller repo (`.github/dependabot.yml`):

```yaml
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
```

Dependabot opens a PR whenever a newer commit lands on `qte77/.github` `main`, so each caller pulls updates on its own cadence. No central fan-out, no `repository_dispatch`, no scripted bumps — decentralized propagation.

References:

- [Reusable workflows](https://docs.github.com/en/actions/sharing-automations/reusing-workflows)
- [Workflow_call event semantics](https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#workflow_call)
- [Keeping actions up to date with Dependabot](https://docs.github.com/en/code-security/dependabot/working-with-dependabot/keeping-your-actions-up-to-date-with-dependabot)
- [`dependabot.yml` configuration](https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file)

## Lint configs

These templates pair with the reusable lint workflow above. Copy into a downstream repo to override the fallback fetched from `main`.

| File | Purpose |
|---|---|
| `.markdownlint.jsonc` | Markdown style rules (MD013 disabled, MD060 padded tables, frontmatter-aware MD041) |
| `lychee.toml` | Link checker config (accept common bot-blocking codes) |

## References

- Default community health files: <https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file>
- Licensing a repository: <https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository>
- User profile README: <https://docs.github.com/en/account-and-profile/setting-up-and-managing-your-github-profile/customizing-your-profile/managing-your-profile-readme>
