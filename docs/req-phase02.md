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

