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
