# Security hardening follow-up

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows `PLANS.md` at `/Users/ran/my-app/PLANS.md`.


## Purpose / Big Picture

This plan captures the security hardening work that followed the repository and cloud security review. The goal is to reduce accidental exposure without changing user-facing product behavior: user-created closets remain private to their owners, shared demo closets remain available to authenticated users, local development services do not listen on public interfaces, deployment credentials are constrained to the intended branch, and Elasticsearch HTTPS uses certificate pinning rather than disabling TLS verification.

The observable result is that the repository no longer contains the literal Firebase browser API key in operational docs, Docker Compose binds development ports to localhost, production deploy scripts carry an Elasticsearch certificate fingerprint, Cloud Run services can be deployed with restricted CORS and ES certificate verification, the Firebase browser key is referrer-restricted, GitHub WIF is constrained to `refs/heads/main`, and the ES VM firewall isolates TCP 9200 to the intended Cloud Run private egress range.


## Progress

- [x] (2026-06-30 15:18Z) Removed the literal Firebase Web API key from `docs/gcp-cheatsheet.md`; it now references `$FIREBASE_API_KEY`.
- [x] (2026-06-30 15:18Z) Changed `docker-compose.yml` host port mappings for Elasticsearch, Firestore emulator, Firebase Auth emulator, MinIO, FastAPI, and ADK to bind to `127.0.0.1`.
- [x] (2026-06-30 15:18Z) Added FastAPI `CORS_ALLOW_ORIGINS` config and wired `fastapi-service/app/main.py` to use it instead of `allow_origins=["*"]`.
- [x] (2026-06-30 15:18Z) Replaced the three `verify_certs=False` Elasticsearch client constructions with support for `ELASTICSEARCH_CA_CERTS` and `ELASTICSEARCH_SSL_ASSERT_FINGERPRINT`.
- [x] (2026-06-30 15:18Z) Updated `scripts/deploy/deploy_fastapi.sh`, `scripts/deploy/deploy_adk.sh`, and `.github/workflows/ci-cd.yml` to pass `ES_SSL_FINGERPRINT`; FastAPI deploy also passes restricted production CORS origins.
- [x] (2026-06-30 15:18Z) Restricted the live Firebase browser key to `https://gen-fashion-app.web.app/*`, `https://animation-agent.web.app/*`, and `http://localhost:8088/*`.
- [x] (2026-06-30 15:19Z) Restricted the live GitHub Workload Identity Federation provider condition to `assertion.repository=='RanArino/gen-fashion' && assertion.ref=='refs/heads/main'`.
- [x] (2026-06-30 15:19Z) Added a GitHub production environment branch policy for `main`.
- [x] (2026-06-30 15:20Z) Hardened the live ES VM firewall path: added the `gen-fashion-es` network tag to the VM, changed `allow-es-from-cloudrun` to priority 800 with target tag `gen-fashion-es` and logging, and created `deny-es-other-internal` at priority 900 for TCP 9200 from `10.128.0.0/9` to the ES tag.
- [x] (2026-06-30 15:20Z) Created `allow-iap-ssh` for IAP SSH from `35.235.240.0/20` to the ES tag and fetched the ES certificate fingerprint over IAP SSH.
- [x] (2026-06-30 15:21Z) Stored the ES fingerprint in GitHub Actions secret `ES_SSL_FINGERPRINT` and Google Secret Manager secret `ELASTICSEARCH_SSL_FINGERPRINT`.
- [x] (2026-06-30 15:27Z) Updated `docs/gcp-cheatsheet.md` with the new GCP operations used in this hardening pass: API key referrer restriction, WIF branch condition update, ES firewall deny/allow pattern, IAP SSH rule, and ES fingerprint retrieval.
- [x] (2026-06-30 15:27Z) Updated `docs/architecture-overview.md` with the current firewall, CORS, WIF, API key, and ES certificate-pinning posture; no diagram changes were needed because no components or edges changed.
- [x] (2026-06-30 15:29Z) Built and pushed Cloud Run images `security-20260701-002707` for both FastAPI and ADK.
- [x] (2026-06-30 15:31Z) Deployed ADK revision `adk-agent-service-00010-dwc`; FastAPI deploy initially failed because comma-separated CORS origins broke `gcloud --set-env-vars` parsing.
- [x] (2026-06-30 15:32Z) Fixed `scripts/deploy/deploy_fastapi.sh` to use a custom `|` delimiter for `--set-env-vars`, then deployed FastAPI revision `fastapi-service-00013-sjr`.
- [x] (2026-06-30 15:32Z) Live verification found `ServerFingerprintMismatch`: Elasticsearch Python compares the served leaf certificate fingerprint, not `/etc/elasticsearch/certs/http_ca.crt`.
- [x] (2026-06-30 15:33Z) Fetched the served ES leaf certificate SHA-256 fingerprint, added it as a new GitHub Actions secret value and Secret Manager version, and redeployed ADK `adk-agent-service-00011-qbp` and FastAPI `fastapi-service-00014-rmb`.
- [x] (2026-06-30 15:34Z) Ran service tests under Python 3.12 with separate service virtualenvs: FastAPI targeted tests `8 passed, 1 skipped`; ADK targeted tests `13 passed`.
- [x] (2026-06-30 15:35Z) Verified live Cloud Run revisions after redeploy: FastAPI health returns `{"status":"ok"}`, unauthenticated ADK `/health` returns 403, allowed CORS origin is echoed, disallowed origin is not echoed, both services carry `ELASTICSEARCH_SSL_ASSERT_FINGERPRINT`, and FastAPI logs show `[startup] Elasticsearch index ready.`.
- [x] (2026-06-30 15:36Z) Final repository checks passed: deploy scripts parse with `bash -n`, `git diff --check` is clean, and the forbidden-pattern grep finds no `verify_certs=False`, wildcard production CORS, or literal Firebase Web API key in active code/config/docs.


## Surprises & Discoveries

- Observation: GitHub environment required-reviewer protection could not be enabled.
  Evidence: `gh api -X PUT repos/RanArino/gen-fashion/environments/production` returned HTTP 422: "Please ensure the billing plan supports the required reviewers protection rule." The fallback applied in this plan is an environment branch policy for `main` plus WIF restriction to `refs/heads/main`.

- Observation: The local global Python is 3.14 and cannot install the FastAPI dependency set.
  Evidence: creating `.tmp/fastapi-venv` and installing `fastapi-service/requirements.txt` failed while building `pydantic-core v2.14.1` because the package is not compatible with Python 3.14's `ForwardRef._evaluate` signature. Earlier direct test attempts also failed because global `python3` did not have `pytest`.

- Observation: FastAPI and ADK dependencies cannot be installed into one shared virtualenv.
  Evidence: pip reported a dependency resolution conflict between `google-genai==0.3.0` and `google-genai>=1.0.0`. Verification must use separate environments or the existing service containers.

- Observation: The ES VM did not allow IAP SSH before this hardening pass.
  Evidence: `gcloud compute ssh gen-fashion-es --tunnel-through-iap` failed with "failed to connect to backend" on port 22. Creating `allow-iap-ssh` for the `gen-fashion-es` tag allowed fingerprint retrieval.

- Observation: Elasticsearch Python `ssl_assert_fingerprint` validates the served leaf certificate fingerprint, not the Elasticsearch CA file fingerprint.
  Evidence: FastAPI revision `fastapi-service-00013-sjr` logged `ServerFingerprintMismatch`, with configured bytes matching the CA fingerprint and received bytes matching the leaf certificate. After updating `ES_SSL_FINGERPRINT` / `ELASTICSEARCH_SSL_FINGERPRINT` to `FA:8E:...:0C:C3` and redeploying `fastapi-service-00014-rmb`, startup logs reported `[startup] Elasticsearch index ready.`


## Decision Log

- Decision: Use Elasticsearch `ssl_assert_fingerprint` support instead of continuing with `verify_certs=False`.
  Rationale: The ES service uses a self-signed certificate on a private IP. Fingerprint pinning is the smallest change that preserves HTTPS identity checking without needing to distribute a CA file into Cloud Run containers.
  Date/Author: 2026-06-30 / Codex

- Decision: Keep local development on HTTP and do not require ES TLS settings locally.
  Rationale: Docker Compose runs Elasticsearch with `xpack.security.enabled=false` and `ELASTICSEARCH_URL=http://elasticsearch:9200`. The new TLS settings are optional and only apply when set.
  Date/Author: 2026-06-30 / Codex

- Decision: Use branch restrictions where reviewer-based environment protection is unavailable.
  Rationale: GitHub rejected required reviewers for the current plan. Restricting WIF to `refs/heads/main` and adding a production environment branch policy still materially narrows deploy authority.
  Date/Author: 2026-06-30 / Codex

- Decision: Add an explicit deny for ES TCP 9200 to the tagged ES VM after the Cloud Run allow rule.
  Rationale: The default VPC has `default-allow-internal`, which would otherwise permit internal TCP traffic broadly. A priority 800 allow for Cloud Run subnet plus priority 900 deny for broader internal ranges narrows ES access while preserving the intended Cloud Run path.
  Date/Author: 2026-06-30 / Codex


## Outcomes & Retrospective

Work began before this ExecPlan was created, which violated repository policy for multi-step security/deployment changes. The follow-up work is now complete: repository hardening changes are in place, documentation is synchronized, live Firebase/GitHub/GCP controls are tightened, Cloud Run is redeployed with restricted CORS and ES certificate pinning, and live FastAPI startup confirms Elasticsearch connectivity with the pinned fingerprint.


## Context and Orientation

The repository is `gen-fashion`, a Flutter Web, FastAPI, ADK agent, Firebase, Cloud Run, and Compute Engine Elasticsearch application. User closet data lives under Firestore `users/{uid}/closet/{itemId}` and is protected by `firestore.rules`. Shared demo closet data is intentionally available to authenticated users through `/shared-closets`.

The security review found four practical hardening areas:

- `docs/gcp-cheatsheet.md` contained a literal Firebase Web API key in a build command.
- `docker-compose.yml` published local development ports on all host interfaces.
- FastAPI used wildcard CORS in `fastapi-service/app/main.py`.
- Three Elasticsearch clients disabled certificate verification in `fastapi-service/app/adapters/elasticsearch_embedding_repo.py`, `fastapi-service/app/adapters/shared_closet_search.py`, and `adk-agent-service/styling_app/adapters/elasticsearch.py`.

Production deployment is controlled by `.github/workflows/ci-cd.yml`, helper scripts in `scripts/deploy/`, GitHub Actions Workload Identity Federation, Cloud Run services `fastapi-service` and `adk-agent-service`, and the Compute Engine VM `gen-fashion-es` at internal IP `10.146.0.2`.


## Plan of Work

First, preserve the intent of the already-started code changes: keep them small and directly tied to the security review. Do not add new architecture or new services. The code surface is limited to configuration, deploy scripts, and client initialization.

Second, synchronize operational documentation. `docs/gcp-cheatsheet.md` must be updated because new project-specific `gcloud` operations were used: API key restrictions, WIF condition updates, firewall hardening, IAP SSH allow, and fingerprint retrieval. `docs/architecture-overview.md` must be checked because live firewall and deployment posture changed.

Third, verify in supported environments. The service dependencies are not compatible with the global Python 3.14 environment, so use Python 3.11 if available, existing containers, or CI. Run targeted FastAPI adapter tests and ADK tool tests, plus shell syntax checks and `git diff --check`.

Fourth, redeploy only after the plan and documentation are current and the user agrees to update live Cloud Run revisions. The repo and live secrets are ready for redeploy, but the currently running Cloud Run revisions do not automatically pick up repository code changes.


## Concrete Steps

From `/Users/ran/my-app/gen-fashion`, inspect the current diff:

    git diff --stat
    git diff --check

Update docs:

    $EDITOR docs/gcp-cheatsheet.md
    $EDITOR docs/architecture-overview.md

Run syntax checks:

    bash -n scripts/deploy/deploy_fastapi.sh
    bash -n scripts/deploy/deploy_adk.sh

Run Python tests using a supported Python version, preferably Python 3.11:

    python3.11 -m venv .tmp/fastapi-venv
    . .tmp/fastapi-venv/bin/activate
    pip install -r fastapi-service/requirements.txt pytest
    cd fastapi-service
    ../.tmp/fastapi-venv/bin/python -m pytest tests/adapters/test_elasticsearch_embedding_repo.py tests/adapters/test_shared_closet_search.py -q

    python3.11 -m venv .tmp/adk-venv
    . .tmp/adk-venv/bin/activate
    pip install -r adk-agent-service/requirements.txt pytest
    cd adk-agent-service
    ../.tmp/adk-venv/bin/python -m pytest styling_app/tests/test_tools.py -q

If redeploying after future changes, run the existing CI/CD workflow from `main` or run the deploy scripts with the existing `ES_SSL_FINGERPRINT` secret value. Confirm that the deployed services carry `ELASTICSEARCH_SSL_ASSERT_FINGERPRINT` and `CORS_ALLOW_ORIGINS`.


## Validation and Acceptance

Acceptance for repository changes:

- `rg -n "verify_certs=False|allow_origins=\\[\"\\*\"\\]|AIzaSyDWx1gLxd" fastapi-service adk-agent-service scripts docker-compose.yml .github/workflows/ci-cd.yml docs/gcp-cheatsheet.md` returns no matching production code or literal Firebase key.
- `git diff --check` returns no whitespace errors.
- `bash -n scripts/deploy/deploy_fastapi.sh && bash -n scripts/deploy/deploy_adk.sh` exits 0.
- Targeted FastAPI and ADK tests pass in Python 3.11 or in service containers.

Acceptance for live cloud changes:

- `gcloud services api-keys get-key-string` is not needed; `gcloud services api-keys list` or `gcloud services api-keys describe` shows browser referrer restrictions for the Firebase browser key.
- `gcloud iam workload-identity-pools providers describe github-provider ...` shows the condition includes `assertion.ref=='refs/heads/main'`.
- `gh api repos/RanArino/gen-fashion/environments/production` shows a branch policy and `main` is present in deployment branch policies.
- `gcloud compute firewall-rules describe allow-es-from-cloudrun` shows priority 800, target tag `gen-fashion-es`, source range `10.146.0.0/20`, and TCP 9200.
- `gcloud compute firewall-rules describe deny-es-other-internal` shows priority 900, target tag `gen-fashion-es`, source range `10.128.0.0/9`, and deny TCP 9200.
- After redeploy, Cloud Run service descriptions show `ELASTICSEARCH_SSL_ASSERT_FINGERPRINT` and restricted `CORS_ALLOW_ORIGINS`.


## Idempotence and Recovery

The repository patches are idempotent as normal git changes. If any edited file needs adjustment, patch forward; do not reset unrelated user changes.

Firebase API key referrer restrictions can be updated repeatedly with `gcloud services api-keys update`. If a legitimate app origin is blocked, add that origin explicitly rather than removing restrictions.

The WIF provider condition can be updated repeatedly. If emergency deploys from another ref are required, temporarily add that exact ref to the condition and record the exception in this plan.

The ES firewall rules are safe to describe and update repeatedly. If Cloud Run cannot reach ES, confirm the Cloud Run Direct VPC egress subnet range and the VM tag before loosening firewall rules. Recovery should prefer fixing source ranges or tags over deleting the deny rule.

The ES fingerprint secret can receive new versions. If the ES certificate is rotated, fetch the served leaf certificate SHA-256 fingerprint over IAP SSH and add a new GitHub/GCP secret version, then redeploy Cloud Run.


## Artifacts and Notes

Live ES CA fingerprint first retrieved on 2026-06-30; this is not the value used by `ssl_assert_fingerprint`:

    sha256 Fingerprint=37:43:6B:8C:5A:CB:19:11:40:9E:78:EC:C7:F6:5F:68:5A:40:0D:45:87:2B:0B:36:DA:1C:59:68:C0:1C:93:2B

Live ES served leaf certificate fingerprint retrieved on 2026-06-30 and used by Cloud Run:

    sha256 Fingerprint=FA:8E:2B:9C:93:C0:32:0E:F3:AB:91:2A:E0:BF:28:E8:2F:8C:87:E2:43:96:0F:76:00:E3:10:E0:1C:50:0C:C3

Verification already completed:

    bash -n scripts/deploy/deploy_fastapi.sh && bash -n scripts/deploy/deploy_adk.sh
    git diff --check

Both commands exited 0.

ADK targeted test completed in a temporary ADK Python 3.12 virtualenv:

    13 passed in 6.08s

FastAPI targeted test completed in a temporary FastAPI Python 3.12 virtualenv:

    8 passed, 1 skipped, 2 warnings in 8.59s

Live Cloud Run verification after corrected fingerprint redeploy:

    fastapi-service revision: fastapi-service-00014-rmb
    adk-agent-service revision: adk-agent-service-00011-qbp
    fastapi /health: {"status":"ok"}
    adk unauthenticated /health: 403
    fastapi startup log: [startup] Elasticsearch index ready.


## Interfaces and Dependencies

FastAPI settings in `fastapi-service/app/config.py` now expose `ELASTICSEARCH_CA_CERTS`, `ELASTICSEARCH_SSL_ASSERT_FINGERPRINT`, and `CORS_ALLOW_ORIGINS`. `fastapi-service/app/main.py` consumes `CORS_ALLOW_ORIGINS`.

ADK settings in `adk-agent-service/styling_app/config.py` now expose `ELASTICSEARCH_CA_CERTS` and `ELASTICSEARCH_SSL_ASSERT_FINGERPRINT`.

Elasticsearch Python clients consume `ssl_assert_fingerprint` and `ca_certs` through the official `elasticsearch` client constructor.

Deployment scripts in `scripts/deploy/` pass the ES fingerprint and FastAPI CORS origins to Cloud Run. `.github/workflows/ci-cd.yml` expects a GitHub Actions secret named `ES_SSL_FINGERPRINT`.

Live cloud dependencies are Google API Keys, GitHub Actions WIF, Cloud Run, Secret Manager, Compute Engine firewall rules, and IAP SSH.
