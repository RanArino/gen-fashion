# M4 — ADK Agents Core


This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.


This plan follows `PLANS.md` at `/Users/ran/my-app/PLANS.md`.


## Purpose / Big Picture


M4 builds the **core agent brain** of gen-fashion: a `StylingOrchestratorAgent` that delegates to two
sub-agents (`ClosetAgent`, `StylingAgent`), and the four tools those agents call
(`analyze_clothing_image`, `search_closet`, `style_synthesizer`, `ask_preference`). Until now the
"coordination" experience has been a skeleton. After M4 a developer can open the **ADK Web UI** on their
machine, type a request like "suggest an outfit from my closet," and watch the orchestrator delegate to a
sub-agent, call a tool, search Elasticsearch for real closet items, and (when image generation succeeds)
return a generated coordinate image — all locally, with the tool-call / tool-result / final-answer event
stream visible in the UI.

This is the critical path. The architecture overview names **M4 → M5** the critical path and M4 the main
implementation target. M4 produces the runnable agents and callable tools; **M5** then wires them into the
FastAPI session routes, the Firestore `agentEvents` relay (ADL-011 / ADL-021), the SSE endpoint, and the
Flutter Accordion / A2UI result UI. M4 deliberately stops at "runs on the ADK Web UI and each tool is
callable end-to-end" (feature-matrix M4 exit criteria; req §15 Phase 1a #1).

**The one load-bearing decision this plan makes:** `adk-agent-service` is **rebuilt in Python ADK**. The
directory currently holds a TypeScript skeleton (every method `throw new Error("Implement in M4-x")`, zero
dependencies, no ADK package). Python is forced by req §2 (Google ADK with a Python/FastAPI backend), the
M1-4 PoC which captured `runner.run_async()` events from the **Python** ADK, ADL-021 which requires this
service to share `FirestoreStyleSessionRepository` with the Python `fastapi-service`, and the fact that
every adapter the tools reuse (Gemini analysis/embedding, the Elasticsearch `clothing_items` schema, the
Nano Banana image-gen PoC) is already Python. The decision is recorded as **ADL-022** in
`docs/req-phase01.md` and in the Decision Log below.

**Acceptance (observable):** `cd adk-agent-service && adk web` lists a `styling_app` agent; selecting it and
sending a coordination request causes the orchestrator to delegate to `ClosetAgent`, call `search_closet`,
and return candidate items drawn from the local Elasticsearch `clothing_items` index — primarily the
**M3-seeded `SHARED_CLOSET` demo data** (90 items, `user_id:"__shared__"`, live-seeded & verified
2026-06-10), optionally the developer's own M2-uploaded `CLOSET` items; `style_synthesizer` returns a
generated image URL or the collage fallback; `pytest` in `adk-agent-service` passes for the tools and the
registry. See **Validation and Acceptance**.


## Progress


- [x] Phase 0 — Python ADK service scaffold; decommission the TS skeleton (M4-9 AGENT_MODEL config)
  - [x] New Python package layout under `adk-agent-service/` (`styling_app/`, `requirements.txt`, `config.py`).
  - [x] Replace `Dockerfile` (python:3.11-slim + `adk api_server`), `.env.example`, and the `docker-compose.yml` `adk-agent-service` service command.
  - [x] Delete the TypeScript skeleton (`src/*.ts`, `package.json`, `tsconfig.json`).
  - [x] Verify: `adk web` boots and lists `styling_app` (only `styling_app`); the container builds and runs `adk api_server` healthy (`/list-apps` 200).
- [x] Phase 1 — Tool Registry + four tools (M4-4, M4-5, M4-6, M4-7, M4-8)
  - [x] Tool Registry pattern (`tools/registry.py`): each tool an independent module registered by name.
  - [x] `analyze_clothing_image` (M4-5) — Gemini structured-output analysis; reuses the M2-5 response schema verbatim.
  - [x] `search_closet` (M4-6) — embed the agent's description (fail-soft), hybrid (keyword-first + additive kNN) search over `clothing_items`, filtered by source; `SHARED_CLOSET` results carry the CC BY-SA 4.0 attribution (M3 parity). Keyword clause re-shaped for keyword-typed fields — see Surprises.
  - [x] `style_synthesizer` (M4-7) — Nano Banana (`gemini-2.5-flash-image`) generation with collage fallback; stores result in R2/MinIO, returns URL.
  - [x] `ask_preference` (M4-8) — Web pre-session-form variant: echo/normalize the `UserPreference` from context (LINE interactive deferred to M6).
  - [x] Verify: registry + all four tools unit-tested with mocked Gemini/ES/storage clients (17 tests).
- [x] Phase 2 — Agents + delegation (M4-1, M4-2, M4-3)
  - [x] `ClosetAgent` (M4-2) — tools `[analyze_clothing_image, search_closet]`.
  - [x] `StylingAgent` (M4-3) — tools `[ask_preference, style_synthesizer]`.
  - [x] `StylingOrchestratorAgent` (M4-1) — `sub_agents=[ClosetAgent, StylingAgent]`; exported as `root_agent`.
  - [x] A2A-ready discipline (ADL-019): explicit context hand-off, no shared in-memory state, per-sub-agent toolsets pulled from the registry by name.
- [x] Phase 3 — Validation & acceptance (2026-06-11)
  - [x] End-to-end against the M3-seeded shared closet (`SHARED_CLOSET`, no upload needed): delegation → 3× `search_closet` (attributed `__shared__` items, signed URLs) → `style_synthesizer` (collage fallback; stored, reachable). Event stream captured (`docs/local/m4_run_events*.json`). `CLOSET` source not exercised live (optional path; same code, only the `user_id` filter differs — covered by unit tests).
  - [x] `pytest -q` green (17 passed); run recorded in Artifacts; M4-1…M4-9 flipped to ✅ in `feature-matrix-phase01.md`; M4 nodes recolored in `architecture-overview.md`.


## Surprises & Discoveries


- **`match` queries are inert against the `clothing_items` keyword fields.** The M2-9 mapping types
  `tags`/`category`/`colors`/`season` as `keyword`, and the M3 seed capitalizes categories (`"Pants"`),
  so the planned M3-3-shaped `match` clauses (`{"match": {"tags": description}}`) returned **zero hits**
  for any multi-word description and for lowercase category filters. Fix: the adapter tokenizes the
  description (`[a-z0-9]+` on the lowercased string) and builds **case-insensitive `term` clauses** over
  `tags`/`category`/`colors`/`season`; the `category`/`colors` filter params are case-insensitive `term`s
  too. Found live (first acceptance run returned `[]`); the M3-3 adapter worked only because its callers
  pass exact single-word lowercase queries that happen to equal the seeded tags.
- **Abstract search descriptions find nothing in the seeded data.** The agent's first attempt searched
  for "casual spring outfit" — no garment noun, zero hits. `ClosetAgent`'s instruction now requires one
  `search_closet` call per garment type with concrete nouns ("casual shirt", "blue pants"), and the tool
  docstring says the same. This is prompt-shape, not architecture.
- **Free-tier Gemini API quota dominated acceptance, beyond the Vertex quirk M1-4 recorded.** With the
  local `GEMINI_API_KEY`: `gemini-2.0-flash` free-tier quota is **0** (the req §7.1 default no longer
  runs free), `gemini-2.5-flash` allows ~20 req/day (exhausted mid-acceptance), and
  `gemini-2.5-flash-image` has no free quota at all. Acceptance ran with `AGENT_MODEL=gemini-2.5-flash-lite`
  (M4-9 override, no code change) and `style_synthesizer` exercised the **collage fallback** path
  (ADL-005) — the Nano Banana call itself is implemented and ports the proven M1-2 PoC shape, but locally
  unverifiable without a billed key or Vertex. flash-lite is noticeably weaker at delegation (asked a
  clarifying question; needed an explicit nudge to transfer/call tools) — fine for tool verification,
  but M5 demos should use `gemini-2.5-flash` on a billed key or Vertex.
- **`adk web`/`api_server` treat every subfolder of the cwd as an agent app**, so a top-level `tests/`
  directory showed up in the agent dropdown. Tests moved to `styling_app/tests/` (pytest unaffected).
- **Event shape matches M1-4.** The captured stream is the same single-`Event` shape (`content.parts[*]`
  with `functionCall`/`functionResponse`/`text`, batched tokens). Multi-agent delegation appears as a
  built-in `transfer_to_agent` function call/response pair, then subsequent events carry the sub-agent's
  name in `author` — a detail the M5 `agentEvents` relay will want to preserve.


## Decision Log


- Decision: **Rebuild `adk-agent-service` in Python ADK; discard the TypeScript skeleton.** Recorded at the
  source of truth as **ADL-022** in `docs/req-phase01.md`.
  Rationale: req §2 specifies Google ADK on a Python/FastAPI backend; the M1-4 PoC captured
  `runner.run_async()` events from the **Python** ADK (`poc/adk_event_stream/run_poc.py`); ADL-021 requires
  this service to write sessions/events via the same `FirestoreStyleSessionRepository` the Python
  `fastapi-service` uses; and every adapter the M4 tools reuse — Gemini analysis/embedding
  (`fastapi-service/app/adapters/gemini_analysis.py`), the Elasticsearch `clothing_items` schema
  (`elasticsearch_embedding_repo.py`), and the Nano Banana image-gen PoC (`poc/image_generation/run_poc.py`)
  — is already Python. The TS skeleton (`src/*.ts`, `throw new Error("Implement in M4-x")`, no ADK
  dependency) was an early M0 scaffold that diverged from req; keeping it would force the agents to RPC into
  or re-implement the Python adapters for no benefit. The architecture overview §8 explicitly flagged this as
  a decision required before M4 starts.
  Date/Author: 2026-06-09 / Claude (Opus 4.8), pending user confirmation.

- Decision: **M4 keeps its tool-side adapters local to `adk-agent-service`; it does not import
  `fastapi-service/app` and does not move M2 code.** The two services are intentionally separate deployables
  (ADL-007); their shared contract is the **Firestore document shape + the Elasticsearch `clothing_items`
  index schema**, not Python classes. M2 is Done and E2E-verified, so a cross-service refactor mid-stream
  would risk regressing it for no M4 benefit.
  Rationale: M4's exit criteria target the **ADK Web UI** (no FastAPI, no Firestore session writes — those
  are M5). The tools only need Gemini + Elasticsearch clients pointed at the same models/index M2 uses. The
  duplicated surface is a handful of thin client calls whose exact model IDs, dimensions, schema, and query
  shape are already pinned by M1-2 / M2-5 / M2-9 and copied verbatim.
  Follow-up: when **M5** needs `FirestoreStyleSessionRepository` in both services (ADL-021), extract a shared
  `gen-fashion-core` package (domain + ports + adapters) and have both services depend on it. M4 leaves clean
  seams (thin adapter modules, ports-style function signatures) so that extraction is mechanical.
  Date/Author: 2026-06-09 / Claude (Opus 4.8).

- Decision: **A2UI result-UI output is out of scope for M4.** ADL-018 commits the agents to emit A2UI
  payloads for the *user-facing result UI*, but that lands with the **M5** result UI (candidate cards,
  preference form, final image) and is gated on a `genui` Flutter Web spike. The ADK Web UI renders the raw
  tool/event stream, which is all M4 needs. M4 still follows the A2A-ready discipline (ADL-019).
  Date/Author: 2026-06-09 / Claude (Opus 4.8).

- Decision: **`search_closet` is keyword-first hybrid, with cross-modal kNN as an additive, fail-soft
  clause.** This honors the M1-3 re-scope (vector/GCE hybrid deferred to the deployment phase; keyword-first
  works on the local Docker ES) and the deep-dive's open risk that text→image kNN quality for clothing is
  unvalidated.
  Date/Author: 2026-06-09 / Claude (Opus 4.8).


## Outcomes & Retrospective


**M4 complete (2026-06-11).** `adk-agent-service` is now a Python ADK app (`styling_app/`, `google-adk`
2.1.0); the TS skeleton is deleted. `adk web` and `adk api_server` list exactly `styling_app`; the
docker-compose service builds (python:3.11-slim, 713MB) and runs `adk api_server` healthy. The service has a
local `.dockerignore` so `.env`, virtualenvs, caches, and ADK runtime state are excluded from Docker build
context.

**What runs:** a live `SHARED_CLOSET` coordination conversation against the M3 seed —
orchestrator → `transfer_to_agent(ClosetAgent)` → three `search_closet` calls (shirt/pants/shoes, each
with concrete-noun descriptions) returning seeded `__shared__` items with `attribution="Clothing Dataset
(CC BY-SA 4.0)"` and signed MinIO image URLs → `transfer_to_agent(StylingAgent)` → `style_synthesizer`
storing `demo-user/coordinates/{uuid}.jpg` (reachable, HTTP 200, 1140×720 JPEG of the two chosen
garments) → final answer with the coordinate URL. For container runs, ADK-owned signed MinIO/R2 URLs are
resolved back to storage object keys before fetching bytes, so `style_synthesizer` does not depend on
container-local `localhost:9000` reachability.

**Live vs. fallback:** `search_closet` and `ask_preference` fully live; `analyze_clothing_image` live in
unit tests (same Gemini call shape as the E2E-verified M2-5 adapter) but not exercised in the acceptance
conversation; `style_synthesizer` live through the **collage fallback** — the Nano Banana generation call
is implemented (M1-2 port) but the local free-tier key has no `gemini-2.5-flash-image` quota.
kNN is additive and inert for `SHARED_CLOSET` (no local embeddings, as planned).

**Event stream:** same shape as M1-4 (`sample_events.jsonl`) — single `Event` class, batched tokens,
`functionCall`/`functionResponse` parts; delegation surfaces as `transfer_to_agent` calls plus per-event
`author`. Captures in `docs/local/m4_run_events*.json`.

**Handoffs into M5:** (1) drive these agents via `Runner` behind `POST /internal/run-session` (ADL-020)
and relay the captured event shape — including `author` and `transfer_to_agent` — into Firestore
`agentEvents` (ADL-011/021); (2) use a billed key or Vertex (`AGENT_MODEL=gemini-2.5-flash`) for demos —
free-tier flash-lite delegates poorly; (3) verify the Nano Banana generation path once quota exists;
(4) closet-level (`closetId`) filtering and the `CLOSET`-source live demo remain M5 add-ons;
(5) extracting a shared `gen-fashion-core` package stays the M5 refactor (Decision Log).


## Context and Orientation


gen-fashion is a hexagonal/DDD monorepo under `/Users/ran/my-app/gen-fashion`. The requirements source of
truth is `docs/req-phase01.md`; implementation status is tracked in `docs/feature-matrix-phase01.md`; the
implemented-vs-planned visualization is `docs/architecture-overview.md`. M0 (foundation), M1 (PoC), M2
(auth + closet management, Web), and **M3 (shared demo closet — Done for the local subset, 2026-06-10;
only the full vector seed on GCE ES remains deployment-deferred per M1-3)** are complete. M4 (this plan)
is the active ExecPlan and the critical path to M5 (full Web E2E coordination flow).

**Two containers (req §9.1, ADL-007).** `fastapi-service/` (Python/FastAPI) is the REST API and the M2-5
upload-processing worker. `adk-agent-service/` is the AI-processing service that runs the ADK agents. This
plan rebuilds the latter in Python.

**What already exists and M4 reuses (do not rebuild):**

- `fastapi-service/app/adapters/gemini_analysis.py` — `GeminiAnalysisAdapter.analyze(image_bytes)` returns a
  structured `ClothingAnalysisResult { category, colors, tags, season, style }` via Gemini; `embed(image_bytes)`
  returns a 768-dim vector from `gemini-embedding-2`. M4's `analyze_clothing_image` tool reproduces the
  `analyze` call; `search_closet` reproduces the `embed` call for the **query** text. The exact response
  schema is `ANALYSIS_RESPONSE_SCHEMA` in that file — copy it verbatim so M4 analysis matches M2.
- `fastapi-service/app/adapters/elasticsearch_embedding_repo.py` — owns the `clothing_items` index mapping
  (`item_id`, `user_id`, `is_shared`, `tags`, `category`, `colors`, `season`, `embedding` dense_vector dims=768,
  cosine). M2-5's worker indexes user closet items here. M4's `search_closet` queries this same index.
- `poc/image_generation/run_poc.py` — the M1-2-approved Nano Banana (`gemini-2.5-flash-image`) virtual-try-on
  call plus the `_build_collage` fallback (ADL-005). M4's `style_synthesizer` ports both.
- `fastapi-service/app/config.py` — pins the model IDs and dimensions M4 must match:
  `image_analysis_model="gemini-2.5-flash"`, `embedding_model="gemini-embedding-2"`, `embedding_dimensions=768`,
  `clothing_items_index="clothing_items"`. M4 reads the same names from env.
- `fastapi-service/app/domain/styling/value_objects.py` — defines `ClothingSource` (`CLOSET` / `SHARED_CLOSET`
  / `RAKUTEN`), `CandidateItem`, `UserPreference`. M4 mirrors these shapes as plain dicts in tool returns
  (ADK tools must return JSON-serializable values); it does not import the module.
- **M3 outputs (live-seeded & verified 2026-06-10).** The `clothing_items` index already holds **90 shared
  items** (`user_id:"__shared__"`, `is_shared:true`) across **3 demo closets** (`adult-01`/`adult-02`/
  `child-01`, 30 each, fields `closetId`/`closetKind`; metadata in Firestore `shared_closets/{closetId}`);
  images live in MinIO/R2 under `__shared__/closet/{item_id}.jpg`. **These docs carry no `embedding`
  vectors locally** (the `--with-embeddings` full seed is deployment-deferred, M1-3), so for
  `SHARED_CLOSET` only the keyword clause of `search_closet` can match until then.
  `fastapi-service/app/adapters/shared_closet_search.py` (M3-3) is the query-shape reference for the M4
  tool: filter on `user_id:"__shared__"`, keyword `should` on `tags`/`category`, fail-soft, signed image
  URLs, `attribution="Clothing Dataset (CC BY-SA 4.0)"`. M4 mirrors the shape; it does not import the
  module (same stance as the other adapters above).

**What M4 does NOT touch (it is M5):** `fastapi-service/app/handlers/session_routes.py` (501 stubs for
`POST /sessions`, `/source`, `/stream`), `app/adapters/firestore_styling_repo.py` (M5-2 stub),
`app/use_cases/styling/*` (M5 use cases). M4 also does not implement the Firestore `agentEvents` relay
(M5-8), the SSE endpoint (M5-9), or the Flutter Accordion (M5-10).

**Key facts from M1-4 (carry into M4):** ADK 2.1.0 yields a single `Event` class (no `ToolCall`/`ToolResult`
subtypes — inspect `content.parts[*]`); tokens are batched, not streamed; ~3 events per turn (reasoning →
tool_call → tool_result → final_answer); `thought_signature` is `bytes` and must become base64 before
Firestore (relevant in M5, not M4); on Vertex AI for this project `gemini-2.0-flash` is unavailable, so use
`gemini-2.5-flash` there. Locally with a direct API key (`GOOGLE_GENAI_API_KEY`), `gemini-2.0-flash` (the
req §7.1 default) works.

**ADK orientation (terms of art).** *ADK* (Agent Development Kit) is Google's Python framework for building
LLM agents; `pip install google-adk`, imported as `google.adk`. An *agent* (`google.adk.agents.Agent` /
`LlmAgent`) wraps an LLM with an `instruction`, a list of `tools` (plain Python functions), and optional
`sub_agents` for delegation. The *ADK Web UI* is launched with the `adk web` CLI from a directory whose
subfolders are agent apps; each app folder has an `__init__.py` (containing `from . import agent`) and an
`agent.py` exposing a module-level `root_agent`. `adk api_server` serves the same agents over HTTP (used for
the container so `make dev` stays coherent). M5 will instead drive the agents via `google.adk.runners.Runner`
behind the `/internal/run-session` endpoint (ADL-020).


## Plan of Work


The work is four phases. Each leaves the repo coherent and is independently checkable. The minimal-sufficient
path is: stand up a Python ADK package that the `adk web` CLI can discover (Phase 0), build the tools the
agents need with their own thin adapters reusing the existing models/index (Phase 1), assemble the
three-agent topology and export the orchestrator as `root_agent` (Phase 2), then prove it on the ADK Web UI
against real M2 closet data (Phase 3). Tools come before agents because an agent with no working tools cannot
be demonstrated end-to-end.

**Target directory layout** (under `adk-agent-service/`, after Phase 0):


    adk-agent-service/
      pyproject.toml            # or requirements.txt — google-adk, google-genai, elasticsearch, boto3, python-dotenv, pytest
      Dockerfile                # python:3.11-slim; CMD runs `adk api_server`
      .env.example              # AGENT_MODEL, GOOGLE_GENAI_*, ELASTICSEARCH_URL, R2_*, CLOTHING_ITEMS_INDEX
      styling_app/              # ADK Web UI discovers this folder by name
        __init__.py             # from . import agent
        agent.py                # root_agent = build_orchestrator()  (M4-1)
        config.py               # reads env: AGENT_MODEL (default gemini-2.0-flash), model IDs, ES url, R2 creds (M4-9)
        agents/
          __init__.py
          orchestrator.py       # build_orchestrator() -> Agent(sub_agents=[closet, styling])  (M4-1)
          closet_agent.py       # build_closet_agent()  (M4-2)
          styling_agent.py      # build_styling_agent() (M4-3)
        tools/
          __init__.py
          registry.py           # ToolRegistry: register/get by name  (M4-4)
          analyze_clothing_image.py   # (M4-5)
          search_closet.py            # (M4-6)
          style_synthesizer.py        # (M4-7)
          ask_preference.py           # (M4-8)
        adapters/
          __init__.py
          gemini.py             # analyze(bytes)->dict, embed_text(str)->list[float]  (reuses M2-5 schema/models)
          elasticsearch.py      # hybrid_search(...)->list[dict]  (queries clothing_items)
          image_generation.py   # generate(image_bytes_list, prompt)->bytes, build_collage(...)->bytes
          image_storage.py      # put_bytes(path, bytes)->url  (boto3 R2/MinIO, same creds as M2)
      tests/
        test_registry.py
        test_tools.py


### Phase 0 — Python ADK service scaffold (M4-9)


What exists at the end: a Python package the `adk web` CLI discovers as `styling_app`, with config that reads
`AGENT_MODEL` (default `gemini-2.0-flash`, req §7.1/§12.2) and the model/ES/R2 env names already used by
fastapi-service; the TS skeleton is gone; the `docker-compose.yml` `adk-agent-service` service runs Python and
boots healthy under `make dev`.

Files: create the layout above with empty-but-importable `agents/`, `tools/`, `adapters/` and a placeholder
`root_agent = Agent(name="styling_app", model=settings.agent_model, instruction="...", tools=[])` so the Web
UI lists it before tools exist. Replace `adk-agent-service/Dockerfile`, `adk-agent-service/.env.example`, and
the `adk-agent-service` block in `docker-compose.yml` (change `command:` from `sh -c "npm run build && npm
start"` to `sh -c "adk api_server --host 0.0.0.0 --port 3000"`, and drop the Node-only env). Delete
`src/index.ts`, `src/config.ts`, `src/tools/*.ts`, `src/agents/*.ts`, `package.json`, `tsconfig.json`.

`config.py` mirrors the relevant fields from `fastapi-service/app/config.py`: `agent_model` (env `AGENT_MODEL`,
default `gemini-2.0-flash`), `image_analysis_model`, `embedding_model`, `embedding_dimensions`,
`elasticsearch_url`, `clothing_items_index`, and the `R2_*` names. Use `pydantic-settings` for parity.

Why minimal: a placeholder `root_agent` is the smallest thing that makes `adk web` show the app, which is the
M4 acceptance surface; everything else hangs off it.


### Phase 1 — Tool Registry + four tools (M4-4, M4-5, M4-6, M4-7, M4-8)


**Tool Registry (M4-4).** `tools/registry.py` exposes a tiny `ToolRegistry` with `register(name, fn)` and
`get(name)` / `all()`, so each tool is an independent module registered by name (req §7.2: "Tool はすべて独立
したモジュールとして定義し、Tool Registry パターンで管理"). Agents pull their toolset from the registry by
name rather than importing tool functions directly — this keeps per-sub-agent toolsets separable (ADL-019).

**`analyze_clothing_image` (M4-5).** Signature `analyze_clothing_image(image_url: str) -> dict`. Fetch the
image bytes (via `adapters/image_storage.py` for R2/MinIO URLs, or `httpx` for public URLs), call
`adapters/gemini.analyze(bytes)` which reproduces `GeminiAnalysisAdapter.analyze` (same model
`image_analysis_model`, same `ANALYSIS_RESPONSE_SCHEMA` copied from `gemini_analysis.py`), and return
`{category, colors, tags, season, style}`. Backs `AnalyzeClothingImageUseCase` (the M5 use case wraps this).

**`search_closet` (M4-6).** Signature `search_closet(description: str, source: str, user_id: str, category:
str | None = None, colors: list[str] | None = None, limit: int = 10) -> list[dict]`. The **agent** supplies
the natural-language `description` of complementary items (req §8.3 step 2); the **tool** embeds it via
`adapters/gemini.embed_text(description)` (model `embedding_model`, `output_dimensionality=embedding_dimensions`)
and runs `adapters/elasticsearch.hybrid_search(...)`. The ES query is keyword-first (a `bool` with `terms` on
`tags`/`category`/`colors`) plus an additive, fail-soft `knn` clause over `embedding` using the query vector,
filtered by `user_id` for `CLOSET` and by `user_id="__shared__"` for `SHARED_CLOSET` (req §8.2). On any kNN
error, fall back to keyword-only (Decision Log; M1-3). Note the M3-seeded shared docs have **no `embedding`
field locally**, so for `SHARED_CLOSET` the kNN clause is inert until the deployment-phase vector seed —
keyword results are the bar. Return `CandidateItem`-shaped dicts (`item_id`, `source`, `image_url`,
`category`, `tags`, `attribution`) where `attribution="Clothing Dataset (CC BY-SA 4.0)"` for `SHARED_CLOSET`
items and `None` for `CLOSET` (parity with the M3-3 adapter, req §16.3); for shared items resolve
`image_url` from the R2 key `__shared__/closet/{item_id}.jpg` via `adapters/image_storage.py` (the ES doc
may carry only the key). The shared docs also carry `closetId`/`closetKind` (3 demo closets), but
**closet-level filtering is an M5 add-on** (M3 Decision Log: "data only" now) — M4's tool returns items
across all `__shared__` closets and does not take a `closet_id` parameter. `RAKUTEN` is Phase 1b — not
wired here.

**`style_synthesizer` (M4-7).** Signature `style_synthesizer(user_id: str, item_image_urls: list[str],
style_description: str) -> dict`. Fetch each garment's bytes, call `adapters/image_generation.generate(...)`
which ports the M1-2-approved Nano Banana call (`gemini-2.5-flash-image`) from `poc/image_generation/run_poc.py`;
on failure, `build_collage(...)` (ported `_build_collage`, ADL-005). Upload the result via
`adapters/image_storage.put_bytes(f"{user_id}/coordinates/{uuid4}.jpg", bytes)` and return
`{coordinate_image_url, items: item_image_urls, model_used}`.

**`ask_preference` (M4-8).** Signature `ask_preference(occasion=None, season=None, style=None,
color_preference=None) -> dict`. Per req §6.4, the Web (Phase 1a) flow collects preferences in a **pre-session
Flutter form** and passes them as initial agent context; this tool therefore just normalizes/echoes the
`UserPreference` fields back as a dict so `StylingAgent` can reason over them. The **LINE interactive**
variant (a real multi-turn question) is deferred to M6 (`AskUserPreferenceUseCase`, M6-7) — leave a docstring
note. No multi-turn ADK session in M4.

Each tool is pure-ish and individually testable with mocked Gemini/ES/storage clients (Phase 1 verify).


### Phase 2 — Agents + delegation (M4-1, M4-2, M4-3)


**`ClosetAgent` (M4-2).** `build_closet_agent()` returns an `Agent(name="ClosetAgent",
model=settings.agent_model, instruction=..., tools=[analyze_clothing_image, search_closet])`. Instruction
(from the deep-dive): "Search the user's closet or shared closet for outfit items. Given clothing analysis
results, generate a natural-language description of complementary items and search for matches." The
description-generation step is the agent's LLM reasoning; the tool does the embedding (req §8.3).

**`StylingAgent` (M4-3).** `build_styling_agent()` returns `Agent(name="StylingAgent", ...,
tools=[ask_preference, style_synthesizer])`. Instruction: "Collect user preferences and generate the final
coordinate image."

**`StylingOrchestratorAgent` (M4-1).** `build_orchestrator()` returns `Agent(name="styling_app",
model=settings.agent_model, instruction="You coordinate outfit suggestions. Delegate to ClosetAgent for
search tasks and StylingAgent for preference handling and image generation.",
sub_agents=[build_closet_agent(), build_styling_agent()])`. `agent.py` sets `root_agent =
build_orchestrator()`.

**Context & A2A-ready discipline (ADL-019).** The orchestrator receives `session_id`, `user_id`, and the
selected `source` as the initial user message (deep-dive open-question #2 pattern); tools fetch data rather
than receiving it preloaded. No shared in-memory state across agents; each sub-agent owns its toolset. This
keeps a future A2A service-split a config change.

Why this order: the three agents are thin once the tools work; building them last means Phase 2 is wiring +
prompt tuning, verifiable immediately on the Web UI.


### Phase 3 — Validation & acceptance


The primary acceptance path is the **hero "try without uploading" demo against the M3-seeded shared
closet**: with local infra up (`make dev`; if the stores are empty because the containers were recreated,
re-run `scripts/seed_shared_closet/run_seed.py` — idempotent), run `adk web`, select `styling_app`, and
drive a coordination turn for `source=SHARED_CLOSET`. Confirm: delegation to `ClosetAgent`, a
`search_closet` tool call returning seeded `__shared__` items **with the CC BY-SA 4.0 attribution**, and a
`style_synthesizer` result (generated image or collage). Optionally also exercise `source=CLOSET` by
uploading 2–3 garments through the existing M2 flow (the M2-5 worker indexes them with the signed-in
`user_id`). Capture the event stream (it should match the M1-4 shape). Run `pytest`. Then flip M4-1…M4-9 to
✅ in `feature-matrix-phase01.md` with the evidence, and (since the agents are now real code, not stubs)
move the M4 nodes in `architecture-overview.md` from Stub to Done.


## Concrete Steps


Run from the repository root `/Users/ran/my-app/gen-fashion` unless stated otherwise.

**Phase 0.**


    # scaffold the Python package (replace the TS tree)
    cd adk-agent-service
    git rm src/index.ts src/config.ts src/tools/*.ts src/agents/*.ts package.json tsconfig.json
    mkdir -p styling_app/agents styling_app/tools styling_app/adapters tests
    # author pyproject.toml / requirements.txt, Dockerfile, .env.example, styling_app/* per the layout above
    python -m venv .venv && . .venv/bin/activate
    pip install google-adk google-genai elasticsearch==8.11.0 boto3 pydantic-settings python-dotenv pytest pytest-asyncio
    pip freeze > requirements.txt   # or pin in pyproject.toml

    # smoke: the Web UI must list the app (needs GOOGLE_GENAI_API_KEY in .env for the model)
    adk web        # open the printed URL; confirm "styling_app" appears in the agent dropdown


Expected: the `adk web` server starts and the dropdown shows `styling_app`. Then update
`docker-compose.yml` and confirm the container builds:


    cd /Users/ran/my-app/gen-fashion
    docker-compose build adk-agent-service
    docker-compose up adk-agent-service   # should start `adk api_server` and stay healthy


**Phase 1 / Phase 2.** Implement the tools, registry, adapters, then the agents per Plan of Work. Re-run
`adk web` after Phase 2 to confirm the orchestrator lists its sub-agents and tools.

**Phase 3 (acceptance).**


    # 1. confirm the M3-seeded shared closet is present (seeded & verified 2026-06-10)
    cd /Users/ran/my-app/gen-fashion && make dev        # boots ES, Firestore/Auth emulators, MinIO, fastapi
    curl -s 'http://localhost:9200/clothing_items/_count' -H 'Content-Type: application/json' \
      -d '{"query":{"term":{"user_id":"__shared__"}}}'   # expect count: 90
    # if 0 (containers recreated; compose has no data volumes), re-seed — idempotent:
    #   cd scripts/seed_shared_closet && . .venv/bin/activate && python run_seed.py

    # (optional, for the CLOSET source) populate personal closet data via the M2 flow:
    # make web   # Flutter app; sign in, upload 2-3 garments

    # 2. run the agents
    cd adk-agent-service && . .venv/bin/activate && adk web
    # select styling_app; send: "Suggest an outfit from the shared closet. user_id=<uid> source=SHARED_CLOSET"
    # observe: delegation -> search_closet -> attributed __shared__ candidates -> style_synthesizer -> final answer
    # (optional) repeat with "…from my closet. user_id=<uid> source=CLOSET" against the M2-uploaded items

    # 3. tests
    cd /Users/ran/my-app/gen-fashion/adk-agent-service && . .venv/bin/activate && pytest -q


Expected `pytest`: tool tests and the registry test pass (Gemini/ES/storage mocked). Expected Web UI: a final
answer containing candidate items and a coordinate image URL (or collage), with tool-call/tool-result events
visible.


## Validation and Acceptance


Acceptance is observable behavior, not "code exists":

1. **ADK Web UI lists and runs the orchestrator.** `cd adk-agent-service && adk web` shows `styling_app`;
   sending a `source=SHARED_CLOSET` coordination request causes the orchestrator to **delegate** to
   `ClosetAgent`, call **`search_closet`**, and return candidate items drawn from the M3-seeded
   `__shared__` docs in `clothing_items` (verified by the `curl` above), each carrying the CC BY-SA 4.0
   attribution. Optionally, a `source=CLOSET` request for a `user_id` with M2-uploaded items returns those
   items. This satisfies the M4 exit criterion "Orchestrator + sub-agents run on local ADK Web UI" and
   req §15 Phase 1a #1.
2. **Each tool is callable end-to-end.** `analyze_clothing_image` returns a structured analysis for a real
   garment URL; `search_closet` returns ES-backed candidates; `style_synthesizer` returns a reachable image
   URL (generated or collage); `ask_preference` returns a normalized preference dict.
3. **Tests pass.** `pytest -q` in `adk-agent-service` is green for the registry and the four tools (mocked
   clients).
4. **`make dev` stays coherent.** The `adk-agent-service` container builds and runs `adk api_server` without
   crashing.

Record the `adk web` transcript / event capture and the `pytest` summary in **Artifacts**. Only then flip
M4-1…M4-9 to ✅ in `feature-matrix-phase01.md` and recolor the M4 nodes in `architecture-overview.md`.

Limitation to state explicitly: the local `SHARED_CLOSET` data is the M3 **keyword-only subset** (90 items,
3 demo closets, no embedding vectors — the full 2,000+ vector seed on GCE ES is deployment-deferred per
M1-3), so for `SHARED_CLOSET` the kNN clause matches nothing locally; keyword-first results are the
acceptance bar, with kNN as additive (it can only fire for `CLOSET` items, whose M2-5 pipeline does embed).
Closet-level (`closetId`) filtering is an M5 add-on. `RAKUTEN` is Phase 1b.


## Idempotence and Recovery


- Re-running `adk web` / `adk api_server` is safe and stateless.
- `search_closet` is read-only against Elasticsearch — safe to repeat.
- `style_synthesizer` writes a **new** object each call (UUID filename) — repeats do not overwrite; orphaned
  demo images in MinIO/R2 are acceptable for MVP (same stance as M2 §6.10).
- The TS deletion is the only destructive step; it is recoverable from git history if the Python rebuild is
  abandoned. Do the deletion in the same commit as the Python scaffold so the tree is never half-built.
- If a Gemini model is unavailable on the configured backend, set `AGENT_MODEL` accordingly (`gemini-2.5-flash`
  on Vertex AI per M1-4; `gemini-2.0-flash` with a direct API key) — no code change (M4-9).
- If `pip install google-adk` pulls a `google-genai` version that conflicts with the image-gen call, pin
  `google-genai` to the ADK-compatible version and adapt the `generate_content` call shape; record it in
  Surprises.


## Artifacts and Notes


All captured 2026-06-11, local `make dev` infra + `.venv` `adk api_server` (the REST engine behind
`adk web`; the Web UI itself verified serving `/dev-ui/` 200 and listing `styling_app`).

- **Acceptance transcript (`SHARED_CLOSET`, condensed; full JSON in `docs/local/m4_run_events*.json`,
  collage in `docs/local/coord.jpg`):**

      user: Suggest an outfit from the shared closet. user_id=demo-user source=SHARED_CLOSET ...
      styling_app   CALL transfer_to_agent {"agent_name": "ClosetAgent"}
      ClosetAgent   CALL search_closet {"description":"casual shirt","source":"SHARED_CLOSET","user_id":"demo-user","category":"shirt","colors":["blue"]}
      ClosetAgent   RESP search_closet [{"item_id":"c4c2f794-…","source":"SHARED_CLOSET","image_url":"http://localhost:9000/gen-fashion-images/__shared__/closet/c4c2f794-….jpg?X-Amz-…","attribution":"Clothing Dataset (CC BY-SA 4.0)"}, …]
      ClosetAgent   CALL search_closet {"description":"casual pants", …}   → seeded __shared__ Pants items
      ClosetAgent   CALL search_closet {"description":"sneakers", "colors":["white"], …} → []  (no white shoes in seed)
      ClosetAgent   CALL transfer_to_agent {"agent_name": "StylingAgent"}
      StylingAgent  CALL style_synthesizer {"user_id":"demo-user","item_image_urls":[shirt_url, pants_url],"style_description":"casual spring outfit"}
      StylingAgent  RESP style_synthesizer {"coordinate_image_url":"http://localhost:9000/gen-fashion-images/demo-user/coordinates/c40b924e….jpg?X-Amz-…","model_used":"collage-fallback"}
      StylingAgent  TEXT "Here is a casual spring outfit, put together with a shirt and pants: http://…"

  The coordinate URL fetched HTTP 200, 281,033 bytes, JPEG 1140×720 — a collage of the two seeded
  garments (ADL-005 path; see Surprises for the quota reason).
- **Event shape vs. M1-4:** identical single-`Event` JSON (`author`, `content.parts[*]` with
  `functionCall`/`functionResponse`/`text`, batched tokens); delegation adds `transfer_to_agent`
  call/response pairs. 11 events for the first full delegated turn.
- **`pytest -q`:** `17 passed, 1 warning in 1.31s` (registry 4, tools 10, agent topology 3; Gemini/ES/
  storage mocked, including own-presigned-URL storage fetch regression).
- **`clothing_items` proof:** `curl …/_count {"term":{"user_id":"__shared__"}}` → `{"count":90}`; the
  acceptance `search_closet` results are drawn from those docs (item_ids match seeded UUIDs).
- **Container:** `docker-compose build adk-agent-service` → `Built`; `docker-compose up -d` → container
  Up, `GET :3000/list-apps` → `["styling_app"]`.
- **Model used for acceptance:** `AGENT_MODEL=gemini-2.5-flash-lite` (M4-9 env override; see Surprises).


## Interfaces and Dependencies


- **`google-adk`** (PyPI; import `google.adk`) — the agent framework: `Agent`/`LlmAgent`, `sub_agents`,
  function tools, and the `adk web` / `adk api_server` CLIs. Core of M4.
- **`google-genai`** — Gemini client for `analyze_clothing_image` (structured output), `search_closet`
  (text embedding via `gemini-embedding-2`), and `style_synthesizer` (Nano Banana `gemini-2.5-flash-image`).
  Reuses the call shapes proven in `gemini_analysis.py` and `poc/image_generation/run_poc.py`.
- **`elasticsearch==8.11.0`** (sync client) — queries the `clothing_items` index created/populated by M2-5/M2-9.
  Same version as `fastapi-service` to avoid wire-protocol drift.
- **`boto3`** — S3-compatible client for R2/MinIO, to fetch garment bytes and store generated coordinates,
  reusing the M2 `R2_*` credentials and bucket.
- **`pydantic-settings`, `python-dotenv`** — env config parity with `fastapi-service/app/config.py`.
- **External services (local via `make dev`):** Elasticsearch (`localhost:9200`), MinIO (`localhost:9000`),
  and a Gemini backend (direct API key `GOOGLE_GENAI_API_KEY`, or Vertex AI ADC with
  `GOOGLE_GENAI_USE_VERTEXAI=true`).
- **Upstream artifacts:** the `clothing_items` ES schema (M2-9), the analysis response schema (M2-5), the
  Nano Banana + collage PoC (M1-2), the model IDs/dimensions in `fastapi-service/app/config.py`, and the
  **M3 shared-closet data + adapter** — the seeded `__shared__` docs (90 items, 3 closets,
  `scripts/seed_shared_closet/run_seed.py`, re-runnable/idempotent) and the M3-3
  `shared_closet_search.py` query shape + attribution string that `search_closet` mirrors.
- **Downstream (M5, not built here):** `Runner` driving these agents behind `POST /internal/run-session`
  (ADL-020); the Firestore `agentEvents` relay and session-state writes via `FirestoreStyleSessionRepository`
  (ADL-011 / ADL-021); the SSE endpoint (M5-9) and Flutter Accordion / A2UI result UI (M5-10, ADL-018).


## Revision Notes


2026-06-09 — Plan created. Targets feature-matrix milestone **M4** (rows M4-1…M4-9), moved to 🟡 In progress
in the same change. Adds **ADL-022** (Python ADK stack) to `docs/req-phase01.md` and updates
`docs/architecture-overview.md` (§0 summary, §1 container node, §3 caption, §8 discrepancy #1 → resolved) to
reflect the TypeScript→Python decision. No node colors flip to Done until M4 code lands and acceptance passes.

2026-06-09 (sequencing) — A separate **M3** plan ([20260609-m3-shared-demo-closet.md](20260609-m3-shared-demo-closet.md))
was authored after noting M3 had been skipped. M3 and M4 are **unblocked siblings** feeding M5 (no dependency
between them). Recommended working order is **M3 → M4**: M3 is smaller/lower-risk and seeds the
`SHARED_CLOSET` data that turns M4's acceptance into the hero "try without uploading" demo (vs. only the
developer's hand-uploaded `CLOSET`). Per the user's "one ExecPlan at a time" preference, M4 may be treated as
**queued behind M3** — both plan files exist, but only M3 need be actively worked first.

2026-06-11 (completion) — **M4 executed and accepted.** All phases done in one pass: Python ADK rebuild
(ADL-022, TS deleted), registry + four tools + thin adapters, three-agent topology, live `SHARED_CLOSET`
acceptance against the M3 seed, `pytest` 17 passed, container healthy. Deviations from the plan text,
all recorded in Surprises/Decision Log: tests live in `styling_app/tests/` (ADK app-discovery), the ES
keyword clause is tokenized case-insensitive `term`s (keyword-typed fields), acceptance used
`AGENT_MODEL=gemini-2.5-flash-lite` (free-tier quota) and the collage fallback (no image-gen quota).
Post-review hardening added `.dockerignore` and storage-key re-fetch for ADK-owned signed URLs in container
runs.
Synced in the same change: `feature-matrix-phase01.md` M4-1…M4-9 → ✅ (+ header note), and
`architecture-overview.md` (§0 milestone summary, §1 container colors + 読み取りポイント, §3 agents → Done,
§5 caption/participant, §7 roadmap M4 → Done). M5 is now the active critical path.

2026-06-10 (M3 completion sync) — **M3 is complete for the local subset** (live seed run & verified:
90 items, 3 demo closets `adult-01`/`adult-02`/`child-01`, idempotent; only the full vector seed on GCE ES
remains deployment-deferred per M1-3). **M4 is now the active ExecPlan.** Plan updated accordingly, before
execution started: (a) acceptance/Phase 3 now lead with the hero `SHARED_CLOSET` demo against the seeded
data instead of requiring hand-uploaded M2 items; (b) `search_closet` (M4-6) sets
`attribution="Clothing Dataset (CC BY-SA 4.0)"` on `SHARED_CLOSET` results (parity with the M3-3 adapter,
req §16.3) and resolves shared `image_url`s from the `__shared__/closet/{item_id}.jpg` R2 key; (c) noted
that shared docs carry no embeddings locally (kNN inert for `SHARED_CLOSET` until the deployment-phase
seed) and carry `closetId`/`closetKind`, with closet-level filtering an M5 add-on per the M3 Decision Log
(no `closet_id` parameter in M4). No architecture or scope change — milestone boundaries, the three-agent
topology, and the four tools are unchanged, so no `architecture-overview.md` or feature-matrix status
update is needed for this revision.
