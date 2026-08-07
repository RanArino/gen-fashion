# Phase 3 Requirements — gen-fashion

> **Status:** Active — differentiation + monetization + mobile (Shipaton target)
> **Deadline:** **2026-09-30** (Shipaton submission). Planning horizon from
> 2026-08-07 is **7.5 weeks with effectively one implementer**, which is the
> binding constraint on everything below. The submission strategy and the fixed
> descope order are §0.4; they are part of the requirements, not a schedule note.
> **Implementation tracker:** [feature-matrix-phase03.md](feature-matrix-phase03.md)
> **Origin:** Two multi-agent panel discussions held 2026-08-01 (Shipaton milestone scope) and 2026-08-02 (differentiation strategy). Those minutes are **local-only and not in the repository** — they were moved to `docs/local/` (gitignored) on 2026-08-07 because they are deliberation records, not specifications, and had already been superseded on several points.
>
> **This document is therefore self-contained and is the sole authority for phase 3.** Every decision those discussions reached is recorded below as an ADL carrying its rejected alternatives and trade-offs, and every conclusion they reached that was *not* adopted is recorded in §0.2 with the reason. If a question about phase 3 scope or rationale cannot be answered from this file, that is a defect in this file — fix it here rather than reconstructing it from the discussion minutes.

---

## 0. Scope and Non-Goals

Phase 3 answers one question the first two phases never did: **why would a user
choose gen-fashion over an incumbent styling app or a general-purpose AI
stylist?** The answer this phase commits to is a closed loop the incumbents are
structurally unlikely to build: the user records *how they want to feel and be
seen* (intent), that record measurably changes what the styling agent proposes,
and the accumulated record pays the user back as self-discovery content and a
shareable monthly magazine image. Monetization moves from a subscription to a
consumable coin balance so cost tracks consumption.

Phase 3 also ships the app on iOS and Android, because the target hackathon
([Shipaton](https://jp.shipaton.com/)) requires a mobile app with RevenueCat
in-app purchases.

### 0.1 In scope

| # | Workstream | Milestones |
|---|---|---|
| 1 | Intent tag layer with a proven ranking read path | MR, MS |
| 2 | Zero-cost self-discovery mirroring | MT |
| 3 | In-app post-hoc feedback | MU |
| 4 | Coin wallet, ledger, and debit gate | MV |
| 5 | RevenueCat in-app purchases, server-verified | MW |
| 6 | Mobile platform (Android/iOS) and store readiness | MX, MY |
| 7 | Second EC integration (eBay) | MZ |
| 8 | Monthly magazine image (free composite / paid single style) | NA, NB, NC |
| 9 | Affiliate confirmed-purchase coin grants | ND |
| 10 | Account deletion and data retention | NE |

### 0.2 Explicit non-goals

These were considered in the source discussions and are deliberately excluded.
Each is listed with the reason, so a future reader does not re-litigate them.

- **Subscription billing.** Rejected in favor of consumable coins; the product
  is low-frequency (roughly 4–12 sessions/month after the frequency decision),
  and a monthly fee against low frequency is the failure mode the growth seat
  identified. See ADL-041.
- **Ad-watching as a coin source.** Removed by the product owner. It creates
  reverse-margin risk (ad eCPM below the marginal model cost of what the coin
  buys), motivational crowding-out against the app's own reward loop, and a
  standing pressure to reuse emotional data as ad-targeting input. See ADL-040.
- **WearLog (daily worn-outfit selfie log) and selfie→item identification.**
  Deferred to phase 4, gated on an identification-accuracy PoC. If that PoC
  fails, the wear-log path is not viable at all, so no phase 3 work may depend
  on it.
- **Push notifications (FCM).** No push infrastructure exists — the repository
  has FCM configuration values but zero token registration, subscription, or
  send code. Building it is an independent workstream. Post-hoc feedback is
  therefore collected in-app in phase 3 (§4), and time-based nagging pushes are
  prohibited by product decision regardless.
- **A second image-generation provider (OpenAI).** The port abstraction lands
  in phase 3 (ADL-046) but ships with a single Nano Banana adapter. Adding a
  provider before measuring quality complaints on paid single styles is
  premature cost optimization, and each provider added is one more data
  processor to contract with.
- **Cross-user collective intelligence (abstracted-feature sharing between
  users) and its k-anonymity gate.** No cross-user recommendation feature
  exists today, so the shared-index schema constraint has nothing to constrain.
  The *type-level* guarantee that makes it buildable later — sensitive tags
  that structurally cannot reach an outbound port — does land in phase 3
  (ADL-040). The aggregation itself does not.
- **Acquisition / buyout positioning.** Removed from scope by the product owner
  before the 2026-08-01 discussion concluded; not an engineering topic.

### 0.3 Facts about the current code that phase 3 depends on

Verified against the working tree on 2026-08-06. These are the load-bearing
assumptions; if any becomes false, the dependent requirement must be re-planned.

- `ClothingItem` (`fastapi-service/app/domain/closet/aggregates.py:16`) has
  `tags: List[ClothingTag]`, `category`, `colors`, `season`, `gender`,
  `ownership_status`, and Rakuten-origin fields. There is no intent, mood, or
  place field.
- `hybrid_search` (`adk-agent-service/styling_app/adapters/elasticsearch.py:30`)
  builds a keyword-first bool query and already tokenizes `description` into
  `should` term clauses over `tags`, `category`, `colors`, and `season`
  (line 70). The read path for a new keyword field is a small, additive change,
  not a rewrite.
- `ownership_status` is written to Firestore and indexed into Elasticsearch but
  is **read by no ranking, search, or agent code**. This is the precedent
  failure this phase must not repeat: a field that is written and never read is
  not a feature. Hence the read-path release condition in §1.6.
- **`PROPOSING → GENERATING` is not an atomic transition, and it does not happen
  in `fastapi-service`.** An earlier draft of this document asserted it was, and
  ADL-041 was built on that assertion; both are corrected here. Verified
  2026-08-07:
  - `GENERATING` is written by **`adk-agent-service`**
    (`styling_app/server.py:151`) as a `set(merge=True)` on the session
    document.
  - The only guard is `FirestoreSessionRepository._status_rank`
    (`styling_app/adapters/firestore_session.py:44`) — an **in-process
    monotonic counter initialised to `-1` per instance**. It is not a
    transaction and not a compare-and-set.
  - `fastapi-service` never transitions to `GENERATING`.
    `StyleSession.select_candidates` (`app/domain/styling/aggregates.py:123`)
    stores `selected_items` and leaves the state at `PROPOSING`;
    `StyleSessionState.can_transition_to(GENERATING)` is called nowhere in the
    repository.
  - The coin ledger will live in `fastapi-service/app/domain/billing/`, so the
    service that performs the status write has no billing context at all.
- The **actual** server-side gate on expensive work is
  `SelectCandidatesUseCase.execute`
  (`fastapi-service/app/use_cases/styling/select_candidates.py`): it verifies
  the session is in `PROPOSING`, validates the selection against the proposed
  candidates, calls `enforce_daily_generation_limit`, persists the selection,
  and only then dispatches `agent_run.start_session_run`. This is one use case,
  in the service that owns billing, with exactly one failure branch. It is
  therefore the debit commit point (ADL-041).
- `UserPreference` (`fastapi-service/app/domain/styling/value_objects.py:33`)
  carries `occasion`, `season`, `style`, `color_preference`, `gender`,
  `language`. There is no intent or mood field.
- `max_daily_generations_per_user` (`fastapi-service/app/config.py:9`) is
  **`5`** in the working tree — the production default of `0` (unlimited) that
  the 2026-08-02 discussion flagged as issue Z has already been changed locally
  but is **not yet committed**. Phase 3 commits it (MV-6).
- There is **no** billing, coin, wallet, entitlement, or RevenueCat code
  anywhere in `fastapi-service`, `adk-agent-service`, or `flutter-web-app`.
  `user_entitlements` appears only in discussion prose. The coin system is a
  pure addition, not a migration.
- `flutter-web-app/` contains **only** a `web/` platform directory. There is no
  `android/` or `ios/` directory. Mobile is a platform bootstrap, not a build
  configuration change.
- `image_generation.generate` (`adk-agent-service/styling_app/adapters/image_generation.py`)
  carries a try-on prompt that explicitly instructs the model *not* to produce a
  product collage. It cannot be reused for magazine composition; the magazine
  needs its own path (ADL-045).

### 0.4 Submission strategy and fixed descope order

The 2026-09-30 deadline is the only hard external constraint in this phase and
the only one engineering effort cannot move. This section fixes what gets built
first and what gets dropped, so the decision is made now rather than in the last
week under pressure.

#### ADL-051: One store submission carries mobile, coins, and IAP together; differentiation ships in the follow-up build

- **Decision:** The first store submission contains **MX (mobile) + MV (coins) +
  MW (IAP) + NE (account deletion) + MY (store readiness)**, plus whatever of MR
  is complete. MS and NA ship in a second build submitted during or after the
  first review. Order of work: `MY-0` (day one, waiting time) → `MR` → `MX` →
  `MV`+`MW` → `NE` → `MY` → **submit** → `MS` → `NA`.
- **Alternatives:** (a) Submit the existing feature set plus mobile only, and add
  purchases in a later build. (b) Build all thirteen milestones and submit once
  at the end.
- **Rationale:** Consumable in-app purchase products must be reviewed alongside a
  binary the first time they are offered, so alternative (a) serialises two
  review cycles inside a 7.5-week window — the one cost that cannot be recovered
  by working harder. Alternative (b) puts the irreversible event last, which is
  the failure mode §7.2 already identifies. Review waiting time is the only slack
  in the phase, so the differentiation work is deliberately scheduled into it.
- **Trade-off:** The first build a reviewer sees is not the build that carries
  the product's differentiation. Accepted: a reviewed build can be updated, a
  build that was never submitted cannot.
- **Date/Author:** 2026-08-07 / Product owner

#### Fixed descope order

Work is dropped from the **bottom** of this list, never from the middle. Nothing
below the cut line may be started while anything above it is incomplete.

| Priority | Milestone | Why it is where it is |
|---|---|---|
| 1 | MY-0 (external account lead time) | Pure waiting time; the start date is the whole cost |
| 2 | MR | Differentiation go/no-go; already in flight |
| 3 | MX | Longest real implementation, blocks MY and MW |
| 4 | MV + MW | Shipaton requires RevenueCat purchases |
| 5 | NE | Store-review blocker (§11) |
| 6 | MY | The submission itself |
| 7 | MS | The visible demo beat; MR is inert without it |
| 8 | MU-1…MU-3, MU-5 | Small, and NA-2's valence axis depends on it (ADL-049) |
| 9 | NA + NC-2/NC-3/NC-4 | The shareable artifact; minimum privacy subset only |
| — | *cut line* | |
| 10 | MU-4 (feedback ranking boost) | Dropping it also removes the three-way ranking-weight contention from this phase (§4) |
| 11 | MT | Valuable but the signup grant (ADL-048) already covers cold start |
| 12 | NC-1, NC-5, NC-6 | Only needed if NA ships an export path |
| 13 | NB | Requires NA and MV both complete |
| 14 | MZ | Contributes nothing to the submission requirements |
| 15 | ND | Feasibility unverified and nothing depends on it |

**If NA cannot ship with the NC-2/3/4 subset, NA ships with no export or share
path at all** rather than with an unguarded one. A magazine the user can only
view is a smaller feature; a magazine that leaks `PRIVATE_ONLY` values is a
broken promise.

---

## 1. Intent Tag Layer and Ranking Read Path (MR)

The differentiating data is not "what the garment looks like" — Gemini already
extracts that — but **why the user keeps it and who they want to be in it**.
Phase 3 captures that as a small, fixed intent vocabulary attached to closet
items, and proves in the same milestone that it changes ranking.

### ADL-038: The user is asked about intent (ありたい状態), never about occasion/TPO

- **Decision:** Both the item-level tag and the session-level selector (§2) ask
  the user for an **intent** — the state they want to be in ("強気でいたい",
  "守られたい", "馴染みたい", "ちゃんとして見られたい", "楽でいたい") — plus an
  optional **mood**. The system does **not** ask the user for an occasion or
  TPO ("date night", "work", "reunion"). Place is optional free input and is
  never required.
- **Alternatives:** (a) A fixed occasion list as the session query parameter,
  as specified in the 2026-08-01 product-owner refinement. (b) Both axes, with
  occasion reusing the existing `UserPreference.occasion` field.
- **Rationale:** Occasion is largely recoverable from garment attributes the
  system already extracts (category, formality, season), so asking a human for
  it produces a category alias — a tag that cannot change ranking beyond what
  category filtering already does, which is exactly the decorative-feature
  failure mode the hackathon judges flagged. Intent is orthogonal to garment
  attributes and therefore carries information the existing metadata does not.
- **Trade-off:** This **supersedes** the 2026-08-01 "session-level occasion
  selector" refinement in its choice of axis, though not in its mechanism — the
  mechanism (agent presents fixed options, user picks one before candidates are
  searched, choice visibly reorders results) is retained in full in §2. Intent
  is a less familiar question than occasion, so the option labels carry short
  explanatory captions. The existing `UserPreference.occasion` field is left
  untouched and unused by this feature.
- **Date/Author:** 2026-08-06 / Product owner (resolving the conflict between
  the 08-01 and 08-02 discussions in favor of the later one)

### ADL-039: Intent tags are a dedicated typed field, not folded into `ClothingItem.tags`

- **Decision:** Add `intent_tags: List[IntentTag]` to `ClothingItem` as its own
  field with its own fixed enum vocabulary, indexed as its own Elasticsearch
  keyword field `intentTags`. Do not express intent as entries in the existing
  free-form `tags: List[ClothingTag]` list.
- **Alternatives:** Reuse `ClothingItem.tags`, as the 2026-08-02 discussion
  proposed ("既存 `ClothingItem.tags` に乗り新データモデルなし").
- **Rationale:** Three properties are impossible on the shared `tags` field.
  (1) **On/off provability:** the release condition in §1.6 requires disabling
  the intent contribution and showing ranking changes. If intent terms are
  mixed into the generic `tags` clause built at
  `elasticsearch.py:70`, there is nothing to switch off without also disabling
  descriptive matching. (2) **Sensitivity typing:** ADL-040 requires that some
  affective values structurally cannot reach an outbound port; a free string in
  a general list cannot carry that guarantee. (3) **Vocabulary control:** intent
  must be a closed set for the aggregation in §3 to produce stable findings;
  `tags` is open free text from Gemini and from Rakuten metadata (MQ).
- **Trade-off:** One added field on the aggregate, one added mapping property,
  and one added `should` clause — a few dozen lines more than the reuse option,
  in exchange for the three properties above. This is a deliberate deviation
  from the 2026-08-02 synthesis, recorded here rather than silently applied.
- **Date/Author:** 2026-08-06 / Phase 3 planning

### ADL-040: Affective data sensitivity is a property of the type, enforced structurally

- **Decision:** Every affective value carries a sensitivity classification in
  its type: `SHAREABLE` or `PRIVATE_ONLY`. Negative-valence moods are
  `PRIVATE_ONLY`. Any code path that leaves the user's own device-facing
  surface — magazine image composition, share export, any future outbound
  adapter — accepts only `SHAREABLE` values, enforced by the parameter type at
  the boundary, not by a runtime `if` filter inside the adapter.
- **Alternatives:** Filter sensitive values out at each call site; document the
  rule and rely on review.
- **Rationale:** A runtime filter must be remembered at every new call site and
  fails open when someone forgets. A type that outbound functions cannot accept
  fails closed: the omission is a type error at the call site, not a privacy
  incident in production. Emotional data creates standing structural pressure
  toward reuse as a targeting or scoring signal; the defense has to be
  "the code cannot express it", not "we agreed not to".
- **Trade-off:** Two parallel representations of the mood vocabulary and a
  conversion at the boundary. Accepted.
- **Date/Author:** 2026-08-06 / Phase 3 planning (Privacy/Data Architect seat,
  2026-08-02 synthesis point G)

### ADL-049: The affective axis is derived from intent and post-hoc feedback, not from an extra mood question

- **Decision:** `IntentTag` carries a **static arousal coordinate** as part of
  its definition (「強気でいたい」= high, 「楽でいたい」= low). The **valence**
  coordinate comes from the §4 post-hoc feedback answer (しっくり来た = positive,
  ふつう = neutral, 違った = negative). Together these are the two axes the
  magazine layout is built on (§9.1). `MoodTag` still exists and still carries
  ADL-040 sensitivity, but it is an **optional session-level input** (§2), not a
  required one, and nothing is allowed to depend on it being set.
- **Alternatives:** (a) Add `mood_tags` to `ClothingItem` alongside
  `intent_tags`. (b) Persist the session-level mood and have the magazine read
  it. (c) Drop the affective layout and lay the magazine out by intent and time.
- **Rationale:** The magazine's affective layout was specified before anything
  was specified that reliably *writes* an affective coordinate. Optional
  session mood would be sparse by construction, so a layout depending on it
  would be empty for most users. Alternative (a) asks a second question at
  capture time, which lowers the opt-in rate on the first one and asks something
  ill-defined ("how does this static garment make you feel"). The chosen source
  costs **no additional user input**: intent is already captured, and the
  feedback answer is a single tap on a screen the user is already looking at.
  It is also the more meaningful pair — intent is the user's prediction, the
  feedback answer is what actually happened, so the layout maps prediction
  against outcome rather than restating one input twice.
- **Trade-off:** This makes **NA depend on MU-1…MU-3**, upgrading what was a
  soft dependency into a real one, and it makes the valence axis three-valued
  rather than continuous. Sessions with no feedback answer have no valence and
  are placed on the neutral row. Accepted.
- **Date/Author:** 2026-08-07 / Phase 3 planning (resolving the missing write
  path for the affective axis)

### 1.1 Intent vocabulary (MR-1)

- A fixed enum `IntentTag` of 5–7 values covering the state the user wants to
  be in. The exact labels are a product/content decision; the ExecPlan proposes
  a starting set and the vocabulary is versioned so it can change without a
  migration of existing rows.
- **Each `IntentTag` value carries a static arousal coordinate (high/low)** as
  part of its definition, per ADL-049. This is a property of the vocabulary, not
  per-item data, so it costs no storage and no user input.
- A fixed enum `MoodTag`, each value carrying a valence (positive/neutral/
  negative) and an arousal (high/low) coordinate, and a sensitivity
  classification per ADL-040. `MoodTag` is optional session input (§2); no
  feature may require it to be set.
- **The vocabulary is authored in Japanese first and translated, not designed
  for translatability.** The primary user is a Japanese speaker and the
  resolution of the affective vocabulary is the source of the differentiation;
  choosing only concepts that are equally natural in both languages would
  generalise the vocabulary back toward occasion, which is exactly what ADL-038
  rejects. Where an English label is weaker than its Japanese source (「馴染みたい」
  → "want to blend in"), the gap is closed by the explanatory caption §2 already
  requires, not by changing the Japanese.
- Both vocabularies are localized (ja/en) in the Flutter layer; the stored
  value is the stable enum name, never the display string. The enum value means
  the same thing in every locale — per-locale vocabularies are prohibited,
  because §3 aggregation and §9.1 layout would stop being comparable across
  languages.

### 1.2 Item-level capture (MR-2)

- Intent tagging is **opt-in and skippable**. An item with no intent tags is
  valid and must behave exactly as it does today.
- Capture happens on the existing closet item metadata edit path
  (`PATCH` on `fastapi-service/app/handlers/closet_routes.py`,
  `UpdateClosetItemMetadata`), and is offered once at upload completion.
- Multi-select, 0–3 values per item.
- No new Gemini call is added. Intent is user input, not inference: an inferred
  intent would be recoverable from the image and would fail the same test
  ADL-038 applies to occasion.

### 1.3 Persistence and indexing (MR-3)

- `intentTags` is added to the canonical Elasticsearch mapping in
  `fastapi-service/app/adapters/elasticsearch_embedding_repo.py` as `keyword`,
  alongside the existing `tags`/`category`/`colors` declarations.
- Existing documents without the field remain valid and searchable. No reindex
  of the shared demo closet is required.

### 1.4 Ranking read path (MR-4)

- `hybrid_search` (`adk-agent-service/styling_app/adapters/elasticsearch.py`)
  accepts an optional `intent` parameter and, when supplied, adds a **weighted
  `should` clause** matching `intentTags`. It is a boost, not a filter: items
  without a matching intent must still be returned, ranked lower.
- The boost weight is a configuration value with a fixed default. Tuning against
  real usage data is explicitly not required for phase 3.
- `search_closet` (`adk-agent-service/styling_app/tools/search_closet.py`)
  threads the parameter through.

### 1.5 On/off switch (MR-5)

- A single configuration flag in `adk-agent-service/styling_app/config.py`
  disables the intent contribution to ranking without disabling anything else.
- This flag exists to make §1.6 executable and to allow a fast rollback if the
  boost degrades results.

### 1.6 Release condition — the read path ships in the same milestone (MR-6)

This is a hard gate, not a preference. The milestone is not complete until a
committed, re-runnable verification produces a log showing that **the same
closet and the same query return a different candidate order with the intent
boost on than with it off**, for at least one realistic fixture.

- If the order does not change, the tag is decorative and must be deleted
  rather than shipped.
- The verification is a checked-in script plus an automated test, so the claim
  can be re-proved after later changes rather than asserted once.

**The fixture must satisfy all three of the following.** A fixture the author
controls can be made to reorder trivially, which would let this gate pass while
the feature is still decorative — the exact outcome it exists to prevent.

1. **Sparse tagging.** Only a subset of the fixture's items carry intent tags.
   A fixture where every item is tagged does not resemble an opt-in feature and
   proves nothing about the untagged majority.
2. **Top-N membership changes.** The set of the top N candidates must differ,
   not merely their internal order. A reshuffle confined to the tail is not a
   result the user can see.
3. **Different intents produce different orders.** Two distinct intent values
   must produce two distinct orders. Boost-on producing one fixed order
   regardless of which intent was selected means the clause is matching
   presence, not intent.

The fixture is built on the **shared demo closet**, so the same tagged data
serves as the material for the 90-second demo (§2) rather than existing only
for the test.

---

## 2. Session-Level Intent Selector (MS)

The item-level tag (§1) records why a user values a garment. The session-level
selector is the **query-time** signal: who the user wants to be *today*. This
is the 2026-08-01 product-owner refinement, retained in mechanism and corrected
in axis per ADL-038.

- `UserPreference` gains `intent` and optional `mood`, threaded through session
  creation and the existing `POST /sessions/{id}/source` and
  `POST /sessions/{id}/assist` contracts.
- The Flutter Coordinate screen presents the fixed intent options **before**
  candidates are searched, with a short caption per option. Selection is
  optional; an unset intent reproduces today's behavior exactly.
- The selected intent does two things:
  1. **Shapes the search** — it is passed to `search_closet` as the `intent`
     boost input from §1.4, and contributes descriptive terms to the
     `search_rakuten` / `search_ebay` query. It must not be concatenated
     blindly into every EC keyword variant; the MQ recall guardrail
     (`req-phase02.md` §3.7) applies unchanged.
  2. **Drives a post-hoc tie-break pass** over the ranked candidate list, so
     the reordering is visible in the proposal UI.
- **Demo beat (acceptance):** with the closet unchanged, changing the selected
  intent and re-running the proposal visibly reorders the candidate list and
  changes the "why this" explanation shown per candidate. A judge must be able
  to see this in well under 90 seconds.
- The explanation chip states the fact ("you tagged this 強気でいたい"), never a
  compliment or a personality claim. Template praise is a product-level
  prohibition, not a style preference.

---

## 3. Self-Discovery Mirroring (MT)

The accumulation loop pays out over months, but a user decides whether to stay
in the first two to three weeks. Mirroring fills that gap with **descriptive
findings about the user's own data** — not predictions, not advice.

### ADL-047: Mirroring is deterministic server-side aggregation with zero model calls at view time

- **Decision:** Findings are produced by a small set of explicit rules over the
  user's own Firestore/Elasticsearch records (counts, co-occurrence, and
  distribution comparisons). No LLM call occurs when a finding is generated or
  viewed. Wording comes from localized templates with slots.
- **Alternatives:** Ask Gemini to summarize the user's closet and history.
- **Rationale:** This is the one feature that must run for every user on day
  one, before they have paid anything and before there is enough data to be
  worth paying for. Its marginal cost has to be zero or it becomes a cost sink
  that scales with retention — the exact inverse-correlation between retention
  and margin the growth seat identified. A deterministic rule also produces the
  same finding twice, which an LLM summary does not, and a finding the user can
  reproduce is a finding they can trust.
- **Trade-off:** Findings are blunter and fewer than generated prose. Accepted;
  a true statement about the user's own behavior is the value, not the phrasing.
- **Date/Author:** 2026-08-06 / Phase 3 planning

### 3.1 Requirements

- A finding is computed from the requesting user's own data only.
- Each rule declares a minimum data threshold and produces nothing below it,
  so a new user sees fewer findings rather than false ones.
- At least one rule must be satisfiable from roughly ten items, so a user who
  has just filled their closet gets something back the same day.
- Findings are precomputed and cached; a view is a read. No aggregation runs on
  the view path.
- Findings are free and unlimited. The paid tier (§9) is the deep summary, not
  the small weekly finding.
- Findings are descriptive and falsifiable ("you chose dark colors on 7 of the
  9 days you tagged 人に会う"). They must not assert personality, mood causation,
  or advice.

---

## 4. In-App Post-Hoc Feedback (MU)

Intent is a *prediction* the user makes before dressing. The learning signal is
the gap between that prediction and how it actually went. Phase 3 collects the
"after" in-app, because push infrastructure does not exist (§0.2).

- A completed styling session shows a three-choice prompt ("しっくり来た" /
  "ふつう" / "違った"). Answering is optional and one tap.
- The answer is stored on the session aggregate (`StyleSession`) as a single
  field with a timestamp. No new aggregate.
- **The answer is the valence axis** of the affective coordinate (ADL-049):
  しっくり来た = positive, ふつう = neutral, 違った = negative. This is what §9.1's
  magazine layout reads. Collecting the answer (the field, the endpoint, the
  three-choice UI) is therefore above the cut line in §0.4, and is a hard
  dependency of NA rather than the soft one the earlier dependency graph showed.
- A positive answer boosts the items that were selected in that session in
  subsequent closet searches, through the same additive `should` mechanism as
  §1.4 — not a new ranking model. **This ranking contribution sits below the cut
  line (§0.4).** It is the only part of §4 that is optional, and dropping it also
  removes the last case where three independent ranking contributions (§1.4
  intent boost, this boost, §2 tie-break) would compete without an arbitration
  rule.
- **If the ranking boost is built, it must not silently swallow the intent
  signal.** All ranking weights live in one configuration block, and the §1.6
  proof runs in CI *after* this boost is added, so a regression that makes
  intent's contribution invisible fails the build instead of passing unnoticed.
  The per-clause contribution to a candidate's score is written to the search
  log; it is not exposed in the API.
- Feedback answers are input to §3 mirroring rules and to §9 magazine style
  selection ("the outfits that actually felt right this month").
- Same-day evening collection via push is phase 4, isolated behind the FCM
  workstream.

---

## 5. Coin Wallet, Ledger, and Debit Gate (MV)

### ADL-041: Coins live in a new `domain/billing/` bounded context with a ledger, and the debit commits in the candidate-approval use case

> **Revised 2026-08-07.** The original decision put the debit commit point at the
> `PROPOSING → GENERATING` transition, on the stated premise that the transition
> was an atomic server-side gate in `fastapi-service`. §0.3 records why that
> premise is false in the current code. The bounded context, the ledger, and the
> idempotency design are unchanged; only the commit point moved.

- **Decision:** Add a bounded context `fastapi-service/app/domain/billing/`
  containing a `CoinWallet` aggregate and an append-only `CoinTransaction`
  ledger. Balance is derived from the ledger, not stored as an
  independently-mutable number. Every ledger entry carries an idempotency key
  (`ref_id`). For styling generation, **the debit is committed inside
  `SelectCandidatesUseCase.execute`** — after the `PROPOSING` check, the
  selection validation, and `enforce_daily_generation_limit`, and immediately
  before `agent_run.start_session_run` — keyed `ref_id = session_id`. **If the
  agent dispatch raises, the same `except` branch that already calls
  `session.mark_error()` writes a compensating credit** keyed
  `ref_id = "{session_id}:refund"`. For magazine styles the commit point is the
  successful put of the generated image, keyed `ref_id = "{issue_id}:{style_no}"`.
- **Alternatives:** (a) Have `adk-agent-service` call back into `fastapi-service`
  to debit just before it writes `GENERATING`. (b) Move the status write into
  `fastapi-service` and commit the debit and a compare-and-set of
  `PROPOSING → GENERATING` in one Firestore transaction. (c) Debit after the
  image returns — a crash between generation and debit gives away the expensive
  call. (d) A mutable balance field without a ledger — no audit trail, and
  concurrent debits race.
- **Rationale:** Correct billing needs **idempotency plus compensation**, not
  atomicity. With `ref_id = session_id` the ledger itself rejects a double
  debit, so the only remaining exposure is the window where a user is charged
  for a run that never starts — and that window has exactly one cause, the
  dispatch failure, which already has exactly one `except` branch to compensate
  in. Alternative (a) makes the agent service responsible for billing and adds a
  cross-service authenticated path without buying atomicity, since it is still
  two writes in two processes. Alternative (b) is the design that would actually
  deliver the original guarantee, but it moves ownership of session status
  writes away from `adk-agent-service`, contradicting an established phase 1
  decision, and its blast radius does not fit the §0.4 schedule.
- **Trade-off:** A debit is committed slightly before the expensive work begins
  rather than at the moment it begins, and correctness in the failure case rests
  on a compensating ledger entry rather than on a transaction. Balance reads are
  a ledger aggregation, so a cached balance document is maintained for display
  and treated as derived — the ledger wins on any disagreement. Every paid path
  must route through the debit gate; leaving a free analysis or generation path
  open would undermine the cap. Alternative (b) is recorded as the phase 4
  candidate if double-charge incidents actually appear.
- **Date/Author:** 2026-08-06 / Phase 3 planning; revised 2026-08-07 after the
  §0.3 verification

### ADL-048: A one-time signup grant is a third coin source, issued through the ledger

- **Decision:** A new account receives a **one-time grant sized at four
  generations**, written through the §5 ledger as an ordinary credit keyed
  `ref_id = "signup:{user_id}"`. Coin grant sources are therefore three: this
  grant, in-app purchase (§6), and confirmed affiliate purchase (§10). The
  prohibition on **recurring** free coins — daily drips, time-based refills, ad
  rewards — is unchanged.
- **Alternatives:** (a) No grant: generation is paid from the first use, and the
  free value on offer is the proposal, mirroring (§3), and the free magazine
  (§9). (b) A free-first-N-uses counter that bypasses the debit path entirely.
  (c) A promo grant for demo and review accounts only.
- **Rationale:** Without a grant, §5.1's "grants come from purchase only" and
  MV-8's "no free generation entry point" combine into a product where a new
  user's balance is zero and the first thing they meet is a paywall — which
  directly contradicts §6.1's requirement that the paywall appear at the point
  of refusal rather than before the user has seen value. There is nothing left
  to refuse. Alternative (b) is worse than it looks: a counter outside the
  ledger is a second accounting system and breaks MV-8's guarantee that every
  consumption is auditable in one place. Alternative (c) fixes the hackathon
  demo and leaves the real funnel broken.
  The reason the original decision banned free coins was that a recurring free
  supply makes cost scale with retention — the inverse relationship between
  retention and margin that ADL-047 also guards against. A one-time fixed grant
  scales with **signups**, not with engagement, so it does not reintroduce that
  failure mode.
- **Trade-off:** The grant is farmable by repeatedly creating throwaway accounts,
  bounded at four generations each. Accepted at this scale; the ledger records
  every grant, so abuse is measurable rather than invisible. **Four** is not
  arbitrary — it is the number of completed coordinate images the free magazine
  composes from (§9.1), so a user who spends the entire grant has exactly enough
  material for a first issue.
- **Date/Author:** 2026-08-07 / Product owner

### 5.1 Requirements

- Wallet operations: `credit(ref_id, amount, reason)`, `debit(ref_id, amount,
  reason)`, `balance()`. Replaying a `ref_id` is a no-op that returns the
  original result.
- A debit that would take the balance below zero fails with a distinct error
  mapped to an HTTP status the client can turn into a purchase prompt.
- **Cost tiers:** paid actions are priced by their marginal cost class
  (image generation ≫ image analysis ≫ metadata operations), declared in one
  table in configuration rather than scattered as literals.
- **`max_daily_generations_per_user` is a runaway/abuse cap, not a free-tier
  cap.** Once generation is debited, calling it a "free-path cap" is wrong: it
  applies to every generation regardless of who paid for it. It stays at `5` and
  keeps its current enforcement point
  (`use_cases/styling/daily_generation_limit.py`, called from `select_source`,
  `select_candidates`, and `assist_session`). Its job is to bound the damage from
  a bug, an automation loop, or a stolen account — cases a balance check does not
  catch, because in all three the coins are genuinely there.
- **The two refusals must be distinguishable to the client.** Insufficient
  balance maps to a status the client turns into a purchase prompt (MV-3); the
  daily cap keeps its existing `DailyGenerationLimitExceeded` → 429 mapping.
  Collapsing them would offer a purchase that does not resolve the refusal.
- Paths that are free by design (§3 mirroring, §9 free magazine) are not covered
  by either mechanism and need their own daily safety cap.
- Coin **grants** come from exactly three sources: the one-time signup grant
  (ADL-048), an in-app purchase (§6), and a confirmed affiliate purchase (§10).
  There is no ad-watching grant (§0.2), and **no recurring free drip** — no
  daily, weekly, or time-based refill of any kind.

---

## 6. RevenueCat In-App Purchases, Server-Verified (MW)

### ADL-042: Purchase state is server-verified via a signature-checked webhook; the client SDK is never the authority

- **Decision:** Coin grants are applied only when `fastapi-service` receives a
  RevenueCat webhook whose signature it has verified, writing the grant through
  the §5 ledger keyed by the RevenueCat event id. The Flutter client's
  `Purchases.getCustomerInfo()` result is used for UI display only and never as
  the basis for granting balance.
- **Alternatives:** Trust the client SDK's customer info; verify lazily on next
  server call.
- **Rationale:** Client-reported entitlement is a direct monetization-fraud
  surface — a modified client can mint balance. The webhook signature check is
  the one part of this that cannot be deferred for deadline reasons.
- **Trade-off:** Deferrable to phase 4 and explicitly out of phase 3 scope: a
  reconciliation job for missed webhooks, a billing-retry state machine, and
  independent double-verification against the Apple/Google receipt APIs. A
  missed webhook in phase 3 means a manually-reconciled grant, which is
  acceptable at this scale; an unsigned webhook means anyone can mint balance,
  which is not.
- **Date/Author:** 2026-08-06 / Phase 3 planning

### 6.1 Requirements

- Products are **consumable** coin packs. No subscription product is offered
  (§0.2).
- Webhook endpoint is unauthenticated by user but authenticated by signature;
  an invalid or missing signature is rejected before any parsing of the body.
- Grants are idempotent on the RevenueCat event id, so redelivery cannot double
  credit.
- The paywall is presented at the point of refusal — when a debit fails for
  insufficient balance — not as an interstitial before the user has seen value.
- Purchase price points and coin amounts are set from measured unit cost (§12).

---

## 7. Mobile Platform and Store Readiness (MX, MY)

### ADL-044: Mobile ships as added platforms on the existing Flutter package, not a new app

- **Decision:** Add `android/` and `ios/` platform directories to the existing
  `flutter-web-app/` package. One codebase, one widget tree, one set of API
  clients, serving web and mobile.
- **Alternatives:** A separate `flutter-mobile-app/` package sharing code via a
  local package dependency; a native shell embedding the web app.
- **Rationale:** Every screen in phase 3 must exist on both web and mobile, and
  the existing screens are already responsive Flutter widgets. A second package
  doubles the l10n, routing, and API-client surface for no gain. The directory
  name `flutter-web-app` becomes a misnomer; renaming it is deliberately **not**
  done in phase 3, because a package rename touches CI, Dockerfiles, deploy
  scripts, and every doc path, and would be indistinguishable from real work in
  the diff.
- **Trade-off:** The misleading directory name persists and is called out here
  so a future reader is not confused by it. Web-only dependencies must be
  checked for mobile compatibility during the bootstrap.
- **Date/Author:** 2026-08-06 / Phase 3 planning

### 7.1 Platform bootstrap (MX)

- `android/` and `ios/` platform directories added to `flutter-web-app/`.
- Firebase Auth configured natively for both platforms (`google-services.json`,
  `GoogleService-Info.plist`), sourced from the existing Firebase project.
- API base URL is configurable per build so a device build can target the local
  stack or production without code changes.
- **Acceptance is behavioral:** the existing flows — sign in, closet upload,
  a Coordinate session through the selection gate to a generated image, History
  — all run on a physical Android device and an iOS device or simulator.

### 7.2 Store readiness (MY)

- **External account provisioning starts on day one and is tracked as work
  (MY-0), not as a prerequisite someone remembers.** Apple Developer Program
  enrolment, Google Play Console registration, RevenueCat project setup, and the
  registration of the consumable products in both stores all carry approval
  waits measured in days to weeks that no engineering effort shortens. Two of
  them are also hidden preconditions of other milestones: a sandbox purchase
  (MW-6) cannot be tested until the store-side products exist and are approved,
  and §0.4's single-submission strategy assumes the products can be attached to
  the first binary. Anything not on the feature matrix does not get tracked, so
  this is a row, not a note.
- App icons, launch screens, bundle identifiers, version/build numbering.
- iOS privacy manifest and App Store data-collection disclosures, which must
  state affective data collection accurately (§1, §4) and its use.
- Distribution to TestFlight and a Play internal testing track.
- **Front-loaded deliberately.** Store review time is the one dependency in this
  phase that no amount of engineering effort can shorten, and a submission
  blocked on review is a submission that does not happen. MY should be started
  in parallel with the differentiation work, not after it.

---

## 8. Second EC Integration — eBay (MZ)

### ADL-043: The second EC adapter shares a result struct by convention; no port abstraction is extracted yet

- **Decision:** `search_ebay` (`adk-agent-service/styling_app/tools/search_ebay.py`
  + `adapters/ebay.py`) mirrors the existing `search_rakuten` registration
  pattern and returns the **same result shape** as `search_rakuten` — a
  `ProductResult` carrying id, title, price, currency, image_url, url, source.
  A formal `EcommerceSearchPort` interface is **not** extracted.
- **Alternatives:** Extract the port interface first, then implement both
  adapters against it.
- **Rationale:** The shared shape is the part that matters: divergent shapes
  force source-specific branching at every downstream consumer — ranking,
  candidate display, save-as-Interesting, and the intent boost. The interface
  extraction is invisible to users and is better done once a second adapter's
  real shape is known rather than guessed from one.
- **Trade-off:** The shared shape is enforced by convention and tests rather
  than by a type, so a third integration is the point at which the port should
  actually be extracted.
- **Date/Author:** 2026-08-06 / Phase 3 planning (adopted from the 2026-08-01
  round-2 compromise)

### 8.1 Requirements

- **A feasibility spike precedes implementation.** eBay Browse API image quality
  and catalog consistency under a New-condition filter plus apparel category
  filters must be checked against real responses before the adapter is built. If
  image quality is not usable for the generation path, eBay is dropped and the
  milestone closes as "verified not viable" rather than shipping a degraded
  source.
- Self-serve OAuth client-credentials Browse API; no partner negotiation.
- New-condition and apparel-category filtering applied at query time.
- Credentials stay server-side; the browser never receives them, matching the
  existing Rakuten constraint (`req-phase02.md` §3.2).
- `search_rakuten`'s existing output is normalized to the shared shape in the
  same milestone, so there is never a period with two divergent shapes.
- Zalando (no confirmed self-serve API), Etsy (catalog skews to accessories and
  craft), ASOS (partner-only), Shopify Storefront (per-merchant, wrong shape for
  aggregation), and AliExpress (weaker image quality) were evaluated and
  rejected.

---

## 9. Monthly Magazine Image (NA, NB, NC)

The magazine is the payout that makes accumulation feel worth it, the reason a
low-frequency user comes back, and the artifact users share — which is the
app's cheapest acquisition channel. It is **one image**, not a booklet: there
are no issues-as-documents, pages, or binding concepts in the data model.

### ADL-045: The free issue is server-side image composition with zero model calls; only paid single styles invoke the image model

- **Decision:** The free monthly issue is a single image composed **server-side
  from the user's already-generated `final_result` images** using an image
  library (PIL), laid out editorially. It calls no generation model. A paid
  single style is one high-quality image generated by Nano Banana, purchased
  and debited per style.
- **Alternatives:** Generate the free composite with the image model; make the
  free tier a lower-resolution generation.
- **Rationale:** The free tier runs for every user on a recurring schedule. If
  it invokes a generation model, its cost scales with total users rather than
  with paying users, and it becomes the single largest cost line in the product.
  Composition of images that were already paid for has a marginal cost of
  storage and CPU. The existing `image_generation.generate` cannot be reused —
  its prompt explicitly forbids producing a collage — so the composite is a
  separate implementation regardless.
- **Trade-off:** The free issue's visual ceiling is set by the source images and
  the layout engine, not by a model. This is accepted with one hard constraint:
  **the free issue is an independent format, not a visibly degraded version.**
  It gets its own name, and its typography and layout quality are not reduced.
  What the paid tier buys is a single style rendered at full quality — not the
  removal of a watermark or a resolution penalty. If cost must be cut, cut the
  frequency, never the quality of the first image a user sees.
- **Date/Author:** 2026-08-06 / Phase 3 planning

### ADL-046: A single sensitive-data transformation layer sits in front of `ImageGenPort`, and every provider goes through it

- **Decision:** Define `ImageGenPort` with one Nano Banana adapter. In front of
  it, place a single transformation layer that converts internal state into an
  **allowlisted, abstract visual instruction**. Affective values, place, face
  images, and identifiers never cross into a provider payload. Direct
  adapter-to-provider calls that bypass this layer are prohibited. Every
  outbound payload is audit-logged. The style-naming engine (§9.3) is separate
  from image generation.
  **The existing try-on path (`adk-agent-service/styling_app/adapters/image_generation.py`)
  is routed through the same layer**, so "every provider call goes through one
  chokepoint" is true from the day the chokepoint exists. In phase 3 this is a
  **routing change only**: the try-on payload that crosses the boundary is
  byte-for-byte what it is today, and no prompt, parameter, or image is altered.
- **Alternatives:** Filter per adapter; add providers directly; apply the
  chokepoint only to the new magazine path (NB) and leave the existing try-on
  call as a direct provider call.
- **Rationale:** Adding an image provider is not "adding a model", it is adding
  a data processor to the set of parties that receive user data. One chokepoint
  means one place to audit and one place that cannot be forgotten when a second
  provider is added. Keeping naming out of the image path means a provider swap
  cannot silently change the titles users have already shared.
- **Trade-off:** One extra indirection on a path that currently has one
  provider. Accepted as the cost of the guarantee. Adapter return values are
  normalized to a storage key so bytes/URL/base64 differences stay inside the
  adapter. Including the existing try-on path costs one indirection on the
  highest-frequency call in the product; excluding it would leave the most
  frequently used outbound path as the one that is not audited, which is the
  opposite of the guarantee this ADL claims to make. Because the payload is
  unchanged, the try-on change is verifiable by asserting the outbound payload
  is identical before and after.
- **Date/Author:** 2026-08-06 / Phase 3 planning

### 9.1 Free issue (NA)

- One image containing four styles, composed server-side from existing
  completed coordinate images.
- **Layout is driven by the affective axis**, not chosen arbitrarily: the four
  styles are placed by valence and arousal, so the composition itself is a map
  of the month. This is what makes the free issue satisfy the same on/off test
  as §1.6 — the arrangement is not recoverable from the images alone. It costs
  nothing extra to do it this way.
- **Where the two coordinates come from (ADL-049), in this order:**
  1. **Arousal** — the static coordinate on the session's selected `IntentTag`
     (§1.1). If no intent was selected, the item-level `intent_tags` of the
     selected garments; if those are absent too, low.
  2. **Valence** — the §4 post-hoc feedback answer for that session. If the
     session was never answered, neutral.
  3. The optional session `MoodTag` (§2), **when it is set**, overrides both.
     It is the most direct signal, but nothing may depend on it being present.

  A month where nothing was tagged or answered still composes: every style
  resolves to low-arousal neutral, and the layout degrades to a plain grid
  rather than failing. That is the §9.1 thin-material requirement applied to the
  axis rather than to the images.
- **Cooldown is 30 days from the moment of generation**, not a calendar month
  reset, and is enforced server-side from a stored timestamp. A client-side
  check is not a cap.
- **The first issue must work with thin material.** A new user's first issue
  composes from whatever exists, including plain closet uploads, and is designed
  to look intentional rather than empty. A user whose first issue looks broken
  does not come back for the second.
- The cooldown period is framed to the user as the window for gathering
  material, and the return trigger is the personal cooldown expiry — not a
  calendar date and not a time-based nag.

### 9.2 Paid single style (NB)

- One style, one image, purchased individually with coins. Users buy the one or
  two styles they liked; there is no issue-pack or bundle concept.
- **The style is fixed before purchase and presented as an editing action.**
  Generate-then-dislike-then-rebuy loops are prohibited: the mechanic must not
  become a gacha.
- Debit commits on successful image put, idempotent per `{issue_id}:{style_no}`
  (ADL-041).

### 9.3 Naming (NA)

- Titles are derived from the user's own recorded data — colors, season, intent,
  mood — through a template engine, and are **user-editable**.
- Titles state facts. They must not praise the user, assert personality, or
  claim emotional states. Generic AI compliments are prohibited by product
  decision.
- Naming is independent of the image provider (ADL-046).

### 9.4 Sharing guardrails (NC)

- **Default private.** Sharing requires explicit per-share consent, every time.
- Exported images carry **no negative-valence affective content and no place**
  by default; `PRIVATE_ONLY` values structurally cannot reach the composition
  path (ADL-040).
- Place, if ever included, is opt-in and limited to a category, never a place
  name or coordinates.
- Exported files have metadata stripped. No watermark. Raw selfies are never
  composited in.
- **Editing is acceptable; fabrication is not.** The user's own garments and own
  records are the subject. The output must not substitute a different face or
  garments the user does not have — an image the user does not recognize as
  theirs is one they will not share, which removes the entire reason for the
  feature.
- If any image or garment data is sent to an external provider, that is stated
  plainly in the UI, consistent with the audit-log requirement in ADL-046.

---

## 10. Affiliate Confirmed-Purchase Coin Grants (ND)

- Coins are granted when an affiliate purchase is **confirmed**, not when a link
  is clicked. A click-based grant is a free tap that mints model credit; a
  confirmed purchase carries revenue that can fund the grant.
- The grant amount must satisfy `grant_value < affiliate_revenue` per
  transaction, so the path cannot run at a loss.
- **This milestone begins with a feasibility spike.** Whether confirmed-purchase
  attribution is actually available to this integration at this scale — through
  the Rakuten Affiliate reporting API or equivalent — is unverified. If it is
  not available, the milestone closes as "not viable", in-app purchase remains
  the sole grant source (§6), and nothing else in phase 3 is affected. No other
  milestone may depend on this one.

---

## 11. Account Deletion and Data Retention (NE)

Phase 3 is the phase where this app starts collecting affective data (§1, §4)
and money (§5, §6). Both stores require an in-app account deletion path for apps
that support account creation, and the disclosures MY-2 makes are only honest if
deletion actually works. The repository today has item deletion
(`closet_routes.py:76`) and session deletion (`session_routes.py:229`) and **no
account deletion path at all**.

### ADL-050: Deletion is a cascade of the user's own data, with the coin ledger anonymized rather than deleted

- **Decision:** Account deletion is its own milestone (NE), not a line item
  inside store readiness. It cascades across every store that holds user data:
  Firestore documents under the user, R2 images, and Elasticsearch documents.
  The **`CoinTransaction` ledger is the single exception**: its rows are retained
  with `user_id` replaced by an unlinkable surrogate, keeping only amount,
  timestamp, reason, and `ref_id`. Nothing that identifies a person, a garment,
  an intent, or a mood survives.
- **Alternatives:** (a) Track it as a row inside MY. (b) Defer to phase 4 and
  offer a request form in the interim. (c) Delete the ledger rows with
  everything else.
- **Rationale:** Deletion is a cross-cutting implementation touching four data
  stores and every aggregate the phase adds — it is not the same kind of work as
  icons, signing, and distribution, and burying it in MY guarantees it is
  under-estimated and started last, which is precisely when the rows added by
  MR, MU, and MV are easiest to miss. Deferring it risks a review rejection on a
  requirement that has no engineering workaround. Alternative (c) collides with
  the append-only ledger that ADL-041 depends on: an audit trail with holes in it
  cannot answer "was this user double-charged", which is the reason the ledger is
  append-only in the first place. Anonymized retention satisfies both — the
  financial record stays complete, and it stops being personal data.
- **Trade-off:** Two deletion semantics in one operation, and a surrogate-id
  scheme to maintain. Accepted. The retention of anonymized financial records
  must be stated in the privacy disclosure (MY-2), not left implicit.
- **Date/Author:** 2026-08-07 / Phase 3 planning

### 11.1 Requirements

- In-app deletion entry point, reachable without contacting support, with an
  explicit confirmation that names what is deleted.
- Server-side cascade over Firestore, R2, and Elasticsearch. A deletion that
  removes the Firestore document but leaves the Elasticsearch document is a
  privacy failure that also breaks search.
- Idempotent and resumable: a partially failed deletion can be re-run and
  converges. Deletion must not leave an account in a half-deleted state that can
  still sign in.
- The affective fields added by this phase (`intent_tags`, session intent/mood,
  feedback answers) are covered by the cascade **by construction** — an
  automated test enumerates the user-scoped collections and fails when a new one
  is added without being handled, so a future milestone cannot silently add an
  uncovered store.
- Coin ledger rows are anonymized in place per ADL-050 and are excluded from the
  cascade by an explicit rule, not by omission.

---

## 12. Open Items Requiring Measurement or a Product Decision

Carried forward unresolved from the source discussions. These are not blocked
work — they are inputs that cannot be derived from the code.

- **Coin price points.** Requires measured unit cost of a Nano Banana generation
  and a Gemini analysis call, plus the dilution from free issues and from the
  signup grant (ADL-048). The user-side intuition recorded is that a single
  premium style should sit in the range of a small impulse purchase, not a
  subscription-sized commitment. The grant is fixed at **four generations**; what
  a generation costs in coins, and what coins cost in money, is still open.
- **Free-path daily cap values.** `max_daily_generations_per_user = 5` is
  committed as the starting value for the runaway/abuse cap (§5.1); the mirroring
  and free-magazine paths need their own caps, set from the same cost
  measurements.
- **The exact intent vocabulary.** §1.1 requires 5–7 values, each carrying a
  static arousal coordinate (ADL-049); which words is a content decision,
  versioned so it can change. The **language policy is decided** (§1.1:
  Japanese-first, captions close the English gap) — only the word list is open.
- **The mirroring rule set.** §3 defines the constraints; the specific rules and
  their thresholds are a content decision.
- **First-issue composition design.** §9.1 requires it to look intentional with
  thin material; how is a design decision.
- **Recall design for low-frequency users.** The frequency decision traded a
  daily-habit risk for a being-forgotten risk. The magazine cooldown-expiry
  trigger is the primary answer; whether anything more is needed is open, under
  the standing constraint that time-based nagging is prohibited.
- **The 90-second demo's lead.** Candidates: the same closet reordering under a
  changed intent, the mirroring finding, and the magazine composing as an
  affective map. Which leads is a presentation decision.
