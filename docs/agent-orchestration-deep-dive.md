<!--
    @date: 2026-06-07
    @description: Use this document to check agent orchestration design decisions before M4 starts.
-->

# Agent Orchestration Deep Dive

## What we know vs. what's open

First, the verified facts from M1-4 PoC:

*   ADK 2.1.0 yields a single `Event` class — no distinct `ToolCall`/`ToolResult` subtypes. Content type is determined by inspecting `parts[*]` fields.
*   Tokens are batched, not streamed. Each `Event` is a complete payload.
*   3 events per turn: `reasoning` → `ToolCall` (1) → `ToolResult` (2) → `FinalAnswer` (3).
*   `model_dump()` requires normalization before Firestore: `thought_signature` (bytes → base64), `long_running_tool_ids` (set → array).
*   `gemini-2.0-flash` is not available on Vertex AI — use `gemini-2.5-flash` in production with Vertex AI ADC.

## The Full Coordination Flow (Phase 1a — Web)

Here's how I read the intended flow end-to-end, with the ambiguities flagged explicitly:

```text
Flutter                  FastAPI                adk-agent-service
  │                         │                          │
  │──POST /sessions─────────▶│                          │
  │◀─{ session_id, SOURCE_SELECT                       │
  │  [User picks source]    │                          │
  │──POST /sessions/{id}/source ──▶│                   │
  │                         │─── update Firestore ──▶  │
  │◀─{ status: SEARCHING? } │                          │
  │                         │                          │
  │──GET /sessions/{id}/stream ─────────────────────▶  │
  │      (SSE connection)   │                          │
  │                         │                          │
  │  ??? TRIGGER ???        │                          │
  │                         │─── Cloud Tasks ──────────▶│
  │                         │   (or direct HTTP)        │ runner.run_async()
  │                         │                          │ ├─ Event(ToolCall: search_closet)
  │                         │                          │ ├─ Event(ToolResult)
  │                         │◀── Firestore writes ─────│
  │                         │    (agentEvents/)         │
  │◀── SSE events ──────────│ (on_snapshot listener)   │
  │  [Accordion UI updates] │                          │
```

### Critical open question #1: What triggers the ADK agent run in Web GUI?

The req says Cloud Tasks handles the LINE flow's 5-second timeout. But for Web GUI, the user is already waiting for the Accordion UI — there's no webhook timeout. Two options:

*   **Option A (Cloud Tasks anyway):** After `SelectClothingSourceUseCase`, FastAPI enqueues a Cloud Tasks job → `adk-agent-service` starts the agent. Advantage: consistent with LINE flow; agent service is always called the same way. Disadvantage: extra latency from queue.
*   **Option B (Direct HTTP):** FastAPI directly calls `POST adk-agent-service/internal/run-session` after source selection. The `adk-agent-service` runs the agent async (background task) and returns 202. FastAPI then streams SSE while Firestore `on_snapshot` relays events.

I lean **Option B** for Web GUI (direct HTTP) with Cloud Tasks only for LINE. The 5-second LINE constraint doesn't exist here, and it removes queue latency from the demo critical path.

## Agent Topology & Tool Assignment

The three-agent hierarchy:

*   **StylingOrchestratorAgent**
    *   **instruction:** "You coordinate outfit suggestions. Delegate to ClosetAgent for search tasks and StylingAgent for preference collection and image generation."
    *   **sub_agents:** `[ClosetAgent, StylingAgent]`
*   **ClosetAgent**
    *   **instruction:** "Search the user's closet or shared closet for outfit items. Given clothing analysis results, generate a natural language description of complementary items and search for matches."
    *   **tools:** `[analyze_clothing_image, search_closet]`
*   **StylingAgent**
    *   **instruction:** "Collect user preferences and generate final coordinate images."
    *   **tools:** `[ask_preference, style_synthesizer]`

> **Note:** `search_rakuten` arguably belongs to `SearchPort` → `RakutenItemAdapter`, so `ClosetAgent` makes sense since it routes searches. But Rakuten is Phase 1b only.

### Critical open question #2: How does the Orchestrator get context?

When the ADK agent run starts, it needs to know:
1.  The `session_id`
2.  The `user_id`
3.  Which source was selected (`CLOSET` / `SHARED_CLOSET`)
4.  The user's closet items summary (or let the tool fetch them)

This context is passed as the initial user message to `runner.run_async()`. Something like:

```python
user_message = Content(role="user", parts=[Part(text=f"""
  Session: {session_id}
  User: {user_id}
  Source: {clothing_source}
  
  Please suggest a coordinate outfit from the user's {clothing_source}.
""")])
```

The agent then uses its tools to fetch data rather than receiving it upfront. This is the right ADK pattern — tools are the source of truth, not the initial prompt.

## The Firestore Event Relay (ADL-011 implementation design)

From M1-4, the normalization pass needed before writing to Firestore:

```python
def _normalize_event(event) -> dict:
    raw = event.model_dump()
    
    # thought_signature: bytes → base64
    if isinstance(raw.get("thought_signature"), bytes):
        raw["thought_signature"] = base64.b64encode(raw["thought_signature"]).decode()
    
    # long_running_tool_ids: set → list
    if isinstance(raw.get("long_running_tool_ids"), set):
        raw["long_running_tool_ids"] = list(raw["long_running_tool_ids"])
    
    # Recursively handle nested bytes (parts can contain bytes too)
    return _deep_normalize(raw)
```

The Firestore schema for `sessions/{sessionId}/agentEvents/{eventId}`:

```json
{
  "seq": int,              // monotonic sequence number within session
  "agent_name": str,       // which agent emitted this (for multi-agent)
  "event_kind": str,       // "tool_call" | "tool_result" | "final_answer" | "thinking"
  "tool_name": str | None, // populated for tool_call and tool_result
  "tool_args": dict | None,
  "tool_result": any | None,
  "text": str | None,      // populated for final_answer
  "thought_text": str | None, // from thought fs if present
  "thought_signature": str | None, // base64
  "timestamp": timestamp,
  "ttl_at": timestamp,     // for Firestore TTL policy (~24h)
}
```

> **Note:** The Accordion UI doesn't need every raw field from ADK events. Mapping to this simplified schema in the relay is cleaner than forwarding the full ADK payload.

## State Machine Gap: Missing States

Looking at `state_machine.py`, the current states are:
`CREATED → SOURCE_SELECTING → ANALYZING → SEARCHING → PROPOSING → COMPLETED | TIMEOUT`

But the Firestore schema in `req-phase01.md` §8.1 lists:
`IMAGE_RECEIVED | ANALYZING | SOURCE_SELECTING | SEARCHING | PROPOSING | GENERATING | COMPLETED | ERROR`

Discrepancies that need resolution before M4:

| Firestore schema (req) | Python code | Resolution needed |
| :--- | :--- | :--- |
| `IMAGE_RECEIVED` | absent | Phase 1b only (LINE receives image before analysis). Web GUI starts at `SOURCE_SELECTING`. Can omit for Phase 1a. |
| `GENERATING` | absent | Between `PROPOSING` and `COMPLETED` — when `style_synthesizer` is running. Should be added to the state machine. |
| `ERROR` | absent | Should be added. Agent failures must set session to `ERROR` state. |
| `CREATED` | present | Not in Firestore schema. Probably fine as initial state before Firestore write. |

The state machine should be:
`SOURCE_SELECTING → ANALYZING → SEARCHING → PROPOSING → GENERATING → COMPLETED`
with `ERROR` as a possible transition from any state.

## Cross-Modal Search: The Key Implementation Detail

The search flow from §8.3 is the most architecturally interesting part:

1.  **AnalyzeClothingImageUseCase**
    *   → `ClothingAnalysisResult { category, colors, tags, season, style }`
2.  **ClosetAgent LLM (gemini-2.5-flash)**
    *   → generates: `{ "description": "ネイビーまたはブラックのスリムパンツ、カジュアル寄り" }`
3.  **gemini-embedding-2 (output_dimensionality=768)**
    *   → text embedding vector of description
4.  **ElasticsearchEmbeddingRepository**
    *   → cross-modal kNN: text vector vs. stored image vectors
    *   → + keyword filter: tags/category

This creates a vector space for text and images. But there are two implementation risks:

1.  **Cross-modal quality:** text-to-image kNN matching quality for clothing hasn't been validated yet (M1-3 Phase 3b deferred). The MVP can fall back to keyword-only if the vectors don't match well.
2.  **The agent needs to call gemini-embedding-2:** This embedding step happens inside the `search_closet` tool, not in the agent's LLM reasoning.

The tool signature is:

```python
def search_closet(description: str, category: str | None, colors: list[str]) -> list[dict]:
    """Search closet items by natural language description and filters."""
    vector = gemini_embed(description)  # inside the tool
    results = es.hybrid_search(vector, category, colors)
    return results
```

The agent provides the description string; the tool handles embedding. This is the right boundary.

## The ask_preference Question in Web GUI

The req says `ask_preference` is a LINE interactive message for 1b, and "Web uses text input" for 1a. This is under-specified. Three interpretations:

*   **Option A — Pre-session form:** Flutter shows a preference form before starting the agent run. Preferences are passed as initial context. No interactive tool needed in Web GUI.
*   **Option B — Chat-style:** The agent pauses execution, writes a question to Firestore, FastAPI SSE delivers it, Flutter shows a text input, user submits, the response re-enters `runner.run_async()`. This requires a multi-turn session which is complex.
*   **Option C — Skip for MVP:** For Phase 1a, `ask_preference` returns a fixed default (casual, any color, any occasion). The user gets a result immediately. Preferences can be refined later.

**Option A** is cleanest for Web GUI — it avoids multi-turn ADK session complexity and fits the "Web uses text input" description. **Option C** is fastest to ship.

## Summary of open decisions before M4 starts

| # | Question | My recommendation |
| :--- | :--- | :--- |
| 1 | What triggers the ADK run in Web GUI? | Direct HTTP to `adk-agent-service` (Option B) |
| 2 | Add `GENERATING` + `ERROR` states to state machine? | Yes, before M4 starts |
| 3 | Which agent runs Rakuten? | `ClosetAgent` (Phase 1b, not M4 priority) |
| 4 | How does `ask_preference` work in Web GUI? | Pre-session preference form (Option A) |
| 5 | Who writes session state transitions — agent or FastAPI? | ADK container writes to Firestore directly via `FirestoreStyleSessionRepository` |
| 6 | TTL on `agentEvents`? | 24h, enforced by Firestore TTL policy |
| 7 | Does the `adk-agent-service` need its own Firestore write path? | Yes — it needs `FirestoreStyleSessionRepository` access, same adapter as `fastapi-service` |
| 8 | Result UI: bespoke Flutter vs. A2UI standard? | **Agent speaks A2UI; render via `genui` pending a Flutter Web spike** — see Integration Assessment below (ADL-018) |
| 9 | A2A for inter-agent calls? | **No for MVP** — keep ADK native delegation; A2A is the future service-split path (ADL-019) |

> **Reflected into `req-phase01.md` (2026-06-08, user-approved):** #1 → ADL-020 + §5.1 `AgentRunInputPort`; #4 → §6.4 (Web pre-session form); #5 + #7 → ADL-021; #6 → §8.1 `agentEvents.ttlAt` + ADL-011/ADL-021; #8/#9 → ADL-018/ADL-019. #2 (`GENERATING`/`ERROR`) is already in req §8.1 status enum — only the Python `state_machine.py` needs to catch up (M4/M5 ExecPlan). #3 (Rakuten → ClosetAgent) is Phase 1b. **req is the source of truth ExecPlans are generated from; this doc is the rationale log only.**

## A2A / A2UI / Elastic Reranking — Integration Assessment

### Source & method

This assessment evaluates the hackathon technical-session notes
([docs/local/20260607_team_building_notes.md](local/20260607_team_building_notes.md)) — A2A, A2UI,
and Elastic reranking — against our actual stack. Claims were not taken at face value: each was
checked with web / OSS research (2026-06-08). The decisions here are recorded formally as **ADL-018**
(A2UI) and **ADL-019** (A2A) in [req-phase01.md](req-phase01.md) §13.

### Verified vs. unverified

The notes are written confidently, but only some claims hold up. Betting MVP time on an unverified or
immature API is the classic hackathon trap, so we separate signal from hype.

| Claim | Verdict | Confidence | Action |
| :--- | :--- | :--- | :--- |
| **A2A (Agent2Agent)** protocol | Real — open interop protocol, Agent Cards, JSON-RPC/HTTP + SSE | High | Future scalability path (ADL-019) |
| **A2UI** *as concept & spec* | Real — Google open project, Apache 2.0, 15.2k★, transport-agnostic, v0.8/0.9 Public Preview | High | Adopt agent-side (ADL-018) |
| **A2UI Flutter renderer** | Real — `genui` pkg (ex `flutter_genui`), verified `labs.flutter.dev`, v0.9.2, Web-capable, implements A2UI v0.9 | High (exists) / Med (maturity) | Spike on Flutter Web first |
| **Elastic** rescore / LTR / semantic rerank | All real Elastic features | High | Keep semantic rerank as a lever |
| **MCP Toolbox for Databases** | Real — but it's a Cloud SQL/RDBMS bridge, **not our stack** (we use Firestore + ES) | High | Skip — out of scope |
| **Vertex AI Agent Engine vs Cloud Run** | Real distinction; notes recommend Cloud Run for protocol freedom | High | Validates our ADL-007/ADL-016 |
| **Gemini Spark**, **Interactions API** | Cannot verify as real named products | Low | **Do not design around** |
| **`uvx google-agents-cli`** | Unverified as that exact package; ADK ships its own `adk` CLI we already use | Low | **Do not design around** |

**Takeaway:** A2A, A2UI (incl. the first-party Flutter renderer), and Elastic semantic reranking are
worth integrating. MCP Toolbox is not our stack; Gemini Spark / Interactions API / `google-agents-cli`
are unverified and must not be load-bearing in the design.

### A2A vs. ADK — they are different layers, not alternatives

A common conflation. They are complementary:

| | ADK | A2A |
| :--- | :--- | :--- |
| Kind | **Framework / SDK** (how to *build* an agent) | **Protocol** (how agents *talk* across boundaries) |
| Scope | **In-process** (sub-agent delegation in one runtime) | **Cross-service / cross-vendor** (network, Agent Card discovery) |
| Our use today | Orchestrator → ClosetAgent / StylingAgent inside `adk-agent-service` | Unused |

Analogy: ADK is "how you write the class"; A2A is "the REST/gRPC contract between microservices." All
three of our agents share one process today, so ADK native delegation is correct — A2A there would only
add network hops, serialization, and Agent-Card infra for no benefit.

### A2UI — decision (formalized as ADL-018)

**Correction of an earlier claim in this doc's discussion:** the concern that A2UI is "DOM/React-only
and awkward to embed in Flutter Web" was **wrong, and verification disproved it.** A first-party Flutter
renderer exists (`genui`, maintained by `labs.flutter.dev`), and Flutter's widget model maps directly to
A2UI's component catalog — Flutter is in fact *well-suited*.

The real risk is **not existence but churn/maturity:**

- `genui` README: *"This is a highly experimental package, which means the API will change (sometimes drastically)."*
- A2UI protocol is **pre-1.0** (v0.8/0.9, still moving toward v1.0).
- `genui` **Web is supported but not the primary focus** (mobile-first). We are Flutter **Web** — so Web is the one real unknown.

**Timing insight:** M5 (Accordion UI + candidate cards) is **not built yet**. So *now is the cheapest
moment* to adopt A2UI. Building bespoke M5 first and migrating later = double work.

**Two-layer strategy:**

1. **Agent side — speak A2UI (commit).** Agents emit A2UI JSON (ADK has `A2uiSchemaManager` to teach the
   LLM valid A2UI output). A2UI is transport-agnostic, so payloads ride the **existing Firestore relay
   (ADL-011)** — no A2A required. This is the renderer-independent, low-regret commitment that delivers
   the scalability win (new agents render without bespoke per-component code) and cross-channel reuse
   (same payload → Flutter now, LINE Flex in Phase 1b).
2. **Client side — spike `genui` on Flutter Web (~1 day) before committing the renderer.** Render one
   static A2UI payload in our Flutter Web app. Clean → adopt `genui` for the M5 result UI (no bespoke
   cards/Accordion). Janky → bespoke fallback for MVP, **but agents keep emitting A2UI** so the renderer
   stays swappable.
3. **Keep the thinking trace and the result UI conceptually separate.** A2UI is what the *user sees and
   interacts with* (candidate carousel, preference form, final image). The `tool_call` / `tool_result`
   reasoning trace (Accordion) is diagnostic observability, not A2UI's domain — keep it a separate stream.

**Revised relay design:** instead of inventing our own `ui_payload` schema (proposed earlier in this
doc), the agent emits **A2UI payloads** through `sessions/{id}/agentEvents` (ADL-011 unchanged). The
thinking-trace events remain a distinct stream from the A2UI result-UI events.

### Elastic reranking — decision

Directly targets this doc's #1 search risk (unvalidated cross-modal kNN). All sit behind
`EmbeddingSearchPort` with zero use-case changes:

| Technique | Verdict |
| :--- | :--- |
| **Semantic reranking** (cross-encoder over top-K) | **Keep as a ready lever** if cross-modal kNN quality is poor — rerank top-K by semantic fit |
| **Query rescore** (cheap second-pass scoring) | Optional polish (season/recency); post-MVP |
| **LTR** (ML on behavior logs) | **Skip** — needs click/conversion logs we won't have at a hackathon |
| **MCP Toolbox for Databases** | **Skip** — Cloud SQL bridge; we use Firestore + ES with typed adapters |

Search path: keyword-first hybrid (M2-9, built) → cross-modal kNN → *if weak,* semantic-rerank top-K
rather than abandoning vectors. Graceful degradation behind one port.

### Action items / TODO

- [ ] **`genui` Flutter Web spike** — render a static A2UI payload in our Flutter Web app; decide adopt vs. bespoke fallback. (Web is the one unverified axis.)
- [ ] **Define the A2UI catalog** — which primitives back our surfaces: candidate carousel (card/list), preference form (form/choice), final coordinate (image/card).
- [x] **`req-phase01.md` updated** — ADL-018 (A2UI) + ADL-019 (A2A) added to §13, and §11 revised to the A2UI/`genui` direction. (req is the source of truth ExecPlans are generated from, so the decisions live there.)
- [ ] **On M4/M5 ExecPlan authoring:** sync `feature-matrix-phase01.md` — revise M5-10 to the A2UI/`genui` direction and add rows for agent-side A2UI output + the `genui` Web spike. (Not done now; feature-matrix intentionally untouched per the original constraint.)

### Sources

- [A2UI site](https://a2ui.org/) · [client-setup](https://a2ui.org/guides/client-setup/)
- [google/A2UI (GitHub)](https://github.com/google/A2UI)
- [flutter/genui (GitHub)](https://github.com/flutter/genui)
- [pub.dev: genui](https://pub.dev/packages/genui) · [flutter_genui (discontinued)](https://pub.dev/packages/flutter_genui)
- [Google Developers Blog: Introducing A2UI](https://developers.googleblog.com/introducing-a2ui-an-open-project-for-agent-driven-interfaces/)
- [Mete Atamel: A2UI with ADK](https://atamel.dev/posts/2026/03-30_a2ui_with_adk/)
- [ICS: Generative UI in Flutter with A2UI](https://www.ics.com/blog/mastering-generative-ui-flutter-a2ui)
