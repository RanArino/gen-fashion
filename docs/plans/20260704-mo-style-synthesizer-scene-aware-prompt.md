# MO — Scene-Aware Style Synthesizer Prompt (Rakuten Non-Garment Photo Robustness)


This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.


This plan follows `PLANS.md` at `/Users/ran/my-app/PLANS.md`.


## Purpose / Big Picture


Today, when a user generates a coordinate image from Rakuten-sourced items (Assisted / "Style & Shop" mode, milestone MK), the result is frequently wrong if the Rakuten product photo is not a plain garment-on-white-background shot. Rakuten listings commonly show the item worn by a model on a street, held in someone's hand, or staged alongside unrelated objects (a bag next to a notebook and a jacket). The current generation prompt (`_TRYON_PROMPT` in `adk-agent-service/styling_app/adapters/image_generation.py`) implicitly assumes every reference photo is a clean single-garment shot, so the model has no instruction to ignore the original person, background, pose, or unrelated props in a scene photo — it blends them into the output instead of isolating the intended item.

This ExecPlan makes the generation call **scene-aware**: each reference image is now labeled with the garment/accessory category it represents (when known), and the prompt explicitly instructs the model to extract only that labeled item from each photo and ignore any person, background, pose, or unrelated object shown in it. This is documented and scoped in `docs/local/20260704_styling_image_generation_issue.md` as "Phase 1 (Approach B)"; this plan implements Phase 1 only. No image pre-selection, cropping, or image-type classification (that document's Phase 2/3) is in scope here.

How to see it working after the change: run `pytest adk-agent-service/styling_app/tests -k "image_generation or style_synthesizer"` and confirm the new/updated tests pass. Then, with real Vertex AI credentials configured, call `style_synthesizer` (or run an Assisted Coordinate session) with the three `docs/local/coord.jpg`-style inputs (a plain garment photo, a person wearing a garment on the street, and a hand holding a bag amid other objects) and visually confirm the generated coordinate keeps only the intended garments' color/pattern/shape, without the original model's face/pose, the street background, or the notebook/jacket props leaking into the output.


## Progress


- [x] (2026-07-04) MO-1 — `image_generation.generate()` now takes `items: list[dict]` (`{"bytes", "category", "note"}`) and inserts a `Reference photo N: {category}.` text part before each image part.
- [x] (2026-07-04) MO-2 — `_TRYON_PROMPT` extended to instruct the model to treat each reference photo as labeled and extract only the named item, ignoring any person/pose/background/unrelated object in that photo.
- [x] (2026-07-04) MO-3 — `style_synthesizer` gained an optional `item_categories: list[str] | None` param; it builds `{bytes, category, note}` per item and passes that list to `image_generation.generate()`.
- [x] (2026-07-04) MO-4 — `styling_app/tests/test_image_generation.py` added: asserts the text part immediately before each image part carries the right label (`"top"` for a labeled item, `"item"` for an unlabeled one) and that the final part still contains the style description.
- [x] (2026-07-04) MO-5 — `test_search_rakuten_category_reaches_style_synthesizer` added to `test_tools.py`: calls `search_rakuten` then `style_synthesizer` and asserts the captured `generate()` items carry the category that originated in the Rakuten result. `test_style_synthesizer_forwards_categories` covers the direct case. `pytest styling_app/tests -q` (run via `.venv/bin/python -m pytest styling_app/tests -q` from `adk-agent-service/`) reports **60 passed**.
- [x] (2026-07-06) MO-6a — Follow-up regression fix after a real EC advertisement/collage image reproduced the failure: `server.py` now threads server-authoritative selected item categories into both the constrained generate tool and the direct generate fallback, so production Assisted/Style & Shop generation no longer loses the Rakuten/search category labels before `image_generation.generate()`. After a second reported regression showed the harsher prompt could degrade into a `collage-fallback`-quality result, `_TRYON_PROMPT` was shortened and `style_synthesizer` now retries once with a compact prompt. If generation still fails, no collage is saved as a completed coordinate; the session errors instead. Tests updated to assert category propagation, retry behavior, and rejection of `collage-fallback` results through the production generate paths.
- [ ] MO-6 — Manual visual check against the three `coord.jpg`-style inputs; not run (requires live Vertex AI credentials — see Outcomes).


## Surprises & Discoveries


- Discovery (2026-07-06): The first MO implementation added `item_categories` to `style_synthesizer` and tested direct `search_rakuten` -> `style_synthesizer` calls, but the production generate paths in `server.py` never passed `item_categories`. Real sessions therefore labeled every reference as generic `"item"` even when `selectedItems` carried `category`. That made the prompt too weak for EC advertisement/collage photos like shorts listings with text, badges, multiple people, and close-up wearing shots.
- Discovery (2026-07-06): A later generated result was visibly just the input garments side by side, meaning `style_synthesizer` had reached `collage-fallback`. The previous prompt hardening used too many negative constraints and likely increased the chance that the image model returned no image. Because fallback was immediate and silent, the UI presented the diagnostic collage as if it were a completed coordinate.


## Decision Log


- Decision: Scope this plan to Phase 1 (prompt/labeling) only, from `docs/local/20260704_styling_image_generation_issue.md`. Do not touch Rakuten image selection (`rakuten.py::_first_image_url`), image-type classification in `gemini.py::analyze`, or cropping — those are the document's Phase 2/3 and are explicitly out of scope here.
  Rationale: Requested by the user; Phase 1 is independently verifiable, requires no new adapter/API calls, and is the cheapest lever to test before investing in classification or cropping.
  Date/Author: 2026-07-04 / ExecPlan

- Decision: No new ADL. This is a prompt/interface refinement inside the existing `GenerateCoordinateUseCase` / `style_synthesizer` contract (req-phase01 §6.5, ADL-005), not a new architectural component, model, or data store.
  Rationale: Matches the precedent set by ML/MM/MN in `docs/feature-matrix-phase02.md` for scoped fixes against already-shipped milestones; the model constraint from ADL-005 (Nano Banana / Imagen 4 only, collage fallback on failure) is unchanged.
  Date/Author: 2026-07-04 / ExecPlan

- Decision: Thread category via a new optional `item_categories: list[str] | None` parameter on `style_synthesizer`, positionally parallel to `item_image_urls`, rather than replacing `item_image_urls` with a list of objects.
  Rationale: `item_image_urls` is a plain `list[str]` today and is also the shape the un-constrained `StylingAgent` (`agents/styling_agent.py`, `_GENERATION_INSTRUCTION` path) already calls with. Keeping it a flat list of URLs avoids a breaking change to that agent-facing tool signature; the new parameter is additive and optional, defaulting to `None` (all items unlabeled, current behavior preserved).
  Date/Author: 2026-07-04 / ExecPlan

- Decision: Bind `item_categories` from `request.selected_items` inside the server's constrained generate paths, the same way `item_image_urls`, user ID, gender, wearer age, and language are already server-bound.
  Rationale: The model-visible tool only exposes `style_description`; allowing the LLM to choose categories would reopen the same trust boundary issue ME fixed for URLs/user identity. The selected candidates are the authoritative source because they round-trip from `search_closet` / `search_rakuten` through the user's explicit selection gate.
  Date/Author: 2026-07-06 / ExecPlan follow-up

- Decision: Keep the reference-photo instruction short and positive, and retry once with an even more compact prompt before failing the generation.
  Rationale: The failure mode is not just "wrong item extracted"; it is also "image model returns no image, then collage fallback is shown as completion." A long list of negative constraints can reduce generation reliability. A concise primary prompt plus compact retry gives the model a simpler second chance without presenting a diagnostic collage as the final coordinate.
  Date/Author: 2026-07-06 / ExecPlan follow-up

- Decision: Do not accept `collage-fallback` as a completed user-facing coordinate.
  Rationale: The product goal is an actual coordinate image. A collage is useful as a low-level diagnostic artifact, but presenting it as "completed" creates exactly the broken result this plan is meant to prevent. If both generation attempts fail, the session should error and let the user retry or choose different candidates.
  Date/Author: 2026-07-06 / ExecPlan follow-up


## Outcomes & Retrospective


MO-1 through MO-5 are implemented and covered by automated tests (`pytest styling_app/tests -q` → 60 passed, no regressions in the pre-existing `style_synthesizer`/`search_rakuten` suites). On 2026-07-06, MO-6a fixed a production wiring gap: selected item categories now reach `style_synthesizer` from both the ADK generate tool path and the direct fallback path. A same-day follow-up shortened the over-constrained prompt, added one compact-prompt retry, and rejects `collage-fallback` as a completed coordinate. MO-6 (the manual before/after visual comparison against the three `coord.jpg` input types) was not run in this session because it requires live Vertex AI credentials (`adk-agent-service/.env.example`) and a running stack; it remains an open item before this fix can be considered visually validated. Whoever runs MO-6 should update this section with the observed pass/partial/fail per input type.


## Context and Orientation


Three files carry the current behavior (all under `adk-agent-service/styling_app/`):

- `adapters/image_generation.py` — `generate(image_bytes_list: list[bytes], style_description: str) -> bytes`. Builds one `types.Part.from_bytes(...)` per input image, appends the `_TRYON_PROMPT` (+ style description) as a final text part, and calls Nano Banana (`gemini-2.5-flash-image`) via `_client().models.generate_content(...)`. `build_collage()` is the unrelated ADL-005 fallback used only when `generate()` raises; it is untouched by this plan.
- `tools/style_synthesizer.py` — the ADK tool wrapping `image_generation.generate`. Signature: `style_synthesizer(user_id, item_image_urls: list[str], style_description, gender="common", wearer_age="adult", language="ja")`. It fetches bytes for each URL via `image_storage.fetch_bytes`, builds a `generation_prompt` string, and calls `image_generation.generate(image_bytes_list, generation_prompt)`.
- `tools/search_rakuten.py` — already returns a `category` field per candidate item (e.g. `{"item_id": "rakuten:123", "category": "top", "image_url": ..., ...}`); this field exists today and is simply not passed forward into generation. This is the origin of the "category" this plan threads through.

`style_synthesizer` is called from two places in `adk-agent-service/styling_app/server.py`, both of which already have access to `category` on each selected item (client-supplied `selected_items` dicts, which round-trip the `category` field originally produced by `search_rakuten`/`search_closet`):

- `_build_generate_style_tool()` (~line 469) — builds the constrained per-session tool closure bound to `image_urls = _selected_image_urls(request.selected_items)`.
- `_run_generate_fallback()` (~line 630) — the direct (non-agent) generation path, using `selected = request.selected_items or []`.

This plan does **not** require editing `server.py`; the two call sites above are documented here only so a future ExecPlan (or this one, if time permits — see Idempotence) knows where `item_categories` could be wired end-to-end from the live request. The MO-5 integration test proves the category reaches `image_generation.generate()` by calling `search_rakuten` → `style_synthesizer` directly in a test, which is sufficient to validate the plumbing without touching the HTTP layer.

`docs/local/coord.jpg` holds the three representative input types referenced in `docs/local/20260704_styling_image_generation_issue.md` (plain garment, person wearing a garment, hand holding a bag amid props) — use it for the manual visual check in MO-6.


## Plan of Work


1. **`image_generation.py`**: Change `generate()`'s first parameter from `image_bytes_list: list[bytes]` to `items: list[dict]`, where each dict is `{"bytes": bytes, "category": str | None, "note": str | None}`. For each item, before appending its `types.Part.from_bytes(...)`, append a `types.Part.from_text(...)` labeling it, e.g. `f"Reference photo {i+1}: {category or 'item'}."` (+ `note` appended if present). Update `_TRYON_PROMPT` to add: reference photos may show the garment worn by a model, styled in a scene, or placed among other objects; for each labeled reference photo, extract and reproduce only the named item's color/pattern/shape, and ignore any person, pose, background, or unrelated object in that photo. Leave `build_collage()` untouched (it still takes `list[bytes]`).

2. **`style_synthesizer.py`**: Add `item_categories: list[str] | None = None` parameter. Build `items = [{"bytes": b, "category": (item_categories[i] if item_categories and i < len(item_categories) else None), "note": None} for i, b in enumerate(image_bytes_list)]` and pass `items` to `image_generation.generate(items, generation_prompt)` in place of the current `image_bytes_list`. Keep `image_generation.build_collage(image_bytes_list)` (plain bytes list) unchanged in the `except` branch.

3. **Tests** (`adk-agent-service/styling_app/tests/`):
   - New `test_image_generation.py`: monkeypatch `image_generation._client` to return a stub whose `models.generate_content(**kwargs)` captures `kwargs["contents"]` and returns a minimal fake response exposing one `inline_data.data` part. Call `generate([{"bytes": b"a", "category": "top", "note": None}, {"bytes": b"b", "category": None, "note": None}], "desc")` and assert: `contents` has a text part immediately before each image part, the labeled text part for the first item mentions `"top"`, and the final text part still contains the style description.
   - `test_tools.py`: extend `_patch_synth`'s `generate` fake to accept `(items, desc)` instead of `(images, desc)` (update the three existing `style_synthesizer` tests accordingly — `test_style_synthesizer_generated`, `test_style_synthesizer_collage_fallback`, `test_style_synthesizer_prompt_includes_child_and_gender`). Add a new test, e.g. `test_style_synthesizer_forwards_categories`, calling `style_synthesizer("user-1", ["u1.jpg", "u2.jpg"], "casual", item_categories=["top", "bag"])` and asserting the captured `items` list has `items[0]["category"] == "top"` and `items[1]["category"] == "bag"`.
   - Integration test (MO-5), e.g. `test_search_rakuten_category_reaches_style_synthesizer` in `test_tools.py`: monkeypatch `rakuten.search_items` to return one raw item (as in the existing `test_search_rakuten_maps_candidate_fields`), call `search_rakuten("white t-shirt", category="top")` to get `results`, then call `style_synthesizer("user-1", [r["image_url"] for r in results], "casual", item_categories=[r["category"] for r in results])` (with `image_storage`/`image_generation` patched as in `_patch_synth`), and assert the captured `items[0]["category"] == "top"` — proving the value that started in `search_rakuten`'s output survives to the `generate()` call.

4. Run the full `adk-agent-service` test suite to confirm no other test relies on `generate()`'s old `list[bytes]` shape.


## Concrete Steps


Working directory for all commands: `adk-agent-service/`.

1. Edit `styling_app/adapters/image_generation.py` per step 1 above.
2. Edit `styling_app/tools/style_synthesizer.py` per step 2 above.
3. Add `styling_app/tests/test_image_generation.py` and edit `styling_app/tests/test_tools.py` per step 3 above.
4. Run:

       cd adk-agent-service && python -m pytest styling_app/tests -q

   Expect all tests to pass, including the new/updated ones.

5. Manual visual check (requires Vertex AI credentials configured per `adk-agent-service/.env.example`): using the three images represented in `docs/local/coord.jpg` (plain garment / person wearing garment / hand holding bag among props), call `style_synthesizer` directly (e.g. via a short local script or an Assisted Coordinate session through the running stack) with matching `item_categories`, and inspect the generated coordinate image.


## Validation and Acceptance


- `python -m pytest styling_app/tests -q` run from `adk-agent-service/` reports all tests passing, including:
  - `test_image_generation.py` confirming a labeled text part precedes each image part in the `generate_content` call.
  - The updated `style_synthesizer` tests in `test_tools.py`, plus the new category-forwarding and search_rakuten-to-style_synthesizer integration tests.
- Manual acceptance (MO-6): generating a coordinate from the three `coord.jpg`-style inputs with categories supplied produces a result where the original model/background/pose from the "person wearing a garment" input and the notebook/jacket props from the "hand holding a bag" input are visibly absent or markedly reduced compared to a before/after run with the old prompt. Record the observed outcome (pass/partial/fail per item) in `Outcomes & Retrospective`.


## Idempotence and Recovery


All edits are pure code/prompt changes with no data migration — safe to re-run tests any number of times. If `item_categories` is omitted by a caller, every item's `category` is `None` and the labeled text part reads `"Reference photo N: item."`, i.e. behavior for existing callers (the un-constrained `StylingAgent` path, which does not pass `item_categories`) is unchanged aside from that generic per-image label. If a test import fails after the `generate()` signature change, check for any other caller of `image_generation.generate()` beyond `style_synthesizer.py` (grep confirmed none exist elsewhere in `adk-agent-service/` at plan-authoring time) before assuming the signature change is complete.


## Artifacts and Notes


- Root-cause writeup and full Phase 1/2/3 roadmap: `docs/local/20260704_styling_image_generation_issue.md`.
- Representative failure-mode screenshot: `docs/local/coord.jpg`.


## Interfaces and Dependencies


- `google.genai.types.Part.from_text` / `Part.from_bytes` — already used in this file; no new dependency.
- No new external API, library, or generated artifact is introduced.
</content>
