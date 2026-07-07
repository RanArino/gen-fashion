# MQ - Rakuten Search Tags for Interesting Items


This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.


This plan follows `PLANS.md` at `/Users/ran/my-app/PLANS.md`.


## Purpose / Big Picture


Assisted Coordinate can search Rakuten for purchasable suggestions and save a suggestion into the user's closet as an **Interesting** item. Today, the Rakuten search query is optimized for recall, but the metadata saved with an imported Interesting item is thin: it usually has `category`, sometimes `colors`, and only whatever `tags` the `search_rakuten` result carried. Since imported Rakuten items do not run the full Gemini image-analysis pipeline, they can be harder to find later from Standard Coordinate `CLOSET` mode unless the user manually edits tags.

After this change, when the agent decides a Rakuten search, it also supplies a concise list of **English metadata tags** for the intended item. These tags are stored on every candidate returned from that search and are copied into the closet item if the user saves the candidate as Interesting. The tags are not required to be appended to the actual Rakuten keyword query; the query remains short enough to avoid over-filtering and zero-result searches.

Observable success: in a Style & Shop run, a `search_rakuten` tool call can include `tags: ["chino", "stretch", "casual"]` while the actual query stays broad such as `"beige pants"`. Candidate cards still show Rakuten results. If the user saves one candidate as Interesting, the resulting `users/{uid}/closet/{itemId}.tags` and Elasticsearch `tags` contain those English tags, without running image analysis.


## Progress


- [x] (2026-07-07) ExecPlan authored after inspecting `search_rakuten`, ADK assisted fallback, `ImportSuggestedClosetItemUseCase`, closet metadata indexing, and Phase 2 feature matrix.
- [x] (2026-07-07) Phase 2 requirements and feature matrix synchronized for MQ (`docs/req-phase02.md` §3.7, `docs/feature-matrix-phase02.md` MQ-1...MQ-5 set to 🟡 In progress).
- [ ] Implement ADK `search_rakuten` tag contract and fallback tag generation.
- [ ] Preserve tag metadata through candidate finalization, UI candidates, and save-as-Interesting import.
- [ ] Add backend/ADK tests and run targeted plus full relevant suites.
- [ ] Record outcomes and any implementation discoveries.


## Surprises & Discoveries


- Observation: Imported Rakuten suggestions are indexed in Elasticsearch immediately, even though they do not run image analysis.
  Evidence: `fastapi-service/app/use_cases/closet/import_suggested_item.py` calls `embedding_search.index_item(..., tags=[tag.value for tag in item.tags], category=item.category, colors=item.colors, season=item.season, embedding=None, ownership_status="INTERESTING", origin="RAKUTEN")`.

- Observation: Standard Coordinate `CLOSET` candidate search is Elasticsearch-based, not Firestore-based.
  Evidence: `adk-agent-service/styling_app/tools/search_closet.py` calls `elasticsearch.hybrid_search(...)`; `adk-agent-service/styling_app/adapters/elasticsearch.py` keyword-matches description tokens against `tags`, `category`, `colors`, and `season`.

- Observation: The Rakuten query should stay separate from tags because too many terms can reduce recall.
  Evidence: `adk-agent-service/styling_app/tools/search_rakuten.py::_search_keywords` already broadens the request through several keyword variants and stops once enough results are found; stuffing every metadata tag into `query` would work against that recall behavior.


## Decision Log


- Decision: Extend `search_rakuten` with an optional `tags: list[str] | None` parameter and candidate field, instead of encoding metadata tags into the query string.
  Rationale: The LLM can provide useful metadata while the adapter keeps recall-oriented search keywords short. This directly addresses the user's concern that tags may over-constrain Rakuten searches.
  Date/Author: 2026-07-07 / Codex

- Decision: Store tags as English canonical strings and de-duplicate them with existing color/category-derived tags before import.
  Rationale: Closet tags are searchable metadata, not localized display copy. English tags keep Elasticsearch keyword matching stable across UI language changes.
  Date/Author: 2026-07-07 / Codex

- Decision: Do not add Gemini image analysis for imported Rakuten suggestions in this plan.
  Rationale: The requested improvement can be achieved during the already-running search/proposal step, avoiding extra latency, cost, and failure modes when saving Interesting items.
  Date/Author: 2026-07-07 / Codex

- Decision: No architecture-overview diagram update is required for this plan.
  Rationale: The component graph, services, routes, storage ownership, and external integrations do not change; only a candidate metadata field is threaded through the existing ADK -> FastAPI -> Firestore/Elasticsearch flow.
  Date/Author: 2026-07-07 / Codex


## Outcomes & Retrospective


Not yet implemented.


## Context and Orientation


Relevant current flow:

- Flutter Assisted Coordinate (`flutter-web-app/lib/coordination/coordination_screen.dart`) lets the user choose anchor closet items, starts an assisted session, renders proposed candidates, and calls `POST /closet/import-suggestion` when the user saves a Rakuten candidate as Interesting.
- FastAPI import (`fastapi-service/app/use_cases/closet/import_suggested_item.py`) looks up the selected candidate from `session.proposed_candidates`, copies the external image into private storage, creates a READY closet item with `ownershipStatus=INTERESTING`, and indexes metadata into Elasticsearch.
- ADK `search_rakuten` (`adk-agent-service/styling_app/tools/search_rakuten.py`) currently accepts `query`, `category`, `colors`, and `limit`, calls the Rakuten adapter, and returns candidate dicts with `tags` derived from `colors`.
- ADK assisted fallback (`adk-agent-service/styling_app/server.py::_run_assisted_rakuten_fallback`) runs a deterministic Rakuten query if the LLM returns no Rakuten candidates.
- Standard Coordinate `CLOSET` mode later finds saved Interesting items through Elasticsearch keyword/filter search in `adk-agent-service/styling_app/adapters/elasticsearch.py`.

Terms:

- **Search query**: the concise keyword string sent to Rakuten, optimized for enough results.
- **Search tags**: English metadata labels generated alongside the query, stored on candidates and later closet items, not necessarily sent to Rakuten.
- **Interesting item**: a saved Rakuten suggestion in the user's closet with `ownershipStatus=INTERESTING`.


## Plan of Work


First, update the ADK tool contract. In `adk-agent-service/styling_app/tools/search_rakuten.py`, add an optional `tags: list[str] | None = None` parameter. Update the docstring to tell the agent that tags are English metadata for the intended item and do not need to be included in the Rakuten query. Candidate results should include normalized tags from `tags` plus existing `colors`, de-duplicated in stable order. Keep `_search_keywords()` recall-oriented: do not append all tags to every keyword. If tags are useful for broad recall, allow only a small safe subset such as color/category terms already covered by `colors`/`category`; do not add material/fit/style tags to the keyword variants by default.

Second, update the server-bound tool wrapper and agent instructions. In `adk-agent-service/styling_app/server.py`, update `_build_propose_rakuten_tool()` so `phase_search_rakuten` accepts and forwards `tags`. Update Assisted-mode proposal text in the same file so the LLM is explicitly instructed to call `search_rakuten` with a concise query and a separate English `tags` list containing item descriptors such as garment type, color, material, fit, formality, season, and style. The instruction must warn that the query should stay concise and tags must not be mechanically stuffed into it.

Third, cover the deterministic fallback path. In `_run_assisted_rakuten_fallback`, add a small helper such as `_rakuten_tags_from_preference(preference, anchors)` or `_fallback_rakuten_tags(request)` that builds English tags from normalized preference colors, category/slot hints where available, and simple style words from `_style_description`. The fallback `tool_args` should include `tags`, and the synthetic tool-call event should show them so the trace remains truthful. Keep the fallback query unchanged or only minimally changed to preserve recall.

Fourth, preserve tags through proposal finalization and import. Existing candidate dicts flow through `_finalize_assisted_candidates` into `session.proposedCandidates`, then `ImportSuggestedClosetItemUseCase` copies `candidate["tags"]` into Firestore and Elasticsearch. Verify this remains true and that candidate import does not append localized product names to tags. If current local code still appends `candidate["name"]` as a tag, remove that behavior as part of this plan.

Fifth, update previews/tests only where needed. The UI already displays candidate tags from `candidate["tags"]` and closet tags from Firestore, so no new UI contract is required. If the trace Preview for `search_rakuten` currently shows only query/category/colors, optionally add tags to the Preview field list in `coordination_screen.dart`; this is useful for debugging but not required for the data flow. Do not add a new user-facing edit surface.


## Concrete Steps


Work from `/Users/ran/my-app/gen-fashion` unless stated otherwise.

1. Update `adk-agent-service/styling_app/tools/search_rakuten.py`.
   - Add `tags` parameter to `search_rakuten`.
   - Normalize/de-duplicate returned candidate tags.
   - Add unit tests in `adk-agent-service/styling_app/tests/test_tools.py` proving `tags=["chino", "stretch"]` appear on every returned candidate, with colors preserved and no duplicates.

2. Update `adk-agent-service/styling_app/server.py`.
   - Add `tags` parameter to the bound `phase_search_rakuten` wrapper.
   - Update assisted prompt/context text to request separate English tags.
   - Add fallback tags in `_run_assisted_rakuten_fallback`.
   - Add tests in `adk-agent-service/styling_app/tests/test_run_session_endpoint.py` proving wrapper/fallback tool args include tags and Japanese color labels normalize to English tags when relevant.

3. Update FastAPI import behavior if needed.
   - Confirm `fastapi-service/app/use_cases/closet/import_suggested_item.py` imports only `candidate["tags"]` and does not append `candidate["name"]`.
   - Add/adjust `fastapi-service/tests/use_cases/test_closet_use_cases.py` so an imported Rakuten candidate with Japanese `name` and English `tags` persists/indexes only the English tags.

4. Optional trace polish.
   - If implemented, update `flutter-web-app/lib/coordination/coordination_screen.dart` `search_rakuten` Preview to show a `tags` field.
   - Add/adjust Flutter widget tests only if the Preview changes.

5. Run validation commands.

    cd adk-agent-service
    .venv/bin/python -m pytest styling_app/tests/test_tools.py styling_app/tests/test_run_session_endpoint.py -q

    cd ../fastapi-service
    .venv/bin/python -m pytest tests/use_cases/test_closet_use_cases.py -q

    cd ../flutter-web-app
    flutter analyze
    flutter test

If local `.venv` directories are unavailable, use the repository's Docker path:

    docker-compose run --rm adk-agent-service pytest styling_app/tests/test_tools.py styling_app/tests/test_run_session_endpoint.py -q
    docker-compose run --rm fastapi-service pytest tests/use_cases/test_closet_use_cases.py -q


## Validation and Acceptance


Acceptance criteria:

- `search_rakuten(query="beige pants", category="bottom", colors=["beige"], tags=["chino", "stretch", "casual"])` returns candidates whose `tags` include `beige`, `chino`, `stretch`, and `casual` once each.
- The Rakuten query remains broad enough for recall; tests should assert tags are not blindly concatenated into every keyword variant.
- In an assisted fallback trace, the `search_rakuten` tool call includes a `tags` list separately from `query`.
- Saving a Rakuten candidate as Interesting stores those tags in Firestore and indexes the same tags into Elasticsearch.
- No Gemini image-analysis call is added to the import path.
- Existing Assisted Coordinate behavior remains intact: candidate cards render, save-as-Interesting still works, and Standard Coordinate can reuse Interesting READY items.

Minimum automated verification:

- ADK targeted tests pass.
- FastAPI closet use-case tests pass.
- Flutter analyze/test pass if the trace preview is touched.

Manual verification after implementation:

1. Run a Style & Shop session with Rakuten available.
2. Inspect the `search_rakuten` trace event: `query` is concise and `tags` is a separate English list.
3. Save one Rakuten candidate as Interesting.
4. Inspect Firestore `users/{uid}/closet/{itemId}.tags`; it contains the search tags, not the localized product name.
5. Optionally query Elasticsearch for that item id and confirm `_source.tags` matches Firestore.


## Idempotence and Recovery


The code changes are idempotent. Re-running tests and smokes does not duplicate production data. Manual Style & Shop checks may create new `INTERESTING` closet items; delete them through the Closet UI or `DELETE /closet/items/{id}` if cleanup is needed.

If Rakuten is unavailable, the agent must continue to degrade to anchor/closet-only suggestions as it does today. Tests for tag handling should use mocked Rakuten responses rather than live API credentials.

If a future implementation accidentally appends too many tags to the query and live searches return zero results, revert the query-building change and keep tags only in candidate metadata. The data contract still works because tags are separate from query.


## Artifacts and Notes


Current code facts used to author this plan:

- `adk-agent-service/styling_app/tools/search_rakuten.py` candidate tags are currently `list(colors or [])`.
- `fastapi-service/app/use_cases/closet/import_suggested_item.py` is the only save-as-Interesting path.
- `adk-agent-service/styling_app/adapters/elasticsearch.py` keyword-matches `tags`, `category`, `colors`, and `season`.
- `fastapi-service/app/adapters/elasticsearch_embedding_repo.py` indexes imported Interesting items with `embedding=None`, so keyword metadata matters.


## Interfaces and Dependencies


Changed internal tool interface:

- `search_rakuten(query: str, category: str | None = None, colors: list[str] | None = None, tags: list[str] | None = None, limit: int = 5) -> list[dict]`

Candidate dict field:

- `tags: list[str]` remains the same field name, but its source becomes "AI-provided search metadata plus normalized colors" rather than colors-only.

No public HTTP API changes:

- `POST /sessions/{id}/assist` request body is unchanged.
- `POST /closet/import-suggestion` request body is unchanged.
- Firestore `users/{uid}/closet/{itemId}.tags` remains `list[str]`.
- Elasticsearch `clothing_items.tags` remains `keyword`.

Dependencies:

- No new package dependency.
- No new external service.
- No Gemini image-analysis call in the import path.
