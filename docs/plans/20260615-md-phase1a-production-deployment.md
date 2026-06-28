# Phase 1a Production Deployment & Hardening (MD)


This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.


This plan follows `PLANS.md` at `/Users/ran/my-app/PLANS.md`.


## Purpose / Big Picture


Phase 1a (milestones M0–M5) is **code-complete and verified locally**: a logged-in user can upload closet images, start a coordination session, watch the Accordion thinking-trace stream over SSE, and receive a generated coordinate image — all against `make dev` (Docker Compose with MinIO, a local Elasticsearch, the Firestore/Firebase-Auth emulators, and both Python services run as containers). What does **not** exist yet is a running deployment: nothing in this repository has ever been pushed to Google Cloud. There is no Artifact Registry image, no Cloud Run service, no Compute Engine Elasticsearch node, no Secret Manager entry, no production Firebase project wiring, and no public URL a judge can open.


After this milestone, a teammate (or a hackathon judge) can open one public URL in a browser, sign in with Google, pick the `SHARED_CLOSET` source, and complete the full coordination flow end-to-end against **deployed** infrastructure — with a **real Nano Banana generated image** (not the local collage fallback), shared-closet candidates returned from a **Compute Engine-hosted Elasticsearch over a private VPC path**, and every secret stored in **Secret Manager** rather than an `.env` file. This is the work the requirements repeatedly defer to "the deployment phase (~1–2 週間 before submission)": feature-matrix `M1-3` (ES on Compute Engine + Cloud Run private connectivity), the `M3-2` full **vector** seed, the `M2-5` production security gate (OIDC + Secret Manager), and the `M4-7`/`M5-6` Nano Banana caveat (only the collage fallback was ever exercised locally because the free-tier key has no image-gen quota).


You can see it working when `curl https://<fastapi-url>/health` returns `200`, the deployed Flutter Web app drives a `SHARED_CLOSET` session to `status: COMPLETED`, and the resulting `styleResult.coordinateImageUrl` opens a generated image hosted in production Cloudflare R2.


This milestone is **Phase 1a** deployment. It is independent of and must not pull in **M6 (LINE / LIFF / Rakuten, Phase 1b)** — per `req-phase01.md` §14, LINE work does not start here.


## Progress


- [x] (2026-06-15) Authored this ExecPlan; selected the deployment requirements (MD-1…MD-14); set them to 🟡 In progress in `docs/feature-matrix-phase01.md`; recorded the new deployment ADLs in `docs/req-phase01.md`; synced `docs/architecture-overview.md`.
- [x] (2026-06-21) Pre-deploy **local re-verification** (`docs/plans/20260621-md-phase1a-local-verification-checklist.md`): ran the local gate end-to-end and found three real bugs the prior "verified locally" claims had masked. Fixed: (a) **MD-8 base-URL split — local portion landed early** (`fastapi_internal_base_url` + `FASTAPI_INTERNAL_BASE_URL`), because the conflation broke `make dev` (upload→READY 404), not just the cloud; (b) Firestore client bound to the Vertex project instead of the Firebase project (`firestore_project_id` added); (c) `closetId` dynamic-`text` mapping broke SHARED_CLOSET search (keyword mapping added). After fixes the local M5 browser E2E reached `COMPLETED` with a **real Nano Banana image** (`gemini-2.5-flash-image`) — confirming the MD-11 model works at least in `us-central1` for project `animation-agent`. **MD-8 remaining (cloud): OIDC tokens on both hops + worker-route OIDC verification + Cloud Tasks audience.**
- [x] (2026-06-21) Resolved the two non-blocking follow-ups from the local re-verification. **MD-10 de-risked:** embedding model corrected to `gemini-embedding-001` (768-dim `embed_content`) and the index side switched from image to **analyzed-text** embeddings so it shares the text-query space; local `--with-embeddings` seeded 90×768-dim vectors and a kNN probe returned semantically relevant hits (the seed's Vertex vs Firestore project was also split, mirroring the app fix; no-op in prod). **Agent timeout/UX:** `adk_run_timeout_seconds` made configurable (45→90) and fastapi `STREAM_MAX_SECONDS` raised (120→150) so the SSE stream always outlasts the ADK timeout + deterministic fallback — the coordination smoke then completed via the **primary** LLM path. Only MD-10's prod execution (seed against GCE ES inside the VPC) remains.
- [x] (2026-06-27) Pre-production deployment readiness audit completed and this plan was resolved before any cloud deployment. Added an explicit **Milestone 0 — deploy readiness patch** for the remaining code/docs/scripts blockers: Cloud Tasks must target `FASTAPI_INTERNAL_BASE_URL`, both internal hops must use OIDC, the worker route must verify the OIDC bearer, Cloud Run containers must honor `$PORT`, `.env.example` must expose production-only deploy knobs, and `scripts/deploy/` helpers must exist before manual deployment or later MF CI/CD automation. Also resolved the ES bootstrap egress gap by allowing a temporary external IP only during VM install/seed and requiring it to be removed before acceptance; no architecture-overview update is needed because this is bootstrap procedure, not a steady-state component.
- [x] (2026-06-27) Milestone 0 — Deploy readiness patch: code/config/script fixes before provisioning (`CloudTasksAdapter`, `HttpAgentRunAdapter`, `require_internal_secret`, Dockerfiles, `.env.example`, deploy helper scripts). Verified: FastAPI 67 passed / ADK 41 passed; both images respond on injected `PORT` (18000 / 13000); `teardown.sh --dry-run` lists exactly the plan resources.
- [x] (2026-06-27) Milestone A — GCP foundation complete (project `animation-agent`, region `asia-northeast1`). Enabled 11 core APIs + Firebase Management/Hosting/Identity Toolkit; created `fastapi-sa`/`adk-sa`/`tasks-invoker-sa` with least-privilege IAM (incl. `fastapi-sa`→`tasks-invoker-sa` `serviceAccountUser` for Cloud Tasks OIDC); created Firestore (Native, `asia-northeast1`) and deployed `firestore.rules` + `firestore.indexes.json`; added Firebase to the project (via console — CLI `addfirebase` 403'd until Firebase ToS accepted), enabled Google sign-in, registered Web app `gen-fashion-web` (config saved to gitignored `credentials/firebase-sdk.md` for MD-12 `--dart-define`); created Cloudflare R2 bucket `gen-fashion-images` + CORS for the `animation-agent.web.app` origin; stored `INTERNAL_TASK_SECRET`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` in Secret Manager (both `fastapi-sa`/`adk-sa` hold `secretmanager.secretAccessor`). MD-1 ✅, MD-9 ✅; MD-2 stays 🟡 (`ELASTICSEARCH_API_KEY` minted in Milestone B; `--set-env-vars` config applied at Cloud Run deploy in Milestone C). **`ELASTICSEARCH_API_KEY` not yet created — deferred to Milestone B per plan step 9.**
- [x] (2026-06-28) Milestone B — Data plane complete (MD-3 ✅, MD-10 ✅; MD-4 infrastructure ready, verification deferred to Milestone C): `gen-fashion-es` (`e2-medium`, `pd-balanced 30GB`, `asia-northeast1-a`); static internal IP `gen-fashion-es-ip`; ES 8.19 installed + two config conflicts resolved (duplicate `xpack.security.enabled`, `cluster.initial_master_nodes` vs `discovery.type: single-node`); cluster health `green`; `ELASTICSEARCH_API_KEY` in Secret Manager (`fastapi-sa`/`adk-sa` granted `secretmanager.secretAccessor`); firewall `allow-es-from-cloudrun` (subnet CIDR → tcp:9200); night-stop schedule `es-night-off` (JST 02:00–08:00); full vector seed `--with-embeddings` completed (`created=209, skipped=1, errors=0`, 210 total, 768-dim embeddings); `_count=210` verified; external IP removed (step 12.1 ✅). Discovered: VM seed `.env` had `FIRESTORE_EMULATOR_HOST=localhost:8080` — commented out before seed.
- [ ] Milestone C — Services: Artifact Registry images, Cloud Run `fastapi-service` + `adk-agent-service`, Cloud Tasks queue, OIDC hardening + internal-base-url split (MD-5, MD-6, MD-7, MD-8).
- [ ] Milestone D — Generation + frontend: production Nano Banana image generation on Vertex AI, Flutter Web build + Firebase Hosting (MD-11, MD-12).
- [ ] Milestone E — Acceptance + ops: production E2E smoke, Cloud Logging verification, documented teardown (MD-13, MD-14).


## Surprises & Discoveries


- Observation: `adk_internal_base_url` (env `ADK_INTERNAL_BASE_URL`) is **conflated across two different targets**. `fastapi-service/app/adapters/adk_agent_run.py` correctly uses it for the ADK service (`POST /internal/run-session`), but `fastapi-service/app/adapters/cloud_tasks_adapter.py` and `local_task_queue.py` reuse the **same** value to build the worker URL `…/internal/tasks/process-upload`, whose route is actually registered in **fastapi-service** (`app/main.py:22` includes `internal_routes`; `app/handlers/internal_routes.py` defines `/internal/tasks/process-upload`). In `docker-compose.yml` `fastapi-service` sets `ADK_INTERNAL_BASE_URL=http://adk-agent-service:3000`, so the embedding-worker task is posted to the ADK service (`:3000`), which only serves `/health` and `/internal/run-session` (`adk-agent-service/styling_app/server.py:34,47`). In the cloud these become two separate Cloud Run services, so the worker task **will 404 / misroute** unless the producer points at the fastapi URL. MD-8 fixes this by introducing a distinct `FASTAPI_INTERNAL_BASE_URL` for the worker target and leaving `ADK_INTERNAL_BASE_URL` for run-session.
  Evidence: `rg -n "adk_internal_base_url" fastapi-service/app` → used in `cloud_tasks_adapter.py:28`, `adk_agent_run.py:11`, `local_task_queue.py:25`; route only in `fastapi-service/app/handlers/internal_routes.py`.
- Observation: The pre-existing `# TODO(deploy)` in `cloud_tasks_adapter.py:39` proposes an OIDC `audience` of `self._settings.adk_internal_base_url`, but the embedding worker lives in **fastapi-service**, so the OIDC audience for the `process-upload` task must be the **fastapi worker URL**, not the ADK URL.
  Evidence: `fastapi-service/app/adapters/cloud_tasks_adapter.py:39-46`.
- Observation: The `M2-5` feature-matrix note prescribes "Cloud Run `fastapi-service` ingress is set to `internal`". That cannot hold as written: `fastapi-service` also serves the public `/closet/*` and `/sessions/*` routes that the browser calls directly. Production protection of the worker route therefore relies on OIDC verification + the shared secret (defense in depth), not service-level internal ingress. Recorded as ADL-024.
  Evidence: `fastapi-service/app/main.py:20-23` registers public and internal routers on one app.
- Observation: Both service Dockerfiles currently hard-code uvicorn ports (`fastapi-service`: `8000`; `adk-agent-service`: `3000`). Cloud Run injects a runtime `PORT` value and routes traffic to the configured container port; using `$PORT` in the image entrypoint is the least-coupled path and avoids silently deploying a revision that never becomes ready because the service expects a different port.
  Evidence: `fastapi-service/Dockerfile:10` and `adk-agent-service/Dockerfile:12`; Cloud Run deploy commands in this plan previously had no `--port` override.
- Observation: The planned ES VM is created with no external IP, but the bootstrap instructions immediately require outbound internet access for Elastic packages, Kaggle data, Cloudflare R2, Vertex AI, and Firestore. Without a bootstrap egress path, install and seed are likely to fail before Cloud Run can ever verify private ES access.
  Evidence: step 8 used `--no-address`; steps 9 and 12 require package download and external API/storage access.
- Observation: `scripts/deploy/` is absent, but the plan and later MF CI/CD milestone expect `scripts/deploy/deploy_fastapi.sh`, `scripts/deploy/deploy_adk.sh`, and `scripts/deploy/teardown.sh` to exist and be the command surface for manual deploys and later automation.
  Evidence: `find scripts -maxdepth 3 -type f` shows smoke and seed scripts only; no `scripts/deploy/*`.
- Observation: There is a documented count tension for the shared closet. `req-phase01.md` §15 Phase 1a #7 originally said "2,000件以上"; the M3/ME re-scope (`feature-matrix-phase01.md` M3-2, ADL-010) uses 3 curated closets with 70 items each. The deployment seed therefore produces **210 demo-closet items with 768-dim embeddings**; "full vector seed" means embeddings present + hybrid/kNN search working, not a raw count of 2,000.
  Evidence: `scripts/seed_shared_closet/README.md` documents `adult-01`, `adult-02`, and `child-01` at 70 items each; `scripts/seed_shared_closet/run_seed.py` uses `gemini-embedding-001`.


## Decision Log


- Decision: Cloud Run reaches the Compute Engine Elasticsearch node over **Direct VPC egress** (`--network`/`--subnet` + `--vpc-egress=private-ranges-only`), **not** a Serverless VPC Access connector; the ES VM has **no external IP**, uses a **reserved static internal IP**, and a firewall rule allows `tcp:9200` only from the Cloud Run egress subnet's internal range.
  Rationale: ADL-013 left the choice open ("VPC Peering または Cloud NAT"). Direct VPC egress is the GA successor to the connector and Google's recommended option: it carries the same egress billing rate but has **no idle connector instances** (the connector runs a minimum of e2-micro×2 billed even when idle), so it removes the connector fixed cost while keeping the identical closed-network posture (ES off the public internet, internal-IP only). Best fit for the hackathon's short-lived, low-cost target; torn down with the VM after the hackathon. **Re-scoped 2026-06-27 from a Serverless VPC Access connector for cost; recorded as ADL-023 in `req-phase01.md`** (which also captures `pd-balanced` + stop-when-idle + optional `Asia/Tokyo` night-stop schedule).
  Date/Author: 2026-06-15 / Ran (proposed at deployment ExecPlan authoring); revised 2026-06-27 (connector → Direct VPC egress)
- Decision: The two internal hops use **Cloud Run OIDC identity tokens** in production. `adk-agent-service` is deployed `--no-allow-unauthenticated` and only `fastapi-sa` holds `roles/run.invoker` on it; `fastapi-service` stays public (browser-facing) and protects `/internal/tasks/process-upload` with OIDC verification **plus** the existing `X-Internal-Secret` (Secret Manager value). The shared secret is retained as defense in depth, not removed.
  Rationale: Private service-to-service auth without exposing the ADK service; `fastapi-service` cannot be internal-only because it serves the SPA. Recorded as ADL-024.
  Date/Author: 2026-06-15 / Ran (proposed at deployment ExecPlan authoring)
- Decision: The Flutter Web client is hosted on **Firebase Hosting** (`<project>.web.app`), with real Firebase config injected via `--dart-define` at build time and `USE_EMULATORS=false`.
  Rationale: The app already depends on Firebase Auth + Firestore; Firebase Hosting gives a stable HTTPS origin and an automatic authorized domain, and `flutter-web-app/lib/config.dart` already reads every Firebase value from `--dart-define`. `req-phase01.md` only ever mentioned a Vercel domain inside a CORS example, so the hosting target was undecided. Recorded as ADL-025.
  Date/Author: 2026-06-15 / Ran (proposed at deployment ExecPlan authoring)
- Decision: Infrastructure (Cloud Run, Compute Engine ES, the Direct VPC egress subnet, Cloud Tasks) lives in `asia-northeast1`; Vertex AI (`GOOGLE_CLOUD_LOCATION`) stays at the region where the image model `gemini-2.5-flash-image` is confirmed available (`us-central1` unless the team verifies a closer region).
  Rationale: ES is pinned to `asia-northeast1` by req §9.2; co-locating Cloud Run minimizes ES latency. Vertex model regional availability is independent and must be verified, not assumed (model availability is time-sensitive; check current Vertex AI docs at execution time).
  Date/Author: 2026-06-15 / Ran (proposed at deployment ExecPlan authoring)
- Decision: Deployment is performed with **`gcloud` CLI commands captured in this plan plus three committed helper scripts** (`scripts/deploy/deploy_fastapi.sh`, `scripts/deploy/deploy_adk.sh`, `scripts/deploy/teardown.sh`), not Terraform.
  Rationale: Hackathon scope and a single throwaway environment do not justify a Terraform state backend; the existing repo convention is shell scripts under `scripts/`. Reproducibility comes from committed scripts + this plan.
  Date/Author: 2026-06-15 / Ran (proposed at deployment ExecPlan authoring)
- Decision: The Cloud Run images must listen on the injected `$PORT` instead of hard-coded service-specific ports; deploy scripts should not rely on `--port` unless rolling back to the old images during recovery.
  Rationale: This matches Cloud Run's container contract, keeps one image usable across local overrides and Cloud Run, and removes a fragile hidden dependency between Dockerfile ports and deploy command flags.
  Date/Author: 2026-06-27 / Codex (pre-production readiness audit)
- Decision: The ES VM may use a **temporary external IP only for bootstrap and production seed**, then the access config must be deleted before acceptance. No firewall rule may expose `tcp:9200` publicly; Elasticsearch remains reachable only from localhost and the Cloud Run Direct VPC egress subnet range.
  Rationale: This avoids adding Cloud NAT as a steady-state component while still giving the VM enough outbound access to install Elasticsearch and run the Kaggle/R2/Vertex/Firestore seed. The final accepted infrastructure still satisfies the "ES VM has no external IP" security posture.
  Date/Author: 2026-06-27 / Codex (pre-production readiness audit)


## Outcomes & Retrospective


To be completed as milestones land. Capture: the chosen GCP project id and region; the ES VM static internal IP and the Direct VPC egress subnet range; final Cloud Run URLs; the deployed image tags; confirmation that the production E2E reached `COMPLETED` with a generated (non-collage) image; and the teardown command actually run after the demo.


Recorded so far (Milestones A + B, 2026-06-28):

**Milestone B (2026-06-28):**
- ES VM: `gen-fashion-es`, zone `asia-northeast1-a`, `e2-medium`, `pd-balanced 30GB`
- Static internal IP: `gen-fashion-es-ip` (reserved, `asia-northeast1` subnet `default`)
- Elasticsearch: 8.19, security enabled, `discovery.type: single-node`, health `green`
- Firewall: `allow-es-from-cloudrun` (source `10.146.0.0/20` → tcp:9200)
- Night-stop schedule: `es-night-off` (JST 02:00 stop / 08:00 start, attached)
- Secret Manager: `ELASTICSEARCH_API_KEY` stored (all 4 secrets now in place)
- Seed: `created=209, skipped=1, errors=0` (210 items, 70/70/70 per closet, 768-dim embeddings)
- Verification: `_count=210` ✅; `embedding` dim=768 present on all shared docs ✅
- External IP: removed (step 12.1 ✅ — VM now IAP-only)
- Discoveries: VM `.env` had `FIRESTORE_EMULATOR_HOST=localhost:8080` and `GOOGLE_APPLICATION_CREDENTIALS` pointing at a missing SA JSON; both commented out for production seed via ADC.

**Milestone A (2026-06-27):**
- GCP project: `animation-agent` (project number 789766161934); billing account `0140CC-06E4FF-5940D6`.
- Regions: infrastructure `asia-northeast1`; Vertex AI `GOOGLE_CLOUD_LOCATION=us-central1` (where `gemini-2.5-flash-image` is confirmed).
- Service accounts: `fastapi-sa`, `adk-sa`, `tasks-invoker-sa` @ `animation-agent.iam.gserviceaccount.com`.
- Firestore: `(default)`, Native mode, `asia-northeast1`; `firestore.rules` + `firestore.indexes.json` deployed.
- Firebase: added to project; Web app `gen-fashion-web` (`1:789766161934:web:e894240fca5dc80b9ede5f`); Google sign-in enabled; web config in gitignored `credentials/firebase-sdk.md`. Hosting origin will be `https://animation-agent.web.app`.
- R2: Cloudflare bucket `gen-fashion-images` + CORS; endpoint `https://<account_id>.r2.cloudflarestorage.com` (account id captured by operator).
- Secret Manager: `INTERNAL_TASK_SECRET`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` (`ELASTICSEARCH_API_KEY` pending Milestone B).


## Context and Orientation


This repository (`gen-fashion`) is a two-container application plus a Flutter Web client, organized with Hexagonal Architecture / DDD. A reader new to it needs these anchors:


- `fastapi-service/` — Python/FastAPI "edge" service. Public routes `/closet/*` (signed upload URLs, register, delete, signed download) and `/sessions/*` (create session, select source, SSE stream), plus the internal worker route `/internal/tasks/process-upload`. Config is `fastapi-service/app/config.py` (`pydantic-settings`, reads env + `.env`). Adapter selection is in `fastapi-service/app/dependencies.py` (`get_task_queue()` switches to `CloudTasksAdapter` only when `TASK_QUEUE_MODE=cloud_tasks` **and** `google_cloud_project` is set). Container entry: `fastapi-service/Dockerfile` (`uvicorn app.main:app` on `:8000`).
- `adk-agent-service/` — Python ADK ("Agent Development Kit") service (ADL-022). It runs the `styling_app` agent topology (orchestrator + ClosetAgent + StylingAgent + four tools) and exposes a FastAPI wrapper `styling_app/server.py` with `/health` and `POST /internal/run-session` (`:3000`). Config: `adk-agent-service/styling_app/config.py`. When `GOOGLE_GENAI_USE_VERTEXAI=true` it bridges `GOOGLE_CLOUD_PROJECT` / `GOOGLE_CLOUD_LOCATION` into the process env so ADK's Gemini client uses Vertex AI + Application Default Credentials. Image generation model defaults to `gemini-2.5-flash-image` (Nano Banana) in `styling_app/adapters/image_generation.py`; on failure or missing quota it falls back to a collage (ADL-005).
- `flutter-web-app/` — Flutter Web SPA. All environment- and Firebase-specific values are compile-time `--dart-define` flags read in `flutter-web-app/lib/config.dart` (`API_BASE_URL`, `USE_EMULATORS`, `FIREBASE_*`, emulator hosts). Generated `firebase_options.dart` is intentionally git-ignored; production values are passed via `--dart-define`.
- `scripts/seed_shared_closet/run_seed.py` — idempotent seeder for the shared demo closet. Flags: `--max-items-per-category N` (default 150 / env `MAX_ITEMS_PER_CATEGORY`), `--with-embeddings` (compute 768-dim `gemini-embedding-001` text vectors and index them), `--source-dir PATH`, `--purge`. It downloads from Kaggle, uploads images to R2, indexes into Elasticsearch `clothing_items` (with `user_id="__shared__"`), and writes `shared_closet/*` + `shared_closets/{closetId}` Firestore docs. `item_id = uuid5(filename)` makes re-runs idempotent.
- `docker-compose.yml` — the local stack. It is the canonical reference for the env vars each service expects; the production deploy substitutes managed services for each Compose service (MinIO→R2, local ES→Compute Engine ES, emulators→real Firestore/Firebase Auth, `TASK_QUEUE_MODE=local`→`cloud_tasks`).
- `firestore.rules` — owner-only read on `users/{uid}` and `users/{uid}/closet/*`, all client writes denied. Must be deployed to the production Firebase project.
- `docs/req-phase01.md` — the source of truth for requirements and ADLs. `docs/feature-matrix-phase01.md` — implementation status. `docs/architecture-overview.md` — the implemented-vs-planned visualization. All three are kept in sync with this plan.


Terms: **R2** = Cloudflare R2 object storage (S3-compatible); locally substituted by **MinIO**. **ADC** = Application Default Credentials (Cloud Run service-account identity). **OIDC token** = a short-lived identity token Cloud Run/Cloud Tasks can mint so a caller proves which service account it is. **Direct VPC egress** = the Cloud Run feature that routes a service's outbound traffic straight into a VPC subnet's private IP range, with no separate connector instances (the GA successor to the Serverless VPC Access connector). **Nano Banana** = the `gemini-2.5-flash-image` model used for coordinate-image generation.


Assumed inputs the operator must have before starting: a billing-enabled GCP project id (this plan calls it `<PROJECT_ID>`; pick e.g. `gen-fashion-prod` — note the local default is `gen-fashion-local`), `Owner`/`Editor` on it, a Cloudflare account for R2, and a Kaggle API token (`~/.kaggle/kaggle.json`) for the seed. `gcloud`, `docker`, the Firebase CLI, and the Flutter SDK are installed locally.


## Plan of Work


The work is sequenced so each milestone leaves a coherent, independently verifiable state. The guiding principle is **the code is already environment-driven**, so deployment is mostly provisioning managed resources and supplying the right env/secret values — with one pre-provisioning readiness patch and then the cloud resources. No feature behavior changes.


Milestone 0 — Deploy readiness patch. Before creating cloud resources, land the small code/config/script changes that make the manual deploy executable: split the Cloud Tasks worker URL in the cloud path, attach and verify OIDC tokens for the two internal hops, make both Dockerfiles honor Cloud Run's injected `$PORT`, mirror deploy-only env knobs in `.env.example`, and add the thin `scripts/deploy/` wrappers that later MF CI/CD will call. This milestone is verified entirely locally with unit tests, Docker image startup checks, and script dry runs.


Milestone A — GCP foundation (MD-1, MD-2, MD-9). Create/select the project, enable APIs, create three least-privilege service accounts (`fastapi-sa`, `adk-sa`, `tasks-invoker-sa`) and bind IAM, create the Firestore database (Native mode) in `asia-northeast1` and deploy `firestore.rules`, create the production Firebase project with Google sign-in enabled, create the production Cloudflare R2 bucket `gen-fashion-images` with the §8.4 CORS rule pointing at the Firebase Hosting origin, and store every secret (R2 keys, `ELASTICSEARCH_API_KEY`, `INTERNAL_TASK_SECRET`) in Secret Manager. This milestone touches no application code; it produces the identities and secrets everything else consumes.


Milestone B — Data plane (MD-3, MD-4, MD-10). Provision the `e2-medium` Elasticsearch VM in `asia-northeast1-a` with a **30 GB `pd-balanced`** boot disk and a **reserved static internal IP**. During bootstrap only, allow the VM an ephemeral external IP so it can install Elasticsearch and run the Kaggle/R2/Vertex/Firestore seed; do not expose `tcp:9200` publicly. Install Elasticsearch 8.x with security enabled, mint an API key, and firewall `tcp:9200` to the **Cloud Run Direct VPC egress subnet range only** (no Serverless VPC Access connector — ADL-023). Then run the seed `--with-embeddings` from the VM, remove the VM's external IP, and verify (from Cloud Run after Milestone C) that ES remains reachable privately over Direct VPC egress and that the JP-analyzer is not required (closing the open M1-3 PoC question). **Cost (ADL-023):** stop the VM when not actively testing (idle cost = the `pd-balanced` disk only); for the post-submission public window an optional Compute Engine instance schedule (`Asia/Tokyo` cron) can auto-stop the VM overnight — wire it but leave it ON/OFF as a judgement call on availability vs. cost.


Milestone C — Services (MD-5, MD-6, MD-7, MD-8). Create an Artifact Registry Docker repo, build and push both images, and deploy both Cloud Run services through the committed helper scripts with the deploy settings from req §9.1 / ADL-016 (`fastapi-service`: public, min 0 / max 10, 1 GB / 1 CPU / 60 s; `adk-agent-service`: private, min 1 / max 5, 2 GB / 1 CPU / 600 s). Create the Cloud Tasks queue `gen-fashion-embed`, flip `TASK_QUEUE_MODE=cloud_tasks`, wire each service's env + secrets and cross-service URLs, and prove the OIDC-hardened internal paths work.


Milestone D — Generation + frontend (MD-11, MD-12). Confirm `gemini-2.5-flash-image` produces a real generated image on Vertex AI for the deployed `adk-agent-service` (not the collage fallback), adjusting `GOOGLE_CLOUD_LOCATION` to a region where the model is available. Build the Flutter Web release with production `--dart-define`s and deploy to Firebase Hosting; add the hosting domain to Firebase Auth authorized domains and the R2 CORS allowlist.


Milestone E — Acceptance + ops (MD-13, MD-14). Run the production E2E: open the hosted app, sign in, run a `SHARED_CLOSET` session to `COMPLETED`, and confirm a generated image. Verify the ADK event stream is queryable in Cloud Logging, confirm the Firestore `agentEvents` TTL policy (24 h, ADL-021) is active, and document/execute teardown so the throwaway VM and services can be deleted after submission.


## Concrete Steps


All `gcloud` commands assume `gcloud config set project <PROJECT_ID>` and a default region of `asia-northeast1`. Replace `<PROJECT_ID>` and Cloudflare values with the real ones. Commands are shown as indented blocks.


Milestone 0 — Deploy readiness patch


0.1. Patch the remaining MD-8 cloud code paths before any cloud resource is created:


    - `fastapi-service/app/config.py`: add `internal_invoker_sa: str | None = None`.
    - `fastapi-service/app/adapters/cloud_tasks_adapter.py`: build the worker URL from `settings.fastapi_internal_base_url or settings.adk_internal_base_url`; when `internal_invoker_sa` and `fastapi_internal_base_url` are set, attach:

        http_request["oidc_token"] = {
            "service_account_email": settings.internal_invoker_sa,
            "audience": settings.fastapi_internal_base_url.rstrip("/"),
        }

      Keep `X-Internal-Secret` in headers as defense in depth.
    - `fastapi-service/app/adapters/adk_agent_run.py`: when cloud OIDC is configured, fetch a Google identity token for `settings.adk_internal_base_url.rstrip("/")` and send `Authorization: Bearer <token>` on `POST /internal/run-session`; keep `X-Internal-Secret`.
    - `fastapi-service/app/auth.py`: update `require_internal_secret` so production accepts only requests with both a valid shared secret and a verified OIDC bearer whose audience is `FASTAPI_INTERNAL_BASE_URL` and whose service-account email equals `INTERNAL_INVOKER_SA`. Local behavior remains shared-secret only when `INTERNAL_INVOKER_SA` is unset. Use Google token verification APIs rather than hand-decoding JWTs.
    - `fastapi-service/requirements.txt` and `fastapi-service/pyproject.toml` / lockfile if needed: ensure `google-auth` is an explicit dependency for token fetch/verification.


0.2. Patch the Cloud Run container contract:


    - `fastapi-service/Dockerfile`: run uvicorn on `${PORT:-8000}` through a shell entrypoint or small startup command.
    - `adk-agent-service/Dockerfile`: run uvicorn on `${PORT:-3000}` through a shell entrypoint or small startup command.
    - Keep `docker-compose.yml` commands pinned to `8000` / `3000` for local hot reload; compose already overrides the Dockerfile command.


0.3. Mirror production deploy knobs in `.env.example`:


    # Production-only internal URLs / OIDC:
    # FASTAPI_INTERNAL_BASE_URL=https://fastapi-service-xxxxx-an.a.run.app
    # ADK_INTERNAL_BASE_URL=https://adk-agent-service-xxxxx-an.a.run.app
    # INTERNAL_INVOKER_SA=tasks-invoker-sa@<PROJECT_ID>.iam.gserviceaccount.com


    Also update stale comments that say `fastapi-service` can use Cloud Run internal ingress; it stays public and protects only `/internal/tasks/process-upload` with OIDC + shared secret.


0.4. Add deploy helper scripts under `scripts/deploy/`:


    - `deploy_adk.sh`: requires `PROJECT_ID`, `REGION`, `IMAGE_TAG`, `ES_INTERNAL_IP`, `R2_ENDPOINT_URL`, `R2_PUBLIC_ENDPOINT_URL`, `R2_BUCKET_NAME`; deploys `adk-agent-service` private and grants `fastapi-sa` `roles/run.invoker`.
    - `deploy_fastapi.sh`: requires the same common inputs plus `ADK_URL`, `FASTAPI_URL` or a `--bootstrap` mode. First deploy may omit `FASTAPI_INTERNAL_BASE_URL`; after the service URL exists, redeploy with `FASTAPI_INTERNAL_BASE_URL=$FASTAPI_URL`.
    - `teardown.sh`: supports `--dry-run` by default and only deletes resources named in this plan.


0.5. Verify Milestone 0 locally:


    (cd fastapi-service && pytest -q)
    (cd adk-agent-service && pytest -q)
    (cd flutter-web-app && flutter analyze && flutter test)
    docker build -t gen-fashion-fastapi:md0 fastapi-service
    docker run --rm -d --name gen-fashion-fastapi-md0 -e PORT=18000 -p 18000:18000 gen-fashion-fastapi:md0
    curl -f http://localhost:18000/health
    docker stop gen-fashion-fastapi-md0
    docker build -t gen-fashion-adk:md0 adk-agent-service
    docker run --rm -d --name gen-fashion-adk-md0 -e PORT=13000 -p 13000:13000 gen-fashion-adk:md0
    curl -f http://localhost:13000/health
    docker stop gen-fashion-adk-md0
    bash scripts/deploy/teardown.sh --dry-run


    Expected results: FastAPI tests match the current ME baseline (68+ passing), ADK tests match the current baseline (41+ passing), Flutter analyze is clean and tests pass (14+), both images respond on the injected `PORT`, and teardown dry run prints only resources created by this plan. Architecture overview does not need an update because these are deployment-contract/script changes, not a new steady-state component.


Milestone A — GCP foundation


1. Enable APIs (run from any directory):


    gcloud services enable \
      run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com \
      secretmanager.googleapis.com cloudtasks.googleapis.com compute.googleapis.com \
      vpcaccess.googleapis.com firestore.googleapis.com aiplatform.googleapis.com \
      logging.googleapis.com iamcredentials.googleapis.com


2. Create service accounts:


    gcloud iam service-accounts create fastapi-sa --display-name="fastapi-service"
    gcloud iam service-accounts create adk-sa --display-name="adk-agent-service"
    gcloud iam service-accounts create tasks-invoker-sa --display-name="cloud-tasks-oidc-invoker"


3. Bind least-privilege IAM (`PROJECT=<PROJECT_ID>`):


    # adk-sa: Vertex AI (Gemini + image gen + embeddings), Firestore, logging
    gcloud projects add-iam-policy-binding $PROJECT --member="serviceAccount:adk-sa@$PROJECT.iam.gserviceaccount.com" --role=roles/aiplatform.user
    gcloud projects add-iam-policy-binding $PROJECT --member="serviceAccount:adk-sa@$PROJECT.iam.gserviceaccount.com" --role=roles/datastore.user
    gcloud projects add-iam-policy-binding $PROJECT --member="serviceAccount:adk-sa@$PROJECT.iam.gserviceaccount.com" --role=roles/logging.logWriter
    # fastapi-sa: Firestore, Cloud Tasks enqueue, Secret access, logging, Vertex (embeddings in worker)
    gcloud projects add-iam-policy-binding $PROJECT --member="serviceAccount:fastapi-sa@$PROJECT.iam.gserviceaccount.com" --role=roles/datastore.user
    gcloud projects add-iam-policy-binding $PROJECT --member="serviceAccount:fastapi-sa@$PROJECT.iam.gserviceaccount.com" --role=roles/cloudtasks.enqueuer
    gcloud projects add-iam-policy-binding $PROJECT --member="serviceAccount:fastapi-sa@$PROJECT.iam.gserviceaccount.com" --role=roles/secretmanager.secretAccessor
    gcloud projects add-iam-policy-binding $PROJECT --member="serviceAccount:fastapi-sa@$PROJECT.iam.gserviceaccount.com" --role=roles/aiplatform.user
    gcloud projects add-iam-policy-binding $PROJECT --member="serviceAccount:fastapi-sa@$PROJECT.iam.gserviceaccount.com" --role=roles/logging.logWriter
    # adk-sa also reads the internal secret from Secret Manager
    gcloud projects add-iam-policy-binding $PROJECT --member="serviceAccount:adk-sa@$PROJECT.iam.gserviceaccount.com" --role=roles/secretmanager.secretAccessor
    # fastapi-sa may attach tasks-invoker-sa to Cloud Tasks OIDC tokens
    gcloud iam service-accounts add-iam-policy-binding tasks-invoker-sa@$PROJECT.iam.gserviceaccount.com \
      --member="serviceAccount:fastapi-sa@$PROJECT.iam.gserviceaccount.com" --role=roles/iam.serviceAccountUser


4. Create the Firestore database (Native mode) and deploy rules:


    gcloud firestore databases create --location=asia-northeast1 --type=firestore-native
    # from repo root, with firebase.json + firestore.rules present:
    firebase deploy --only firestore:rules,firestore:indexes --project <PROJECT_ID>


5. Create the production Firebase project artifacts: in the Firebase console, attach Firebase to `<PROJECT_ID>`, enable the **Google** sign-in provider, register a **Web app**, and copy its config (apiKey, appId, messagingSenderId, authDomain, storageBucket) for MD-12's `--dart-define`s.


6. Store secrets (MD-2). Values come from Cloudflare (R2), the ES API key minted in MD-3 (store after that step), and a freshly generated internal secret:


    printf '%s' "<R2_ACCESS_KEY_ID>"     | gcloud secrets create R2_ACCESS_KEY_ID --data-file=-
    printf '%s' "<R2_SECRET_ACCESS_KEY>" | gcloud secrets create R2_SECRET_ACCESS_KEY --data-file=-
    printf '%s' "$(openssl rand -hex 32)" | gcloud secrets create INTERNAL_TASK_SECRET --data-file=-
    # ELASTICSEARCH_API_KEY is created in MD-3 once the key is minted.


7. Create the production R2 bucket `gen-fashion-images` in the Cloudflare dashboard, capture the S3 API endpoint (`https://<account_id>.r2.cloudflarestorage.com`) and account id, and apply the CORS rule from req §8.4 with `AllowedOrigins` = the Firebase Hosting origin (`https://<PROJECT_ID>.web.app`) and `AllowedMethods` = `[GET, PUT, POST, OPTIONS]`.


Milestone B — Data plane


8. Reserve a static internal IP (so the VM's address survives stop/start), then create the ES VM with a `pd-balanced` disk and a temporary external IP for bootstrap. Do not create any firewall rule that exposes Elasticsearch publicly:


    # Static internal IP from the asia-northeast1 default subnet
    gcloud compute addresses create gen-fashion-es-ip \
      --region=asia-northeast1 --subnet=default
    ES_IP=$(gcloud compute addresses describe gen-fashion-es-ip \
      --region=asia-northeast1 --format='value(address)')

    gcloud compute instances create gen-fashion-es \
      --zone=asia-northeast1-a --machine-type=e2-medium \
      --image-family=debian-12 --image-project=debian-cloud \
      --boot-disk-size=30GB --boot-disk-type=pd-balanced \
      --network=default --subnet=default --private-network-ip="$ES_IP"


9. SSH in and install Elasticsearch 8.x:


    gcloud compute ssh gen-fashion-es --zone=asia-northeast1-a
    # on the VM:
    wget -qO - https://artifacts.elastic.co/GPG-KEY-elasticsearch | sudo gpg --dearmor -o /usr/share/keyrings/elasticsearch-keyring.gpg
    echo "deb [signed-by=/usr/share/keyrings/elasticsearch-keyring.gpg] https://artifacts.elastic.co/packages/8.x/apt stable main" | sudo tee /etc/apt/sources.list.d/elastic-8.x.list
    sudo apt-get update && sudo apt-get install -y elasticsearch
    # /etc/elasticsearch/elasticsearch.yml: network.host: 0.0.0.0 ; discovery.type: single-node ; xpack.security.enabled: true
    sudo systemctl enable --now elasticsearch
    # reset or capture the elastic password, then mint an application API key with the security API:
    sudo /usr/share/elasticsearch/bin/elasticsearch-reset-password -u elastic


    Create an API key scoped to the app's index, then from the workstation store the base64 `encoded` value in Secret Manager:


    curl -k -u elastic:<pw> -X POST https://localhost:9200/_security/api_key \
      -H 'Content-Type: application/json' \
      -d '{"name":"gen-fashion-app","role_descriptors":{"gen-fashion-app":{"cluster":["monitor"],"indices":[{"names":["clothing_items"],"privileges":["create_index","read","write","delete","manage"]}]}}}'


    printf '%s' "<ELASTICSEARCH_API_KEY>" | gcloud secrets create ELASTICSEARCH_API_KEY --data-file=-


10. Open the private path. Direct VPC egress needs **no connector resource** — it is enabled on the Cloud Run services in Milestone C (`--network=default --subnet=default --vpc-egress=private-ranges-only`). Here, just allow `tcp:9200` from the egress subnet's range so Cloud Run can reach ES (and nothing else can):


    SUBNET_RANGE=$(gcloud compute networks subnets describe default \
      --region=asia-northeast1 --format='value(ipCidrRange)')
    gcloud compute firewall-rules create allow-es-from-cloudrun \
      --network=default --direction=INGRESS --action=ALLOW \
      --rules=tcp:9200 --source-ranges="$SUBNET_RANGE"


    Optional cost control for the post-submission public window — auto-stop the VM overnight (JST). Leave this OFF if judges/users may access at night; the schedule can be detached anytime. (First schedule creation may prompt a one-time IAM grant to the Compute Engine service agent.)


    gcloud compute resource-policies create instance-schedule es-night-off \
      --region=asia-northeast1 \
      --vm-stop-schedule="0 2 * * *" --vm-start-schedule="0 8 * * *" \
      --timezone="Asia/Tokyo"
    gcloud compute instances add-resource-policies gen-fashion-es \
      --zone=asia-northeast1-a --resource-policies=es-night-off


11. Verify private connectivity (MD-4): from the ES VM, `curl -k -u elastic:<pw> https://localhost:9200/_cluster/health` returns `status: green|yellow`; after MD-7, confirm `adk-agent-service` logs show successful ES queries. Record the JP-analyzer finding (expected: not required for the curated demo set), closing the M1-3 PoC question.


12. Run the full vector seed (MD-10) from inside the VPC (run it on the ES VM, which has the private ES path; export the prod R2 + Firestore + Vertex env, place the Kaggle token, then):


    MAX_ITEMS_PER_CATEGORY=150 python scripts/seed_shared_closet/run_seed.py --with-embeddings


    Expect a non-zero `created` on first run (~210 total: 70 per closet across `adult-01`, `adult-02`, `child-01`) and `created=0` on a second run (idempotent). Verify ES has `embedding` populated: `GET clothing_items/_count` returns ≥ 210 and a `knn` probe returns shared docs carrying `embedding`.


12.1. Remove the bootstrap external IP before continuing to Cloud Run deploy:


    ACCESS_CONFIG=$(gcloud compute instances describe gen-fashion-es \
      --zone=asia-northeast1-a \
      --format='value(networkInterfaces[0].accessConfigs[0].name)')
    gcloud compute instances delete-access-config gen-fashion-es \
      --zone=asia-northeast1-a \
      --access-config-name="$ACCESS_CONFIG"
    gcloud compute instances describe gen-fashion-es \
      --zone=asia-northeast1-a \
      --format='value(networkInterfaces[0].accessConfigs)'


    The final command must print nothing. From this point forward, access the VM through IAP (`gcloud compute ssh gen-fashion-es --zone=asia-northeast1-a --tunnel-through-iap`). This restores the final-state security posture: no external IP and ES reachable only from localhost plus the Cloud Run Direct VPC egress subnet range.


Milestone C — Services


13. Create the Artifact Registry repo and build/push both Milestone-0-patched images:


    gcloud artifacts repositories create gen-fashion --repository-format=docker --location=asia-northeast1
    REPO=asia-northeast1-docker.pkg.dev/<PROJECT_ID>/gen-fashion
    IMAGE_TAG=md-$(date +%Y%m%d-%H%M)
    gcloud builds submit fastapi-service --tag $REPO/fastapi-service:$IMAGE_TAG
    gcloud builds submit adk-agent-service --tag $REPO/adk-agent-service:$IMAGE_TAG


14. Confirm the image tag was built from the Milestone 0 readiness patch:


    git status --short
    gcloud artifacts docker images list $REPO/fastapi-service --include-tags --filter="tags:$IMAGE_TAG"
    gcloud artifacts docker images list $REPO/adk-agent-service --include-tags --filter="tags:$IMAGE_TAG"


    `git status --short` may show the committed plan/doc changes before commit, but must not show uncommitted application-code edits that were omitted from the image build.


15. Create the Cloud Tasks queue:


    gcloud tasks queues create gen-fashion-embed --location=asia-northeast1


16. Deploy `adk-agent-service` (private):


    bash scripts/deploy/deploy_adk.sh \
      --project <PROJECT_ID> --region asia-northeast1 --image "$REPO/adk-agent-service:$IMAGE_TAG" \
      --es-internal-ip <es-vm-internal-ip> \
      --r2-endpoint-url https://<account_id>.r2.cloudflarestorage.com \
      --r2-public-endpoint-url https://<account_id>.r2.cloudflarestorage.com \
      --r2-bucket-name gen-fashion-images


    The script expands to the equivalent of:


    gcloud run deploy adk-agent-service --image $REPO/adk-agent-service:$IMAGE_TAG \
      --region=asia-northeast1 --service-account=adk-sa@<PROJECT_ID>.iam.gserviceaccount.com \
      --no-allow-unauthenticated --min-instances=1 --max-instances=5 --memory=2Gi --cpu=1 --timeout=600 \
      --network=default --subnet=default --vpc-egress=private-ranges-only \
      --set-env-vars=GOOGLE_CLOUD_PROJECT=<PROJECT_ID>,GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_LOCATION=us-central1,AGENT_MODEL=gemini-2.5-flash,ELASTICSEARCH_URL=https://<es-vm-internal-ip>:9200,R2_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com,R2_PUBLIC_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com,R2_BUCKET_NAME=gen-fashion-images \
      --set-secrets=ELASTICSEARCH_API_KEY=ELASTICSEARCH_API_KEY:latest,R2_ACCESS_KEY_ID=R2_ACCESS_KEY_ID:latest,R2_SECRET_ACCESS_KEY=R2_SECRET_ACCESS_KEY:latest,INTERNAL_TASK_SECRET=INTERNAL_TASK_SECRET:latest


    Then grant the caller: `gcloud run services add-iam-policy-binding adk-agent-service --region=asia-northeast1 --member="serviceAccount:fastapi-sa@<PROJECT_ID>.iam.gserviceaccount.com" --role=roles/run.invoker`.


17. Deploy `fastapi-service` (public), wiring the ADK URL and the new fastapi-internal URL (its own URL) and OIDC invoker:


    ADK_URL=$(gcloud run services describe adk-agent-service --region=asia-northeast1 --format='value(status.url)')
    bash scripts/deploy/deploy_fastapi.sh \
      --project <PROJECT_ID> --region asia-northeast1 --image "$REPO/fastapi-service:$IMAGE_TAG" \
      --adk-url "$ADK_URL" --bootstrap \
      --es-internal-ip <es-vm-internal-ip> \
      --r2-endpoint-url https://<account_id>.r2.cloudflarestorage.com \
      --r2-public-endpoint-url https://<account_id>.r2.cloudflarestorage.com \
      --r2-bucket-name gen-fashion-images
    FASTAPI_URL=$(gcloud run services describe fastapi-service --region=asia-northeast1 --format='value(status.url)')
    bash scripts/deploy/deploy_fastapi.sh \
      --project <PROJECT_ID> --region asia-northeast1 --image "$REPO/fastapi-service:$IMAGE_TAG" \
      --adk-url "$ADK_URL" --fastapi-url "$FASTAPI_URL" \
      --es-internal-ip <es-vm-internal-ip> \
      --r2-endpoint-url https://<account_id>.r2.cloudflarestorage.com \
      --r2-public-endpoint-url https://<account_id>.r2.cloudflarestorage.com \
      --r2-bucket-name gen-fashion-images


    The script expands to the equivalent of:


    gcloud run deploy fastapi-service --image $REPO/fastapi-service:$IMAGE_TAG \
      --region=asia-northeast1 --service-account=fastapi-sa@<PROJECT_ID>.iam.gserviceaccount.com \
      --allow-unauthenticated --min-instances=0 --max-instances=10 --memory=1Gi --cpu=1 --timeout=60 \
      --network=default --subnet=default --vpc-egress=private-ranges-only \
      --set-env-vars=GOOGLE_CLOUD_PROJECT=<PROJECT_ID>,FIREBASE_PROJECT_ID=<PROJECT_ID>,GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_LOCATION=us-central1,ELASTICSEARCH_URL=https://<es-vm-internal-ip>:9200,R2_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com,R2_PUBLIC_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com,R2_BUCKET_NAME=gen-fashion-images,TASK_QUEUE_MODE=cloud_tasks,CLOUD_TASKS_QUEUE_EMBED=gen-fashion-embed,CLOUD_TASKS_LOCATION=asia-northeast1,ADK_INTERNAL_BASE_URL=$ADK_URL,FASTAPI_INTERNAL_BASE_URL=$FASTAPI_URL,INTERNAL_INVOKER_SA=tasks-invoker-sa@<PROJECT_ID>.iam.gserviceaccount.com \
      --set-secrets=ELASTICSEARCH_API_KEY=ELASTICSEARCH_API_KEY:latest,R2_ACCESS_KEY_ID=R2_ACCESS_KEY_ID:latest,R2_SECRET_ACCESS_KEY=R2_SECRET_ACCESS_KEY:latest,INTERNAL_TASK_SECRET=INTERNAL_TASK_SECRET:latest


    The second deploy must include `FASTAPI_INTERNAL_BASE_URL=$FASTAPI_URL` so the worker task targets the fastapi service's own URL. Grant `tasks-invoker-sa` `roles/run.invoker` on `fastapi-service` so the OIDC-authenticated Cloud Task is accepted:


    gcloud run services add-iam-policy-binding fastapi-service \
      --region=asia-northeast1 \
      --member="serviceAccount:tasks-invoker-sa@<PROJECT_ID>.iam.gserviceaccount.com" \
      --role=roles/run.invoker


Milestone D — Generation + frontend


18. Verify production image generation (MD-11): trigger one `SHARED_CLOSET` run (MD-13's curl flow) and confirm in `adk-agent-service` logs that the `style_synthesizer` used the Nano Banana path (not "collage fallback"), and that `styleResult.coordinateImageUrl` opens a generated image. If the model is unavailable in `us-central1`, set `GOOGLE_CLOUD_LOCATION` to a supported region and redeploy. Verify current Vertex AI availability/quota for `gemini-2.5-flash-image` at execution time.


19. Build and host the Flutter Web client (MD-12):


    cd flutter-web-app
    flutter build web --release \
      --dart-define=API_BASE_URL=$FASTAPI_URL \
      --dart-define=USE_EMULATORS=false \
      --dart-define=FIREBASE_PROJECT_ID=<PROJECT_ID> \
      --dart-define=FIREBASE_API_KEY=<web_api_key> \
      --dart-define=FIREBASE_APP_ID=<web_app_id> \
      --dart-define=FIREBASE_MESSAGING_SENDER_ID=<sender_id> \
      --dart-define=FIREBASE_AUTH_DOMAIN=<PROJECT_ID>.firebaseapp.com \
      --dart-define=FIREBASE_STORAGE_BUCKET=<PROJECT_ID>.appspot.com
    firebase deploy --only hosting --project <PROJECT_ID>


    Add `<PROJECT_ID>.web.app` to Firebase Auth → Authorized domains, and confirm it is in the R2 CORS allowlist (MD-9).


Milestone E — Acceptance + ops


20. Production E2E (MD-13). Open `https://<PROJECT_ID>.web.app`, sign in with Google, start a session, choose `SHARED_CLOSET`, and confirm the Accordion streams tool events and the session reaches `COMPLETED` with a generated image. The API-level equivalent (adapt the existing `scripts/m5_coordination_smoke.py` against the deployed URL with a real Firebase ID token) must reach `status: COMPLETED`.


21. Ops (MD-14). Confirm ADK events appear in Cloud Logging (`gcloud logging read 'resource.labels.service_name="adk-agent-service"' --limit=20`). Ensure the Firestore TTL policy on `sessions/{id}/agentEvents.ttlAt` (24 h, ADL-021) exists: `gcloud firestore fields ttls update ttlAt --collection-group=agentEvents --enable-ttl`. Set an Artifact Registry cleanup policy on the `gen-fashion` repo so only the latest image tag per service is retained during active development (images accumulate at $0.10/GB with every `md-YYYYMMDD-HHMM` tag push; the repo is deleted entirely at teardown, but managing tags during the development window avoids surprise storage costs):


    gcloud artifacts repositories set-cleanup-policies gen-fashion \
      --project=<PROJECT_ID> --location=asia-northeast1 \
      --policy='[{"name":"keep-recent","action":{"type":"Keep"},"mostRecentVersions":{"keepCount":3}}]'


Write the teardown steps into `scripts/deploy/teardown.sh` (delete both Cloud Run services, the VM, the static internal IP, the firewall rule, any night-stop instance schedule, the queue, the Artifact Registry repo) and dry-run it.


## Validation and Acceptance


Local pre-deploy gate (run before building images, from repo root): Milestone 0 step 0.5 is mandatory. It covers FastAPI tests (expect the ME baseline 68+ passing), ADK tests (expect 41+ passing), Flutter analyze/test (expect clean / 14+ passing), Docker image `$PORT` startup checks, and deploy-script dry runs. Add or adjust unit tests for the OIDC header attachment, OIDC bearer verification, and the `cloud_tasks_adapter.py` URL fix in `fastapi-service/app/adapters/`.


Per-milestone acceptance, phrased as observable behavior:
- 0: tests pass locally; both Docker images answer `/health` on an arbitrary injected `PORT`; `scripts/deploy/teardown.sh --dry-run` lists only resources named in this plan; `.env.example` contains `FASTAPI_INTERNAL_BASE_URL` and `INTERNAL_INVOKER_SA`.
- A: `gcloud secrets list` shows `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `ELASTICSEARCH_API_KEY`, `INTERNAL_TASK_SECRET`; `firebase deploy --only firestore:rules` succeeds; the R2 bucket returns the configured CORS headers on an `OPTIONS` preflight from the hosting origin.
- B: `curl` to ES from the VM returns cluster health `green`/`yellow`; the seed prints a non-zero `created` then `created=0` on re-run; `GET clothing_items/_count` ≥ 210 and a `knn` query returns shared items carrying `embedding`; `gcloud compute instances describe gen-fashion-es --format='value(networkInterfaces[0].accessConfigs)'` prints nothing before Cloud Run deployment starts.
- C: `curl https://<FASTAPI_URL>/health` → `200`; the ADK service rejects an unauthenticated call (`403`) but accepts the OIDC-authenticated call from `fastapi-service`; a closet upload drives a Firestore doc to `status: READY` (proving the Cloud Task reached the fastapi worker URL, i.e. the base-url split works).
- D: a `SHARED_CLOSET` run yields a `styleResult.coordinateImageUrl` that opens a **generated** image; `adk-agent-service` logs show the Nano Banana path, not the collage fallback. The hosted SPA loads and signs in with Google.
- E: the browser E2E reaches `COMPLETED`; ADK events are visible in Cloud Logging; the `agentEvents` TTL policy is `enabled`; `teardown.sh` exists and its dry run lists exactly the resources created here.


Milestone acceptance overall: opening the public Firebase Hosting URL and completing a `SHARED_CLOSET` coordination to a generated image is the definition of done — this is `req-phase01.md` §15 Phase 1a #6 satisfied against deployed infrastructure.


## Idempotence and Recovery


Resource-creation commands are safe to re-run if you treat "already exists" as success (or `gcloud ... describe` first). `gcloud run deploy` is fully idempotent — it creates a new revision each time, so re-running with corrected env/secrets is the normal recovery path; roll back with `gcloud run services update-traffic <svc> --to-revisions=<prev>=100`. The seed is idempotent by design (`uuid5(filename)`); `--purge` clears prior shared data before reseeding. Secrets are versioned; add a new version rather than recreating. The ES VM is the one piece of mutable state — snapshot the disk before risky changes. If bootstrap install or seed fails due to outbound connectivity, temporarily recreate the external access config, finish the failed step, then delete the access config again before Milestone C. If private connectivity fails after Cloud Run deploy, the most common causes are (a) the firewall source range not matching the Direct VPC egress subnet's range, (b) `--vpc-egress` not set to `private-ranges-only` (or `--network`/`--subnet` omitted on `gcloud run deploy`), or (c) using the VM's name instead of its static internal IP in `ELASTICSEARCH_URL`.


## Artifacts and Notes


Helper scripts to commit under `scripts/deploy/`: `deploy_fastapi.sh`, `deploy_adk.sh`, `teardown.sh` (thin wrappers over the `gcloud` commands above, parameterized by `PROJECT_ID`/region/image tag). Keep the canonical command list in this plan as the source of truth; the scripts are conveniences, not a second spec. Record the final URLs, the ES internal IP, the temporary external-IP removal evidence, and the deployed image tags in `Outcomes & Retrospective` when the milestone completes.


No secret values belong in this file, the scripts, commits, or logs — only Secret Manager names. The `.env.example` already separates local defaults from the "[4] 本番デプロイ時のみ" block; mirror any new variable there (`FASTAPI_INTERNAL_BASE_URL`, `INTERNAL_INVOKER_SA`) with placeholder values.


## Interfaces and Dependencies


GCP services: Cloud Run (two services), Artifact Registry (image storage), Cloud Build (image builds), Secret Manager (secrets), Cloud Tasks (embedding worker queue), Compute Engine (ES VM), Cloud Run Direct VPC egress (private connectivity, ADL-023 — no Serverless VPC Access connector), Firestore (Native mode), Vertex AI / `aiplatform` (Gemini analysis, `gemini-embedding-001`, `gemini-2.5-flash-image`), Cloud Logging (ADK event stream), IAM Credentials API (identity-token support). External: Cloudflare R2 (object storage) and Kaggle (dataset for the seed). Tooling: `gcloud`, `docker`/Cloud Build, Firebase CLI, Flutter SDK.


Milestone 0 code/script changes (all required before provisioning):
- `fastapi-service/app/config.py`: add `internal_invoker_sa: str | None = None` (`fastapi_internal_base_url` is already present).
- `fastapi-service/app/adapters/cloud_tasks_adapter.py`: use `fastapi_internal_base_url or adk_internal_base_url` for the `process-upload` URL; attach Cloud Tasks OIDC with `service_account_email=internal_invoker_sa` and `audience=fastapi_internal_base_url.rstrip("/")`.
- `fastapi-service/app/adapters/adk_agent_run.py`: when `adk_internal_base_url` points at Cloud Run and production OIDC is configured, attach a Google ID token with audience `adk_internal_base_url.rstrip("/")` to `/internal/run-session`.
- `fastapi-service/app/auth.py` `require_internal_secret`: in production, require both the shared secret and a verified OIDC bearer whose audience and service-account email match config; locally, keep shared-secret-only behavior when `internal_invoker_sa` is unset.
- `fastapi-service/Dockerfile` and `adk-agent-service/Dockerfile`: listen on `${PORT:-8000}` and `${PORT:-3000}` respectively.
- `.env.example`: document `FASTAPI_INTERNAL_BASE_URL` and `INTERNAL_INVOKER_SA`.
- `scripts/deploy/deploy_fastapi.sh`, `scripts/deploy/deploy_adk.sh`, `scripts/deploy/teardown.sh`: add thin wrappers and dry-run teardown.


These code changes preserve `make dev` behavior because the new settings are unset locally (the code falls back to the existing shared-secret + `adk_internal_base_url` paths).


Requirements traceability: MD-1/MD-2 ← req §9.1, §12.1/§12.2, ADL-012; MD-3/MD-4 ← req §9.2, ADL-013, ADL-023, M1-3; MD-5/MD-6/MD-7 ← req §9.1, ADL-016; MD-8 ← req §6.8, §10.3, ADL-024; MD-9 ← req §8.4, ADL-014; MD-10 ← req §15 Phase 1a #7, §16.4, ADL-010, M3-2; MD-11 ← req §6.5, ADL-005, M4-7/M5-6; MD-12 ← req §11, ADL-025; MD-13 ← req §15 Phase 1a #6; MD-14 ← req §9.3, ADL-021.


## Revision Notes


2026-06-15 — Initial authoring. Milestones A–E defined; deployment requirements MD-1…MD-14 scoped; ADLs added to `req-phase01.md`; architecture overview synchronized.

2026-06-21 — Local re-verification completed; three bugs found and fixed (MD-8 local base-URL split, Firestore project binding, `closetId` keyword mapping). MD-10 de-risked (embedding model corrected to `gemini-embedding-001`, `adk_run_timeout_seconds` raised to 90, `STREAM_MAX_SECONDS` raised to 150).

2026-06-25 — Synchronized with completed ME ExecPlan. Changes: (1) step 4 firebase deploy command now includes `firestore:indexes` (ME-7 composite index is committed in `firestore.indexes.json`); (2) step 12 expected seed count updated from ~90 to 210 items (70/70/70, from ME shared-closet expansion); (3) step 14 clarified — `fastapi_internal_base_url` in `config.py` and `local_task_queue.py` URL routing are already done; remaining is `cloud_tasks_adapter.py` URL fix (line 28 still uses `adk_internal_base_url`), OIDC token with corrected audience, `internal_invoker_sa` in config, and OIDC bearer in `auth.py`; (4) Validation baselines updated to 68 FastAPI / 41 ADK / 14 Flutter; (5) Interfaces and Dependencies code-changes list updated to reflect what is already done vs. remaining.

2026-06-27 — Resolved the pre-production deployment readiness audit before cloud work starts. Added Milestone 0 for the required code/config/script patch: Cloud Tasks worker URL split in the cloud path, OIDC token attachment and verification, `$PORT`-compatible Dockerfiles, `.env.example` deploy knobs, and `scripts/deploy/` wrappers. Updated Milestone B so the ES VM may use a temporary external IP for bootstrap/seed only, with a mandatory access-config deletion before Cloud Run deployment. Updated Milestone C to deploy one timestamped Milestone-0-patched image tag via helper scripts. Updated validation, recovery, artifacts, and dependencies to match the resolved flow.

2026-06-27 — Milestone 0 complete. Implemented all code/config/script changes: `internal_invoker_sa` added to `config.py`; `cloud_tasks_adapter.py` worker URL fixed to use `FASTAPI_INTERNAL_BASE_URL` + OIDC token attached; `adk_agent_run.py` fetches Google identity token via ADC when `internal_invoker_sa` is set; `auth.py` `require_internal_secret` verifies OIDC bearer in production (audience = `FASTAPI_INTERNAL_BASE_URL`, email = `INTERNAL_INVOKER_SA`); both Dockerfiles now listen on `${PORT:-default}`; `google-auth==2.29.0` added to `fastapi-service/requirements.txt`; `.env.example` section [4] documents `FASTAPI_INTERNAL_BASE_URL`, `ADK_INTERNAL_BASE_URL`, `INTERNAL_INVOKER_SA`; `scripts/deploy/deploy_fastapi.sh`, `deploy_adk.sh`, `teardown.sh` committed. All step-0.5 checks passed: FastAPI 67 passed, ADK 41 passed, both Docker images responded on injected PORT, `teardown.sh --dry-run` listed exactly plan resources.

2026-06-28 — Milestone B **in progress** (data plane): ES VM `gen-fashion-es` provisioned (`e2-medium`, `pd-balanced 30GB`, `asia-northeast1-a`); static internal IP `gen-fashion-es-ip` reserved; Elasticsearch 8.19 installed (two config conflicts resolved); cluster health `green`; `ELASTICSEARCH_API_KEY` in Secret Manager; firewall `allow-es-from-cloudrun` (subnet CIDR → tcp:9200); night-stop schedule `es-night-off` attached (JST 02:00–08:00); ADC configured on VM. Full vector seed `--with-embeddings` executing (100+/210 items). Discovered: seed `.env` on VM had `FIRESTORE_EMULATOR_HOST=localhost:8080` and `GOOGLE_APPLICATION_CREDENTIALS` pointing at a missing SA JSON — both commented out; prod Firestore now reached via ADC `authorized_user`.

2026-06-27 — Milestone A complete (GCP foundation): project `animation-agent` / `asia-northeast1`; 11 APIs + Firebase; 3 service accounts + least-privilege IAM; Firestore Native + rules/indexes deployed; Firebase + Google sign-in + Web app `gen-fashion-web`; R2 bucket `gen-fashion-images` + CORS; `INTERNAL_TASK_SECRET`/`R2_ACCESS_KEY_ID`/`R2_SECRET_ACCESS_KEY` in Secret Manager. MD-1 ✅, MD-9 ✅; MD-2 stays 🟡 (`ELASTICSEARCH_API_KEY` in Milestone B, env config at Cloud Run deploy).

2026-06-28 — Milestone B complete (data plane). `gen-fashion-es` (`e2-medium`, `pd-balanced 30GB`, `asia-northeast1-a`); static IP `gen-fashion-es-ip`; ES 8.19 health `green`; `ELASTICSEARCH_API_KEY` in Secret Manager; firewall `allow-es-from-cloudrun`; night-stop `es-night-off`; full vector seed `--with-embeddings` completed (`created=209/210`, 768-dim, `_count=210`); external IP removed. MD-3 ✅, MD-10 ✅; MD-4 infrastructure ready (Cloud Run verification deferred to Milestone C). Discoveries: VM `.env` had `FIRESTORE_EMULATOR_HOST=localhost:8080` — commented out before seed.

2026-06-27 — **Milestone B re-scoped for hackathon cost (ADL-023 revised).** Cloud Run → ES private path switched from a **Serverless VPC Access connector** to **Direct VPC egress** (`--network=default --subnet=default --vpc-egress=private-ranges-only`): removes the connector's idle fixed fee (min e2-micro×2) while keeping the same closed-network posture (ES no external IP, `tcp:9200` only from the egress subnet range). ES VM now uses **`pd-balanced` (not SSD)** + a **reserved static internal IP** (survives stop/start), with stop-when-idle operation and an optional `Asia/Tokyo` night-stop instance schedule for the post-submission window. Updated: ADL-023 (req-phase01.md), Milestone B prose + steps 8/10/12.1, Cloud Run deploy flags (steps + `deploy_fastapi.sh`/`deploy_adk.sh` now take `--network`/`--subnet`, default `default`/`default`), `teardown.sh` (drop connector delete; add static-IP + night-stop deletes), glossary, dependencies, recovery, feature-matrix MD-3/MD-4/M1-3, and architecture-overview.
