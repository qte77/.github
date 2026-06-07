# Contributing

Thanks for considering a contribution.

## Before you start

- Check open issues to avoid duplication
- For non-trivial changes, open an issue first to discuss direction
- Small fixes (typos, docs) can go straight to a PR

## Pull requests

- Keep PRs focused — one concern per PR
- Write a clear description: what changed and why
- Reference related issues (`Closes #123`)
- Ensure CI passes before requesting review

> **Templates & the CLI:** PR, issue, and discussion templates auto-populate
> only in the web UI — `gh`/the REST API won't pull these owner-level defaults.
> A repo's own committed template always takes precedence; only when none exists
> does the cascade apply, sourced from the git-tracked file in `qte77/.github`.
> When scripting, use the web UI or fetch that file explicitly. See the
> [cascade notes](https://github.com/qte77/.github/blob/main/README.md#cascading-files).

## Commit messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation only
- `chore:` tooling, dependencies, non-user-facing
- `refactor:` code change that neither fixes nor adds
- `test:` tests only

## Questions

Open an issue in the relevant repository.
