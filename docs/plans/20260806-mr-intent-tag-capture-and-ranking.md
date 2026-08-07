# MR — Intent Tag Capture and Proven Ranking Read Path


This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.


This plan follows `PLANS.md` at `/Users/ran/my-app/PLANS.md`.


## Purpose / Big Picture


Today gen-fashion knows what a garment *looks like* — Gemini extracts category,
colors, season, and descriptive tags at upload. It knows nothing about why the
user keeps it or who they want to be while wearing it. That gap is the reason a
general-purpose AI stylist can reproduce this product's output: everything the
ranking sees is recoverable from the photo.

After this change, a user can tag a closet item with a small, fixed set of
**intent** values — the state they want to be in when they wear it ("強気でいたい",
"守られたい", "馴染みたい") — and the styling agent's candidate search will rank
items carrying the active intent higher. The user sees this as: same closet,
same request, different order.

The thing that makes this milestone worth doing, and the thing that makes it
possible to fail, is the last step. `ownership_status` already exists in this
repository: it is written to Firestore, indexed into Elasticsearch, and read by
no ranking, search, or agent code anywhere. It is a label, not a feature. This
plan is explicitly structured so that the same outcome is impossible — the read
path and a re-runnable proof that the read path changes output ship in this
milestone, or the feature gets deleted instead of shipped.

Requirements: `docs/req-phase03.md` §1 (ADL-038, ADL-039, ADL-040, ADL-049).
Tracker: `docs/feature-matrix-phase03.md` rows **MR-1 … MR-7**.


## Progress


- [x] Milestone A — Domain vocabulary and persistence (MR-1, MR-2, MR-4). 2026-08-07.
      Steps A1-A5 implemented and A6's `pytest` verification passed (124
      passed, 1 skipped, up from 113 passed, 1 skipped before this milestone —
      11 new tests). The `make dev` / live-infrastructure half of A6 (upload
      an item, PATCH intent tags, curl the ES mapping) was **not performed**:
      the Docker daemon is unreachable from this environment's sandboxed
      shell (`docker ps` / `docker-compose up -d` both fail with "Cannot
      connect to the Docker daemon at unix:///Users/ran/.docker/run/docker.sock").
      This must be run by someone with a working local Docker daemon before
      Milestone A is considered fully verified per the plan's own acceptance
      bar.
- [ ] Milestone B — Ranking read path, on/off flag, and the ranking-change proof (MR-5, MR-6).
- [ ] Milestone C — Capture UI, API surface, and localization (MR-3, MR-7).
- [ ] Final: feature-matrix rows MR-1…MR-7 set to their end state and `docs/architecture-overview.md` synced.


## Surprises & Discoveries


- Observation: `ensure_index` returns early when the index already exists, so a
  new mapping property will **not** be applied to an existing `clothing_items`
  index by that method alone.
  Evidence: `fastapi-service/app/adapters/elasticsearch_embedding_repo.py:25` —

      exists = await self._client.indices.exists(index=self._index)
      if exists:
          return

  This matters because every developer machine and the deployed environment
  already have the index. Without an additive mapping update, `intentTags`
  falls to dynamic `text` mapping and the exact-term boost clause matches
  nothing. This is the identical failure mode already recorded for `closetId`
  in `docs/architecture-overview.md` §8 item 4, where a missing keyword
  declaration silently produced zero-hit term filters and ended coordination
  sessions in `ERROR`. Milestone A step 4 addresses it directly.

- Observation: `app/ports/embedding_search.py` (the `EmbeddingSearchPort`
  ABC) was not in the plan's file list for A4/A5, but its abstract
  `index_item` and `update_item_metadata` signatures already matched the
  concrete `ElasticsearchEmbeddingRepository` adapter's signatures exactly
  before this change (same parameter names, same optional-with-default
  pattern for `ownership_status`/`origin`/etc.). Treated as a companion
  change: added `intent_tags: Optional[List[str]] = None` to both abstract
  methods in the port to preserve that existing invariant, rather than
  letting the port's documented contract silently drift from the adapter
  that implements it. Python ABCs do not enforce signature equality at
  runtime, so nothing would have failed without this — the port would just
  have been an inaccurate description of the adapter.
  Evidence: `fastapi-service/app/ports/embedding_search.py:17` and `:43`.

- Observation: the Docker daemon is not reachable from this agent's sandboxed
  shell environment, even though the `docker` CLI itself reports a valid
  client version and `docker-compose config` can parse `docker-compose.yml`.
  `docker ps` and `docker-compose up -d` both fail with "Cannot connect to
  the Docker daemon at unix:///Users/ran/.docker/run/docker.sock. Is the
  docker daemon running?" — this looks like sandboxed socket access being
  blocked rather than Docker Desktop actually being stopped. Consequence:
  the live-infrastructure half of A6 (upload via UI, PATCH intent tags via
  API, `curl` the ES `_mapping` endpoint to confirm `intentTags` is
  `keyword` not `text`) could not be executed in this session. The unit-level
  equivalent (`test_ensure_index_issues_put_mapping_when_index_already_exists`
  in `tests/adapters/test_elasticsearch_embedding_repo.py`, mocking
  `AsyncElasticsearch`) was added and passes, but it does not substitute for
  the plan's live check against a real Elasticsearch index that may already
  have `intentTags` dynamically mapped as `text` from an earlier partial run.

- (Add findings here as work proceeds.)


## Decision Log


- Decision: Store intent as a dedicated `intent_tags` field with a closed enum
  vocabulary, rather than as entries in the existing free-form
  `ClothingItem.tags`.
  Rationale: Three properties are unobtainable on the shared field. The on/off
  proof required by MR-6 needs something to switch off — intent terms mixed
  into the generic `tags` clause at
  `adk-agent-service/styling_app/adapters/elasticsearch.py:70` cannot be
  disabled without also disabling descriptive matching. Sensitivity typing
  (ADL-040) cannot ride on a free string in an open list. And the aggregation
  planned for MT needs a stable closed vocabulary, whereas `tags` receives open
  free text from both Gemini analysis and Rakuten metadata (MQ). Recorded as
  ADL-039; this is a deliberate deviation from the 2026-08-02 discussion's
  "reuse the existing tags field" synthesis.
  Date/Author: 2026-08-06 / Phase 3 planning

- Decision: Intent is user input only. No Gemini call infers it.
  Rationale: An inferred intent is by construction recoverable from the image,
  which means it carries no information the existing metadata lacks — the exact
  degeneration ADL-038 rejects occasion for. It would also pass MR-6 for the
  wrong reason: the ranking would change, but only because the model re-encoded
  attributes already present.
  Date/Author: 2026-08-06 / Phase 3 planning

- Decision: The affective vocabularies live in a new
  `app/domain/shared/affective.py`, not in `app/domain/closet/value_objects.py`
  as this plan originally specified.
  Rationale: `domain/closet/` and `domain/styling/` are separate bounded
  contexts, and today neither imports the other — both import only
  `domain/shared/base_models`. MS-1 puts `intent` and `mood` on `UserPreference`
  in `domain/styling/`, and ADL-049's arousal coordinate is read by NA's layout.
  Defining the vocabulary inside `closet/` would force the first cross-context
  domain import in the repository, for a vocabulary that belongs to neither
  context exclusively. Moving it later means touching every import site plus the
  persisted-value assumptions, so the cheap moment is before MR ships.
  `IntentTag` is still re-exported from `app/domain/closet/__init__.py` so
  closet use cases keep their current import style.
  Date/Author: 2026-08-07 / Phase 3 planning

- Decision: Each `IntentTag` value carries a static arousal coordinate, and the
  vocabulary is authored Japanese-first rather than being restricted to concepts
  that translate cleanly.
  Rationale: NA-2 lays the free magazine out on a valence × arousal map, but
  nothing in the phase was specified that reliably *writes* an affective
  coordinate — session `MoodTag` is optional and would be sparse by
  construction, so a layout depending on it would be empty for most users.
  Putting arousal on the intent vocabulary itself supplies one axis at zero
  storage and zero extra user input (the other axis comes from MU's three-choice
  feedback). On language: choosing only concepts equally natural in Japanese and
  English generalises the vocabulary back toward occasion, which is what ADL-038
  rejects; where the English label is weaker than its Japanese source, the
  caption §2 already requires closes the gap. Per-locale vocabularies are
  prohibited — the same enum value must mean the same thing everywhere or MT
  aggregation and NA layout stop being comparable across languages.
  Recorded as ADL-049 and `req-phase03.md` §1.1.
  Date/Author: 2026-08-07 / Product owner

- Decision: MR-6's fixture must satisfy three conditions, not just "the order
  changed": sparse tagging, a change in top-N *membership*, and two different
  intents producing two different orders. The fixture is built on the shared
  demo closet so it doubles as the 90-second demo material.
  Rationale: The author controls the fixture, so "boost on/off changes the
  order" is nearly self-fulfilling — adding any weighted clause moves something.
  A gate that can be passed vacuously does not prevent the `ownership_status`
  outcome it exists to prevent. The three conditions each close one vacuous
  path: an all-tagged fixture does not resemble an opt-in feature, a tail
  reshuffle is not visible to a user, and a single fixed boost-on order means
  the clause is matching presence rather than intent.
  Date/Author: 2026-08-07 / Product owner

- Decision: The intent contribution is an additive weighted `should` clause, not
  a filter and not a rescore.
  Rationale: The existing query is keyword-first with a fail-soft kNN clause and
  already accumulates `should` terms; a weighted `should` is the smallest change
  that fits the established shape. A filter would hide untagged items entirely,
  which breaks every user who has not opted in — and opt-in is a requirement.
  Date/Author: 2026-08-06 / Phase 3 planning


## Outcomes & Retrospective


(To be completed at each milestone and at the end. The final entry must state
explicitly whether the MR-6 proof passed, and if it did not, what was deleted.)


## Context and Orientation


### The two services involved


`fastapi-service` owns closet data. It is a hexagonal (ports-and-adapters)
Python service: domain aggregates in `app/domain/`, use cases in
`app/use_cases/`, HTTP routes in `app/handlers/`, and outbound adapters in
`app/adapters/`. It writes clothing items to Firestore and mirrors a searchable
projection of them into an Elasticsearch index named `clothing_items`.

`adk-agent-service` owns the styling agents. It runs Google ADK agents that call
tools; one of those tools, `search_closet`, queries the same `clothing_items`
index that `fastapi-service` writes. It does not write to that index.

So this milestone's write path lives in `fastapi-service` and its read path
lives in `adk-agent-service`, connected only by the Elasticsearch mapping. That
mapping is therefore the contract between them, and it is the part most likely
to break silently.

`flutter-web-app` is the client. Despite the directory name it is the single
Flutter package that will also serve mobile (see `req-phase03.md` ADL-044); this
milestone touches only widgets and localization files, which are shared.


### The specific files this plan changes


Write side, `fastapi-service`:

- `app/domain/shared/affective.py` — **new module**, holds `IntentTag`,
  `MoodTag`, `Sensitivity`, and `INTENT_VOCABULARY_VERSION`. It goes in
  `shared/` and not in `closet/` because `domain/styling` needs the same
  vocabulary in MS-1 and the two contexts do not import each other (see A1).
- `app/domain/closet/value_objects.py` — currently holds `ClothingItemStatus`,
  `ClosetOwnershipStatus`, `ClothingItemId`, `ClothingTag`, `ImageEmbedding`.
  Unchanged by this milestone.
- `app/domain/closet/aggregates.py` — `ClothingItem` at line 16. It is a
  `@dataclass` whose mutators use `object.__setattr__` and call `_mark_updated()`;
  follow that idiom exactly rather than introducing a different one.
- `app/domain/closet/__init__.py` — re-exports domain names for use-case imports
  (`update_item_metadata.py` imports `ClothingTag` from `app.domain.closet`).
- `app/adapters/firestore_closet_repo.py` — serialization to and from Firestore.
- `app/adapters/elasticsearch_embedding_repo.py` — `ensure_index` mapping at
  line 24, `index_item` at line 79, `update_item_metadata` at line 124.
- `app/use_cases/closet/update_item_metadata.py` — `UpdateClosetItemMetadataUseCase.execute`
  takes keyword-only optional metadata fields and mirrors to Elasticsearch in a
  `try/except` that logs rather than fails the request.
- `app/handlers/closet_routes.py` — the closet `PATCH` route's request model.

Read side, `adk-agent-service`:

- `styling_app/adapters/elasticsearch.py` — `hybrid_search` at line 30. Note
  `_ci_term` at line 106: fields are keyword-typed and the seed data is
  capitalized, so term queries are built case-insensitively rather than using
  `match`. New clauses must follow this or they will silently miss.
- `styling_app/tools/search_closet.py` — `search_closet` at line 30. Its
  docstring is the tool description the LLM reads, so parameter documentation
  here is functional, not decorative.
- `styling_app/config.py` — `Settings`, a `pydantic_settings.BaseSettings`.

Client, `flutter-web-app`:

- `lib/closet/closet_screen.dart` — contains `_onEdit`'s edit dialog, whose
  fields follow a 360px-wide `SizedBox` with `SizedBox(height: 12)` gaps
  (established by ML-2 and `_SaveInterestingDialog`).
- `lib/l10n/*.arb` — the two ARB catalogs, regenerated with `flutter gen-l10n`.


### Terms used in this plan


**Intent** — the state a user wants to be in while wearing something. Not an
occasion, not a scene, not a style adjective. "強気でいたい" is an intent;
"work" is an occasion and is deliberately not collected (ADL-038).

**Sensitivity classification** — a property of a vocabulary value marking it
`SHAREABLE` or `PRIVATE_ONLY`. Nothing in this milestone exports data, so the
classification is unused here; it is defined now because later milestones (NC)
must enforce it by parameter type at outbound boundaries, and retrofitting a
type onto values already persisted without one is far more expensive.

**Boost, not filter** — a clause that raises the score of matching documents
while leaving non-matching documents in the result set.

**The read path** — the code that actually consumes stored data to change
output. A field with no read path is a label.


## Plan of Work


The work splits into three milestones ordered so that the riskiest question is
answered as early as possible.

Milestone A establishes the vocabulary, the aggregate field, and persistence in
both Firestore and Elasticsearch. It has no user-visible effect. It exists so
that Milestone B has data to rank against.

Milestone B implements the ranking clause, the flag that disables it, and the
proof that it changes output. **This is the milestone that can fail**, and it
deliberately comes before the UI work so that failure costs the least. It is
verified with a checked-in script against a locally seeded closet, not through
the UI, so the proof is re-runnable in CI-like conditions and does not depend on
browser automation.

Milestone C adds the capture UI and localization. It is last because it is the
most predictable and the least informative: if Milestone B fails, this work is
discarded, and doing it first would create pressure to ship a feature already
known to be decorative.

The approach is minimal in three specific ways. It adds one field rather than a
new aggregate, because intent belongs to the clothing item and has no
independent lifecycle. It reuses the existing metadata update use case and route
rather than adding a parallel one, because intent is user-correctable searchable
metadata and that is exactly what `UpdateClosetItemMetadataUseCase` is for. And
it adds one `should` clause to an existing query builder rather than introducing
a rescore phase or a function-score query, because the existing query already
accumulates `should` clauses and a second mechanism would need justification the
outcome does not provide.


## Concrete Steps


All commands run from the repository root, `/Users/ran/my-app/gen-fashion`,
unless stated otherwise.


### Milestone A — Domain vocabulary and persistence


**A1. Define the vocabularies.** In a **new module
`fastapi-service/app/domain/shared/affective.py`**, add two string enums.

> **Placement changed 2026-08-07 — do not put these in `domain/closet/`.**
> `domain/closet/` and `domain/styling/` are separate bounded contexts and
> neither imports the other today; both import only from `domain/shared/`
> (`base_models.py`). MS-1 puts `intent` and `mood` on
> `UserPreference` in `app/domain/styling/value_objects.py`, and ADL-049's
> arousal coordinate is read by NA's magazine layout. Defining these enums in
> `domain/closet/` would make `domain/styling` import from `domain/closet` —
> the first cross-context domain import in the repository, introduced for a
> vocabulary that belongs to neither context exclusively. `domain/shared/` is
> where the codebase already puts what both contexts need.

`IntentTag` with a starting vocabulary of six values. The enum *name* is the
stored value and must never change without a versioning step; the display label
lives only in the Flutter ARB catalogs. **Each value also carries a static
arousal coordinate** (ADL-049) — it is a property of the vocabulary, not
per-item data, so it costs no storage and no user input, and it is one of the
two axes NA-2's magazine layout is built on. Proposed starting set, to be
confirmed by the product owner (`req-phase03.md` §12 lists the word list as an
open content decision; the language policy is settled — Japanese-first, with the
caption closing any English gap):

      name           arousal   ja / en
      CONFIDENT      high      強気でいたい / want to feel bold
      PROTECTED      low       守られたい / want to feel safe
      BLEND_IN       low       馴染みたい / want to blend in
      PUT_TOGETHER   high      ちゃんとして見られたい / want to look put together
      AT_EASE        low       楽でいたい / want to feel at ease
      EXPRESSIVE     high      自分らしくいたい / want to feel like myself

`MoodTag` with a valence and arousal coordinate and a sensitivity
classification. Add a `Sensitivity` enum (`SHAREABLE`, `PRIVATE_ONLY`) and make
every negative-valence mood `PRIVATE_ONLY`. Expose the coordinates as properties
on the enum rather than a parallel lookup dict, so a new value cannot be added
without them.

Add a module-level `INTENT_VOCABULARY_VERSION = 1`. Persist it alongside the
tags in step A2 so a future vocabulary change can be detected per row rather
than requiring a migration.

Re-export `IntentTag`, `MoodTag`, `Sensitivity`, and `INTENT_VOCABULARY_VERSION`
from `app/domain/shared/__init__.py`, and re-export `IntentTag` from
`app/domain/closet/__init__.py` as well, so closet use cases keep importing from
the context they already import from (`update_item_metadata.py` imports
`ClothingTag` from `app.domain.closet`).

**A2. Add the aggregate field.** In
`fastapi-service/app/domain/closet/aggregates.py`, add to `ClothingItem`:

      intent_tags: List[IntentTag] = None
      intent_vocabulary_version: Optional[int] = None

Default `intent_tags` to `[]` in `__post_init__`, following the existing
`colors` handling at line 48. Add a `set_intent_tags` mutator that validates
0–3 values, rejects duplicates, sets `intent_vocabulary_version` to the current
constant when the list is non-empty, and calls `_mark_updated()`. Use
`object.__setattr__`, matching every other mutator in the file.

Extend `set_metadata` to accept `intent_tags` as an optional keyword, following
its existing `if x is not None` pattern, so the metadata update path can carry
it. Re-export the new names from `app/domain/closet/__init__.py`.

**A3. Persist to Firestore.** In
`fastapi-service/app/adapters/firestore_closet_repo.py`, serialize
`intent_tags` as a list of enum names under the key `intentTags` and
`intent_vocabulary_version` as `intentVocabularyVersion`, and deserialize both.
A document missing the keys must load as an empty list and `None` — every
existing document is in that state, so this is the common case, not an edge
case.

**A4. Declare and backfill the Elasticsearch mapping.** In
`fastapi-service/app/adapters/elasticsearch_embedding_repo.py`:

Add `"intentTags": {"type": "keyword"}` to the `ensure_index` mappings block at
line 30, next to the existing `"tags"` declaration.

Then handle the already-exists case, which `ensure_index` currently short-
circuits. Replace the early `return` with an additive mapping update so an
existing index gains the new property:

      exists = await self._client.indices.exists(index=self._index)
      if exists:
          await self._client.indices.put_mapping(
              index=self._index,
              properties={"intentTags": {"type": "keyword"}},
          )
          return

Adding a new field to an existing mapping is a permitted, non-breaking
Elasticsearch operation; changing an existing field's type is not, and this
step must not attempt one. Without this, `intentTags` is dynamically mapped as
`text` on every existing index and the case-insensitive term clause added in
Milestone B matches nothing — the failure recorded for `closetId` in
`docs/architecture-overview.md` §8 item 4.

Add `intent_tags: List[str]` to `index_item` (line 79) and
`update_item_metadata` (line 124), writing it into the document body as
`intentTags` alongside the existing `"tags"` key.

**A5. Thread it through the use case.** In
`fastapi-service/app/use_cases/closet/update_item_metadata.py`, add an
`intent_tags: list[str] | None = None` keyword parameter, convert each string to
`IntentTag` (raising a domain error on an unknown value rather than silently
dropping it), pass it to `item.set_metadata`, and include
`intent_tags=[t.value for t in item.intent_tags]` in the
`embedding_search.update_item_metadata` call. Note that this mirror call is
wrapped in a `try/except` that logs — that behavior is pre-existing and stays,
but it means an indexing failure is invisible to the caller, so the verification
in A6 checks Elasticsearch directly rather than trusting the HTTP response.

**A6. Verify Milestone A.**

      cd fastapi-service && python -m pytest -q

Expect all pre-existing tests to pass plus the new ones. Add unit tests for:
`set_intent_tags` rejecting four values and rejecting duplicates; an unknown
enum name producing a domain error; a Firestore document without `intentTags`
loading as `[]`; and `ensure_index` issuing a `put_mapping` when the index
already exists.

Then verify against real infrastructure:

      make dev

Upload a closet item through the UI, wait for `READY`, patch it with intent
tags (Milestone C's UI does not exist yet, so use the API directly), and read
the document back out of Elasticsearch:

      curl -s "http://localhost:9200/clothing_items/_mapping" | grep -o '"intentTags":{"type":"[a-z]*"}'

Expected output is `"intentTags":{"type":"keyword"}`. If it reports `text`, A4
did not take effect on the pre-existing index and Milestone B's clause will
silently match nothing.


### Milestone B — Ranking read path and the proof


**B1. Add the config flag.** In `adk-agent-service/styling_app/config.py`, add
to `Settings`:

      intent_boost_enabled: bool = True
      intent_boost_weight: float = 2.0

Document in a comment that the flag exists to make the MR-6 ranking-change
proof executable and to allow a fast rollback, and that the weight ships at a
fixed default because tuning against usage data is explicitly out of scope for
phase 3 (`req-phase03.md` §1.4).

**B2. Add the boost clause.** In
`adk-agent-service/styling_app/adapters/elasticsearch.py`, add an
`intent: str | None = None` keyword parameter to `hybrid_search` (line 30).
When it is set and `intent_boost_enabled` is true, append a boosted
case-insensitive term clause to `bool_query["should"]`, following the existing
`gender` handling at line 66 as the closest precedent:

      if intent and settings.intent_boost_enabled:
          clause = _ci_term("intentTags", intent)
          clause["term"]["intentTags"]["boost"] = settings.intent_boost_weight
          bool_query.setdefault("should", []).append(clause)

Do not add it to `bool_query["filter"]`, and do not set or raise
`minimum_should_match` on its account. Both would exclude untagged items, and
intent tagging is opt-in — most items will have no tags at all. That stays true
of the shared demo closet even after B4 tags part of it, which is exactly why
B4's fixture is required to be sparse.

**B3. Thread it through the tool.** In
`adk-agent-service/styling_app/tools/search_closet.py`, add an
`intent: str | None = None` parameter to `search_closet` and pass it to
`hybrid_search`. Add a line to the `Args:` docstring block describing it. That
docstring is the tool description the model reads when deciding how to call the
tool, so describe it as an optional preference signal rather than a filter, to
avoid the model treating an absent intent as a reason not to search.

**B4. Write the proof script.** Create
`scripts/mr6_intent_ranking_proof.py`, modeled on the existing verification
scripts in `scripts/` (`mo6_scene_aware_visual_check.py` and
`mp7_tab_persistence_browser_e2e.py` are the closest precedents for structure
and evidence output). It must:

1. **Tag a fixed subset of the existing shared demo closet**, rather than
   seeding a private fixture closet for a throwaway test user. The script
   applies intent tags to a hard-coded list of item ids and then queries with
   `SHARED_CLOSET` as the source. Two reasons: the same tagged data is then the
   material for the 90-second demo instead of test-only scaffolding, and the
   shared closet is real seeded data whose items were not chosen to make this
   proof pass.

   The subset must satisfy two properties. At least two items are plausible
   answers to the same query and carry *different* intent tags — if the tagged
   and untagged items are not otherwise comparable, a rank change proves
   nothing. And the tagging is **sparse**: a clear majority of the closet's
   items stay untagged, matching how an opt-in feature actually looks. A
   fully-tagged fixture proves nothing about the untagged majority.

   Tagging by fixed item id is what makes re-runs idempotent — see *Idempotence
   and Recovery*.
2. Run `search_closet` with a fixed description and `intent` set, with
   `intent_boost_enabled=True`, and record the returned item order.
3. Run the identical query with `intent_boost_enabled=False`, and record the
   order.
4. Run the identical query with a *different* `intent` value and boost enabled,
   and record the order.
5. Write all three orders to an evidence file and assert **all three** of the
   following (`req-phase03.md` §1.6):
   - run 2 differs from run 1 — the boost changes the result at all;
   - the **set** of the top N items differs between run 1 and run 2, not merely
     their internal order — a reshuffle confined to the tail is not something a
     user can see;
   - run 3 differs from run 1 — two different intents produce two different
     orders. If boost-on yields one fixed order regardless of which intent was
     passed, the clause is matching the presence of tags, not intent, and the
     feature is decorative in a way the first two assertions would not catch.
6. Exit non-zero if any assertion fails, printing the orders side by side.

**B5. Add the automated test.** Add a test to
`adk-agent-service/styling_app/tests/` that covers the same property against a
mocked Elasticsearch client: assert that the emitted query body contains the
boosted `intentTags` clause when intent is supplied and the flag is on, that it
does not when the flag is off, and that the clause lands in `should` and never
in `filter`. The script proves the behavior end to end; the test prevents
regression without requiring a live cluster.

**B6. Verify Milestone B — this is the release gate.**

      cd adk-agent-service && python -m pytest styling_app/tests -q

Then, against a running `make dev` stack:

      python3 scripts/mr6_intent_ranking_proof.py

Expected: exit code 0 and an evidence file showing three orderings, with the
boost-off ordering and the different-intent ordering both differing from the
baseline.

**If the orderings are identical, stop.** Do not proceed to Milestone C, and do
not tune the weight upward until the test passes — a boost weight raised until
something moves proves only that the weight is large. Investigate in this order:
whether `intentTags` is `keyword` and not `text` in the live mapping (A6),
whether the fixture items are genuinely comparable for the query used, and
whether the tagged items are being excluded by an unrelated `filter` clause. If
after that the ordering still does not change, the honest outcome is that the
signal does not carry information for this ranking, and the correct action is to
record that in `Outcomes & Retrospective` and remove the feature rather than
ship a field that is written and never meaningfully read. That is the entire
point of running this before Milestone C.


### Milestone C — Capture UI, API, and localization


**C1. Extend the API surface.** In `fastapi-service/app/handlers/closet_routes.py`,
add `intentTags: list[str] | None = None` to the metadata `PATCH` request model
and pass it through to the use case. Reject unknown vocabulary values with a 400
carrying the offending value, rather than silently dropping them — a silently
dropped tag looks to the user like the feature not working.

**C2. Add the capture UI.** In `flutter-web-app/lib/closet/closet_screen.dart`,
add a localized multi-select for intent to `_onEdit`'s dialog, following the
established field convention there (the 360px-wide `SizedBox` with
`SizedBox(height: 12)` gaps). Each option carries a short caption explaining
what the intent means — intent is a less familiar question than category, and an
uncaptioned list of abstract states will be answered inconsistently or not at
all.

Enforce the 0–3 selection limit in the widget as well as the domain, and make
skipping explicit and costless: a "not now" affordance, no required-field
styling, no blocking.

Offer the same selector once at upload completion, reusing the same widget
rather than building a second one.

**C3. Localize.** Add ARB keys to both catalogs in `flutter-web-app/lib/l10n/`
for every `IntentTag` label, every caption, the section title, and the skip
affordance. Then:

      cd flutter-web-app && flutter gen-l10n

Display strings live only here. If an enum name leaks into the UI, or a display
string is sent to the API, the vocabulary versioning in A1 is defeated.

**C4. Verify Milestone C.**

      cd flutter-web-app && flutter analyze
      cd flutter-web-app && flutter test
      cd fastapi-service && python -m pytest -q

Expect `flutter analyze` clean and both test suites green with the new cases
added. Then against `make dev`, in both 日本語 and English: tag an item, reload
the page and confirm the tags persisted, edit them down to zero and confirm the
item still behaves normally, and confirm the skip path leaves an item with no
tags.


## Validation and Acceptance


Acceptance is behavioral, in this order of importance.

**The ranking-change proof (MR-6).** Running
`python3 scripts/mr6_intent_ranking_proof.py` against a live `make dev` stack
exits 0 and writes an evidence file showing that the same closet and the same
query return a different candidate order with the intent boost enabled than
disabled, and a different order again for a different intent value. This is the
milestone's reason to exist; the other criteria are supporting.

**Round trip.** A user tags a closet item with up to three intent values in
either language, reloads, and sees the same tags. Querying Elasticsearch
directly shows `intentTags` present on the document and mapped as `keyword`.

**Opt-in is real.** An item with no intent tags is created, searched, proposed,
and generated exactly as before this change. A user who never opens the intent
selector sees no behavioral difference and no prompt they must dismiss.

**Boost, not filter.** In a closet where only some items carry the active
intent, a search still returns untagged items — ranked lower, not absent.

**Test suites.** `fastapi-service` pytest, `adk-agent-service` pytest, and
`flutter analyze` / `flutter test` all pass, with new cases covering the
vocabulary limits, the mapping backfill, and the query-shape assertions.

**Documentation sync.** `docs/feature-matrix-phase03.md` rows MR-1…MR-7 reflect
the end state, and `docs/architecture-overview.md` is updated — this milestone
adds a field to an existing aggregate and a parameter to an existing port, and
does not add a component, adapter, data store, or external service, so the
architecture change is limited to the milestone summary and roadmap sections.


## Idempotence and Recovery


Steps A1, A2, A3, A5, B1, B2, B3, C1, C2, and C3 are ordinary source edits and
are safe to repeat.

Step A4's `put_mapping` is idempotent: applying the same additive property to a
mapping that already has it succeeds without effect. It cannot be used to change
an existing field's type — if `intentTags` was already created as dynamic `text`
on some index by an earlier partial run, `put_mapping` will fail with a mapping
conflict. Recovery in that case, and only that case, is to delete and rebuild
the affected index. Locally:

      curl -X DELETE "http://localhost:9200/clothing_items"

then restart `fastapi-service` so `ensure_index` recreates it with the full
mapping, and re-run the shared closet seed. **Do not run this against a
deployed environment** — there the recovery is a reindex into a new index with
the corrected mapping followed by an alias swap, not a delete.

Step B4's proof script must be safe to run repeatedly. It tags a hard-coded list
of shared-demo-closet item ids, which is idempotent by construction — re-running
sets the same tags on the same items, creating nothing and duplicating nothing.
It must not create items, and it must not clear tags on exit: the tagging is
intentionally durable because the demo depends on it.

Because it writes to shared demo data rather than a throwaway user, the script
must be **explicit about which ids it touches** and must fail rather than guess
if an id is missing — a silently skipped item would weaken the fixture without
failing the proof.

Nothing in this plan deletes or rewrites existing user data. The new field is
additive and absent on every existing document, which the deserialization in A3
must treat as the normal case.


## Artifacts and Notes


On completion, record here:

- The evidence file from `scripts/mr6_intent_ranking_proof.py`, showing all
  three candidate orderings.
- The final `IntentTag` vocabulary as confirmed by the product owner, if it
  differs from the proposed set in A1.
- The `intent_boost_weight` value shipped, and any evidence that informed it.
- Test counts before and after for all three suites.

### Milestone A verification evidence (2026-08-07, role 4 — verifier)

**Environment check.** Confirmed independently before attempting the live check:

    $ docker ps
    Cannot connect to the Docker daemon at unix:///Users/ran/.docker/run/docker.sock. Is the docker daemon running?
    exit=1

    $ curl -s --max-time 3 http://localhost:9200
    (no output, curl exit=7 — connection refused)

Docker is unreachable in this sandboxed shell; `make dev` cannot be started here.
This matches the implementer's and scope-auditor's prior reports.

**A6 check 1 — full unit test suite.** Run independently (not trusting prior
reported counts):

    $ cd /Users/ran/my-app/gen-fashion/fastapi-service && source .venv/bin/activate && python -m pytest -q
    ....................................s................................... [ 57%]
    .....................................................                    [100%]
    124 passed, 1 skipped, 2 warnings in 1.32s

Skip reason confirmed via `pytest -q -rs`:

    SKIPPED [1] tests/adapters/test_elasticsearch_embedding_repo.py:16: Elasticsearch is not reachable at http://localhost:9200

— this is the pre-existing live-ES integration test (`test_elasticsearch_embedding_repo_index_lifecycle`), unrelated to this milestone's new code, self-skipping for the same reason `make dev` can't run (no reachable ES/Docker).

All four scenarios the plan's A6 names were confirmed present and passing,
run explicitly by node ID:

    $ python -m pytest -q \
      "tests/domain/test_clothing_item.py::test_set_intent_tags_rejects_more_than_three_values" \
      "tests/domain/test_clothing_item.py::test_set_intent_tags_rejects_duplicates" \
      "tests/use_cases/test_closet_use_cases.py::test_update_metadata_rejects_unknown_intent_tag" \
      "tests/adapters/test_firestore_closet_repo_mapping.py::test_firestore_document_without_intent_tags_loads_as_empty" \
      "tests/adapters/test_elasticsearch_embedding_repo.py::test_ensure_index_issues_put_mapping_when_index_already_exists" \
      -v
    5 passed in 0.86s

Mapped to the plan's required scenarios:
  - set_intent_tags rejecting 4 values -> `test_set_intent_tags_rejects_more_than_three_values` PASS
  - set_intent_tags rejecting duplicates -> `test_set_intent_tags_rejects_duplicates` PASS
  - unknown enum name -> domain error -> `test_update_metadata_rejects_unknown_intent_tag` PASS
  - Firestore doc without intentTags loads as [] -> `test_firestore_document_without_intent_tags_loads_as_empty` PASS
  - ensure_index issues put_mapping when index already exists -> `test_ensure_index_issues_put_mapping_when_index_already_exists` PASS

**A6 check 2 — live `make dev` / ES mapping check.** UNPROVEN. Docker daemon
is unreachable in this environment (see environment check above), so `make dev`
cannot be started, no Elasticsearch instance is reachable at
`localhost:9200`, and the `curl .../_mapping | grep intentTags` command
specified by the plan cannot be executed. This is an environmental gap, not a
behavioral one: the code path it would exercise (additive `put_mapping` on an
already-existing index) is covered by a mocked-client unit test
(`test_ensure_index_issues_put_mapping_when_index_already_exists`), but that
does not substitute for observing a real Elasticsearch index's mapping, which
is the exact failure mode (`closetId` dynamically mapped as `text`,
documented in `docs/architecture-overview.md` §8 item 4) A4/A6 exist to
guard against. This criterion remains open until run by someone with a
working Docker daemon.


## Interfaces and Dependencies


No new libraries, services, or external APIs are required. This is deliberate —
every dependency this milestone would have added is either already present or
belongs to a later milestone.

- **Elasticsearch** (existing, `clothing_items` index) — carries the new
  `intentTags` keyword field. It is the contract between the write path in
  `fastapi-service` and the read path in `adk-agent-service`; those two services
  do not otherwise communicate about closet data.
- **Firestore** (existing) — system of record for `intentTags` and
  `intentVocabularyVersion`.
- **`pydantic_settings`** (existing, both services) — carries
  `intent_boost_enabled` and `intent_boost_weight`.
- **`flutter_localizations` / ARB catalogs** (existing) — hold every display
  label, so the stored enum names stay stable across languages and vocabulary
  revisions.

Explicitly **not** required: no Gemini call is added (intent is user input, per
the Decision Log), no new aggregate, no new collection, no new port, no new
adapter, and no schema migration of existing rows.
