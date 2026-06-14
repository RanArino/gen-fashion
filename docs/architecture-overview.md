# Architecture Overview — gen-fashion (Phase 1)

> **生成日:** 2026-06-08
> **最終同期:** 2026-06-14 — M5 完了（`docs/plans/20260612-m5-coordination-flow-accordion-ui.md`）。FastAPI `/sessions`、ADK `/internal/run-session`、`agentEvents` 書き込み、SSE polling stream、Flutter Coordination/Accordion UI は実装済み。review hardening として final SSE drain、cursor event reads、ADK trigger failure compensation、ADK internal-secret guard、selected shared-closet filtering、ADK status sequencing を追加済み。local Docker/API smoke と rendered Flutter Web browser E2E は authenticated `SHARED_CLOSET` session → Accordion event evidence → `COMPLETED` result image まで通過。
> **ベース:** [req-phase01.md](req-phase01.md)（仕様の source of truth）・[feature-matrix-phase01.md](feature-matrix-phase01.md)（実装状況）
> **目的:** アーキテクチャ／システム構成を可視化し、**既に実装済みのコード**と**これから実装予定のコード**の境界を明確に強調する。

---

## 凡例 (Legend)

このドキュメントの全図は、コードの**実在状態**で色分けする。「ファイルが存在する」ことと「動作する」ことを区別する点が要点。

| 表記 | 意味 | コードの状態 |
|---|---|---|
| 🟩 **Done** | E2E で動作する実装済み機能 | 実装あり・検証済み |
| 🟨 **WIP** | 進行中／一部のみ確定 | 局所的に実装、残りは保留 |
| 🟧 **Stub**（橙・破線） | **スケルトンのみ**。ファイルは存在するが `NotImplementedError` / `throw Error("Implement in M…")` / `501` を返す | **これから実装予定** |
| ⬜ **Not started**（灰・破線） | コードが存在しない | **これから実装予定** |

```mermaid
flowchart LR
  A["🟩 Done<br/>動作する"] --> B["🟨 WIP<br/>進行中"] --> C["🟧 Stub<br/>骨組みのみ"] --> D["⬜ Not started<br/>未着手"]
  classDef done fill:#c8e6c9,stroke:#2e7d32,color:#1b5e20;
  classDef wip fill:#fff3cd,stroke:#f9a825,color:#795548;
  classDef stub fill:#ffe0b2,stroke:#e65100,color:#bf360c,stroke-dasharray:5 3;
  classDef todo fill:#eceff1,stroke:#90a4ae,color:#455a64,stroke-dasharray:6 3;
  class A done; class B wip; class C stub; class D todo;
```

> **🟧 Stub と ⬜ Not started はどちらも「これから実装予定」**である。違いは、M0 で骨組み（ポート IF・空のユースケース・空のエージェント）まで先行配置済みか否か。M5 は session/ADK/SSE/Flutter UI と rendered browser E2E まで完了、Phase 1b（M6・LINE）は ⬜ 未着手。M3 は local で実装完了（フル vector seed のみ deployment 待ち）。M4 は Python ADK で実装完了（ローカル ADK Web UI / api_server で稼働）。

---

## マイルストーン別 実装サマリ

| Milestone | 内容 | Phase | 状態 |
|---|---|---|---|
| **M0** | プロジェクト基盤・ローカル開発環境 | 1a | 🟩 **Done** |
| **M1** | PoC & インフラ検証（画像生成・ADK イベント・ES） | 1a | 🟩 Done（M1-3 ES の GCE デプロイ部分のみ 🟨 WIP） |
| **M2** | 認証 & クローゼット管理（Web） | 1a | 🟩 **Done**（E2E 検証済み） |
| **M3** | 共有デモクローゼット | 1a | 🟩 **Done（local）**（seed script / SharedClosetSearchAdapter / attribution UI 実装済み。3クローゼットの live seed 済み＝90件・30/30/30・冪等性検証済み 2026-06-10。フル vector seed（GCE ES）のみ deployment 待ち） |
| **M4** | ADK エージェント中核 | 1a | 🟩 **Done（local）**（2026-06-11: Python ADK 再構築完了（ADL-022・TS 骨組み削除）。orchestrator + 2 sub-agents + 4 tools が `adk api_server`/Web UI でローカル稼働、M3 シード済み `SHARED_CLOSET` に対する委譲 → `search_closet`（attribution 付き）→ `style_synthesizer`（collage fallback）E2E 確認、pytest 17 passed。Nano Banana 生成パスは free-tier quota の都合で fallback のみ実証） |
| **M5** | コーディネートフロー & Accordion UI | 1a | 🟩 **Done**（FastAPI session routes/repository/use cases、ADK run endpoint/event writer、SSE polling stream、Flutter Coordination/Accordion UI 実装済み。local API/SSE smoke と rendered browser E2E は `COMPLETED` まで検証済み） |
| **M6** | LINE チャネル統合 | 1b | ⬜ **Not started**（ファイル無し） |

**現在地:** Phase 1a は M5 まで完了。エージェント中核（orchestrator / sub-agents / tools）はローカル ADK Web UI で動作し、Web GUI coordination flow は local API/SSE smoke と rendered browser E2E で通過済み。次の主要未着手領域は Phase 1b の LINE / LIFF / Rakuten。

---

## 1. システム構成図（コンテナ / デプロイ）

req §9.1 の 2 コンテナ構成を、外部サービス・データストアと合わせて示す。色は各要素の現状。

```mermaid
flowchart TB
  subgraph client["クライアント"]
    flutter_auth["Flutter Web: 認証 + クローゼット管理UI<br/>(flutter-web-app/lib/auth, /closet)"]
    flutter_acc["Flutter Web: Coordination + Accordion + 結果UI<br/>(M5-10 Done)"]
    lineapp["LINE App / LIFF (M6)"]
  end

  subgraph cloudrun["Google Cloud Run"]
    subgraph fastapi["fastapi-service (Python/FastAPI) — 稼働中"]
      r_closet["/closet/* ルート (M2)"]
      r_internal["/internal/tasks/process-upload (M2-5)"]
      r_session["/sessions/* ルート (M5: create/source/stream)"]
      r_line["LINE Webhook ルート (M6)"]
    end
    subgraph adk["adk-agent-service (Python ADK・ADL-022) — FastAPI wrapper + ADK app"]
      orch["StylingOrchestratorAgent + sub-agents (M4)"]
    end
  end

  subgraph data["データストア / 外部"]
    fs["Firestore<br/>(users, closet, sessions, agentEvents)"]
    es["Elasticsearch<br/>(clothing_items, ローカルDocker)"]
    r2["Cloudflare R2 / ローカルMinIO<br/>(服画像)"]
    ct["Cloud Tasks / LocalHttpTaskQueue"]
    gem_an["Gemini 2.0 Flash (画像分析・Embedding)"]
    gem_img["Nano Banana (コーデ画像生成)"]
    rakuten["楽天 Ichiba API (M6)"]
    fauth["Firebase Authentication"]
    shared_seed["scripts/seed_shared_closet/run_seed.py<br/>(live seed 済み: 3クローゼット90件; フル vector seed は deployment 待ち)"]
  end

  flutter_auth -->|"Firebase ID Token"| fastapi
  flutter_auth -->|"署名付きPUT (直接)"| r2
  flutter_auth -->|"realtime listener"| fs
  flutter_auth --- fauth
  flutter_acc -.->|"SSE (M5-9)"| r_session
  lineapp -.-> r_line

  r_closet --> fs
  r_closet --> r2
  r_closet -->|"enqueue"| ct
  ct --> r_internal
  r_internal --> gem_an
  r_internal --> es
  r_internal --> fs
  shared_seed -.-> r2
  shared_seed -.-> es
  shared_seed -.-> fs

  r_session -.-> adk
  r_line -.-> ct
  orch -.-> gem_an
  orch -.-> gem_img
  orch -.-> es
  orch -.-> fs
  orch -.-> rakuten

  classDef done fill:#c8e6c9,stroke:#2e7d32,color:#1b5e20;
  classDef wip fill:#fff3cd,stroke:#f9a825,color:#795548;
  classDef stub fill:#ffe0b2,stroke:#e65100,color:#bf360c,stroke-dasharray:5 3;
  classDef todo fill:#eceff1,stroke:#90a4ae,color:#455a64,stroke-dasharray:6 3;

  class flutter_auth,flutter_acc,r_closet,r_internal,r_session,fs,r2,ct,gem_an,fauth,shared_seed,adk,orch done;
  class es,gem_img wip;
  class r_line stub;
  class lineapp,rakuten todo;
```

**読み取りポイント:**
- 🟩 **動く経路**: Flutter（認証＋クローゼット）→ fastapi `/closet` → R2 / Firestore / Cloud Tasks → `/internal` worker → Gemini 分析 + ES インデックス。これが M2 で E2E 検証済みの幹線。
- 🟨 **共有クローゼット**: seed script / shared search adapter / attribution UI は実装済み。live seed/reseed と GCE ES への full vector seed は未完了。
- 🟩 **エージェント中核（M4）**: `adk-agent-service` は Python ADK で実装済み・ローカル稼働（`adk web` / `adk api_server`、コンテナも healthy）。`search_closet` は ES の実データ（M3 シード含む）を返し、`style_synthesizer` は MinIO/R2 に結果画像を保存する。ADK が自前で発行した署名付き MinIO/R2 URL は内部 storage key として再取得できるため、Compose コンテナ内でも `localhost:9000` URL に依存しない。
- 🟨 **Nano Banana 画像生成**: `style_synthesizer` の生成呼び出しは実装済みだが、ローカル（free-tier API key）では quota の都合で **collage fallback（ADL-005）のみ実証**。生成パスは課金キー / Vertex AI で確認する。
- 🟩 **M5 Done**: `/sessions/*`、ADK `/internal/run-session`、`agentEvents` 書き込み、SSE、Accordion UI は実装済み。review hardening で SSE terminal race、orphaned `SEARCHING`、unbounded stream、unprotected ADK internal route、shared-closet picker filtering、ADK/FastAPI status-sequence mismatch を修正済み。local API/SSE smoke と rendered browser E2E は authenticated `SHARED_CLOSET` session → `COMPLETED` result まで通過。
- ⬜ **未着手**: LINE / LIFF / 楽天。
- 🟨 ES はローカル Docker では動作。GCE VM + VPC + Cloud Run プライベート接続はデプロイ期に延期（M1-3）。

---

## 2. ヘキサゴナル ポート & アダプタ マップ

req §5 / §6 の Ports & Adapters を、実コードの状態で塗り分けたもの。**橙破線＝骨組み（実装予定）**が一目で分かる。

```mermaid
flowchart LR
  subgraph in["Input Adapters (handlers/)"]
    h_closet["closet_routes (M2)"]
    h_internal["internal_routes /process-upload (M2-5)"]
    h_session["session_routes create/source/stream (M5)"]
    h_line["LINE webhook (M6)"]
  end

  subgraph uc["Use Cases"]
    subgraph uc_closet["closet/"]
      u1["GetUploadUrl (6.7)"]
      u2["RegisterClothingItem (6.8)"]
      u3["ProcessUploadedItem (6.9)"]
      u4["DeleteClosetItem (6.10)"]
      u5["GetDownloadUrl (追加)"]
    end
    subgraph uc_style["styling/"]
      s1["CreateSession (6.11)"]
      s2["SelectSource (6.2)"]
      s3["AnalyzeImage (6.1)"]
      s4["SearchCandidates (6.3)"]
      s5["GenerateCoordinate (6.5)"]
    end
  end

  subgraph out["Output Ports → Adapters"]
    p1["ClosetRepositoryPort → FirestoreClosetRepository"]
    p2["EmbeddingSearchPort → ElasticsearchEmbeddingRepository"]
    p3["ImageStoragePort → R2ImageStorageAdapter"]
    p4["TaskQueuePort → CloudTasks / LocalHttp"]
    p5["GeminiAnalysisPort → gemini_analysis"]
    p6["StylingRepositoryPort → FirestoreStyleSessionRepository"]
    p7["ClothingSearchPort → SharedCloset / Closet / Rakuten"]
    p8["ImageGenerationPort → image_generation_stub"]
    p9["LineReplyPort → LineReplyAdapter"]
  end

  h_closet --> u1 & u2 & u4 & u5
  h_internal --> u3
  h_session --> s1 & s2
  u1 --> p3 & p1
  u2 --> p1 & p4
  u3 --> p3 & p5 & p1 & p2
  u4 --> p1 & p2 & p3
  u5 --> p3
  s1 --> p6
  s3 --> p5 & p6
  s4 --> p7 & p2
  s5 --> p8 & p6

  classDef done fill:#c8e6c9,stroke:#2e7d32,color:#1b5e20;
  classDef wip fill:#fff3cd,stroke:#f9a825,color:#795548;
  classDef stub fill:#ffe0b2,stroke:#e65100,color:#bf360c,stroke-dasharray:5 3;
  classDef todo fill:#eceff1,stroke:#90a4ae,color:#455a64,stroke-dasharray:6 3;

  class h_closet,h_internal,h_session,u1,u2,u3,u4,u5,s1,s2,s3,s4,s5,p1,p3,p4,p5,p6 done;
  class p2,p7 wip;
  class p8 stub;
  class h_line,p9 todo;
```

> `ClothingSearchPort`(p7) は `SharedClosetSearchAdapter` が実装済み（署名付き共有画像 URL + attribution 返却）だが、`ClosetSearchAdapter` / `RakutenItemAdapter` は未作成（⬜）のため全体としては 🟨。`EmbeddingSearchPort`(p2) はキーワード検索まで実装済みだがベクトル/ハイブリッド検索の本番運用は ES デプロイ（M1-3）待ちで 🟨。

---

## 3. ADK エージェント構成（M4 — 🟩 実装済み・ローカル稼働）

req §7.1 のエージェントトポロジ。M4 ExecPlan（`docs/plans/20260609-m4-adk-agents-core.md`）で TS 骨組みを破棄し、**Python ADK（`google-adk` 2.1.0）** の `adk-agent-service/styling_app/` として実装完了（ADL-022、2026-06-11）。`adk web` / `adk api_server` が `styling_app` を `root_agent`（orchestrator）として公開し、各ツールは Tool Registry 経由でサブエージェントに配線される。委譲 → `search_closet`（M3 シード済み `__shared__` データ + CC BY-SA 4.0 attribution）→ `style_synthesizer`（collage fallback）を E2E 確認済み。

```mermaid
flowchart TB
  orch["StylingOrchestratorAgent (M4-1)"]
  closet["ClosetAgent (M4-2)"]
  styling["StylingAgent (M4-3)"]
  reg["Tool Registry (M4-4)"]
  t1["analyze_clothing_image (M4-5)"]
  t2["search_closet (M4-6)"]
  t3["style_synthesizer (M4-7)"]
  t4["ask_preference (M4-8)"]

  orch --> closet
  orch --> styling
  closet --> reg
  styling --> reg
  reg --> t1 & t2 & t3 & t4

  classDef done fill:#c8e6c9,stroke:#2e7d32,color:#1b5e20;
  class orch,closet,styling,reg,t1,t2,t3,t4 done;
```

---

## 4. フロー図① — クローゼット画像アップロード（🟩 M2: 実装済み・動作する）

req §6.7–6.9 / §8.4 / ADL-014。M2 で E2E 検証済みの実フロー。

```mermaid
sequenceDiagram
  autonumber
  participant F as Flutter Web 🟩
  participant API as fastapi /closet 🟩
  participant R2 as R2/MinIO 🟩
  participant FS as Firestore 🟩
  participant Q as Cloud Tasks 🟩
  participant W as /internal worker 🟩
  participant G as Gemini Flash 🟩
  participant ES as Elasticsearch 🟨

  F->>API: GET /closet/upload-url (Firebase ID Token)
  API->>API: 上限(MAX_CLOSET_IMAGES)検証
  API-->>F: 署名付きPUT URL + item_id
  F->>R2: PUT 画像 (直接アップロード, CORS)
  F->>API: POST /closet/items/{id}/complete
  API->>FS: placeholder {status: PROCESSING}
  API->>Q: enqueue ProcessUploadedJob
  Q->>W: POST /internal/tasks/process-upload
  W->>R2: 画像bytes取得
  W->>G: 構造化分析 + Embedding
  W->>FS: 更新 {status: READY, tags, category…}
  W->>ES: clothing_items に upsert
  FS-->>F: realtime listener で READY 反映
```

---

## 5. フロー図② — コーディネート提案（🟩 M4 エージェント部分 実装済み ／ 🟩 M5 配線 Done）

req §6.1–6.5 / ADL-011 / ADL-020 / ADL-021。**エージェント内部（委譲・search_closet・style_synthesizer）は M4 で実装済み**（ローカル ADK Web UI で動作）。fastapi `/sessions` 配線・ADK `agentEvents` リレー・SSE・Accordion/result UI は M5 で実装済みで、local API/SSE smoke と rendered browser E2E を通過済み。

```mermaid
sequenceDiagram
  autonumber
  participant F as Flutter (Accordion/A2UI) 🟩
  participant API as fastapi /sessions 🟩
  participant ADK as adk-agent-service 🟩
  participant FS as Firestore 🟩
  participant ES as Elasticsearch 🟨
  participant IMG as Nano Banana 🟧

  F-->>API: POST /sessions (好み入力済み)
  API-->>FS: sessions/{id} {status: SOURCE_SELECTING}
  F-->>API: POST /sessions/{id}/source (SHARED_CLOSET 等)
  API-->>ADK: POST /internal/run-session (直接HTTP, ADL-020)
  ADK-->>API: 202 Accepted
  Note over ADK: Orchestrator → Closet/Styling 委譲 (M4)
  ADK-->>ES: cross-modal ハイブリッド検索 (search_closet)
  ADK-->>FS: agentEvents 書き込み (思考トレース, ADL-021)
  ADK-->>IMG: style_synthesizer 画像生成
  ADK-->>FS: sessions/{id} {status: COMPLETED, styleResult}
  loop event polling → SSE (ADL-011)
    API-->>F: GET /sessions/{id}/stream で Accordion 配信
  end
```

---

## 6. フロー図③ — LINE チャネル（⬜ M6: 未着手 / Phase 1b）

req §1 Phase 1b / §7.4 / §10.2 / ADL-006。**ファイル自体が存在しない**。M5 完了後の次フェーズとして着手する（req §14）。

```mermaid
sequenceDiagram
  autonumber
  participant U as LINE User ⬜
  participant API as fastapi LINE Webhook ⬜
  participant Q as Cloud Tasks ⬜
  participant ADK as adk-agent-service 🟩
  participant LINE as LINE Reply/Push ⬜

  U-->>API: 画像メッセージ送信
  API-->>U: 即時 200 OK (5秒制約, ADL-006)
  API-->>Q: enqueue agent job
  Q-->>ADK: 非同期 Agent 実行
  ADK-->>LINE: コーデ画像 Reply (失効時は Push)
  LINE-->>U: トーク画面に返信
```

---

## 7. 実装ロードマップ（依存関係）

```mermaid
flowchart LR
  M0["M0 基盤"] --> M1["M1 PoC/インフラ"]
  M0 --> M2["M2 認証+クローゼット"]
  M1 --> M2
  M2 --> M3["M3 共有クローゼット"]
  M1 --> M4["M4 ADKエージェント"]
  M2 --> M4
  M3 --> M5["M5 コーデフロー+Accordion"]
  M4 --> M5
  M5 --> M6["M6 LINE統合"]

  classDef done fill:#c8e6c9,stroke:#2e7d32,color:#1b5e20;
  classDef wip fill:#fff3cd,stroke:#f9a825,color:#795548;
  classDef stub fill:#ffe0b2,stroke:#e65100,color:#bf360c,stroke-dasharray:5 3;
  classDef todo fill:#eceff1,stroke:#90a4ae,color:#455a64,stroke-dasharray:6 3;
  class M0,M2,M3,M4,M5 done; class M1 wip; class M6 todo;
```

**次の一手:** M6（LINE / LIFF / Rakuten）に着手する前に、M5 のデプロイ環境向け確認項目（Vertex/Nano Banana quota と Cloud Run 接続）を整理する。

---

## 8. 実装と要件の乖離メモ（可視化中に検出）

図と実コードを突き合わせる過程で、req と実装の不一致を 2 点検出した。#1 は M4 ExecPlan 起票時に解消済み。#2 は引き続き申し送り。

1. ~~**`adk-agent-service` の言語スタック**~~ — **解消済み（2026-06-09, ADL-022）**: **Python ADK に統一**する決定を `req-phase01.md` ADL-022 に記録。現状の TS 骨組み（`src/*.ts`）は M4 ExecPlan（`docs/plans/20260609-m4-adk-agents-core.md`）で破棄・置換する。根拠は req §2/§6/§7、M1-4 の Python `runner.run_async()` PoC、ADL-021 の共有 `FirestoreStyleSessionRepository`、および既存 Python アダプタの再利用。

2. **`process-upload` worker の配置**: req §6.9 / §9.1 は当該 worker を `adk-agent-service` 配置と記述。実装は **`fastapi-service` の `/internal/tasks/process-upload`**（feature-matrix M2-5 も fastapi-service と明記）。動作はするが req のコンテナ責務記述と不一致のため、req 側の追記で整合させると良い。**未解消**。

> #2 は feature-matrix の status とは矛盾しない。本メモはドキュメント整合のための申し送り。
