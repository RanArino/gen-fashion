# Phase 2 Requirements — gen-fashion

> **Status:** Active
> **Implementation tracker:** [feature-matrix-phase02.md](feature-matrix-phase02.md)

---

## 1. LINE Channel Integration

(LINE channel integration requirements have been moved here from Phase 1. Refer to the previous req-phase01.md for detailed specs like `ReplyCoordinateToLineUseCase`, `LineWebhookAdapter`, LIFF integration, etc.)

---

## 2. Client-Side Routing & Browser Navigation (Web)

### ADL-033: Flutter Web のナビゲーションは URL アドレス可能なルーティング（go_router + path URL strategy）

- **Decision:** Flutter Web のトップレベル画面遷移を、`HomeScreen` の `int _index` + `NavigationBar`（状態のみ・URL は常に `/`）から **URL アドレス可能なルーティング**へ移行する。**go_router** を採用し、`usePathUrlStrategy()`（`flutter_web_plugins`）でハッシュなしのクリーンなパスにする。永続 `NavigationBar` は go_router の **ShellRoute** で保持し、各タブを `/closet` `/coordinate` `/history` `/shared` のルートに割り当て、認証は go_router の `redirect`（未認証は `/login`、認証済みの `/login` アクセスはアプリへ）で行う（現 `AuthGate` の `authStateChanges` 判定を `redirect` + `refreshListenable` に置き換える）。`MaterialApp(home:)` は `MaterialApp.router` に変更する。
- **Alternatives:** (a) Navigator 1.0 の名前付きルート（宣言的なシェル + タブ + 認証 redirect には不向き、Web 履歴連携が手薄）、(b) Router API を go_router 無しで直接実装（ボイラープレートが多い）、(c) 現状維持（ブラウザの戻る/進む・ディープリンク・リロードでのビュー復元が壊れたまま＝UX 不良）。
- **Rationale:** go_router は Flutter 公式推奨のルーティングで、ShellRoute による永続ナビゲーションバー、`redirect` による認証ゲート、ブラウザ履歴 + path URL strategy 連携を標準でサポートする。現状の状態ベース遷移では URL が `/` のまま変わらず、Chrome の戻るボタン・ディープリンク・リロード時のビュー復元がいずれも機能しない（`ToDo`「ページパスの概念が無く戻るボタンが効かない」）。
- **Trade-off:** 新規依存（go_router）の追加と、認証 redirect の慎重な配線（サインイン直後のフリッカ回避、`refreshListenable` で `authStateChanges` を購読）が必要。コーディネートセッションや履歴詳細へのディープリンク（パスパラメータ）は最小スコープ外（将来拡張）とする。Firebase Hosting は SPA fallback（`rewrites` で全パス → `/index.html`）が既に有効なため、path URL strategy のディープリンク直アクセスでも 404 にならない（MD-12 / `firebase.json`）。
- **Date/Author:** 2026-06-30 / Ran（ブラウザ戻るボタン UX 改善の起票時に提案）

---

## 3. Assisted Coordinate Mode (Web)

> **ExecPlan:** [20260703-mk-assisted-coordinate-mode.md](plans/20260703-mk-assisted-coordinate-mode.md)
> **Tracker:** feature-matrix rows **MK-1...MK-8**.

Add a second Coordinate mode for a shopping-aided styling flow. The current
Coordinate mode remains available and unchanged. Assisted Coordinate starts
from one to three of the user's own READY closet items, uses the same style
preference inputs as the current Coordinate screen, asks the agent to propose a
complete styling with text and image-backed clothes/accessories, lets the user
accept the default checked recommendations or modify the selection, and then
generates the coordinate image through the existing post-selection generation
gate.

Suggested purchasable items are retrieved through Rakuten Ichiba Item Search /
Affiliate data. Users can save agent-suggested Rakuten item images to their own
closet as **Interesting**. Later they can change the item to **Owned** (the
user-facing "already bought" / "already purchased" state). Both Interesting and
Owned READY items are selectable in Coordinate-from-closet.

### ADL-035: Closet ownership state is separate from image processing state

- **Decision:** Keep `ClothingItemStatus` as the analysis pipeline state
  (`PROCESSING` / `READY` / `ERROR`) and add a separate closet ownership
  classification for user meaning: `OWNED` and `INTERESTING`.
- **Alternatives:** Add `INTERESTING` to `ClothingItemStatus`; rejected because
  an Interesting Rakuten suggestion can already be image-ready and should be
  searchable/generatable. Overloading the pipeline state would break existing
  `READY` filters.
- **Rationale:** The UI needs to show two concepts at once: whether an image is
  usable and whether the user owns it. A separate field keeps backend search and
  generation behavior stable while allowing a clear closet UI.
- **Date/Author:** 2026-07-03 / ExecPlan

### ADL-036: Assisted Coordinate is a session mode, not a clothing source

- **Decision:** Add a session mode (`STANDARD` default, `ASSISTED` new) and keep
  source on individual candidates (`CLOSET`, `SHARED_CLOSET`, `RAKUTEN`).
- **Alternatives:** Treat Assisted Coordinate as a third `ClothingSource`; rejected
  because one assisted proposal can mix own closet anchors and Rakuten
  accessories/items in the same candidate set.
- **Rationale:** The current source enum still describes where each item came
  from. The new mode describes the workflow shape.
- **Date/Author:** 2026-07-03 / ExecPlan

### 3.1 Assisted anchor clothes (MK-1 / MK-2)

- The user selects or uploads **1 to 3** own closet items as assisted-run anchors.
- The global closet cap remains unchanged (`MAX_CLOSET_IMAGES_PER_USER`, currently
  20). The new maximum applies only to one Assisted Coordinate run.
- Backend validation must reject 0, more than 3, non-owner, missing, or non-READY
  anchor items before launching the agent.

### 3.2 Rakuten suggestions (MK-3 / MK-4)

- Add a Rakuten Ichiba item search adapter/tool using backend/agent secrets only.
  The browser must never receive Rakuten application/access keys.
- Candidate output must include a stable id, source, display name, image URL,
  price when present, external/affiliate URL, shop/brand when present, and
  attribution.
- The agent may propose clothes and accessories, not only garments.

### 3.3 Selection and generation (MK-5)

- Agent-recommended suggestions are checked by default in the UI.
- The user can uncheck/check items before generation.
- The user can modify style preferences and rerun proposal before generation.
- Image generation still requires explicit selected candidates and must reuse the
  existing `PROPOSING` -> `POST /sessions/{id}/select` -> `GENERATING` gate.

### 3.4 Save suggestions to closet (MK-6)

- A Rakuten suggestion can be imported into the user's own closet.
- Imported suggestions are copied into private image storage, persisted as
  `READY`, default to ownership status `INTERESTING`, and are indexed for future
  closet search.
- Users can change `INTERESTING` to `OWNED` through the closet UI.

### 3.5 Coordinate-from-closet inclusion (MK-7)

- Existing Standard Coordinate `CLOSET` mode includes both Owned and Interesting
  READY items.
- Search/generation should not exclude Interesting items unless a future explicit
  filter is added.

### 3.6 Acceptance (MK-8)

- Local backend, ADK, Flutter, and Firestore rules tests pass.
- A local smoke or browser E2E demonstrates: assisted anchors -> Rakuten
  suggestions -> default checks -> generation -> save suggestion as Interesting
  -> change to Owned -> reuse the item from Standard Coordinate closet mode.

---

## 4. UI Onboarding & Contextual Help

First-time and returning users get no in-app explanation of what a page is for:
the Closet page and the Coordination result panel both showed the Shared
tab's CC BY-SA dataset banner unconditionally (irrelevant to a user's own
items or a generated result), there is no explanation of Closet's
purpose, upload flow, or ownership/category filters, and Coordination's
mode/source selectors ("Closet Styling"/"Style & Shop", "Shared"/"Mine") and
the "Owned"/"Interesting" ownership distinction relied on hover-only
tooltips, which don't work for touch (mobile/tablet) users. The header
language switcher also truncated the Japanese label ("日本..."), and nothing
pointed a brand-new (or empty-closet) user at the app's one help affordance.
This is UI-only polish, not an architecture change; no ADL is needed (see
ExecPlan Decision Log).

- The Closet page's default view and the Coordination result panel no longer
  show the CC BY-SA banner; that banner remains only on the Shared tab, where
  the images actually are the shared dataset.
- A single header "How this app works" icon (replacing the earlier
  Closet-only help icon and the old shared-closet-only dialog) opens one
  dialog with a collapsible Accordion section per tab (Closet, Coordinate,
  History, Shared). Opening it from a given tab auto-expands that tab's
  section; the rest start collapsed. The Shared section explicitly states
  that the shared closet exists so users can try a full styling demo without
  uploading their own clothes first, and still carries the CC BY-SA 4.0
  attribution/Kaggle link.
- Every previously hover-only explanation (Coordination's mode/source
  segments, Closet's ownership filter) now also renders as an always-visible
  caption, so touch users see the same explanation mouse users get from
  hovering; the hover tooltip remains as a bonus for desktop.
- The header info icon pulses (a subtle animation) whenever the user's
  closet is empty or their account was created in the last 24h, to guide
  new users toward it; the pulse stops for that session once tapped.
- The header language switcher no longer truncates the Japanese label.
