# CI/CD Pipeline Runbook — gen-fashion

Operational runbook for `.github/workflows/ci-cd.yml` (the "CI / CD" GitHub
Actions workflow). Written for whoever is on point when a run needs
attention — a failed merge-blocking test, a bad production deploy, or a
rollback that needs to happen by hand.

This doc does not duplicate raw `gcloud` commands or the WIF setup steps —
those live in [`docs/gcp-cheatsheet.md`](../gcp-cheatsheet.md) (§ "CI/CD —
Workload Identity Federation 設定" and its GitHub Secrets table). For
feature-tracking status of the CI/CD milestone (MF), see
[`docs/feature-matrix-phase01.md`](../feature-matrix-phase01.md), section
"MF — CI/CD (Continuous Delivery)". The requirement text this pipeline
implements is `docs/req-phase01.md` §19.

---

## 1. Pipeline overview

**File:** `.github/workflows/ci-cd.yml`
**Name in GitHub UI:** `CI / CD`

### Triggers

```yaml
on:
  push:
  pull_request:
    branches: [main, develop]
  workflow_dispatch:
```

- Every `push` (any branch) runs the four test jobs.
- Every PR targeting `main` or `develop` runs the four test jobs.
- `Deploy to Production` only runs when **either**:
  - the event is a `push` to `refs/heads/main`, **or**
  - the workflow was triggered manually via `workflow_dispatch`.
- `concurrency: group: ${{ github.workflow }}-${{ github.ref }}` with
  `cancel-in-progress: true` means a new push to the same ref cancels an
  in-flight run for that ref (so pushing twice to `main` in quick succession
  will cancel the first deploy attempt).

### Job graph

```
test-fastapi ─┐
test-adk ─────┼──► Deploy to Production   (only on push to main, or workflow_dispatch)
test-flutter ─┤
test-deploy-scripts ─┘
```

All four test jobs run in parallel on every push/PR. `deploy` declares
`needs: [test-fastapi, test-adk, test-flutter, test-deploy-scripts]`, so it
only starts once all four have passed — this is the CI gate (MF-2) blocking
a bad merge from reaching production.

| Job | What it does |
|---|---|
| `test-fastapi` | `pip install -r requirements.txt`, then `pytest tests/adapters/test_cloud_tasks_adapter.py -q` (isolated worker-thread regression) followed by the full `pytest -q` suite, in `fastapi-service/`. |
| `test-adk` | `pip install -r requirements.txt` then `pytest -q` in `adk-agent-service/`. |
| `test-flutter` | `flutter pub get`, `flutter analyze`, `flutter test` in `flutter-web-app/`. |
| `test-deploy-scripts` | `python3 -m unittest scripts.deploy.tests.test_deploy_firebase_hosting` — unit tests for the Firebase Hosting REST deploy script itself. |

### What "Deploy to Production" actually does

Job `deploy` (`name: Deploy to Production`), runs on `ubuntu-latest` under
the `production` GitHub Environment, with `permissions: id-token: write,
contents: read` (required for the WIF OIDC token exchange — see §2). Steps
in order:

1. **Authenticate to GCP (WIF)** — `google-github-actions/auth@v2` using
   `secrets.WIF_PROVIDER` / `secrets.WIF_SA`. No JSON key is stored anywhere
   (ADL-030).
2. **Set up gcloud CLI** — `google-github-actions/setup-gcloud@v2`.
3. **Configure Docker auth for Artifact Registry** —
   `gcloud auth configure-docker ${REGION}-docker.pkg.dev`.
4. **Deploy Firestore composite indexes** — runs
   `bash scripts/deploy/deploy_firestore_indexes.sh --project "${PROJECT}"`
   *before* the image build/deploy steps, so a query needing a new composite
   index never reaches prod without one (MF-6 note in the workflow). The
   script is idempotent: it diffs `firestore.indexes.json` against
   `gcloud firestore indexes composite list` and only creates indexes that
   don't already exist; new indexes build asynchronously in the background.
5. **Set image tag and registry path** — `IMAGE_TAG=ci-$(date
   +%Y%m%d)-${GITHUB_SHA::7}`, `REPO=${REGION}-docker.pkg.dev/${PROJECT}/gen-fashion`.
6. **Set up Docker Buildx** (`docker/setup-buildx-action@v3`), then build
   and push **both** service images with `docker/build-push-action@v5`,
   each using a GitHub Actions cache scope (`scope=fastapi` /
   `scope=adk`, `mode=max`) to speed up repeat builds:
   - `${REPO}/fastapi-service:${IMAGE_TAG}` from `./fastapi-service`
   - `${REPO}/adk-agent-service:${IMAGE_TAG}` from `./adk-agent-service`
7. **Get existing Cloud Run service URLs** — `gcloud run services describe`
   for both `adk-agent-service` and `fastapi-service`, capturing
   `ADK_URL` / `FASTAPI_URL` into `$GITHUB_ENV`. Cloud Run URLs are stable
   across revisions of the same named service, so this avoids a two-pass
   bootstrap (that's only needed the first time a service is provisioned;
   see the `--bootstrap` flag note in `deploy_fastapi.sh`).
8. **Record pre-deploy fastapi revision (for rollback)** — lists
   `fastapi-service` revisions sorted by `~metadata.creationTimestamp` and
   takes the top one into `PREV_FASTAPI_REV`. This is the revision the
   automated rollback (§4) will restore traffic to if the post-deploy smoke
   fails. **Important:** this is captured *before* the new revision is
   deployed, so it is the last-known-good revision at the start of this run,
   not necessarily "the revision that was serving traffic 5 minutes ago" if
   a prior run left something in a partial state.
9. **Deploy adk-agent-service** — `bash scripts/deploy/deploy_adk.sh
   --project ... --region ... --image ...` plus `--es-internal-ip`,
   `--es-ssl-fingerprint`, `--r2-endpoint-url`, `--r2-public-endpoint-url`,
   `--r2-bucket-name`, all sourced from GitHub Secrets. This service is
   deployed `--no-allow-unauthenticated` (private; only `fastapi-sa` can
   invoke it).
10. **Deploy fastapi-service** — `bash scripts/deploy/deploy_fastapi.sh
    --project ... --region ... --image ... --adk-url "${ADK_URL}"
    --fastapi-url "${FASTAPI_URL}" --es-internal-ip ... --es-ssl-fingerprint
    ... --cors-allow-origins "https://gen-fashion-app.web.app" --r2-... `.
    This service is public (`--allow-unauthenticated`) and gets the second
    (full-OIDC) pass of `deploy_fastapi.sh`, wiring `FASTAPI_INTERNAL_BASE_URL`
    and `INTERNAL_INVOKER_SA` for the internal worker route.
11. **Set up Flutter**, then **Build Flutter web (production)** —
    `flutter build web --release` with production `--dart-define`s:
    `API_BASE_URL=${FASTAPI_URL}`, `USE_EMULATORS=false`,
    `FIREBASE_PROJECT_ID`, and the `FIREBASE_*` values from GitHub Secrets.
12. **Deploy to Firebase Hosting** — `python3
    scripts/deploy/deploy_firebase_hosting.py --site gen-fashion-app
    --build-dir flutter-web-app/build/web`. This is a custom REST-API-based
    deploy script, **not** `firebase deploy`, because `firebase-tools` does
    not support WIF external-account credentials; the script instead calls
    `gcloud auth print-access-token` (which does work with WIF) and drives
    the Firebase Hosting REST API directly (create version → populate files
    → upload missing gzipped files by sha256 → finalize → create release).
13. **Post-deploy smoke check** — see §3.

---

## 2. Authentication (WIF, no stored keys)

The `deploy` job authenticates to GCP using **Workload Identity Federation**
— GitHub's OIDC token is exchanged for short-lived GCP credentials via the
`google-github-actions/auth@v2` action, scoped to `secrets.WIF_PROVIDER` and
`secrets.WIF_SA`. This requires `permissions: id-token: write` on the job
(present in the workflow). No service-account JSON key is stored in GitHub
Secrets or anywhere else (ADL-030).

The full one-time setup (Workload Identity Pool, OIDC provider, the
`github-deployer` service account and its IAM roles, and the WIF→SA binding
scoped to this repo) plus the complete GitHub Secrets table are documented
in **`docs/gcp-cheatsheet.md`**, section "CI/CD — Workload Identity
Federation 設定 (MF-1)". Do not re-derive those commands here — refer to
that doc directly so the two don't drift. Notably:

- The WIF provider's `attribute-condition` is scoped to
  `assertion.repository=='<org>/<repo>' && assertion.ref=='refs/heads/main'`,
  so `workflow_dispatch` runs from any branch other than `main` cannot
  obtain GCP credentials even though the workflow trigger technically allows
  `workflow_dispatch` from any ref.
- The GitHub `production` Environment is restricted (via deployment branch
  policy) to `main` only, since the current GitHub plan doesn't support
  Required reviewers.
- `firebase-tools` cannot use WIF external-account credentials — that's why
  Firebase Hosting deploys go through `deploy_firebase_hosting.py` +
  `gcloud auth print-access-token` instead of the `firebase` CLI/action.

If a deploy run fails at the "Authenticate to GCP (WIF)" step, see §5
(Troubleshooting) below.

---

## 3. Post-deploy smoke behavior

**What's checked today:** the last step of `deploy`, "Post-deploy smoke
check," curls `${FASTAPI_URL}/health` and expects HTTP `200`:

```bash
HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" "${FASTAPI_URL}/health")
if [ "$HTTP_CODE" != "200" ]; then
  echo "::error::Smoke check failed: /health returned ${HTTP_CODE}. Rolling back fastapi-service..."
  gcloud run services update-traffic fastapi-service \
    --region="${REGION}" \
    --to-revisions="${PREV_FASTAPI_REV}=100"
  exit 1
fi
```

**On failure:** the job rolls `fastapi-service` traffic back to
`PREV_FASTAPI_REV` (captured in step 8 of §1, before the new revision was
deployed) at 100%, then `exit 1`s so the GitHub Actions run is marked
failed. Note this rollback only targets `fastapi-service` — it does not roll
back `adk-agent-service` traffic, Firestore index changes, or the Firebase
Hosting release, since none of those have automated rollback wired up.

**Known gap (MF-5, still 🟡 In progress):** `req-phase01.md` §19.4 requires
the post-deploy smoke to include an **authenticated coordination run that
reaches `COMPLETED`** (a deployed equivalent of
`scripts/m5_coordination_smoke.py`), not just an unauthenticated `/health`
check. That is **not implemented yet** — CI currently has no path to obtain
a Firebase ID token for an authenticated request, so a deploy can pass the
current smoke step (`/health` returns 200) while the actual coordination
flow (search → propose → select → generate → `COMPLETED`) is broken. Don't
assume a green `Deploy to Production` run means the full user-facing flow
works — treat it as "the service booted," not "the product works
end-to-end." Closing this gap is tracked separately as MF-5 in
`docs/feature-matrix-phase01.md`; it is out of scope for this runbook.

---

## 4. Manual rollback

Use this when either (a) the automated rollback in §3 didn't run — e.g. the
job failed before reaching the smoke step, or the smoke check itself passed
but a problem was found later — or (b) a bad revision is already serving
traffic and you need to revert by hand.

### Step 1 — find the revision to roll back to

```bash
gcloud run revisions list \
  --service=fastapi-service --region=asia-northeast1 \
  --format='table(metadata.name,metadata.creationTimestamp,status.conditions[0].status)'
```

The workflow's own rollback logic (§1 step 8 / §3) picks the revision at
the top of this list **sorted by `~metadata.creationTimestamp`** — i.e. the
most recently created revision *before* the one just deployed. Use the same
logic by eye: pick the most recent revision that predates the bad deploy.

### Step 2 — shift traffic back

This is the exact command the workflow itself runs on smoke failure (from
`.github/workflows/ci-cd.yml`, and mirrored in `docs/gcp-cheatsheet.md`'s
Cloud Run section):

```bash
gcloud run services update-traffic fastapi-service \
  --region=asia-northeast1 \
  --to-revisions=<REVISION_NAME>=100
```

Replace `<REVISION_NAME>` with the revision identified in Step 1 (e.g.
`fastapi-service-00042-xyz`).

### Notes

- This only covers `fastapi-service`. If `adk-agent-service` also needs a
  rollback, the same two steps apply with `--service=adk-agent-service` /
  `gcloud run services update-traffic adk-agent-service`.
- There is no automated or scripted rollback for Firestore composite
  indexes or the Firebase Hosting release — `deploy_firestore_indexes.sh`
  only adds indexes (it never deletes one), and Firebase Hosting rollback
  would need a separate manual release-revert via the Firebase Hosting API
  or console (not scripted anywhere in this repo today).
- After rolling back, re-run the pipeline (`workflow_dispatch` or a new
  push to `main`) once the underlying issue is fixed, rather than leaving
  production pinned to an old revision indefinitely.

---

## 5. Troubleshooting

Start by identifying **which job** failed in the GitHub Actions run — the
job graph (§1) tells you what's already known-good by the time a later job
runs.

| Failing job | Likely causes |
|---|---|
| `test-fastapi` | A real test regression, or a missing/changed dependency in `fastapi-service/requirements.txt`. Check the Cloud Tasks worker-thread regression step (`tests/adapters/test_cloud_tasks_adapter.py`) separately — it's run in isolation because it's a known source of flakiness with threading. |
| `test-adk` | A real test regression, or an `adk-agent-service/requirements.txt` change (e.g. an ADK/`google-adk` version bump). |
| `test-flutter` | `flutter analyze` failing usually means a lint/type issue; `flutter test` failures are widget/unit-test regressions. Confirm the pinned `flutter-version: '3.44.1'` in the workflow still matches what's used locally. |
| `test-deploy-scripts` | Only exercises `deploy_firebase_hosting.py` via `scripts/deploy/tests/test_deploy_firebase_hosting.py` — a failure here means a regression in that script's logic (file hashing, populateFiles diffing, etc.), not an infra problem. |
| `deploy` — "Authenticate to GCP (WIF)" | Most common causes: `WIF_PROVIDER` / `WIF_SA` secrets missing or stale (e.g. after recreating the pool/provider), the WIF provider's `attribute-condition` no longer matching (e.g. run triggered from a branch other than `main`), or the `production` Environment's branch policy blocking the run. Cross-check against the WIF setup in `docs/gcp-cheatsheet.md`. |
| `deploy` — "Deploy Firestore composite indexes" | `deploy_firestore_indexes.sh` failing usually means malformed `firestore.indexes.json`, or the `github-deployer` SA lacking Firestore index permissions. See the Firestore pitfall note in `docs/gcp-cheatsheet.md` ("落とし穴 (2026-07-04 の障害)") about composite indexes and `.where()`/`.order_by()` combinations — if a new query shape was added without a matching index declaration, `fastapi-service/tests/adapters/test_firestore_composite_indexes.py` should have caught it in `test-fastapi` first. |
| `deploy` — image build/push steps | Dockerfile syntax errors, a broken dependency install inside the image, or an Artifact Registry auth/permission problem (`github-deployer` needs `roles/artifactregistry.writer`, granted per `docs/gcp-cheatsheet.md`'s WIF setup). |
| `deploy` — "Deploy adk-agent-service" / "Deploy fastapi-service" | A missing GitHub secret (`ES_INTERNAL_IP`, `ES_SSL_FINGERPRINT`, `R2_*`) will fail the scripts' `: "${VAR:?...}"` guards with a clear "X is required" message — check the step's log for which flag was empty. Also check whether the ES VM is running (`docs/gcp-cheatsheet.md`'s Elasticsearch VM section) — the deploy itself will succeed even if the VM is down, but the revision will fail its own health checks against ES if the app needs a live connection at startup. |
| `deploy` — "Deploy to Firebase Hosting" | `deploy_firebase_hosting.py` failures are usually an expired/invalid `gcloud auth print-access-token` (WIF token exchange issue — same root cause as the auth step) or a Firebase Hosting REST API error surfaced via `HTTPError` (the script prints the response body to stderr — read it directly). |
| `deploy` — "Post-deploy smoke check" | `/health` returning non-200 (or timing out) triggers the automated rollback described in §3. Check `fastapi-service` logs (`docs/gcp-cheatsheet.md`'s Cloud Run logging one-liner) for the actual startup/runtime error on the new revision. |

**General first move for any `deploy` job failure:** check whether the job
even reached the WIF auth step — if it failed before that, it's a pure CI
config/test issue unrelated to GCP. If it failed after, cross-reference the
specific `gcloud`/script command in the failing step against
`docs/gcp-cheatsheet.md` to reproduce it locally with the same flags (minus
secrets, which you'd need to fetch from Secret Manager per that doc's
"Secret Manager" section).

---

## 6. See also

- [`docs/gcp-cheatsheet.md`](../gcp-cheatsheet.md) — raw `gcloud` commands:
  WIF one-time setup, GitHub Secrets table, Cloud Run inspection/rollback,
  Artifact Registry, Firestore indexes, Elasticsearch VM operations, and
  general troubleshooting one-liners.
- [`docs/feature-matrix-phase01.md`](../feature-matrix-phase01.md) — "MF —
  CI/CD (Continuous Delivery)" section for the current implementation
  status of MF-1…MF-6, including the still-open MF-5 gap referenced in §3.
- [`docs/req-phase01.md`](../req-phase01.md) §19 — the requirement text
  (19.1–19.5) this pipeline implements.
- `.github/workflows/ci-cd.yml` — the workflow itself (source of truth for
  exact steps; this runbook describes it as of the MF-6 close-out, but the
  workflow file always wins if they disagree).
- `scripts/deploy/` — `deploy_adk.sh`, `deploy_fastapi.sh`,
  `deploy_firestore_indexes.sh`, `deploy_firebase_hosting.py`, and
  `teardown.sh` (manual teardown of the throwaway environment; not called
  by CI).
