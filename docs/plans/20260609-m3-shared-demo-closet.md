# M3 — Shared Demo Closet


This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.


This plan follows `PLANS.md` at `/Users/ran/my-app/PLANS.md`.


## Purpose / Big Picture


M3 gives gen-fashion a **pre-seeded, read-only shared closet** so a brand-new user — or a hackathon judge —
can try the coordination experience **without uploading any clothes**. Today the only way to get clothing
into the system is the M2 personal-closet upload flow; a first-time user with an empty closet has nothing to
coordinate. After M3, selecting the `SHARED_CLOSET` source returns real candidate garments (sampled from a
public, CC BY-SA 4.0 dataset) complete with the required attribution.

Concretely, M3 delivers four things (feature-matrix M3-1…M3-4): an **idempotent seeding script**
(`scripts/seed_shared_closet/run_seed.py`) that downloads the dataset, samples it, uploads images to R2/MinIO,
optionally embeds them, indexes them into Elasticsearch, and writes `shared_closet` documents to Firestore;
the **seeded data itself** (`user_id: "__shared__"` in ES, `shared_closet/*` in Firestore, objects in R2);
the **`SharedClosetSearchAdapter`** (a `ClothingSearchPort` implementation that returns shared candidates
filtered by `user_id: "__shared__"`); and the **attribution** surface (the `CandidateItem.attribution` field
plus a Flutter footer / "About the shared closet" modal) required by the CC BY-SA 4.0 licence.

**Why this is the right "next" plan, and how it sits next to M4.** The roadmap (architecture-overview §7) has
two unblocked siblings feeding M5: **M3** (shared closet) and **M4** (ADK agents). Neither blocks the other —
both depend only on M0/M1/M2, which are Done. M3 is the smaller, lower-risk track (a batch script + one
read adapter + a footer; no new agent runtime), and it directly **enriches the M4 demo**: once the shared
closet is seeded, the M4 agents can demonstrate the hero "try without uploading" path against
`SHARED_CLOSET`, instead of only the developer's hand-uploaded `CLOSET`. Recommended working order is **M3
first (or in parallel), then M4**. (Note: the user's standing "one ExecPlan at a time" preference means you
may wish to treat M4 as *queued behind M3*; both plan files exist, but only M3 need be actively worked.)

**Scope boundary forced by M1-3.** The M1-3 re-scope decision (M1 ExecPlan Decision Log) explicitly **deferred
the shared-closet *vector* seeding and the GCE-hosted Elasticsearch to the deployment phase** (~1–2 weeks
before submission), and committed to **keyword-first** search on the local Docker ES until then. M3 therefore
splits cleanly: the **script, the adapter, the attribution, and a keyword-first seeded *subset* on local
infra** are built and verified **now**; the **full 2,000–3,000-item seed with embedding vectors on the GCE ES**
is a documented **deployment-phase re-run of the same script** (`--with-embeddings`, larger
`MAX_ITEMS_PER_CATEGORY`). The script is built deployment-ready from day one so that re-run is a config change,
not new code.

**Acceptance (observable):** `python scripts/seed_shared_closet/run_seed.py` (against `make dev`) populates
Firestore `shared_closet/*`, ES `clothing_items` docs with `user_id: "__shared__"`, and R2/MinIO objects under
`__shared__/closet/`; a second run produces **no duplicates** (idempotent); `SharedClosetSearchAdapter`
returns `CandidateItem`s for `SHARED_CLOSET` each carrying `attribution="Clothing Dataset (CC BY-SA 4.0)"`;
and the Flutter app shows the attribution footer/modal. See **Validation and Acceptance**.


## Progress


**▶ Current status (2026-06-10, latest — read this first).** The code re-scope to **3 demo closets**
(Adult×2 + Child×1, 30 items each; see Decision Log) is **implemented and the multi-closet live seed is
now COMPLETE**. The seed ran against local infra (`docker-compose up -d elasticsearch minio
firestore-emulator`), all three stores verified at 90 items, idempotency confirmed, adapter pytest (8) +
`flutter analyze` re-run green. **M3-2 is ✅ for the local subset**; the full vector seed on GCE ES stays
deployment-deferred (M1-3). Precise timeline:

1. ✅ M3 code (script + adapter + attribution) built; adapter unit tests (8) pass; `flutter analyze` clean.
2. ✅ **First live seed ran** against local `make dev` (infra-only: ES+MinIO+Firestore emulator) →
   **360 docs / 18 categories** from the high-res set. This surfaced the `images.csv` label-file fix and
   the underwear/junk inclusion (see Surprises). **Update (2026-06-10):** this stale 360-doc data was still
   present at reseed time (compose has no data volumes but the containers had not been recreated), so
   `--purge` deleted it (ES 360 + MinIO 360) before the clean multi-closet seed.
3. ✅ **Re-scoped & rewrote `run_seed.py`** for 3 closets: `kids`-split pools, `_CLOSET_QUOTA`
   auto-composition, `closetId`/`closetKind` on ES+Firestore docs, `shared_closets/{closetId}` metadata,
   `--purge` extended. **Builder dry-run verified (no store writes): 3×30 = 90 items, adult closets
   disjoint, no underwear/junk.**
4. ✅ Docs synced: req §16.1/§16.2/§16.4 + §8.1/§8.2, feature-matrix M3-2 → ✅, this plan, architecture-overview.
5. ✅ **DONE (2026-06-10)** — multi-closet live seed (`--purge` → reseed → verify → idempotency), adapter
   pytest re-run (8 passed), and `flutter analyze` re-check (No issues found) all complete. **created=90,
   per-closet 30/30/30, idempotent re-run created=0/skipped=90.** Evidence in Artifacts. M3-2 → ✅ (local).

Phase checklist (✅ = done; the single-closet design in 0/1 was superseded by step 3):

- [x] Phase 0 — Seeding-script scaffold + dataset acquisition (M3-1)
  - [x] `scripts/seed_shared_closet/` with `run_seed.py`, `requirements.txt`, `.env.example`, `README.md` (self-contained per req §16.4).
  - [x] Kaggle download of `agrigorev/clothing-dataset-full` (~6.5 GB; uses high-res `images_original/` + `images.csv` labels) **and** a `--source-dir` local-images fallback. Cache-hit fixed so re-runs don't re-download.
  - [x] Config via env/flags: ES URL, R2 endpoint/creds/bucket, Firestore target, `--with-embeddings` (default off locally). `--purge` flag added (now clears `shared_closet` + `shared_closets`).
- [x] Phase 1 — Idempotent multi-closet seeding pipeline (M3-1, M3-2) — **code done; live seed run & verified (2026-06-10)**
  - [x] **Re-scoped to 3 closets:** `kids`-split adult/child pools + `_CLOSET_QUOTA` auto-composition (tops8/outer4/bottoms6/dress4/shoes5/hat3); same-kind closets draw disjoint, deterministic items.
  - [x] Per item: deterministic `item_id` (uuid5 of filename) → R2 PUT `__shared__/closet/{item_id}.jpg` → optional embedding → ES upsert (`user_id:"__shared__"`, `is_shared:true`, `closetId`, `closetKind`) → Firestore `shared_closet/{item_id}` set (+ `shared_closets/{closetId}` metadata).
  - [x] Builder validated by **dry-run** (90 items, disjoint, no underwear/junk); `py_compile` clean.
  - [x] **Live multi-closet seed against local infra (2026-06-10): created=90, closets 30/30/30, idempotent re-run created=0/skipped=90.** Evidence in Artifacts. (The superseded single-closet form had run live: 360 docs, purged first.)
- [x] Phase 2 — `SharedClosetSearchAdapter` (M3-3) — **unchanged by the re-scope** (still returns all `__shared__`)
  - [x] `search_by_source` / `search_all_sources` for `SHARED_CLOSET`: ES bool filter on `user_id:"__shared__"`, keyword `should` on `tags`/`category`, signed image URLs, fail-soft.
  - [x] Unit tests pass in `tests/adapters/test_shared_closet_search.py` (mocked ES + fake storage).
- [x] Phase 3 — Attribution (M3-4)
  - [x] Backend: `CandidateItem.attribution = "Clothing Dataset (CC BY-SA 4.0)"` set in adapter.
  - [x] Flutter: `lib/shared/attribution.dart` — `AttributionFooter` + `showSharedClosetAboutDialog`; wired into `closet_screen.dart`. `url_launcher: ^6.3.1` added.
- [x] Phase 4 — Validation & acceptance — **complete (local subset; 2026-06-10)**
  - [x] Adapter unit tests pass (8); `flutter analyze`: No issues found (re-run 2026-06-10).
  - [x] Feature matrix updated: M3-1/M3-3/M3-4 → ✅; M3-2 → ✅ (local subset; full vector seed deployment-deferred).
  - [x] **Multi-closet live seed + 3-store verification + idempotency + re-run of pytest/`flutter analyze` — DONE.** See Artifacts for evidence.


## Surprises & Discoveries


- The Kaggle dataset CSV uses column name `image` (not `filename`); the parser handles multiple name variants
  (`image`, `filename`, `image_id`) for robustness.
- The label CSV may unzip alongside the images rather than into a sibling directory; the script probes
  multiple candidate paths.
- `url_launcher` was absent from `pubspec.yaml`; added `^6.3.1` — resolved cleanly, `flutter analyze` clean.
- **Live-seed findings (2026-06-09).** (a) The dataset's label file is **`images.csv`** (columns
  `image`, `sender_id`, `label`, `kids`), **not** `image_labels_merged.csv` — `run_seed.py` was patched
  to discover `images.csv` and probe `images_compressed/`/`images_original/`. (b) The download is
  **6.5 GB** (`images_compressed/` 165 MB + `images_original/` 6.4 GB, 5,762 images each); Kaggle has no
  folder-level partial download, so both resolutions arrive in the zip. (c) The Kaggle CLI reports the
  licence as **`CC0-1.0`**, while req §16.3 / ADL-010 fix the attribution as `CC BY-SA 4.0` — discrepancy
  flagged for separate confirmation; attribution string unchanged for now.
- The first subset seed (20/category) produced 360 docs across 18 categories — but those included
  underwear/innerwear (`Undershirt`, `Body`) and the junk label `Other` (it slipped through because
  `_SKIP_LABELS` had `"Others"` plural while the data uses `"Other"` singular). Per user direction these
  are now excluded (see Decision Log).
- req-phase01.md §16.2 / §16.4 were updated (image variant, category exclusion, 500–1,000 target,
  `images.csv`) — superseding the earlier "no req change needed" note.


## Decision Log


- Decision: **Replace the single shared closet with 3 realistic demo closets (Adult×2 + Child×1, ~30
  items each), composed automatically by category quota.** Rationale (user, 2026-06-09): a closet with
  100+ garments is unrealistic; small curated-size wardrobes demo better. The dataset has **no gender
  column** (`images.csv` = `image, sender_id, label, kids`), so men's/women's is impossible; we segment by
  the `kids` flag into adult/child. Data model: items keep `user_id:"__shared__"` and gain
  `closetId`/`closetKind`; a `shared_closets/{closetId}` metadata collection (kind/displayName/itemCount)
  is added. **Closet-selection UI + adapter generalization are deferred to M5** (user chose "data only"
  now) — so M3-3 `SharedClosetSearchAdapter` is unchanged and still returns all `__shared__` items.
  Composition is auto via `_CLOSET_QUOTA` (tops 8 / outer 4 / bottoms 6 / dress 4 / shoes 5 / hat 3);
  same-kind closets draw disjoint, deterministic items (idempotent). req §16.1/§16.2/§16.4 and §8.1/§8.2
  updated. Dry-run verified: 3×30 = 90 items, adult closets non-overlapping, no underwear/junk.
  Date/Author: 2026-06-09 / User + Claude (Opus 4.8).

- Decision: **For the shared closet, use the high-resolution `images_original/` (not `images_compressed/`),
  exclude non-styling categories, and target 500–1,000 items for the hackathon demo.** Rationale (user,
  2026-06-09): the demo only needs 500–1,000 garments, so compression is unnecessary and high-quality
  images present better; underwear/innerwear (`Undershirt`, `Body`) and junk labels (`Other`, `Others`,
  `Not sure`, `Skip`) add no styling value and are dropped. `Hat`/`Shoes` are kept (visually meaningful
  accessories). req §16.2 / §16.4 updated accordingly. Implementation: extend the seed's skip-list and
  point the image source at `images_original/`; re-seed after a `--purge` so the excluded items are removed.
  Date/Author: 2026-06-09 / User + Claude (Opus 4.8).

- Decision: **Build M3 against local infra now (keyword-first, seeded subset); defer the full 2,000+ vector
  seed on GCE Elasticsearch to the deployment phase.** This is the direct application of the **M1-3** re-scope
  (M1 ExecPlan Decision Log): vector hybrid + GCE ES + shared-closet embedding seeding were deferred, with
  keyword-first on local Docker ES committed for the MVP. The seeding script is written deployment-ready
  (`--with-embeddings`, configurable `MAX_ITEMS_PER_CATEGORY` and targets) so the deployment-phase full seed
  is a re-run, not new code.
  Date/Author: 2026-06-09 / Claude (Opus 4.8).

- Decision: **The seed script is self-contained (its own `requirements.txt`), per req §16.4 — it does not
  import `fastapi-service/app`.** It writes to the **same** R2 bucket, ES `clothing_items` mapping, and
  Firestore `shared_closet` shape the app reads (the shared contract is the data schema, not Python classes).
  Rationale: matches the established PoC/script convention (`poc/*`, `scripts/m2_closet_smoke.py`), keeps the
  batch tool runnable with a single `pip install`, and avoids coupling a one-shot script to the service's
  dependency graph.
  Date/Author: 2026-06-09 / Claude (Opus 4.8).

- Decision: **`item_id = uuid5(NAMESPACE_URL, "<dataset>:<source_filename>")`** — a deterministic, UUID-shaped
  id. Satisfies the §16.4 idempotency requirement ("item_id from the source image filename hash") while
  staying consistent with the UUID ids used everywhere else (R2 keys, ES `_id`, Firestore doc id).
  Date/Author: 2026-06-09 / Claude (Opus 4.8).

- Decision: **`SharedClosetSearchAdapter` uses its own `AsyncElasticsearch` client; it does not modify the
  M2-9 `ElasticsearchEmbeddingRepository`.** M2 is Done and E2E-verified; the shared search needs a different
  filter (`user_id:"__shared__"`), a different `CandidateItem.source` (`SHARED_CLOSET`), and the attribution
  field, so a focused new adapter is cleaner than widening the verified M2 repo.
  Date/Author: 2026-06-09 / Claude (Opus 4.8).

- Decision: **No `req-phase01.md` change is needed for M3.** Everything M3 builds is already specified in req
  §16 (Shared Demo Closet), §6.3 (routing), §8.1 (`shared_closet` schema), §8.2 (ES mapping), §16.3
  (attribution), and ADL-010. M3 introduces no new architecture decision.
  Date/Author: 2026-06-09 / Claude (Opus 4.8).

- Decision: **Use Vertex AI (ADC / service account) instead of the Gemini API (API key) for all Gemini calls
  in the seed script.** The user holds Google Cloud credits from the hackathon organiser and wishes to draw
  them down first; a budget alert is already configured. Vertex AI is the service-account-based Google Cloud
  path; the Gemini API (api.generativeai.google.com) is the API-key path. Both are accessed through the same
  `google-genai` SDK — the only difference is initialisation: `genai.Client(vertexai=True,
  project=GOOGLE_CLOUD_PROJECT, location=GOOGLE_CLOUD_LOCATION)`. Model (`gemini-embedding-2`, 768 dims) and
  call semantics are unchanged. Locally, authentication reuses the existing ADC credential
  (`gcloud auth application-default login`), the same mechanism already used for Firestore. `.env.example`
  gains `GOOGLE_CLOUD_LOCATION` (default `us-central1`); `GOOGLE_CLOUD_PROJECT` is already present.
  Date/Author: 2026-06-09 / User + Claude (Sonnet 4.6).


## Outcomes & Retrospective


**M3 complete for the local subset (incl. multi-closet re-scope); multi-closet live seed run & verified (2026-06-10).**

Adapter + attribution are done and verified. The seeding script is done **and re-scoped** to 3 demo
closets; the **live seed has now run** against local infra — 90 items across `adult-01`/`adult-02`/`child-01`
(30 each), verified in ES + MinIO + Firestore, idempotent on re-run, with adapter pytest (8) and
`flutter analyze` green. **M3-2 is ✅ for local.** See the **Current status** block and **Artifacts** for
the exact evidence.

- **Seeding script** (`scripts/seed_shared_closet/run_seed.py`): self-contained, idempotent. Builds the 3
  demo closets (`adult-01`, `adult-02`, `child-01`) via `kids`-split pools + `_CLOSET_QUOTA`
  auto-composition (~30 items each, ~90 total). `item_id = uuid5(NAMESPACE_URL, "kaggle:…:{filename}")`;
  each file maps to exactly one closet, so re-runs upsert. Writes `closetId`/`closetKind` to ES+Firestore
  and `shared_closets/{closetId}` metadata. Uses high-res `images_original/` + `images.csv` labels;
  underwear (`Undershirt`,`Body`) and junk (`Other`) excluded. `--with-embeddings` is deployment-only.
- **`SharedClosetSearchAdapter`**: unchanged by the re-scope (still queries all `user_id:"__shared__"`).
  Keyword-first, fail-soft, attribution set on every `CandidateItem`. Unit tests pass (mocked).
- **Attribution**: `attribution = "Clothing Dataset (CC BY-SA 4.0)"`; Flutter `AttributionFooter` +
  `showSharedClosetAboutDialog` wired into the closet screen. `flutter analyze`: No issues found.

**What remains:**
1. ✅ **(Done 2026-06-10)** Multi-closet live seed against local infra: `--purge` (cleared the stale
   360-doc single-closet data) → reseed (90 items) → verified per-`closetId` counts (30/30/30) →
   idempotency re-run (created=0) → re-ran adapter pytest (8 passed) + `flutter analyze` (clean).
   **M3-2 → ✅** for local; feature-matrix + architecture-overview synced.
2. **(Deployment phase, M1-3 deferral)** Re-run with `--with-embeddings` against the GCE-hosted ES to add
   768-dim vectors — a config change (`ELASTICSEARCH_URL`, `GOOGLE_APPLICATION_CREDENTIALS`), no new code.
3. **(M5 handoff)** Closet-selection UI + adapter `closetId` filter (the data model is ready now).
4. **(Open)** Licence discrepancy: Kaggle CLI reports `CC0-1.0` vs req's `CC BY-SA 4.0` — confirm separately.


## Context and Orientation


gen-fashion is a hexagonal/DDD monorepo under `/Users/ran/my-app/gen-fashion`. Source of truth:
`docs/req-phase01.md`; status tracker: `docs/feature-matrix-phase01.md`; visualization:
`docs/architecture-overview.md`. M0/M1/M2 are Done; M3 (this plan) and M4 are the unblocked siblings feeding
M5.

**What M3 builds, and the req that defines it:**

- **Seeding script (M3-1, req §16.4, §15 Phase 1a #7).** `scripts/seed_shared_closet/run_seed.py` — a single,
  self-contained file runnable with `pip install -r requirements.txt`, a Kaggle API token
  (`~/.kaggle/kaggle.json`), and `GOOGLE_CLOUD_PROJECT`. Flow (req §16.4): Kaggle download → category sampling
  → R2 upload → Gemini embedding → ES indexing → Firestore `shared_closet` write. Idempotent; controllable via
  `MAX_ITEMS_PER_CATEGORY` (default 150). The convention to follow is the existing self-contained scripts:
  `poc/image_generation/run_poc.py`, `poc/adk_event_stream/run_poc.py`, and `scripts/m2_closet_smoke.py`
  (which already talks to local MinIO via `boto3` and the local services).
- **Dataset (req §16.2).** Kaggle `agrigorev/clothing-dataset-full`, **CC BY-SA 4.0** (commercial use allowed,
  attribution + share-alike required). 20+ categories (Blazer, Blouse, Dress, Hoodie, Pants, Shirt, Shorts,
  Skirt, T-Shirt, …); take up to 150/category, ~2,000–3,000 total; prefer high-confidence labels from
  `image_labels_merged.csv`.
- **Data targets (req §8.1, §8.2).** Firestore `shared_closet/{itemId}` = `{ imageUrl, category, tags[],
  season, colors[], embeddingId, datasetSource: "kaggle:agrigorev/clothing-dataset-full", originalLabel,
  createdAt }`. Elasticsearch `clothing_items` (the **same** index M2 uses) with `user_id: "__shared__"`,
  `is_shared: true`. R2 bucket `gen-fashion-images`, object key `__shared__/closet/{itemId}.jpg` (mirrors the
  user pattern `{userId}/closet/{itemId}.jpg`).
- **Domain rules (req §16.5, ADL-010).** Only the seed script writes `shared_closet`; shared items are **not**
  counted against `MAX_CLOSET_IMAGES_PER_USER`; `SHARED_CLOSET` is **always** selectable; source-selection
  order is `SHARED_CLOSET` / `CLOSET` (only if the user has data) / `RAKUTEN`.
- **`SharedClosetSearchAdapter` (M3-3, req §5.2, §6.3, ADL-010).** Implements `ClothingSearchPort` (defined in
  `fastapi-service/app/ports/clothing_search.py`: `search_by_source(user_id, source, query, limit)` and
  `search_all_sources(...)` returning `List[CandidateItem]`). The current
  `fastapi-service/app/adapters/shared_closet_search.py` is a stub (`NotImplementedError("Implement in M3-3")`)
  — this plan implements it. `CandidateItem`
  (`fastapi-service/app/domain/styling/value_objects.py`) = `{ item_id, source, image_url, tags, attribution }`.
- **Attribution (M3-4, req §16.3).** `CandidateItem.attribution = "Clothing Dataset (CC BY-SA 4.0)"` for shared
  items; a Web GUI footer / "About the shared closet" modal: "共有クローゼットの画像は Clothing Dataset
  (CC BY-SA 4.0) を使用しています" with the Kaggle link.

**What M3 does NOT do (boundaries):**

- It does not implement `SearchCandidateItemsUseCase` (M5-5) — that use case *routes* to this adapter; M3 only
  provides the adapter + data. It does not implement the `search_closet` **agent tool** (M4-6) — that is M4
  (the agent tool reads the same seeded `__shared__` ES docs). It does not build the result-UI candidate cards
  (M5-10); per-card attribution rendering is an M5 handoff. It does not provision the GCE ES or run the
  full-scale embedding seed (M1-3 deployment phase).

**Existing code M3 reads for schema parity (do not modify):**
`fastapi-service/app/adapters/elasticsearch_embedding_repo.py` (the `clothing_items` mapping + the
`user_id`/`is_shared`/`embedding` fields), `fastapi-service/app/config.py` (`embedding_model="gemini-embedding-2"`,
`embedding_dimensions=768`, `clothing_items_index="clothing_items"`, `r2_bucket_name`), and
`scripts/m2_closet_smoke.py` (local `boto3` MinIO usage).


## Plan of Work


> ⚠️ **Historical design (partially superseded).** The sections below — Plan of Work, Concrete Steps, and
> Validation — describe the **original single-shared-closet** design (150/category, `image_labels_merged.csv`,
> a single `__shared__` set, the `:4000` Firestore UI). They are kept for provenance. The **current** design
> is the **3-closet re-scope** — see **Current status** (Progress) and the **Decision Log**; commands live in
> **Artifacts**. Where they conflict, the Progress/Decision Log/Artifacts sections win.

Five phases. The seed pipeline (Phases 0–1) and the read adapter (Phase 2) are independent and could proceed
in parallel; attribution (Phase 3) depends on the adapter for the backend half. Validation (Phase 4) ties it
together against `make dev`.

**Target layout:**


    scripts/seed_shared_closet/
      run_seed.py            # single-file pipeline (M3-1)
      requirements.txt       # kaggle, boto3, elasticsearch==8.11.0, google-genai, google-cloud-firestore, pillow, python-dotenv
      .env.example           # ES/R2/Firestore/Kaggle/Vertex AI/embedding config
      README.md              # how to run locally and at deployment
    fastapi-service/app/adapters/shared_closet_search.py   # implement the M3-3 stub
    fastapi-service/tests/adapters/test_shared_closet_search.py  # new
    flutter-web-app/lib/shared/attribution.dart            # footer widget + about-dialog (M3-4)


### Phase 0 — Seeding-script scaffold + dataset acquisition (M3-1)


Create `scripts/seed_shared_closet/` with `run_seed.py` and its own `requirements.txt` (`kaggle`, `boto3`,
`elasticsearch==8.11.0`, `google-genai`, `google-cloud-firestore`, `pillow`, `python-dotenv`). Config is read
from env + CLI flags: `ELASTICSEARCH_URL`, `R2_ENDPOINT_URL`/`R2_PUBLIC_ENDPOINT_URL`/`R2_ACCESS_KEY_ID`/
`R2_SECRET_ACCESS_KEY`/`R2_BUCKET_NAME`, the Firestore target (`FIRESTORE_EMULATOR_HOST` + `GOOGLE_CLOUD_PROJECT`
locally, ADC at deployment), `GOOGLE_CLOUD_LOCATION` (default `us-central1`; used for Vertex AI endpoint),
`MAX_ITEMS_PER_CATEGORY` (default 150), `--with-embeddings` (default off; on at deployment per M1-3), and
`--source-dir` (offline fallback that skips the Kaggle download and reads images from a local directory, so
acceptance is runnable without Kaggle creds). The `.env.example` documents the local `make dev` values
(mirroring `docker-compose.yml`: ES `http://localhost:9200`, MinIO `http://localhost:9000` with
`minioadmin`/`minioadmin`, Firestore emulator `localhost:8080`). Gemini calls (embeddings) are routed through
**Vertex AI** (`genai.Client(vertexai=True, project=..., location=...)`) — no Gemini API key is required; the
same ADC credential used for Firestore is sufficient. When authenticating via a service account JSON
(recommended for local Vertex AI billing against the hackathon project), set
`GOOGLE_APPLICATION_CREDENTIALS=../../credentials/vertex-ai-sa.json` in the script's `.env`
(path relative to `scripts/seed_shared_closet/`; the file lives in the gitignored `credentials/` dir at
the repo root).

Dataset acquisition: with Kaggle creds, use the `kaggle` API to download `agrigorev/clothing-dataset-full` to a
cache dir; otherwise read `--source-dir`. Parse `image_labels_merged.csv` to map filenames → labels and to
filter out non-garment labels (`Not sure`, `Skip`, `Others`, etc.).

Why minimal: a thin scaffold with config + acquisition is the smallest thing that lets Phase 1 iterate on the
pipeline without re-downloading each run.


### Phase 1 — Idempotent seeding pipeline (M3-1, M3-2)


Implement the per-category sampling and the per-item pipeline in `run_seed.py`:

1. **Sample** up to `MAX_ITEMS_PER_CATEGORY` images per kept category, preferring high-confidence labels.
2. For each image: compute `item_id = uuid5(uuid.NAMESPACE_URL, f"kaggle:agrigorev/clothing-dataset-full:{filename}")`.
3. **R2 PUT** the JPEG to `__shared__/closet/{item_id}.jpg` (boto3, same creds/bucket as M2). Idempotent by key.
4. **Optional embedding** (`--with-embeddings`): `gemini-embedding-2`, `output_dimensionality=768`, on the image
   bytes — same model/dims as M2-5 so the vectors are comparable. Skipped locally by default (M1-3).
5. **ES upsert** into `clothing_items` with `_id = item_id`: `{ item_id, user_id: "__shared__", is_shared: true,
   tags, category, colors, season, embedding? }`.
6. **Firestore set** `shared_closet/{item_id}` = the §8.1 shape (`imageUrl`, `category`, `tags`, `season`,
   `colors`, `embeddingId: item_id`, `datasetSource`, `originalLabel`, `createdAt`).

Derive `category`/`tags`/`season`/`colors` from the dataset label (a lightweight mapping; the rich Gemini
analysis is the user-upload path — for the shared set the dataset label is the authoritative category, with a
small heuristic for season/colors, or `--with-analysis` to run Gemini analysis at deployment if desired).

Idempotency: steps 3/5/6 are deterministic upserts keyed by `item_id`, so a re-run overwrites rather than
duplicates; the script logs created-vs-skipped counts. Run a **local subset** now (e.g.,
`MAX_ITEMS_PER_CATEGORY=20`, embeddings off) to prove the pipeline; the full 150/category with embeddings on
GCE ES is the deployment-phase re-run.


### Phase 2 — `SharedClosetSearchAdapter` (M3-3)


Implement `fastapi-service/app/adapters/shared_closet_search.py` (replace the `NotImplementedError` stub).
`search_by_source(user_id, source, query, limit)` asserts `source == ClothingSource.SHARED_CLOSET` and queries
the `clothing_items` index with an ES `bool` filter on `user_id: "__shared__"` (and/or `is_shared: true`) plus
a keyword `match`/`terms` on the `query` text against `tags`/`category`; an additive, **fail-soft** `knn`
clause is included only when query vectors are available (deployment phase) and is caught so failures degrade
to keyword-only (M1-3). It returns `CandidateItem(item_id=_id, source=SHARED_CLOSET, image_url=<key or
resolvable url>, tags=[...], attribution="Clothing Dataset (CC BY-SA 4.0)")`. `search_all_sources` handles a
source list that includes `SHARED_CLOSET`. The adapter creates its own `AsyncElasticsearch` (same construction
as `ElasticsearchEmbeddingRepository`) — it does not modify the M2-9 repo.

`image_url`: store the R2 key; the M5 result UI resolves a viewable/ signed URL via the existing M2
download-url mechanism (a shared-item variant) — noted as an M5 handoff so M3 stays decoupled from URL signing.


### Phase 3 — Attribution (M3-4)


Backend: the attribution string is set by the adapter (Phase 2) — no other backend change.

Flutter: add `flutter-web-app/lib/shared/attribution.dart` exposing a small `AttributionFooter` widget and a
`showSharedClosetAboutDialog(context)` — both rendering "共有クローゼットの画像は Clothing Dataset
(CC BY-SA 4.0) を使用しています" with a tappable Kaggle link (`url_launcher`, already a common Flutter dep; add
if missing). Surface it from the closet screen scaffold (`flutter-web-app/lib/closet/closet_screen.dart`) as a
footer or an app-bar "ℹ️" action. Per-candidate-card attribution (on the M5 result cards) is an explicit M5
handoff. Keep it minimal and consistent with the existing Material 3 theme in `main.dart`.


### Phase 4 — Validation & acceptance


Run the seed against `make dev`, verify the three stores, re-run for idempotency, unit-test the adapter, and
check the Flutter surface — see **Validation and Acceptance**. Then flip M3-1/M3-3/M3-4 to ✅ and leave M3-2 at
🟡 with a note that the local subset is seeded and the full-scale GCE seed is the deployment-phase re-run;
update `architecture-overview.md` accordingly.


## Concrete Steps


Run from `/Users/ran/my-app/gen-fashion` unless stated otherwise.

**Phase 0–1 (build + seed locally).**


    cd /Users/ran/my-app/gen-fashion && make dev     # ES :9200, MinIO :9000, Firestore emu :8080, fastapi

    cd scripts/seed_shared_closet
    python -m venv .venv && . .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env        # local make dev values

    # local subset seed (Kaggle creds present) — embeddings off per M1-3
    python run_seed.py --max-items-per-category 20

    # offline fallback if no Kaggle creds:
    # python run_seed.py --source-dir /path/to/local/images --max-items-per-category 20


Verify the three stores:


    # ES: shared docs present
    curl -s 'http://localhost:9200/clothing_items/_count' -H 'Content-Type: application/json' \
      -d '{"query":{"term":{"user_id":"__shared__"}}}'
    # MinIO: objects under __shared__/closet/ (via mc or the console at :9001)
    # Firestore emulator UI (http://localhost:4000) -> shared_closet collection populated


Idempotency — re-run and confirm counts are stable (created=0, skipped/updated=N on the second pass):


    python run_seed.py --max-items-per-category 20      # second run: no new docs


**Phase 2 (adapter test).**


    cd /Users/ran/my-app/gen-fashion && make test       # or: docker-compose run --rm fastapi-service pytest -q
    # expect the new tests/adapters/test_shared_closet_search.py to pass alongside the existing suite


**Phase 3 (Flutter).**


    cd flutter-web-app && flutter analyze       # expect: No issues found
    make web                                    # sign in; confirm the attribution footer/modal renders with the Kaggle link


## Validation and Acceptance


Acceptance is observable behavior:

1. **Seeding populates all three stores.** After `python run_seed.py --max-items-per-category 20` against
   `make dev`: ES `clothing_items` has docs with `user_id:"__shared__"` (the `_count` query returns N>0),
   R2/MinIO has objects under `__shared__/closet/`, and Firestore `shared_closet/*` has matching documents with
   the §8.1 fields (incl. `datasetSource` and `originalLabel`). Satisfies M3-2 (local subset) and req §15
   Phase 1a #7.
2. **Idempotent.** A second identical run creates **zero** new documents/objects (logged created=0); total
   counts are unchanged. Satisfies the M3-1 / §16.4 idempotency requirement.
3. **`SHARED_CLOSET` search returns attributed candidates.** `SharedClosetSearchAdapter.search_by_source(...,
   source=SHARED_CLOSET, query=...)` returns `CandidateItem`s filtered to `user_id:"__shared__"`, each with
   `attribution == "Clothing Dataset (CC BY-SA 4.0)"`. Proven by `test_shared_closet_search.py` and the M4/M5
   demo. Satisfies M3-3 and the milestone exit criterion.
4. **Attribution is visible.** The Flutter app renders the CC BY-SA 4.0 attribution footer/modal with the
   Kaggle link; `flutter analyze` is clean. Satisfies M3-4 / req §16.3.

**Milestone exit criteria (feature-matrix):** "Seeding script runs idempotently; `SHARED_CLOSET` source returns
candidate items with attribution." Met by (2) + (3).

**Stated limitation (M1-3).** Local acceptance uses a keyword-first **subset**. The full 2,000–3,000-item seed
with embedding vectors on the GCE-hosted ES is a deployment-phase re-run of the same script
(`--with-embeddings`, `--max-items-per-category 150`); M3-2 remains 🟡 (partial) until that runs.


## Idempotence and Recovery


- The whole pipeline is designed to be re-run safely: `item_id` is deterministic (uuid5 of the source
  filename), so R2 PUT (by key), ES index (by `_id`), and Firestore `set` (by doc id) all **upsert** rather
  than duplicate. Re-running after a partial failure simply completes the missing writes.
- The seed only ever writes the `__shared__` / `shared_closet` namespace — it never touches a real user's
  `users/{uid}/closet`, so it cannot corrupt user data.
- To reset the shared closet locally: delete ES docs where `user_id:"__shared__"`, the `shared_closet`
  collection in the Firestore emulator, and the `__shared__/closet/` objects in MinIO; then re-run. (Provide a
  `--purge` flag that does this for convenience.)
- `SharedClosetSearchAdapter` is read-only — safe to call repeatedly.
- Kaggle download is cached; re-runs reuse the cache. `--source-dir` avoids the network entirely.


## Artifacts and Notes


**Adapter unit test run (2026-06-09):**
```
platform darwin -- Python 3.12.9, pytest-7.4.0
tests/adapters/test_shared_closet_search.py::test_search_by_source_returns_attributed_candidates PASSED
tests/adapters/test_shared_closet_search.py::test_search_by_source_wrong_source_raises_value_error PASSED
tests/adapters/test_shared_closet_search.py::test_search_all_sources_includes_shared PASSED
tests/adapters/test_shared_closet_search.py::test_search_non_empty_query_requires_keyword_match PASSED
tests/adapters/test_shared_closet_search.py::test_search_all_sources_without_shared_returns_empty PASSED
tests/adapters/test_shared_closet_search.py::test_search_empty_query_uses_filter_only PASSED
tests/adapters/test_shared_closet_search.py::test_search_fails_soft_on_es_error PASSED
tests/adapters/test_shared_closet_search.py::test_image_url_fallback_when_no_imageUrl PASSED
8 passed in 7.15s
```

**Flutter analyze (2026-06-09):** `No issues found! (ran in 7.8s)`

**First live seed — single-closet form, since superseded (2026-06-09):** ran against infra-only
`docker-compose up -d elasticsearch minio firestore-emulator`:
```json
{ "total_samples": 360, "created": 360, "skipped": 0, "errors": 0, "with_embeddings": false }
```
ES `_count` (user_id:"__shared__") = 360 across 18 categories (incl. the now-excluded Undershirt/Body/Other).
Firestore `shared_closet/*` carried the §8.1 fields. **Update (2026-06-10): the local containers have since
been removed; the compose uses no data volumes, so this data is gone — the next seed is a clean slate.**

**Builder dry-run — multi-closet form (2026-06-09, NO store writes):**
```
Loaded 4909 labelled entries; Closet adult-01: 30, adult-02: 30, child-01: 30; Built 90 items total
adult-01 ∩ adult-02 overlap: 0    (each closet: Shoes5 Pants3 Shorts3 Hat3 +2 each tops/outer/dress, etc.)
```

**Multi-closet live seed — EXECUTED & VERIFIED (2026-06-10).** Ran against local infra
(`docker-compose up -d elasticsearch minio firestore-emulator`; ES yellow, MinIO healthy, Firestore
emulator reachable). Credentials/embeddings not needed (infra-only, `--with-embeddings` off).

Purge (cleared the still-present stale single-closet data) then seed:
```
$ python run_seed.py --purge
ES deleted: 360 | R2/MinIO deleted: 360 objects | Firestore deleted: 0 docs

$ python run_seed.py
{ "total_samples": 90, "created": 90, "skipped": 0, "errors": 0,
  "closets": { "adult-01": 30, "adult-02": 30, "child-01": 30 }, "with_embeddings": false }
```

3-store verification:
```
# ES — total user_id:"__shared__"
count: 90
# ES — by closetId.keyword            # (closetId is dynamically mapped text → aggregate on .keyword)
adult-01 30 | adult-02 30 | child-01 30
# ES — by closetKind.keyword
adult 60 | child 30
# ES — category breakdown (no Undershirt/Body/Other):
Shoes15 Hat9 Pants9 Shorts9 Dress6 Outwear6 Shirt6 Skirt6 T-Shirt6 Longsleeve4 Blazer3 Hoodie3 Polo3 Top3 Blouse2
# ES — per-closet × category (adult-01 ≡ adult-02 quota; child-01 swaps a Blouse for a Longsleeve):
adult-01 => Shoes5 Hat3 Pants3 Shorts3 Dress2 Outwear2 Shirt2 Skirt2 T-Shirt2 Blazer1 Blouse1 Hoodie1 Longsleeve1 Polo1 Top1
adult-02 => Shoes5 Hat3 Pants3 Shorts3 Dress2 Outwear2 Shirt2 Skirt2 T-Shirt2 Blazer1 Blouse1 Hoodie1 Longsleeve1 Polo1 Top1
child-01 => Shoes5 Hat3 Pants3 Shorts3 Dress2 Longsleeve2 Outwear2 Shirt2 Skirt2 T-Shirt2 Blazer1 Hoodie1 Polo1 Top1

# MinIO — objects under __shared__/closet/
90

# Firestore — shared_closet/{itemId} sample carries closetId+closetKind + §8.1 fields:
{ closetId: "adult-01", closetKind: "adult", category: "Pants", originalLabel: "Pants",
  season: "all", colors: ["black","blue","beige"], tags: ["pants"], embeddingId: <itemId>,
  datasetSource: "kaggle:agrigorev/clothing-dataset-full", imageUrl: "__shared__/closet/<itemId>.jpg" }
# Firestore — shared_closets/* metadata (3 docs):
adult-01: kind=adult  displayName="Adult Closet A" itemCount=30
adult-02: kind=adult  displayName="Adult Closet B" itemCount=30
child-01: kind=child  displayName="Kids Closet"    itemCount=30
```

Idempotency (second identical run): `created=0, skipped=90, errors=0`; ES `_count` stayed **90**.

Re-run checks: `pytest -q tests/adapters/test_shared_closet_search.py` → **8 passed** (run in a local
py3.12 venv with `fastapi-service/requirements.txt`, not via `docker-compose run`, since
`credentials/vertex-ai-sa.json` is absent — the adapter tests are ES-free/mocked). `flutter analyze` →
**No issues found**.


## Interfaces and Dependencies


- **`kaggle`** — downloads `agrigorev/clothing-dataset-full` (needs `~/.kaggle/kaggle.json`). `--source-dir`
  bypasses it for offline/CI.
- **`boto3`** — S3-compatible client for R2/MinIO uploads (same creds/bucket as M2).
- **`elasticsearch==8.11.0`** — writes/reads the `clothing_items` index; pinned to the `fastapi-service`
  version to avoid wire drift.
- **`google-genai`** — `gemini-embedding-2` embeddings via **Vertex AI** (`vertexai=True`; only when
  `--with-embeddings`); same model/dims as M2-5. Authentication via ADC (no API key needed). Google Cloud
  credits from the hackathon organiser are the intended billing account.
- **`google-cloud-firestore`** — writes `shared_closet/*` (emulator locally via `FIRESTORE_EMULATOR_HOST`; ADC
  at deployment).
- **`pillow`** — image validation/normalization to JPEG before upload.
- **`url_launcher`** (Flutter) — the attribution link (add to `flutter-web-app/pubspec.yaml` if absent).
- **Existing artifacts depended on:** the `clothing_items` ES mapping and config model IDs
  (`fastapi-service/app/config.py`, `elasticsearch_embedding_repo.py`); the `ClothingSearchPort` /
  `CandidateItem` contracts (`app/ports/clothing_search.py`, `app/domain/styling/value_objects.py`); `make dev`
  local services (`docker-compose.yml`).
- **Downstream consumers:** M5-5 `SearchCandidateItemsUseCase` routes to `SharedClosetSearchAdapter`; the M4-6
  `search_closet` agent tool reads the same seeded `__shared__` ES docs; M5 result cards render per-item
  attribution.


## Revision Notes


2026-06-09 — Plan created at user request after noting M3 had been skipped between M2 and the M4 plan. Targets
feature-matrix milestone **M3** (rows M3-1…M3-4), moved to 🟡 In progress in the same change (M3-2 kept partial
per the M1-3 deployment-phase deferral). No `req-phase01.md` change (M3 is fully specified by req §16 / §8 /
ADL-010). `architecture-overview.md` updated for the M3 status row. Recommended working order: **M3 before
M4** (siblings; M3 enriches the M4 demo). If strict "one ExecPlan at a time" is desired, treat the M4 plan as
queued behind this one.
