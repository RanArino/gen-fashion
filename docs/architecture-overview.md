# Architecture Overview — gen-fashion (Phase 1)

> **生成日:** 2026-06-08
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

> **🟧 Stub と ⬜ Not started はどちらも「これから実装予定」**である。違いは、M0 で骨組み（ポート IF・空のユースケース・空のエージェント）まで先行配置済みか否か。Phase 1a の残機能（M4/M5）は 🟧 Stub、Phase 1b（M6・LINE）は ⬜ 未着手。M3 は local で実装完了（フル vector seed のみ deployment 待ち）。

---

## マイルストーン別 実装サマリ

| Milestone | 内容 | Phase | 状態 |
|---|---|---|---|
| **M0** | プロジェクト基盤・ローカル開発環境 | 1a | 🟩 **Done** |
| **M1** | PoC & インフラ検証（画像生成・ADK イベント・ES） | 1a | 🟩 Done（M1-3 ES の GCE デプロイ部分のみ 🟨 WIP） |
| **M2** | 認証 & クローゼット管理（Web） | 1a | 🟩 **Done**（E2E 検証済み） |
| **M3** | 共有デモクローゼット | 1a | 🟩 **Done（local）**（seed script / SharedClosetSearchAdapter / attribution UI 実装済み。3クローゼットの live seed 済み＝90件・30/30/30・冪等性検証済み 2026-06-10。フル vector seed（GCE ES）のみ deployment 待ち） |
| **M4** | ADK エージェント中核 | 1a | 🟧 **Stub → 着手**（M4 ExecPlan 進行中・Python ADK へ移行 ADL-022。コード未着手のため色は Stub のまま） |
| **M5** | コーディネートフロー & Accordion UI | 1a | 🟧 **Stub**（`styling/` use case・`session_routes` 全て 501） |
| **M6** | LINE チャネル統合 | 1b | ⬜ **Not started**（ファイル無し） |

**現在地:** Phase 1a の前半（基盤＋クローゼット管理）まで動作し、共有デモクローゼットのコード実装（seed script / shared search / attribution）は完了。live seed/reseed とコア体験である**エージェントオーケストレーション（M4/M5）**が次の主要実装対象。

---

## 1. システム構成図（コンテナ / デプロイ）

req §9.1 の 2 コンテナ構成を、外部サービス・データストアと合わせて示す。色は各要素の現状。

```mermaid
flowchart TB
  subgraph client["クライアント"]
    flutter_auth["Flutter Web: 認証 + クローゼット管理UI<br/>(flutter-web-app/lib/auth, /closet)"]
    flutter_acc["Flutter Web: Accordion + 結果UI (A2UI/genui)<br/>(M5-10 未着手)"]
    lineapp["LINE App / LIFF (M6)"]
  end

  subgraph cloudrun["Google Cloud Run"]
    subgraph fastapi["fastapi-service (Python/FastAPI) — 稼働中"]
      r_closet["/closet/* ルート (M2)"]
      r_internal["/internal/tasks/process-upload (M2-5)"]
      r_session["/sessions/* ルート (M5: create/source/stream)"]
      r_line["LINE Webhook ルート (M6)"]
    end
    subgraph adk["adk-agent-service (Python ADK へ移行中・ADL-022) — 未稼働"]
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

  class flutter_auth,r_closet,r_internal,fs,r2,ct,gem_an,fauth,shared_seed done;
  class es wip;
  class flutter_acc,r_session,adk,orch,gem_img,r_line stub;
  class lineapp,rakuten todo;
```

**読み取りポイント:**
- 🟩 **動く経路**: Flutter（認証＋クローゼット）→ fastapi `/closet` → R2 / Firestore / Cloud Tasks → `/internal` worker → Gemini 分析 + ES インデックス。これが M2 で E2E 検証済みの幹線。
- 🟨 **共有クローゼット**: seed script / shared search adapter / attribution UI は実装済み。live seed/reseed と GCE ES への full vector seed は未完了。
- 🟧 **骨組みのみ**: `adk-agent-service` 全体、`/sessions/*`、SSE、画像生成、Accordion UI。
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

  class h_closet,h_internal,u1,u2,u3,u4,u5,p1,p3,p4,p5 done;
  class p2,p7 wip;
  class h_session,s1,s2,s3,s4,s5,p6,p8 stub;
  class h_line,p9 todo;
```

> `ClothingSearchPort`(p7) は `SharedClosetSearchAdapter` が実装済み（署名付き共有画像 URL + attribution 返却）だが、`ClosetSearchAdapter` / `RakutenItemAdapter` は未作成（⬜）のため全体としては 🟨。`EmbeddingSearchPort`(p2) はキーワード検索まで実装済みだがベクトル/ハイブリッド検索の本番運用は ES デプロイ（M1-3）待ちで 🟨。

---

## 3. ADK エージェント構成（M4 — 骨組み／Python ADK へ移行中）

req §7.1 のエージェントトポロジ。現状 `adk-agent-service/src/` に TS の骨組みクラスが置かれている（全メソッド `throw Error("Implement in M4-x")`）が、M4 ExecPlan（`docs/plans/20260609-m4-adk-agents-core.md`）でこれを破棄し **Python ADK（`google-adk`）** に置換する（ADL-022）。下図のトポロジ自体は不変で、各エージェント／ツールを Python で実装する。

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

  classDef stub fill:#ffe0b2,stroke:#e65100,color:#bf360c,stroke-dasharray:5 3;
  class orch,closet,styling,reg,t1,t2,t3,t4 stub;
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

## 5. フロー図② — コーディネート提案（🟧 M4/M5: これから実装）

req §6.1–6.5 / ADL-011 / ADL-020 / ADL-021。**この図全体が実装予定**（点線＝未実装経路）。

```mermaid
sequenceDiagram
  autonumber
  participant F as Flutter (Accordion/A2UI) 🟧
  participant API as fastapi /sessions 🟧
  participant ADK as adk-agent-service 🟧
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
  loop on_snapshot → SSE (ADL-011)
    API-->>F: GET /sessions/{id}/stream で Accordion 配信
  end
```

---

## 6. フロー図③ — LINE チャネル（⬜ M6: 未着手 / Phase 1b）

req §1 Phase 1b / §7.4 / §10.2 / ADL-006。**ファイル自体が存在しない**。M5 完了まで着手しない（req §14）。

```mermaid
sequenceDiagram
  autonumber
  participant U as LINE User ⬜
  participant API as fastapi LINE Webhook ⬜
  participant Q as Cloud Tasks ⬜
  participant ADK as adk-agent-service 🟧
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
  class M0,M2,M3 done; class M1 wip; class M4,M5 stub; class M6 todo;
```

**次の一手:** M3（共有クローゼット seeding）は local 完了済み（フル vector seed のみ deployment 待ち）。残るクリティカルパスは **M4（ADK エージェント）→ M5（コア体験の E2E）**。

---

## 8. 実装と要件の乖離メモ（可視化中に検出）

図と実コードを突き合わせる過程で、req と実装の不一致を 2 点検出した。#1 は M4 ExecPlan 起票時に解消済み。#2 は引き続き申し送り。

1. ~~**`adk-agent-service` の言語スタック**~~ — **解消済み（2026-06-09, ADL-022）**: **Python ADK に統一**する決定を `req-phase01.md` ADL-022 に記録。現状の TS 骨組み（`src/*.ts`）は M4 ExecPlan（`docs/plans/20260609-m4-adk-agents-core.md`）で破棄・置換する。根拠は req §2/§6/§7、M1-4 の Python `runner.run_async()` PoC、ADL-021 の共有 `FirestoreStyleSessionRepository`、および既存 Python アダプタの再利用。

2. **`process-upload` worker の配置**: req §6.9 / §9.1 は当該 worker を `adk-agent-service` 配置と記述。実装は **`fastapi-service` の `/internal/tasks/process-upload`**（feature-matrix M2-5 も fastapi-service と明記）。動作はするが req のコンテナ責務記述と不一致のため、req 側の追記で整合させると良い。**未解消**。

> #2 は feature-matrix の status とは矛盾しない。本メモはドキュメント整合のための申し送り。
