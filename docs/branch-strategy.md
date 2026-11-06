# Branching and commit discipline

Source: PRD §12.

- `main` is always stable: it builds, it starts, and its tests pass.
- Each milestone gets one feature branch, such as `feat/m0-foundation` or `feat/m1-document-upload`. Larger milestones may use several short-lived branches.
- A branch merges to `main` with `git merge --no-ff` only after its milestone exit criteria are verified, so the history shows where each milestone landed.
- Commits follow [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`. Each commit is one verified, coherent unit.
- Forbidden: force-push, history rewriting, backdated or fabricated commits, artificial author identities, and commits that skip or delete failing tests to get green.
- Never commit `.env`, secrets, uploads (`data/`), model weights, DB volumes or private evaluation corpora. `.gitignore` and the CI `policy` job enforce this.
- After each commit, report the hash, changed files, the tests that ran, and their results.
- Pushing requires a configured remote and credentials. As of 2026-11-06 there is no remote: commits are local only.
