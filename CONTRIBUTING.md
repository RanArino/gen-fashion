# Contributing to gen-fashion

## Branch model

```
main        ← production (auto-deploy to Cloud Run + Firebase Hosting on every push)
  └── develop   ← integration (CI checks only — no cloud deploy)
        └── feat/*   ← feature work (local only)
```

### Rules

| Branch | Created from | Merged into | Deployed? |
|--------|-------------|-------------|-----------|
| `feat/*` | `develop` | `develop` (via PR) | No |
| `develop` | — | `main` (via PR) | No (CI only) |
| `main` | — | — | Yes (auto on push) |

- **Never push directly to `main` or `develop`.** Both branches are protected; all changes must go through a pull request with passing CI.
- **Every merge to `main` triggers a production deploy.** Keep `develop` as the staging ground and only open a `develop → main` PR when the integration branch is verified.

## Branch naming

| Type | Pattern | Example |
|------|---------|---------|
| Feature | `feat/<short-description>` | `feat/user-history-gallery` |
| Bug fix | `fix/<short-description>` | `fix/session-timeout` |
| Docs / chores | `docs/<topic>` or `chore/<topic>` | `docs/api-reference` |

Use kebab-case, all lowercase.

## Workflow

```bash
# 1. Start from develop
git checkout develop && git pull

# 2. Create a feature branch
git checkout -b feat/my-feature

# 3. Work, commit, push
git push -u origin feat/my-feature

# 4. Open PR: feat/my-feature → develop
#    CI (test-fastapi, test-adk, test-flutter) must pass before merge.

# 5. When develop is ready for production:
#    Open PR: develop → main
#    CI must pass; merge triggers the deploy job.
```

## Commit messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short summary>
```

Common types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`

Examples:
```
feat(session): add run-history gallery endpoint
fix(ci): patch firestore mock in shared_closet_search test
chore(docs): update feature matrix for MF-1 completion
```

## CI checks (required to merge)

All three jobs must pass on every PR:

| Job | Command | Working dir |
|-----|---------|-------------|
| `test-fastapi` | `pytest -q` | `fastapi-service/` |
| `test-adk` | `pytest -q` | `adk-agent-service/` |
| `test-flutter` | `flutter analyze && flutter test` | `flutter-web-app/` |

See [`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml) for the full pipeline.

## Local development

See [`README_LOCAL_DEV.md`](README_LOCAL_DEV.md) for setup instructions (`make dev`, emulators, seed data).
