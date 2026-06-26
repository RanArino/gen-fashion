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
- [ ] Milestone A — GCP foundation: project, APIs, service accounts, IAM, Secret Manager, production R2 bucket + CORS, Firebase project (MD-1, MD-2, MD-9).
- [ ] Milestone B — Data plane: Compute Engine Elasticsearch node, Serverless VPC Access connector + private connectivity verification, full vector seed (MD-3, MD-4, MD-10).
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
- Observation: There is a documented count tension for the shared closet. `req-phase01.md` §15 Phase 1a #7 still says "2,000件以上"; the M3 re-scope (`feature-matrix-phase01.md` M3-2, ADL-010) reduced the demo to 3 curated closets (~90 items) and the seed script's `_CLOSET_QUOTA` totals 30 per closet. The deployment seed therefore produces ~90 demo-closet items **with 768-dim embeddings**; "full vector seed" means embeddings present + hybrid/kNN search working, not a raw count of 2,000. §15 #7 is clarified in this change.
  Evidence: `scripts/seed_shared_closet/run_seed.py:86` `_CLOSET_QUOTA = {"tops": 8, "outer": 4, "bottoms": 6, "dress": 4, "shoes": 5, "hat": 3}`.


## Decision Log


- Decision: Cloud Run reaches the Compute Engine Elasticsearch node over a **Serverless VPC Access connector** with `--vpc-egress=private-ranges-only`; the ES VM has **no external IP** and a firewall rule allows `tcp:9200` only from the connector's `/28` range.
  Rationale: ADL-013 left the choice open ("VPC Peering または Cloud NAT"). A Serverless VPC Access connector is the lowest-friction, well-documented path for Cloud Run → private VM in one VPC, keeps ES off the public internet, and is trivially torn down after the hackathon. Recorded as ADL-023 in `req-phase01.md`.
  Date/Author: 2026-06-15 / Ran (proposed at deployment ExecPlan authoring)
- Decision: The two internal hops use **Cloud Run OIDC identity tokens** in production. `adk-agent-service` is deployed `--no-allow-unauthenticated` and only `fastapi-sa` holds `roles/run.invoker` on it; `fastapi-service` stays public (browser-facing) and protects `/internal/tasks/process-upload` with OIDC verification **plus** the existing `X-Internal-Secret` (Secret Manager value). The shared secret is retained as defense in depth, not removed.
  Rationale: Private service-to-service auth without exposing the ADK service; `fastapi-service` cannot be internal-only because it serves the SPA. Recorded as ADL-024.
  Date/Author: 2026-06-15 / Ran (proposed at deployment ExecPlan authoring)
- Decision: The Flutter Web client is hosted on **Firebase Hosting** (`<project>.web.app`), with real Firebase config injected via `--dart-define` at build time and `USE_EMULATORS=false`.
  Rationale: The app already depends on Firebase Auth + Firestore; Firebase Hosting gives a stable HTTPS origin and an automatic authorized domain, and `flutter-web-app/lib/config.dart` already reads every Firebase value from `--dart-define`. `req-phase01.md` only ever mentioned a Vercel domain inside a CORS example, so the hosting target was undecided. Recorded as ADL-025.
  Date/Author: 2026-06-15 / Ran (proposed at deployment ExecPlan authoring)
- Decision: Infrastructure (Cloud Run, Compute Engine ES, VPC connector, Cloud Tasks) lives in `asia-northeast1`; Vertex AI (`GOOGLE_CLOUD_LOCATION`) stays at the region where the image model `gemini-2.5-flash-image` is confirmed available (`us-central1` unless the team verifies a closer region).
  Rationale: ES is pinned to `asia-northeast1` by req §9.2; co-locating Cloud Run minimizes ES latency. Vertex model regional availability is independent and must be verified, not assumed (model availability is time-sensitive; check current Vertex AI docs at execution time).
  Date/Author: 2026-06-15 / Ran (proposed at deployment ExecPlan authoring)
- Decision: Deployment is performed with **`gcloud` CLI commands captured in this plan plus two committed helper scripts** (`scripts/deploy/deploy_fastapi.sh`, `scripts/deploy/deploy_adk.sh`), not Terraform.
  Rationale: Hackathon scope and a single throwaway environment do not justify a Terraform state backend; the existing repo convention is shell scripts under `scripts/`. Reproducibility comes from committed scripts + this plan.
  Date/Author: 2026-06-15 / Ran (proposed at deployment ExecPlan authoring)


## Outcomes & Retrospective


To be completed as milestones land. Capture: the chosen GCP project id and region; the ES VM internal IP and connector range; final Cloud Run URLs; the deployed image tags; confirmation that the production E2E reached `COMPLETED` with a generated (non-collage) image; and the teardown command actually run after the demo.


## Context and Orientation


This repository (`gen-fashion`) is a two-container application plus a Flutter Web client, organized with Hexagonal Architecture / DDD. A reader new to it needs these anchors:


- `fastapi-service/` — Python/FastAPI "edge" service. Public routes `/closet/*` (signed upload URLs, register, delete, signed download) and `/sessions/*` (create session, select source, SSE stream), plus the internal worker route `/internal/tasks/process-upload`. Config is `fastapi-service/app/config.py` (`pydantic-settings`, reads env + `.env`). Adapter selection is in `fastapi-service/app/dependencies.py` (`get_task_queue()` switches to `CloudTasksAdapter` only when `TASK_QUEUE_MODE=cloud_tasks` **and** `google_cloud_project` is set). Container entry: `fastapi-service/Dockerfile` (`uvicorn app.main:app` on `:8000`).
- `adk-agent-service/` — Python ADK ("Agent Development Kit") service (ADL-022). It runs the `styling_app` agent topology (orchestrator + ClosetAgent + StylingAgent + four tools) and exposes a FastAPI wrapper `styling_app/server.py` with `/health` and `POST /internal/run-session` (`:3000`). Config: `adk-agent-service/styling_app/config.py`. When `GOOGLE_GENAI_USE_VERTEXAI=true` it bridges `GOOGLE_CLOUD_PROJECT` / `GOOGLE_CLOUD_LOCATION` into the process env so ADK's Gemini client uses Vertex AI + Application Default Credentials. Image generation model defaults to `gemini-2.5-flash-image` (Nano Banana) in `styling_app/adapters/image_generation.py`; on failure or missing quota it falls back to a collage (ADL-005).
- `flutter-web-app/` — Flutter Web SPA. All environment- and Firebase-specific values are compile-time `--dart-define` flags read in `flutter-web-app/lib/config.dart` (`API_BASE_URL`, `USE_EMULATORS`, `FIREBASE_*`, emulator hosts). Generated `firebase_options.dart` is intentionally git-ignored; production values are passed via `--dart-define`.
- `scripts/seed_shared_closet/run_seed.py` — idempotent seeder for the shared demo closet. Flags: `--max-items-per-category N` (default 150 / env `MAX_ITEMS_PER_CATEGORY`), `--with-embeddings` (compute 768-dim `gemini-embedding-2` vectors and index them), `--source-dir PATH`, `--purge`. It downloads from Kaggle, uploads images to R2, indexes into Elasticsearch `clothing_items` (with `user_id="__shared__"`), and writes `shared_closet/*` + `shared_closets/{closetId}` Firestore docs. `item_id = uuid5(filename)` makes re-runs idempotent.
- `docker-compose.yml` — the local stack. It is the canonical reference for the env vars each service expects; the production deploy substitutes managed services for each Compose service (MinIO→R2, local ES→Compute Engine ES, emulators→real Firestore/Firebase Auth, `TASK_QUEUE_MODE=local`→`cloud_tasks`).
- `firestore.rules` — owner-only read on `users/{uid}` and `users/{uid}/closet/*`, all client writes denied. Must be deployed to the production Firebase project.
- `docs/req-phase01.md` — the source of truth for requirements and ADLs. `docs/feature-matrix-phase01.md` — implementation status. `docs/architecture-overview.md` — the implemented-vs-planned visualization. All three are kept in sync with this plan.


Terms: **R2** = Cloudflare R2 object storage (S3-compatible); locally substituted by **MinIO**. **ADC** = Application Default Credentials (Cloud Run service-account identity). **OIDC token** = a short-lived identity token Cloud Run/Cloud Tasks can mint so a caller proves which service account it is. **Serverless VPC Access connector** = the bridge that lets Cloud Run send traffic into a VPC's private IP range. **Nano Banana** = the `gemini-2.5-flash-image` model used for coordinate-image generation.


Assumed inputs the operator must have before starting: a billing-enabled GCP project id (this plan calls it `<PROJECT_ID>`; pick e.g. `gen-fashion-prod` — note the local default is `gen-fashion-local`), `Owner`/`Editor` on it, a Cloudflare account for R2, and a Kaggle API token (`~/.kaggle/kaggle.json`) for the seed. `gcloud`, `docker`, the Firebase CLI, and the Flutter SDK are installed locally.


## Plan of Work


The work is sequenced so each milestone leaves a coherent, independently verifiable state. The guiding principle is **the code is already environment-driven**, so deployment is mostly provisioning managed resources and supplying the right env/secret values — with three small, necessary code changes (the conflated internal base URL, OIDC tokens on both internal hops, and a `gcloud`-friendly config surface). No feature behavior changes.


Milestone A — GCP foundation (MD-1, MD-2, MD-9). Create/select the project, enable APIs, create three least-privilege service accounts (`fastapi-sa`, `adk-sa`, `tasks-invoker-sa`) and bind IAM, create the Firestore database (Native mode) in `asia-northeast1` and deploy `firestore.rules`, create the production Firebase project with Google sign-in enabled, create the production Cloudflare R2 bucket `gen-fashion-images` with the §8.4 CORS rule pointing at the Firebase Hosting origin, and store every secret (R2 keys, `ELASTICSEARCH_API_KEY`, `INTERNAL_TASK_SECRET`) in Secret Manager. This milestone touches no application code; it produces the identities and secrets everything else consumes.


Milestone B — Data plane (MD-3, MD-4, MD-10). Provision the `e2-medium` Elasticsearch VM (no external IP) in `asia-northeast1-a` with a 30 GB SSD, install Elasticsearch 8.x with security enabled, mint an API key, and firewall `tcp:9200` to the connector range only. Create the Serverless VPC Access connector and verify (from the VM and later from a deployed service) that ES is reachable privately and that the JP-analyzer is not required (closing the open M1-3 PoC question). Then run the seed `--with-embeddings` from inside the VPC (on the ES VM itself, which has the network path and credentials) so the shared closet exists in production R2 + ES + Firestore with vectors.


Milestone C — Services (MD-5, MD-6, MD-7, MD-8). Create an Artifact Registry Docker repo, build and push both images, and deploy both Cloud Run services with the deploy settings from req §9.1 / ADL-016 (`fastapi-service`: public, min 0 / max 10, 1 GB / 1 CPU / 60 s; `adk-agent-service`: private, min 1 / max 5, 2 GB / 1 CPU / 600 s). Create the Cloud Tasks queue `gen-fashion-embed`, flip `TASK_QUEUE_MODE=cloud_tasks`, and land the three code changes: (1) split the internal base URL so the worker task targets the fastapi URL; (2) attach OIDC tokens on both internal hops; (3) verify the OIDC bearer on the worker route. Wire each service's env + secrets and the cross-service URLs.


Milestone D — Generation + frontend (MD-11, MD-12). Confirm `gemini-2.5-flash-image` produces a real generated image on Vertex AI for the deployed `adk-agent-service` (not the collage fallback), adjusting `GOOGLE_CLOUD_LOCATION` to a region where the model is available. Build the Flutter Web release with production `--dart-define`s and deploy to Firebase Hosting; add the hosting domain to Firebase Auth authorized domains and the R2 CORS allowlist.


Milestone E — Acceptance + ops (MD-13, MD-14). Run the production E2E: open the hosted app, sign in, run a `SHARED_CLOSET` session to `COMPLETED`, and confirm a generated image. Verify the ADK event stream is queryable in Cloud Logging, confirm the Firestore `agentEvents` TTL policy (24 h, ADL-021) is active, and document/execute teardown so the throwaway VM and services can be deleted after submission.


## Concrete Steps


All `gcloud` commands assume `gcloud config set project <PROJECT_ID>` and a default region of `asia-northeast1`. Replace `<PROJECT_ID>` and Cloudflare values with the real ones. Commands are shown as indented blocks.


Milestone A — GCP foundation


1. Enable APIs (run from any directory):


    gcloud services enable \
      run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com \
      secretmanager.googleapis.com cloudtasks.googleapis.com compute.googleapis.com \
      vpcaccess.googleapis.com firestore.googleapis.com aiplatform.googleapis.com \
      logging.googleapis.com


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
    # fastapi-sa may mint OIDC tokens as tasks-invoker-sa for Cloud Tasks
    gcloud iam service-accounts add-iam-policy-binding tasks-invoker-sa@$PROJECT.iam.gserviceaccount.com \
      --member="serviceAccount:fastapi-sa@$PROJECT.iam.gserviceaccount.com" --role=roles/iam.serviceAccountTokenCreator


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


8. Create the ES VM (no external IP) and SSD disk:


    gcloud compute instances create gen-fashion-es \
      --zone=asia-northeast1-a --machine-type=e2-medium \
      --image-family=debian-12 --image-project=debian-cloud \
      --boot-disk-size=30GB --boot-disk-type=pd-ssd \
      --network=default --no-address


9. SSH in (via IAP, since there is no external IP) and install Elasticsearch 8.x:


    gcloud compute ssh gen-fashion-es --zone=asia-northeast1-a --tunnel-through-iap
    # on the VM:
    wget -qO - https://artifacts.elastic.co/GPG-KEY-elasticsearch | sudo gpg --dearmor -o /usr/share/keyrings/elasticsearch-keyring.gpg
    echo "deb [signed-by=/usr/share/keyrings/elasticsearch-keyring.gpg] https://artifacts.elastic.co/packages/8.x/apt stable main" | sudo tee /etc/apt/sources.list.d/elastic-8.x.list
    sudo apt-get update && sudo apt-get install -y elasticsearch
    # /etc/elasticsearch/elasticsearch.yml: network.host: 0.0.0.0 ; discovery.type: single-node ; xpack.security.enabled: true
    sudo systemctl enable --now elasticsearch
    # mint an API key for the app and store it in Secret Manager (MD-2):
    sudo /usr/share/elasticsearch/bin/elasticsearch-create-enrollment-token -s node   # (or use the security API to create an API key)


    Take the resulting API key and, from the workstation, store it:


    printf '%s' "<ELASTICSEARCH_API_KEY>" | gcloud secrets create ELASTICSEARCH_API_KEY --data-file=-


10. Create the Serverless VPC Access connector and a firewall rule that allows only the connector range to reach ES:


    gcloud compute networks vpc-access connectors create gen-fashion-conn \
      --region=asia-northeast1 --network=default --range=10.8.0.0/28
    gcloud compute firewall-rules create allow-es-from-connector \
      --network=default --direction=INGRESS --action=ALLOW \
      --rules=tcp:9200 --source-ranges=10.8.0.0/28


11. Verify private connectivity (MD-4): from the ES VM, `curl -k -u elastic:<pw> https://localhost:9200/_cluster/health` returns `status: green|yellow`; after MD-7, confirm `adk-agent-service` logs show successful ES queries. Record the JP-analyzer finding (expected: not required for the curated demo set), closing the M1-3 PoC question.


12. Run the full vector seed (MD-10) from inside the VPC (run it on the ES VM, which has the private ES path; export the prod R2 + Firestore + Vertex env, place the Kaggle token, then):


    MAX_ITEMS_PER_CATEGORY=150 python scripts/seed_shared_closet/run_seed.py --with-embeddings


    Expect a non-zero `created` on first run (~210 total: 70 per closet across `adult-01`, `adult-02`, `child-01`) and `created=0` on a second run (idempotent). Verify ES has `embedding` populated: `GET clothing_items/_count` returns ≥ 210 and a `knn` probe returns shared docs carrying `embedding`.


Milestone C — Services


13. Create the Artifact Registry repo and build/push both images:


    gcloud artifacts repositories create gen-fashion --repository-format=docker --location=asia-northeast1
    REPO=asia-northeast1-docker.pkg.dev/<PROJECT_ID>/gen-fashion
    gcloud builds submit fastapi-service --tag $REPO/fastapi-service:v1
    gcloud builds submit adk-agent-service --tag $REPO/adk-agent-service:v1


14. Land the remaining cloud-auth code changes (see Interfaces and Dependencies for exact edits). Note: `fastapi_internal_base_url: str | None = None` is already in `config.py` and `local_task_queue.py` already uses it (both landed during the local re-verification, 2026-06-21); only the cloud-path changes below remain.
    - Fix `cloud_tasks_adapter.py` line 28: change `adk_internal_base_url` → `fastapi_internal_base_url` (with the same `or adk_internal_base_url` fallback as `local_task_queue.py`) so the Cloud Tasks worker URL targets the fastapi service.
    - Add `internal_invoker_sa: str | None = None` to `fastapi-service/app/config.py`; in `CloudTasksAdapter`, uncomment and correct the `oidc_token` block — set `service_account_email=internal_invoker_sa` and `audience=fastapi_internal_base_url` (the existing comment says `adk_internal_base_url` — that is wrong); in `HttpAgentRunAdapter`, attach a Cloud Run OIDC identity token (audience = `adk_internal_base_url`) via `google.auth` when running in the cloud.
    - In `fastapi-service/app/auth.py` `require_internal_secret`, additionally accept a verified Cloud Run OIDC bearer (verify the token's audience + that the SA email is `tasks-invoker-sa`); keep the shared secret as defense in depth.
    Rebuild/push `:v2` after these edits.


15. Create the Cloud Tasks queue:


    gcloud tasks queues create gen-fashion-embed --location=asia-northeast1


16. Deploy `adk-agent-service` (private):


    gcloud run deploy adk-agent-service --image $REPO/adk-agent-service:v2 \
      --region=asia-northeast1 --service-account=adk-sa@<PROJECT_ID>.iam.gserviceaccount.com \
      --no-allow-unauthenticated --min-instances=1 --max-instances=5 --memory=2Gi --cpu=1 --timeout=600 \
      --vpc-connector=gen-fashion-conn --vpc-egress=private-ranges-only \
      --set-env-vars=GOOGLE_CLOUD_PROJECT=<PROJECT_ID>,GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_LOCATION=us-central1,AGENT_MODEL=gemini-2.5-flash,ELASTICSEARCH_URL=https://<es-vm-internal-ip>:9200,R2_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com,R2_PUBLIC_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com,R2_BUCKET_NAME=gen-fashion-images \
      --set-secrets=ELASTICSEARCH_API_KEY=ELASTICSEARCH_API_KEY:latest,R2_ACCESS_KEY_ID=R2_ACCESS_KEY_ID:latest,R2_SECRET_ACCESS_KEY=R2_SECRET_ACCESS_KEY:latest,INTERNAL_TASK_SECRET=INTERNAL_TASK_SECRET:latest


    Then grant the caller: `gcloud run services add-iam-policy-binding adk-agent-service --region=asia-northeast1 --member="serviceAccount:fastapi-sa@<PROJECT_ID>.iam.gserviceaccount.com" --role=roles/run.invoker`.


17. Deploy `fastapi-service` (public), wiring the ADK URL and the new fastapi-internal URL (its own URL) and OIDC invoker:


    ADK_URL=$(gcloud run services describe adk-agent-service --region=asia-northeast1 --format='value(status.url)')
    gcloud run deploy fastapi-service --image $REPO/fastapi-service:v2 \
      --region=asia-northeast1 --service-account=fastapi-sa@<PROJECT_ID>.iam.gserviceaccount.com \
      --allow-unauthenticated --min-instances=0 --max-instances=10 --memory=1Gi --cpu=1 --timeout=60 \
      --vpc-connector=gen-fashion-conn --vpc-egress=private-ranges-only \
      --set-env-vars=GOOGLE_CLOUD_PROJECT=<PROJECT_ID>,FIREBASE_PROJECT_ID=<PROJECT_ID>,GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_LOCATION=us-central1,ELASTICSEARCH_URL=https://<es-vm-internal-ip>:9200,R2_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com,R2_PUBLIC_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com,R2_BUCKET_NAME=gen-fashion-images,TASK_QUEUE_MODE=cloud_tasks,CLOUD_TASKS_QUEUE_EMBED=gen-fashion-embed,CLOUD_TASKS_LOCATION=asia-northeast1,ADK_INTERNAL_BASE_URL=$ADK_URL,INTERNAL_INVOKER_SA=tasks-invoker-sa@<PROJECT_ID>.iam.gserviceaccount.com \
      --set-secrets=ELASTICSEARCH_API_KEY=ELASTICSEARCH_API_KEY:latest,R2_ACCESS_KEY_ID=R2_ACCESS_KEY_ID:latest,R2_SECRET_ACCESS_KEY=R2_SECRET_ACCESS_KEY:latest,INTERNAL_TASK_SECRET=INTERNAL_TASK_SECRET:latest


    Capture `FASTAPI_URL`, then redeploy `fastapi-service` once more setting `FASTAPI_INTERNAL_BASE_URL=$FASTAPI_URL` (the worker task targets the fastapi service's own URL). Grant `tasks-invoker-sa` `roles/run.invoker` on `fastapi-service` so the OIDC-authenticated Cloud Task is accepted.


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


21. Ops (MD-14). Confirm ADK events appear in Cloud Logging (`gcloud logging read 'resource.labels.service_name="adk-agent-service"' --limit=20`). Ensure the Firestore TTL policy on `sessions/{id}/agentEvents.ttlAt` (24 h, ADL-021) exists: `gcloud firestore fields ttls update ttlAt --collection-group=agentEvents --enable-ttl`. Write the teardown steps into `scripts/deploy/teardown.sh` (delete both Cloud Run services, the VM, the connector, the firewall rule, the queue, the Artifact Registry repo) and dry-run it.


## Validation and Acceptance


Local pre-deploy gate (run before building images, from repo root): `docker-compose run --rm fastapi-service pytest` (expect the ME baseline 68 passed), `cd adk-agent-service && pytest -q` (expect 41 passed), `cd flutter-web-app && flutter analyze` (no issues) and `flutter test` (expect 14 passed). The code edits in step 14 must keep all of these green; add/adjust unit tests for the OIDC header attachment and the `cloud_tasks_adapter.py` URL fix in `fastapi-service/app/adapters/`.


Per-milestone acceptance, phrased as observable behavior:
- A: `gcloud secrets list` shows `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `ELASTICSEARCH_API_KEY`, `INTERNAL_TASK_SECRET`; `firebase deploy --only firestore:rules` succeeds; the R2 bucket returns the configured CORS headers on an `OPTIONS` preflight from the hosting origin.
- B: `curl` to ES from the VM returns cluster health `green`/`yellow`; the seed prints a non-zero `created` then `created=0` on re-run; `GET clothing_items/_count` ≥ ~90 and a `knn` query returns shared items carrying `embedding`.
- C: `curl https://<FASTAPI_URL>/health` → `200`; the ADK service rejects an unauthenticated call (`403`) but accepts the OIDC-authenticated call from `fastapi-service`; a closet upload drives a Firestore doc to `status: READY` (proving the Cloud Task reached the fastapi worker URL, i.e. the base-url split works).
- D: a `SHARED_CLOSET` run yields a `styleResult.coordinateImageUrl` that opens a **generated** image; `adk-agent-service` logs show the Nano Banana path, not the collage fallback. The hosted SPA loads and signs in with Google.
- E: the browser E2E reaches `COMPLETED`; ADK events are visible in Cloud Logging; the `agentEvents` TTL policy is `enabled`; `teardown.sh` exists and its dry run lists exactly the resources created here.


Milestone acceptance overall: opening the public Firebase Hosting URL and completing a `SHARED_CLOSET` coordination to a generated image is the definition of done — this is `req-phase01.md` §15 Phase 1a #6 satisfied against deployed infrastructure.


## Idempotence and Recovery


Resource-creation commands are safe to re-run if you treat "already exists" as success (or `gcloud ... describe` first). `gcloud run deploy` is fully idempotent — it creates a new revision each time, so re-running with corrected env/secrets is the normal recovery path; roll back with `gcloud run services update-traffic <svc> --to-revisions=<prev>=100`. The seed is idempotent by design (`uuid5(filename)`); `--purge` clears prior shared data before reseeding. Secrets are versioned; add a new version rather than recreating. The ES VM is the one piece of mutable state — snapshot the disk before risky changes. If private connectivity fails, the most common causes are (a) the firewall source range not matching the connector `/28`, (b) `--vpc-egress` not set to `private-ranges-only`, or (c) using the VM's name instead of its internal IP in `ELASTICSEARCH_URL`.


## Artifacts and Notes


Helper scripts to commit under `scripts/deploy/`: `deploy_fastapi.sh`, `deploy_adk.sh`, `teardown.sh` (thin wrappers over the `gcloud` commands above, parameterized by `PROJECT_ID`/region/image tag). Keep the canonical command list in this plan as the source of truth; the scripts are conveniences, not a second spec. Record the final URLs, the ES internal IP, and the deployed image tags in `Outcomes & Retrospective` when the milestone completes.


No secret values belong in this file, the scripts, commits, or logs — only Secret Manager names. The `.env.example` already separates local defaults from the "[4] 本番デプロイ時のみ" block; mirror any new variable there (`FASTAPI_INTERNAL_BASE_URL`, `INTERNAL_INVOKER_SA`) with placeholder values.


## Interfaces and Dependencies


GCP services: Cloud Run (two services), Artifact Registry (image storage), Cloud Build (image builds), Secret Manager (secrets), Cloud Tasks (embedding worker queue), Compute Engine (ES VM), Serverless VPC Access (private connectivity), Firestore (Native mode), Vertex AI / `aiplatform` (Gemini analysis, `gemini-embedding-2`, `gemini-2.5-flash-image`), Cloud Logging (ADK event stream). External: Cloudflare R2 (object storage) and Kaggle (dataset for the seed). Tooling: `gcloud`, `docker`/Cloud Build, Firebase CLI, Flutter SDK.


Code changes remaining (all in `fastapi-service/`; `config.py` `fastapi_internal_base_url` field and `local_task_queue.py` URL routing are already done from the local re-verification):
- `app/config.py`: add `internal_invoker_sa: str | None = None` (only this remains; `fastapi_internal_base_url` is already present).
- `app/adapters/cloud_tasks_adapter.py`: fix line 28 to use `fastapi_internal_base_url or adk_internal_base_url` (not bare `adk_internal_base_url`) for the `process-upload` URL; uncomment and correct the `oidc_token` block (change the audience from `adk_internal_base_url` to `fastapi_internal_base_url` — the existing comment has the wrong value). `app/adapters/local_task_queue.py` already uses `fastapi_internal_base_url`; no further change there.
- `app/adapters/adk_agent_run.py`: when `internal_invoker_sa`/cloud mode is configured, attach a Cloud Run OIDC identity token (`google.auth` ID token, audience = `adk_internal_base_url`) to the `/internal/run-session` call.
- `app/auth.py` `require_internal_secret`: accept a verified Cloud Run OIDC bearer (audience + SA email check) in addition to the shared secret.


These code changes preserve `make dev` behavior because the new settings are unset locally (the code falls back to the existing shared-secret + `adk_internal_base_url` paths).


Requirements traceability: MD-1/MD-2 ← req §9.1, §12.1/§12.2, ADL-012; MD-3/MD-4 ← req §9.2, ADL-013, ADL-023, M1-3; MD-5/MD-6/MD-7 ← req §9.1, ADL-016; MD-8 ← req §6.8, §10.3, ADL-024; MD-9 ← req §8.4, ADL-014; MD-10 ← req §15 Phase 1a #7, §16.4, ADL-010, M3-2; MD-11 ← req §6.5, ADL-005, M4-7/M5-6; MD-12 ← req §11, ADL-025; MD-13 ← req §15 Phase 1a #6; MD-14 ← req §9.3, ADL-021.


## Revision Notes


2026-06-15 — Initial authoring. Milestones A–E defined; deployment requirements MD-1…MD-14 scoped; ADLs added to `req-phase01.md`; architecture overview synchronized.

2026-06-21 — Local re-verification completed; three bugs found and fixed (MD-8 local base-URL split, Firestore project binding, `closetId` keyword mapping). MD-10 de-risked (embedding model corrected to `gemini-embedding-001`, `adk_run_timeout_seconds` raised to 90, `STREAM_MAX_SECONDS` raised to 150).

2026-06-25 — Synchronized with completed ME ExecPlan. Changes: (1) step 4 firebase deploy command now includes `firestore:indexes` (ME-7 composite index is committed in `firestore.indexes.json`); (2) step 12 expected seed count updated from ~90 to 210 items (70/70/70, from ME shared-closet expansion); (3) step 14 clarified — `fastapi_internal_base_url` in `config.py` and `local_task_queue.py` URL routing are already done; remaining is `cloud_tasks_adapter.py` URL fix (line 28 still uses `adk_internal_base_url`), OIDC token with corrected audience, `internal_invoker_sa` in config, and OIDC bearer in `auth.py`; (4) Validation baselines updated to 68 FastAPI / 41 ADK / 14 Flutter; (5) Interfaces and Dependencies code-changes list updated to reflect what is already done vs. remaining.
