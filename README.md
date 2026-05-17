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
| `.github/workflows/bump-version.yml` | Version bump → signed commit → PR (via `bump-my-version`) |

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

**Schedule runs only check links** — the markdown job is skipped on `schedule` events because markdown content is stable post-merge; only links rot independently. PR/push runs check both.

Repos that don't need cron monitoring can omit the `schedule:` trigger and drop the `with: notify_on_failure:` line. **The `issues: write` permission must still be granted**, however — the reusable's `notify` job declares it unconditionally, and GitHub Actions validates all reusable-job permissions at workflow startup, *before* `if:` conditions are evaluated. Omitting it yields `startup_failure` on every run, even when `notify_on_failure` is `false` and the notify job is correctly skipped at runtime.

Minimal caller (no cron, no notify):

```yaml
name: Lint MD and Links
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:
permissions:
  contents: read
  issues: write  # required at workflow startup even when not opting into notify
jobs:
  lint:
    uses: qte77/.github/.github/workflows/lint-md-links.yml@<SHA>
```

### Bump version (workflow_dispatch)

The `bump-version.yml` reusable workflow runs `bump-my-version` on the caller's project, makes a signed commit via the GitHub API, pushes a bump branch, and opens a PR. It does **not** create tags or releases — that stays a separate concern. After the bump PR merges, run `gh release create vX.Y.Z` manually; release automation is a [follow-up](https://github.com/qte77/.github/issues/23).

```yaml
name: Bump Version
on:
  workflow_dispatch:
    inputs:
      bump_type:
        description: "[major|minor|patch]"
        required: true
        type: choice
        options: [patch, minor, major]
permissions:
  contents: write
  pull-requests: write
jobs:
  bump:
    uses: qte77/.github/.github/workflows/bump-version.yml@<SHA>
    with:
      bump_type: ${{ inputs.bump_type }}
    secrets: inherit
```

Consumer-repo prerequisites:

- *Settings → Actions → General → Workflow permissions → "Allow GitHub Actions to create and approve pull requests"* must be enabled, otherwise `gh pr create` returns `403 not authorized`.
- A bumpversion source must be present in the caller repo. Typical setup is `pyproject.toml` with a `[tool.bumpversion]` table containing `current_version` and any `[[tool.bumpversion.files]]` entries.

Inputs (all optional except `bump_type`):

| Input | Default | Notes |
|---|---|---|
| `bump_type` | — | `patch` / `minor` / `major` |
| `python_version` | `"3.13"` | Passed to `actions/setup-python` |
| `bump_my_version_pin` | `"1.3.0"` | Pip version spec |
| `branch_prefix` | `"bump"` | Branch is `<prefix>-<run_number>-<ref_name>` |
| `pr_title_template` | `"chore(release): bump {previous} → {current}"` | `{previous}` / `{current}` substituted at runtime |
| `open_pr` | `"true"` | Set to `"false"` to push the branch but skip PR creation |

Outputs: `previous_version`, `current_version`, `branch`, `pr_url`.

On failure or cancellation, the workflow closes the PR (if any) and deletes the bump branch. It **never** deletes tags or releases — GitHub's release-immutability setting remembers deleted tag names forever, so deleting on failure permanently burns the version number (see [#23](https://github.com/qte77/.github/issues/23) for the incident that led to this rule).

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

### Local linting

Install `markdownlint-cli2` to match CI behavior (the action uses cli2). The older `markdownlint` CLI does not honor `.markdownlint-cli2.jsonc` ignore files, which causes local-vs-CI discrepancies.

```bash
npm install -g markdownlint-cli2
markdownlint-cli2 '**/*.md'
```

## References

- Default community health files: <https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file>
- Licensing a repository: <https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository>
- User profile README: <https://docs.github.com/en/account-and-profile/setting-up-and-managing-your-github-profile/customizing-your-profile/managing-your-profile-readme>
