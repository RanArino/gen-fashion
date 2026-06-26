# Phase 1 MVP Requirements — gen-fashion

> **Last updated:** 2026-05-10
> **Status:** Active — Hackathon MVP target
> **Architecture:** Hexagonal Architecture + DDD (see SKILL.md in `.claude/skills/hexagonal-ddd-coach/`)
> **Implementation tracker:** [feature-matrix-phase01.md](feature-matrix-phase01.md) — milestone-based status of every requirement below. Keep both files in sync when requirements change.

> **実装優先方針:** Web GUI エージェントオーケストレーション（Accordion UI）を Phase 1a として先行実装する。LINE 統合は Phase 1b として後続実装とする。
> **設計原則:** 最低限の認証・エラー処理のみ実装しシンプルに保つ。不明なプロセスを追加しない。処理のボトルネックが常に特定可能な構成を維持する。

---

## 1. Core Value Proposition

ユーザーがアップロードした服の画像をベースとして、複数の AI エージェントが協調しコーディネートを提案する体験を提供する。

**Phase 1a — Web GUI（先行実装）:**

1. ユーザーが Web GUI にログインし、服の画像をアップロードする。
2. 複数エージェントが議論・推論する様子を **Accordion UI でリアルタイム表示**する（Codex / Claude Code の段階的思考 UI と同等の体験）。
3. エージェントが画像を分析し、コーディネート候補を提示する。
4. ユーザーが選択後、最終コーディネート画像を生成・表示する。
5. クローゼット管理（画像アップロード、上限: `MAX_CLOSET_IMAGES_PER_USER` = 20）。

**Phase 1b — LINE チャネル（後続実装）:**

1. ユーザーが LINE でアップロードした服の画像をエージェントが受信する。
2. エージェントが画像を分析し、服のメタデータを構造化出力として生成する。
3. エージェントが選択肢を提示する：
   - 「自分の持っている服からコーディネートする（クローゼットデータがある場合のみ）」
   - 「楽天で検索した服からコーディネートする」
4. ユーザーが選択後、エージェントがコーディネート候補を提示し、ユーザーが選択する。
5. 最終的にコーディネート画像を生成し、LINE のトーク画面に返信する。

---

## 2. Technology Stack

| レイヤー | 技術 | 備考 |
|---|---|---|
| Frontend | Flutter | Firebase Auth 統合済み |
| Messaging UI | LINE Messaging API | Webhook 受信 + Reply API |
| Backend API | Python / FastAPI | REST API + 画像前処理 |
| AI Agent | Google ADK (Agent Development Kit) | LLM 推論・ツールコール専用コンテナ |
| Auth | Firebase Authentication | Flutter と自然に統合 |
| Primary DB | Firestore | ADK との自然な統合 |
| Vector DB | Elasticsearch (Self-hosted on Compute Engine, Basic license) | ハイブリッド検索（キーワード + ベクトル）。e2-medium VM に単一ノード構成で運用 |
| Object Storage | Cloudflare R2 | 画像などの大容量ファイル |
| Infrastructure | Google Cloud Run | パブリック公開、コンテナ 2 種 |
| Async Queue | Cloud Tasks | LINE の 5 秒タイムアウト対応 + 楽天 API レート制限遵守 |
| Logging | Cloud Logging | ADK の Event Stream を出力 |
| Image Gen | Nano Banana 2 / Imagen 4 (PoC 要) | コーディネート画像生成 |
| Image Analysis | Gemini 2.0 Flash | 服画像の構造化出力、低コスト 

---

## 3. Architecture Classification (Hexagonal DDD SKILL.md § 1)

**Classification: Large**

理由:
- LINE・Web という複数の入力チャネルが存在し、ライフサイクルが異なる。
- 楽天検索とクローゼット検索という 2 種類の Output Port が存在し、スイッチ可能である必要がある。
- コーディネート生成（画像生成）は副作用が大きく、独立した Use Case として分離が必要。

---

## 4. Domain Model (DDD)

### 4.1 Bounded Contexts

```
┌─────────────────────────────┐   ┌──────────────────────────────────┐
│   Closet Context            │   │   Styling Context                │
│                             │   │                                  │
│  ClothingItem (Aggregate)   │   │  StyleSession (Aggregate)        │
│  ClosetRepository (Port)    │   │  CoordinateProposal (Entity)     │
│  ImageEmbedding (VO)        │   │  UserPreference (VO)             │
│  ClothingTag (VO)           │   │  StyleResult (VO)                │
└─────────────────────────────┘   └──────────────────────────────────┘
          ↑                                    ↑
          │  (Anti-Corruption Layer)           │  (Anti-Corruption Layer)
┌─────────────────────────────┐   ┌──────────────────────────────────┐
│  Rakuten Context (External) │   │  LINE Context (External)         │
│  RakutenItemPort (Port)     │   │  LineWebhookAdapter              │
│  RakutenItemAdapter (Impl)  │   │  LineReplyAdapter                │
└─────────────────────────────┘   └──────────────────────────────────┘
```

### 4.2 Aggregates & Value Objects

#### Closet Context

| 要素 | 種別 | 責務 |
|---|---|---|
| `ClothingItem` | Aggregate Root | 1 着の服。色・カテゴリ・タグ・画像 URL・embedding vector を保持 |
| `ClothingItemId` | Value Object | UUID |
| `ClothingTag` | Value Object | タグ文字列の集合（カテゴリ・色・シーズンなど） |
| `ImageEmbedding` | Value Object | float[]。Elasticsearch に格納するベクトル |
| `ClosetRepository` | Output Port | CRUD + ハイブリッド検索（Firestore + Elasticsearch） |

#### Styling Context

| 要素 | 種別 | 責務 |
|---|---|---|
| `StyleSession` | Aggregate Root | LINE セッションを表現。ステートマシン（画像受信→分析→選択→提案→生成→完了） |
| `StyleSessionId` | Value Object | UUID |
| `CoordinateProposal` | Entity | 提案されたコーディネートアイテムのリスト |
| `UserPreference` | Value Object | ユーザーの好み情報（テキスト入力から収集）。`gender`（`male` / `female` / `common`）を含む（§18.1、ADL-026） |
| `StyleResult` | Value Object | 生成されたコーディネート画像の URL + 構成アイテムのリスト |
| `ClothingSource` | Value Object (Enum) | `CLOSET` / `SHARED_CLOSET` / `RAKUTEN` |

### 4.3 Domain Invariants

- `StyleSession` は画像なしに分析フェーズに進めない。
- `ClothingSource.CLOSET` を選択した場合、ユーザーのクローゼットにデータが存在しなければ提示できない。
- `ClothingSource.SHARED_CLOSET` は常に選択可能（共有データが存在することを前提とする）。
- コーディネート生成は必ずユーザーが服を選択してから実行する（同意なき自動生成禁止）。
- **候補選択は明示的な一時停止状態:** Web GUI でも上記「同意なき自動生成禁止」を満たすため、検索後にセッションは候補提示状態（`PROPOSING`）で**一時停止**し、ユーザーが候補を選択・承認するまで `GENERATING` に遷移しない（§18.2、ADL-027）。
- **生成画像は着用者の性別・年代に一致する:** `child` クローゼット選択時は子供のコーディネート画像を生成する（大人を生成してはならない）。`UserPreference.gender` と対象クローゼットの `closetKind`（adult / child）を検索・スタイリング・画像生成へ伝播する（§18.1、ADL-026）。
- **セッションの完了:** 1セッションにつき最終的に生成・提示できるコーディネート画像は1つまでとする。画像が生成・送信された時点でセッションは `COMPLETED` 状態となる。
- **セッションの再開と新規開始:** `COMPLETED` 状態、または一定時間（例: 3時間）経過してタイムアウトしたセッションの後に新しい画像がアップロードされた場合は、既存セッションを引き継がず、新規セッションを作成する。
- ユーザー 1 名あたりの `ClothingItem` 上限は `MAX_CLOSET_IMAGES_PER_USER`（デフォルト: 20）。

---

## 5. Ports & Adapters (Hexagonal Implementation Template § 3)

### 5.1 Input Ports

| Port | 実装 Adapter | 呼び出しタイミング |
|---|---|---|
| `LineWebhookInputPort` | `LineWebhookAdapter` (FastAPI) | LINE Webhook 受信時 |
| `WebUploadInputPort` | `WebUploadAdapter` (FastAPI) | Flutter Web からのアップロード |
| `StyleCommandPort` | `StyleSessionApplicationService` | Agent からの Use Case 呼び出し |
| `ClosetManagementInputPort` | `ClosetManagementAdapter` (FastAPI) | 署名付き URL 発行（`GET /closet/upload-url`）・アップロード完了受付（`POST /closet/items/{item_id}/complete`）・アイテム削除（`DELETE /closet/items/{item_id}`） |
| `CloudTasksWorkerInputPort` | `CloudTasksWorkerAdapter` (adk-agent-service) | Cloud Tasks からの非同期ジョブ受信（`POST /internal/tasks/process-upload`） |
| `SessionInputPort` | `SessionAdapter` (FastAPI) | セッション開始（`POST /sessions`） |
| `AgentRunInputPort` | `AgentRunAdapter` (adk-agent-service) | Web GUI のコーディネート実行トリガー（FastAPI からの直接 HTTP `POST /internal/run-session`、ADL-020） |

### 5.2 Output Ports

| Port | Adapter 実装 | 備考 |
|---|---|---|
| `ClosetRepositoryPort` | `FirestoreClosetRepository` | メタデータ CRUD |
| `EmbeddingSearchPort` | `ElasticsearchEmbeddingRepository` | ベクトル + キーワードハイブリッド検索 |
| `ClothingSearchPort` | `RakutenItemAdapter` / `ClosetSearchAdapter` / `SharedClosetSearchAdapter` | 差し替え可能（`ClothingSource` で切り替え） |
| `ImageStoragePort` | `R2ImageStorageAdapter` | Cloudflare R2 への画像保存・取得 |
| `LineReplyPort` | `LineReplyAdapter` | LINE Reply API |
| `StyleSessionRepositoryPort` | `FirestoreStyleSessionRepository` | セッション状態の永続化 |
| `TaskQueuePort` | `CloudTasksAdapter` | 非同期ジョブ投入 |
| `ImageGenerationPort` | `GeminiImageGenerationAdapter` | コーディネート画像生成（PoC 要） |

> **Clean Architecture 原則:** `ClothingSearchPort` を抽象 Port として定義することで、楽天・クローゼット・将来の他サービス（ZOZOTOWN 等）に容易にスイッチ可能とする。

---

## 6. Use Cases

### 6.1 AnalyzeClothingImageUseCase

- **Input:** `userId`, `imageBytes`, `sessionId`
- **Output:** `ClothingAnalysisResult { category, colors, tags, season, style }`（Structured Output）
- **Success:** Firestore に分析結果を保存し、`StyleSession` を「分析完了」状態に遷移
- **Failure:** 画像フォーマット不正、Gemini API エラー
- **Agent Tool:** `analyze_clothing_image` (Gemini 2.0 Flash, Structured Output)

### 6.2 SelectClothingSourceUseCase

- **Input:** `sessionId`, `userId`, `source: ClothingSource`
- **Output:** `void`（`StyleSession` の `source` フィールドを更新）
- **Validation:** `CLOSET` 選択時はユーザーのクローゼットにデータが存在することを確認。`SHARED_CLOSET` は常に選択可能

### 6.3 SearchCandidateItemsUseCase

- **Input:** `sessionId`, `analysisResult`, `userPreference`
- **Output:** `List<CandidateItem>` （共通スキーマ、`ClothingSource` に関わらず同一構造）
- **Routing:** `CLOSET` → `ClosetSearchAdapter`（ユーザー個人クローゼット）、`SHARED_CLOSET` → `SharedClosetSearchAdapter`（共有デモクローゼット）、`RAKUTEN` → `RakutenItemAdapter`
- **Agent Tool:** `search_rakuten`（楽天用）、`search_closet`（クローゼット・共有クローゼット共通）

```python
# 共通スキーマ (CandidateItem)
class CandidateItem(BaseModel):
    item_id: str
    source: ClothingSource  # CLOSET | SHARED_CLOSET | RAKUTEN
    name: str
    image_url: str
    price: Optional[int]     # None if CLOSET / SHARED_CLOSET
    category: str
    tags: list[str]
    external_url: Optional[str]  # 楽天商品ページ URL など
    attribution: Optional[str]   # SHARED_CLOSET の場合のみ: "Clothing Dataset (CC BY-SA 4.0)"
```

### 6.4 AskUserPreferenceUseCase

- **Input:** `sessionId`, `analysisResult`
- **Output:** `UserPreference { style, colors, occasion, budget, gender }`（`gender`: `male` / `female` / `common`、§18.1）
- **Agent Tool:** `ask_preference`（LINE インタラクティブメッセージで選択肢を提示）
- **Web GUI（Phase 1a）の方式:** Accordion のマルチターン対話ではなく、**エージェント実行の起動前に Flutter で好み入力フォームを表示**し、収集した `UserPreference` を `runner.run_async()` の初期コンテキストとして渡す（Web では `ask_preference` のインタラクティブツール・マルチターン ADK セッションは使わない）。LINE（Phase 1b）は従来どおり `ask_preference` のインタラクティブメッセージを使用する。

### 6.5 GenerateCoordinateUseCase

- **Input:** `sessionId`, `selectedItems: List<CandidateItem>`
- **Precondition:** `selectedItems` はユーザーが `PROPOSING` 状態で選択・承認した候補。空のまま呼び出してはならない（§4.3 / §18.2、ADL-027）。
- **着用者属性:** `UserPreference.gender` と対象クローゼットの `closetKind`（adult / child）を画像生成プロンプトに渡し、生成画像を着用者に一致させる（§18.1、ADL-026）。
- **Output:** `StyleResult { coordinateImageUrl, items }`
- **Agent Tool:** `style_synthesizer`
- **モデル制約:** コーディネート画像生成（複数服画像をインプットとした合成・仮想着用）は **Imagen 4** または **Nano Banana 2** でのみ実現可能。Gemini 2.0 Flash は画像分析専用とし、画像生成には使用しない。

#### PoC テストスクリプト要件

コーディネート画像生成の実現可否を検証するため、以下の仕様で独立したテストスクリプトを作成・保持する。

| 項目 | 仕様 |
|---|---|
| **配置場所** | `gen-fashion/poc/image_generation/` |
| **スクリプト** | `run_poc.py`（単一ファイル、`python run_poc.py` で即起動） |
| **テスト画像** | 同ディレクトリ `gen-fashion/poc/image_generation/samples/` に保管 |
| **テスト対象** | Imagen 4 と Nano Banana 2 の両モデルを同一入力で実行し結果を並列保存 |
| **出力** | `gen-fashion/poc/image_generation/results/` に `imagen4_result.jpg` / `nanobanana2_result.jpg` を出力 |
| **依存関係** | コンテナ不要。`pip install -r requirements.txt` のみで動作（requirements.txt を同ディレクトリに配置） |
| **API 認証** | `GOOGLE_CLOUD_PROJECT` 環境変数のみで動作（`.env` ファイルサポートを含む） |

**目的:** PoC ファイルを保持することで誰でも同条件で再現・比較でき、Imagen 4 と Nano Banana 2 のどちらが品質・コスト・速度で優れるかを客観的に判断できる状態を維持する。PoC が失敗した場合のフォールバックはコラージュ画像（服画像を並べたもの）とする。

### 6.7 GetUploadUrlUseCase

- **Endpoint:** `GET /closet/upload-url?item_id={item_id}`
- **Input:** `userId`（Firebase ID Token から取得）、`item_id`（UUID、Flutter 側で生成）
- **Output:** `{ upload_url: str, item_id: str }` — R2 署名付き PUT URL（有効期限: 15 分）
- **Validation:** `users/{userId}/closet` のドキュメント数が `MAX_CLOSET_IMAGES_PER_USER` 未満であることを確認。超過時は `429 Too Many Requests`
- **Side Effect:** なし（URL 発行のみ。Firestore への書き込みは `RegisterClothingItemUseCase` で行う）
- **R2 パス:** `/{userId}/closet/{item_id}.jpg`

### 6.8 RegisterClothingItemUseCase

- **Endpoint:** `POST /closet/items/{item_id}/complete`
- **Input:** `userId`（Firebase ID Token から取得）、`item_id`（パスパラメーター）
- **Output:** `{ item_id: str, status: "PROCESSING" }`
- **Steps:**
  1. Firestore `users/{userId}/closet/{item_id}` にプレースホルダー文書を作成: `{ status: "PROCESSING", imageUrl: "/{userId}/closet/{item_id}.jpg", createdAt }`
  2. `CLOUD_TASKS_QUEUE_EMBED` キューに `ProcessUploadedClothingItemJob { userId, item_id }` を投入
- **Failure:** R2 にファイルが存在しない場合（Flutter の PUT 失敗を検知できない点は許容）、Cloud Tasks ジョブが失敗し `status: "ERROR"` に更新される

### 6.9 ProcessUploadedClothingItemUseCase

- **Endpoint:** `POST /internal/tasks/process-upload`（Cloud Tasks からのみ呼び出し）
- **Input:** Cloud Tasks ジョブペイロード `{ userId: str, item_id: str }`
- **実行コンテナ:** `adk-agent-service`（ADK 不使用。Gemini API・Elasticsearch・Firestore を直接呼び出す）
- **Steps:**
  1. R2 から `/{userId}/closet/{item_id}.jpg` の画像 bytes を取得
  2. Gemini 2.0 Flash で画像を Structured Output 分析 → `ClothingAnalysisResult { category, colors, tags, season, style }`
  3. `gemini-embedding-2`（`output_dimensionality=768`）で画像 bytes を Embedding → `ImageEmbedding` vector（dims=768）
  4. Firestore `users/{userId}/closet/{item_id}` を更新: `{ status: "READY", category, colors, tags, season, embeddingId: item_id }`
  5. Elasticsearch `clothing_items` インデックスに upsert: `{ item_id, user_id: userId, is_shared: false, tags, category, colors, season, embedding }`
- **Failure handling:** 例外発生時は Firestore の `status` を `"ERROR"` に更新。Cloud Tasks の自動リトライ（最大3回）に委ねる。3回失敗後は Cloud Tasks の Dead Letter Queue に転送

### 6.10 DeleteClosetItemUseCase

- **Endpoint:** `DELETE /closet/items/{item_id}`
- **Input:** `userId`（Firebase ID Token から取得）、`item_id`（パスパラメーター）
- **Output:** `204 No Content`
- **Steps:**
  1. Firestore `users/{userId}/closet/{item_id}` が存在することを確認（存在しない場合は `404 Not Found`）
  2. Elasticsearch `clothing_items` インデックスから `item_id` の doc を削除
  3. R2 から `/{userId}/closet/{item_id}.jpg` を削除
  4. Firestore `users/{userId}/closet/{item_id}` を削除
- **Failure handling:** ステップ 2-3 の失敗はエラーログに記録するが、ステップ 4（Firestore 削除）は続行する。R2・ES の孤立データは MVP では許容する
- **Note:** `status: "PROCESSING"` 中のアイテムも削除可能とする。その後 Cloud Tasks ジョブが実行された場合、削除済み Firestore doc への更新は失敗するが、エラーは無視してよい

### 6.11 CreateSessionUseCase

- **Endpoint:** `POST /sessions`
- **Input:** `userId`（Firebase ID Token から取得）
- **Output:** `{ session_id: str, status: "SOURCE_SELECTING" }`
- **Steps:**
  1. UUIDv4 で `sessionId` を生成
  2. Firestore `sessions/{sessionId}` を作成: `{ userId, status: "SOURCE_SELECTING", source: "UNSET", createdAt, updatedAt }`
- **Precondition:** なし。アクティブなセッションが存在する場合に再度呼び出すか否かの制御は Flutter 側の責務とする
- **Phase:** Web GUI Phase 1a のコーディネートフロー開始エントリポイント。LINE フロー（Phase 1b）では LINE Webhook 受信時に FastAPI が内部的に本 Use Case を呼び出す
- **初期 status が `SOURCE_SELECTING` の理由:** Web GUI では服画像はクローゼットに登録済み（Use Cases 6.7-6.9 で処理完了）のため、新規画像アップロードなしにソース選択フェーズから開始する

### 6.6 ReplyCoordinateToLineUseCase

- **Input:** `sessionId`, `styleResult`
- **Output:** `void`
- **Side Effect:** LINE Reply API でコーディネート画像 + テキストを送信

---

## 7. Agent Design (ADK)

### 7.1 Agent 構成

```
StylingOrchestratorAgent
├── ClosetAgent         # クローゼット検索・管理
└── StylingAgent        # コーディネート生成・提案
```

**Phase 1 では ClosetAgent + StylingAgent の 2 体から開始する。**

`StylingOrchestratorAgent` が入力を判断し、適切なサブエージェントに委譲する。ADK のネイティブ設計思想（Sub-agent delegation）に準拠。

**デフォルトモデル:** 全 Agent の LLM は `gemini-2.0-flash` を使用する。環境変数 `AGENT_MODEL` で上書き可能とし、デモ中のモデル切り替えに対応する。

### 7.2 Agent Tools

| Tool | モデル | 入力 | 出力 | 備考 |
|---|---|---|---|---|
| `analyze_clothing_image` | Gemini 2.0 Flash | 画像 bytes | `ClothingAnalysisResult` (Structured Output) | 低コスト、高速 |
| `search_rakuten` | — (API 呼び出し) | 検索パラメーター (Structured) | `List<CandidateItem>` | Cloud Tasks 経由でレート制限遵守 |
| `search_closet` | — (DB 呼び出し) | `ClothingTag`, `ImageEmbedding` | `List<CandidateItem>` | ハイブリッド検索 (ES + Firestore)。Agent が分析結果をもとに「合う服の特徴」を自然言語で表現し、その説明テキストを `gemini-embedding-2` で Embedding してクエリベクトルとする |
| `ask_preference` | — | `ClothingAnalysisResult` | `UserPreference` | LINE インタラクティブメッセージ |
| `style_synthesizer` | Imagen 4 / Gemini 2.0 Flash (PoC) | `List<CandidateItem>` + 画像 | `StyleResult` | 最終コーディネート画像生成 |

> 将来の拡張性のため、Tool はすべて独立したモジュールとして定義し、Tool Registry パターンで管理すること。

### 7.3 Rakuten API レート制限対応

- エージェントが `search_rakuten` Tool を呼び出した際、直接 API を叩かず **Cloud Tasks にジョブを投入する**。
- Cloud Tasks のキュー設定: `maxConcurrentDispatches: 1`（物理的に 1 秒 1 リクエストを保証）。

### 7.4 LINE の 5 秒タイムアウト対応

- LINE Webhook を受信した FastAPI エンドポイントは即座に `200 OK` を返す。
- 処理本体（ADK Agent 実行）は Cloud Tasks 経由で非同期実行する。
- 結果は LINE Reply API（`replyToken`）または Push API で後から送信する。

---

## 8. Data Architecture

### 8.1 Firestore コレクション設計

```
users/{userId}                        # Firebase UID をドキュメント ID とする
  - displayName: string
  - lineUserId: string                # LINE ユーザー ID（紐付け後に書き込み）
  - createdAt: timestamp

lineUsers/{lineUserId}                # lineUserId → Firebase UID の逆引きマッピング
  - userId: string                    # Firebase UID（users コレクションへの参照）
  - createdAt: timestamp

users/{userId}/closet/{itemId}        # ユーザー個人クローゼット
  - status: enum ("PROCESSING" | "READY" | "ERROR")  # ProcessUploadedClothingItemUseCase の処理状態
  - imageUrl: string (R2 URL)
  - category: string        # status="READY" 以降のみ有効
  - tags: string[]          # status="READY" 以降のみ有効
  - season: string          # status="READY" 以降のみ有効
  - colors: string[]        # status="READY" 以降のみ有効
  - gender: string          # "male" | "female" | "common"。分析時にカテゴリヒューリスティックで自動付与し、ギャラリーでユーザーが編集可（§18.1/§18.3、ADL-026/ADL-028）
  - embeddingId: string     # Elasticsearch document ID。status="READY" 以降のみ有効
  - createdAt: timestamp

shared_closet/{itemId}                # デモクローゼットのアイテム（読み取り専用）
  - imageUrl: string (R2 URL)
  - closetId: string     # 所属デモクローゼット（"adult-01" | "adult-02" | "child-01"）
  - closetKind: string   # "adult" | "child"
  - gender: string       # "male" | "female" | "common"（シード時にカテゴリヒューリスティックで付与、全ユーザー共通・読み取り専用、§18.1/§16、ADL-026）
  - category: string
  - tags: string[]
  - season: string
  - colors: string[]
  - embeddingId: string  # Elasticsearch document ID（clothing_items インデックス、user_id: "__shared__"）
  - datasetSource: string  # "kaggle:agrigorev/clothing-dataset-full"
  - originalLabel: string  # データセット元のラベル（例: "T-Shirt"）
  - createdAt: timestamp   # シーディング日時

shared_closets/{closetId}             # デモクローゼットのメタデータ（M5 の選択 UI 用）
  - kind: string         # "adult" | "child"
  - displayName: string  # 表示名（例: "Adult Closet A"）
  - itemCount: int       # 含まれるアイテム数（70）
  - datasetSource: string
  - createdAt: timestamp

sessions/{sessionId}
  - userId: string
  - lineReplyToken: string
  - status: enum (IMAGE_RECEIVED | ANALYZING | SOURCE_SELECTING | SEARCHING | PROPOSING | GENERATING | COMPLETED | ERROR)
  - source: enum (CLOSET | SHARED_CLOSET | RAKUTEN | UNSET)
  - analysisResult: map
  - userPreference: map               # gender（male/female/common）を含む（§18.1）
  - selectedItems: array              # ユーザーが PROPOSING 状態で選択・承認した候補（§18.2、ADL-027）。空のまま GENERATING へ遷移してはならない
  - styleResult: map
  - createdAt: timestamp
  - updatedAt: timestamp

sessions/{sessionId}/agentEvents/{eventId}   # ADK エージェント実行イベント（ADL-011 リレー / ADL-021）
  - seq: int                   # セッション内の連番
  - agentName: string          # イベント発行元エージェント名（マルチエージェント識別）
  - eventKind: enum (tool_call | tool_result | final_answer | thinking | a2ui_surface)
  - toolName: string           # tool_call / tool_result のみ
  - toolArgs: map
  - toolResult: map
  - text: string               # final_answer のみ
  - a2uiPayload: map           # a2ui_surface のみ: 結果UIコンポーネント（A2UI、ADL-018）
  - thoughtSignature: string   # base64（M1-4 検証: bytes→base64 正規化が必要）
  - createdAt: timestamp
  - ttlAt: timestamp           # Firestore TTL=24h で自動削除（ADL-021）
```

> `agentEvents` は ADK 実行の進捗（思考トレース + A2UI 結果UI）を保持する。`adk-agent-service` が直接書き込み（ADL-021）、FastAPI が `on_snapshot` で購読して SSE 配信する（ADL-011）。

### 8.2 Elasticsearch インデックス設計

```json
// index: clothing_items
{
  "mappings": {
    "properties": {
      "item_id": { "type": "keyword" },
      "user_id": { "type": "keyword" },  // ユーザー個人: Firebase UID / 共有: "__shared__"
      "is_shared": { "type": "boolean" },
      "closetId": { "type": "keyword" },   // デモクローゼット識別子（共有アイテムのみ）
      "closetKind": { "type": "keyword" }, // "adult" | "child"
      "gender": { "type": "keyword" },     // "male" | "female" | "common"（§18.1、ADL-026）
      "tags": { "type": "keyword" },
      "category": { "type": "keyword" },
      "colors": { "type": "keyword" },
      "season": { "type": "keyword" },
      "embedding": {
        "type": "dense_vector",
        "dims": 768,
        "index": true,
        "similarity": "cosine"
      }
    }
  }
}
```

ハイブリッド検索: テキストクエリ（キーワード）と Embedding Vector を組み合わせた `knn` + `query` の Hybrid Query。`SHARED_CLOSET` 検索時は `user_id: "__shared__"` でフィルタリング。

### 8.3 Embedding パイプライン

#### インデックス側（服画像の格納）

| 場面 | 入力 | タイミング | 実行箇所 |
|---|---|---|---|
| ユーザーのクローゼット | 服の画像 bytes | アップロード毎・非同期 | `RegisterClothingItemUseCase` が Cloud Tasks 投入 → `ProcessUploadedClothingItemUseCase` が実行 |
| 共有クローゼット | 服の画像 bytes | 初回シーディング時のみ | `run_seed.py` バッチ |

- **モデル:** `gemini-embedding-2`
- **output_dimensionality:** `768`（公式 Recommended）
- 生成した vector を `clothing_items` インデックスの `embedding` フィールドに格納する

#### クエリ側（検索時）

`SearchCandidateItemsUseCase` 内の `search_closet` ツール実行時に以下のステップで処理する：

1. `AnalyzeClothingImageUseCase` が生成した `ClothingAnalysisResult`（category / colors / style / tags）を入力とする
2. `ClosetAgent` の LLM が `ClothingAnalysisResult` と `UserPreference` をもとに、**コーディネートに合う服の特徴を自然言語テキストで生成する**（Structured Output。例：`{ "description": "ネイビーまたはブラックのスリムパンツ、カジュアル寄り" }`）
3. その説明テキストを `gemini-embedding-2`（`output_dimensionality=768`）で Embedding し、クエリベクトルとする
4. ES に対して画像ベクトル（インデックス）× テキストベクトル（クエリ）の **cross-modal knn 検索** + キーワード検索（tags / category）の Hybrid Query を実行する

> `gemini-embedding-2` は画像・テキストを同一ベクトル空間にマッピングするため、cross-modal 検索が成立する。

### 8.4 Cloudflare R2

#### アップロード仕様

- **バケット名:** `gen-fashion-images`
- **ディレクトリ構成:** `/{userId}/closet/{itemId}.jpg`
- **署名付き URL:** FastAPI の `GetUploadUrlUseCase` で R2 SDK 経由で 15 分 TTL の PUT URL を発行。Flutter Web が直接 R2 に PUT

#### CORS 設定

Flutter Web からのブラウザベース PUT リクエストに対応するため、R2 バケットに以下の CORS ルールを設定：

```json
{
  "CORSRules": [
    {
      "AllowedOrigins": ["https://localhost:8080", "https://your-flutter-web-domain.vercel.app"],
      "AllowedMethods": ["GET", "PUT", "POST", "OPTIONS"],
      "AllowedHeaders": ["*"],
      "ExposeHeaders": ["ETag"],
      "MaxAgeSeconds": 3600
    }
  ]
}
```

**フロー:**
1. Flutter が `OPTIONS` （preflight） → R2 が CORS ヘッダ返却 (`Access-Control-Allow-Origin` など)
2. Flutter が `PUT {signed_url}` でバイナリアップロード → R2 が署名検証 + CORS チェック → 200 OK

署名付き URL は PUT 権限を内包するため、CORS チェック後は R2 が PUT を受け入れる。

---

## 9. Infrastructure & Deployment

### 9.1 コンテナ構成（Cloud Run 上の 2 コンテナ）

| コンテナ | 役割 |
|---|---|
| `fastapi-service` | REST API（LINE Webhook 受信、画像前処理、Cloud Tasks 投入）。Gemini API 依存を持たない |
| `adk-agent-service` | AI 処理専用（ADK Agent 実行 + 直接 Gemini 呼び出しを含む）。Cloud Tasks からの `POST /internal/tasks/process-upload` も受信する |

両コンテナとも **Google Cloud Run** にデプロイし、パブリックに公開する。

#### デプロイ設定

| 項目 | `fastapi-service` | `adk-agent-service` | 理由 |
|---|---|---|---|
| **Min Instances** | 0 | 1 | ADK の LLM 推論コールドスタートは 10-30 秒。ユーザーの待ち時間を削減するため常時起動。FastAPI は軽量で冷えても 1 秒程度なため min: 0 で初期コスト削減 |
| **Max Instances** | 10 | 5 | FastAPI は軽量で高スループット。ADK は メモリ・CPU 集約的なため低めに制御 |
| **Memory** | 1GB | 2GB | |
| **CPU** | 1 | 1 | |
| **Timeout** | 60s | 600s（10 分） | FastAPI は即座に 200 返却（LINE 5 秒タイムアウト対応済み）。ADK Agent は推論に時間がかかるため大きめに設定 |
| **Service Account** | GCP デフォルト（or 専用 SA） | GCP デフォルト（or 専用 SA） | `roles/aiplatform.user`（Vertex AI/Gemini）、`roles/datastore.user`（Firestore）、`roles/logging.logWriter`（Cloud Logging） を付与 |

### 9.2 Elasticsearch インスタンス（Compute Engine）

- **マシンタイプ:** `e2-medium`（2 vCPU, 4GB RAM）
- **リージョン:** `asia-northeast1` （日本、GCP デフォルト）
- **ストレージ:** 30GB 永続ディスク（SSD 推奨）
- **ネットワーク:** VPC Peering または Cloud NAT を通じて Cloud Run からアクセス可能とする
- **インストール:** `sudo apt-get install elasticsearch` で Elasticsearch をインストール、systemd で自動起動
- **運用:** 脆弱性パッチ・メジャーバージョン更新は手動（ハッカソン MVP 規模では許容）。ハッカソン終了後に VM 削除して廃止
- **PoC 検証項目:** Compute Engine 上でのインストール・起動確認、Cloud Run プライベート接続検証、日本語分析器の要否確認（MVP では不要の見込み）

### 9.3 Logging

- ADK の Event Stream は **Cloud Logging** に出力する。
- ローカル開発時は **ADK Web UI** を使用する。
- 本番環境は Cloud Logging でクエリ可能な状態を維持する。

### 9.4 ローカル開発環境セットアップ

#### 概要

チーム開発での環境再現性を担保するため、以下の構成を採用：

- **Docker Compose:** Elasticsearch + Firestore Emulator をコンテナで隔離
- **ローカル Python 環境:** FastAPI・ADK を `python -m uvicorn` で起動（Hot Reload 対応）
- **Makefile:** 開発コマンド統一（`make dev`, `make test` 等）

#### ファイル構成

| ファイル | 概要 |
|---|---|
| `docker-compose.yml` | Elasticsearch（`localhost:9200`）+ Firestore Emulator（`localhost:8080`）。`make dev` で自動起動 |
| `Makefile` | `make dev`（全サービス起動）、`make test`（テスト実行）、`make clean`（後始末） |
| `.env.example` | ローカル開発用の環境変数テンプレート（Git 管理）。`.env` にコピーして利用 |
| `README_LOCAL_DEV.md` | セットアップ手順の詳細ドキュメント |

#### 起動手順（簡略版）

```bash
# 1. 環境変数テンプレートをコピー
cp .env.example .env

# 2. 全サービス起動（docker-compose + FastAPI + ADK）
make dev

# 3. ブラウザで確認
# - FastAPI: http://localhost:8000/docs
# - ADK Web UI: http://localhost:8080  (ADK が起動した場合)
# - Firestore Emulator: http://localhost:4000
```

#### 環境変数（ローカル開発時）

`.env.example` に以下をテンプレートとして記載：

```env
# GCP
GOOGLE_CLOUD_PROJECT=your-gcp-project
GOOGLE_GENAI_USE_VERTEXAI=false  # ローカルでは Gemini API キー認証を使用

# 開発用 API キー（ローカルテスト用ダミー値も可）
GEMINI_API_KEY=your-test-key
RAKUTEN_APP_ID=your-test-key
R2_ACCESS_KEY_ID=your-test-key
R2_SECRET_ACCESS_KEY=your-test-key
LINE_CHANNEL_SECRET=your-test-key
LINE_CHANNEL_ACCESS_TOKEN=your-test-key

# ローカルサービス URL
ELASTICSEARCH_URL=http://localhost:9200
FIRESTORE_DATABASE_ID=(default)
```

#### テスト実行

```bash
# 単体テスト + 統合テスト（Firestore Emulator + Elasticsearch 接続）
make test
```

---

## 10. Authentication

- **Firebase Authentication** を使用する（Flutter と自然に統合）。
- Phase 1 では `user_id` によるフィルタリングのみ実装する（Row Level Security は不要）。
- 管理者ダッシュボードは Phase 2 とする。

### 10.1 Web GUI ログイン（通常フロー）

Flutter Web で **Google Sign-In** を使用。Firebase Auth が UID を発行し、初回ログイン時に `users/{uid}` ドキュメントを作成する。

### 10.2 LINE → GUI 紐付けフロー（LIFF 経由）

LINE Webhook で `lineUserId` を受信した際に `lineUsers/{lineUserId}` が存在しない場合、以下のフローで GUI へ誘導してアカウント紐付けを行う。

```
[ユーザー] LINE Bot にメッセージ送信
     ↓
[FastAPI] lineUsers/{lineUserId} を Firestore で検索
     ↓ 未登録
[LINE Bot] 「アカウント登録が必要です」+ LIFF URL をリプライ
     ↓
[ユーザー] LIFF URL をタップ → LINE アプリ内ブラウザで Flutter Web (LIFF) が開く
     ↓
[LIFF] liff.init() → LINE Login 自動実行 → LINE Access Token 取得
     ↓
[LIFF → FastAPI] POST /auth/line-link  { lineAccessToken }
     ↓
[FastAPI]
  1. LINE API で lineAccessToken を検証 → lineUserId / displayName を取得
  2. Firebase Admin SDK で Custom Token を生成（uid = 新規 UUID）
  3. Firestore に書き込み:
       users/{uid}          { lineUserId, displayName, createdAt }
       lineUsers/{lineUserId} { userId: uid, createdAt }
  4. Custom Token をレスポンスで返却
     ↓
[LIFF] Firebase Auth で signInWithCustomToken(customToken) → 認証完了
     ↓
[LIFF] 登録完了画面を表示し、LINE を閉じるよう案内
     ↓
[ユーザー] LINE Bot に再度メッセージ → 通常フローで処理
```

**実装ポイント:**

| 項目 | 仕様 |
|---|---|
| LIFF URL | `https://liff.line.me/{LIFF_ID}` — Flutter Web の `/line-signup` ルートにマッピング |
| Custom Token の UID | 新規 UUID を発行（LINE UID を Firebase UID として使わない） |
| 既存 Google Sign-In ユーザーとの統合 | Phase 1 では対象外。同一人物でも別アカウントとして扱う（Phase 2 で統合） |
| LIFF のサイズ | `full`（フルスクリーン）を使用し、登録完了後は `liff.closeWindow()` で閉じる |

### 10.3 FastAPI 認証ミドルウェア

#### Flutter → FastAPI（Firebase ID Token 検証）

**責務:** すべての認証が必要なエンドポイント（`/closet/...`, `/sessions/...`）で Firebase ID Token を検証し、`user_id` を抽出する。

**実装パターン:**

```python
from firebase_admin import auth as firebase_auth
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthCredentials

security = HTTPBearer()

async def verify_firebase_token(credentials: HTTPAuthCredentials = Depends(security)) -> str:
    """Firebase ID Token を検証し、user_id を返す"""
    token = credentials.credentials
    try:
        decoded = firebase_auth.verify_id_token(token)
        return decoded['uid']
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

@app.get("/closet/upload-url")
async def get_upload_url(item_id: str, user_id: str = Depends(verify_firebase_token)):
    # user_id は Firebase UID として使用可能
    ...
```

**トークン検証の詳細:**
- Flutter は Google Sign-In または LINE Login で Firebase ID Token を取得し、`Authorization: Bearer {token}` で送付
- FastAPI は `firebase_admin.auth.verify_id_token()` で署名・有効期限・発行者を検証
- トークン失効時は 401 Unauthorized を返す。Flutter は再ログインフローを実行

#### LINE Webhook での認証済みユーザー識別

```python
# FastAPI での lineUserId → userId 解決パターン
async def resolve_user(line_user_id: str) -> str | None:
    doc = await firestore.collection("lineUsers").document(line_user_id).get()
    if not doc.exists:
        return None  # 未登録 → LIFF 誘導
    return doc.get("userId")
```

#### 内部エンドポイント（Cloud Tasks → adk-agent-service）

**現設計では不要:** Cloud Tasks は GCP 内部のジョブキューサービスで、Cloud Run の VPC 内で実行。ADK Agent への内部呼び出しは private network に限定される。

**将来的な ADK ↔ FastAPI 通信が必要になった場合:** Cloud Run OIDC トークンを使用。ADK（Cloud Run サービス）が自動取得した OIDC トークンを HTTP `Authorization: Bearer {oidc_token}` で送付し、FastAPI は `google-auth` ライブラリで検証。詳細は ADL-011 の "ケース B-3" を参照。

---

## 11. Web GUI (Flutter)

- Firebase Auth によるログイン。
- クローゼット管理画面（画像アップロード、上限: `MAX_CLOSET_IMAGES_PER_USER` = 20）。
- **エージェント思考の可視化:** 複数エージェントが議論・推論する様子を Accordion UI でリアルタイム表示する（ADK Event Stream を WebSocket or SSE で Flutter に配信）。
- **結果 UI のレンダリング方針（ADL-018）:** ユーザー向けの結果 UI（コーディネート候補カード・好み入力・最終コーディネート画像）は、エージェントが出力する **A2UI ペイロード**を Flutter 公式の `genui` で描画する方針とする（採否は Flutter Web スパイクで確定）。**思考トレース（Accordion）と結果 UI（A2UI）は別ストリームとして概念分離する。**
- **クローゼットギャラリー（自分＋共有、§18.3 / ADL-028）:** 各クローゼット（共有 `adult-01` / `adult-02` / `child-01` を含む）の中身をメタデータ（category / colors / season / tags / gender）付きで閲覧できるギャラリーを提供する。自分のクローゼットのアイテムは `gender` ほか検索用メタデータをユーザーが編集できる（共有は読み取り専用）。
- **性別・年代の指定（§18.1 / ADL-026）:** コーディネート起動前の好み入力フォームで `gender`（male / female / common）を選べる。これと対象クローゼットの `closetKind`（adult / child）が検索・生成画像に反映される。
- **候補選択（§18.2 / ADL-027）:** 検索後に候補カード（上位数件 ＋ 推薦）を提示し、ユーザーが選択・承認するまで画像生成しない（同意なき自動生成禁止、§4.3）。
- **実行履歴ギャラリー（§18.5 / ADL-029、将来拡張）:** 過去の実行（選択アイテム ＋ 生成画像 ＋ 日時）を時系列ギャラリーで再確認できる。

---

## 12. Environment Variables & Secret Management

### 12.1 シークレット管理ポリシー

- **シークレット（機密情報）は Google Cloud Secret Manager で管理する。** Cloud Run のデプロイ時に `--set-secrets` でシークレットを環境変数としてマウントする。
- **非機密の設定値は Cloud Run の環境変数（`--set-env-vars`）に直接設定する。**
- アプリケーションコードは両者を区別せず、すべて環境変数として読み取る（差異はデプロイ設定にのみ存在する）。
- シークレットを `.env` ファイルや Git リポジトリにコミットしない。ローカル開発時のみ `.env`（`.gitignore` 済み）を使用する。
- **Gemini / Vertex AI 認証:** API キーは使用しない。`GOOGLE_GENAI_USE_VERTEXAI=true` を設定し、Cloud Run のサービスアカウントに `roles/aiplatform.user` を付与して Application Default Credentials（ADC）経由で認証する。これによりシークレット管理対象から Gemini 認証情報を除外できる。
- **Firestore 認証:** 同じく Cloud Run のサービスアカウント（ADC）経由。シークレット不要。
- **ADK → FastAPI コールバック URL（`FASTAPI_INTERNAL_URL`）は不要。** ADL-011 の選択肢 A（Firestore 中継）を採用したため、ADK から FastAPI への直接 HTTP コールバックは発生しない。

### 12.2 環境変数一覧

| 変数名 | デフォルト | 管理方法 | 説明 |
|---|---|---|---|
| `MAX_CLOSET_IMAGES_PER_USER` | `20` | env var | ユーザーあたりのクローゼット画像上限 |
| `LINE_CHANNEL_SECRET` | — | **Secret Manager** | LINE Webhook 署名検証 |
| `LINE_CHANNEL_ACCESS_TOKEN` | — | **Secret Manager** | LINE Reply/Push API |
| `RAKUTEN_APP_ID` | — | **Secret Manager** | 楽天 Ichiba Item Search API（API 呼び出しの認証クレデンシャル） |
| `R2_ACCESS_KEY_ID` | — | **Secret Manager** | Cloudflare R2 アクセスキー ID（署名付き URL 発行・画像取得） |
| `R2_SECRET_ACCESS_KEY` | — | **Secret Manager** | Cloudflare R2 シークレットアクセスキー |
| `ELASTICSEARCH_API_KEY` | — | **Secret Manager** | Elasticsearch 認証 API キー（Self-hosted Basic で認証を有効化する場合） |
| `GOOGLE_CLOUD_PROJECT` | — | env var | GCP プロジェクト ID |
| `GOOGLE_GENAI_USE_VERTEXAI` | `true` | env var | `google.genai` クライアントを Vertex AI モードで動作させる（ADC 認証） |
| `FIRESTORE_DATABASE_ID` | `(default)` | env var | Firestore データベース ID |
| `ELASTICSEARCH_URL` | — | env var | Elasticsearch エンドポイント |
| `R2_BUCKET_NAME` | `gen-fashion-images` | env var | Cloudflare R2 バケット名 |
| `R2_ACCOUNT_ID` | — | env var | Cloudflare アカウント ID |
| `CLOUD_TASKS_QUEUE_RAKUTEN` | — | env var | 楽天 API 用 Cloud Tasks キュー名 |
| `CLOUD_TASKS_QUEUE_AGENT` | — | env var | ADK Agent 非同期実行キュー名 |
| `CLOUD_TASKS_QUEUE_EMBED` | — | env var | 画像 Embedding 処理（`ProcessUploadedClothingItemUseCase`）用 Cloud Tasks キュー名 |
| `ADK_SERVICE_URL` | — | env var | `adk-agent-service` の内部 URL。`fastapi-service` が Cloud Tasks ジョブのターゲット URL を構築する際に使用 |
| `LIFF_ID` | — | env var | LINE LIFF アプリ ID（LINE Developers Console で発行） |
| `LINE_LOGIN_CHANNEL_ID` | — | env var | LINE Login チャネル ID（LIFF 用、Messaging API チャネルとは別） |
| `AGENT_MODEL` | `gemini-2.0-flash` | env var | 全 Agent の LLM モデル ID。デモ中のモデル切り替えに使用 |

---

## 13. Architecture Decision Log (ADL)

### ADL-001: Firestore を Session DB として採用

- **Decision:** Firestore
- **Alternatives:** Supabase（PostgreSQL）
- **Rationale:** ADK との自然な統合、Supabase 使用禁止ルール。Firestore はリアルタイム更新が容易で Flutter との統合もスムーズ。
- **Trade-off:** SQL ライクなクエリが不可。複雑な JOIN が必要な場合は Elasticsearch で補完。

### ADL-002: 非同期処理に Cloud Tasks を採用

- **Decision:** Cloud Tasks + Queue 制御
- **Alternatives:** Pub/Sub、インプロセス非同期
- **Rationale:** LINE の 5 秒タイムアウト対応が必須。楽天 API の「1 秒 1 リクエスト」制限をインフラ側で物理的に制御するため `maxConcurrentDispatches: 1` で設定。
- **Trade-off:** Cloud Tasks のコスト（低い）と運用複雑性のトレードオフ。

### ADL-003: ClothingSearchPort を抽象化して差し替え可能とする

- **Decision:** Hexagonal の Output Port として `ClothingSearchPort` を定義
- **Rationale:** 楽天・クローゼット・将来の他サービス（ZOZOTOWN 等）を同一 Port で抽象化。DDD の Anti-Corruption Layer によって外部サービスの変更が Domain に影響しない。
- **Trade-off:** 初期実装コストが増えるが、将来の拡張性を担保。

### ADL-004: 画像ベクトル化は Elasticsearch で管理

- **Decision:** Elasticsearch (Self-hosted Basic)
- **Alternatives:** Firestore Vector Search、pgvector（Supabase は使用禁止）
- **Rationale:** ハイブリッド検索（キーワード + ベクトル）が 1 クエリで実現可能。Self-hosted Basic は無料。
- **Trade-off:** 運用・インフラ管理が必要。ハッカソンでは検証が必要。

### ADL-005: コーディネート画像生成は PoC が必要

- **Decision:** Gemini 2.0 Flash / Imagen 4 でPoC を実施してから確定
- **Rationale:** 服の画像をインプットとして、人間がその服を着ているかのような画像生成が可能かを検証する必要がある。
- **Rollback:** PoC が失敗した場合、コラージュ画像（服の画像を並べたもの）にフォールバックする。

### ADL-006: LINE の 5 秒タイムアウト対応

- **Decision:** FastAPI が即座に 200 を返し、Agent 実行は Cloud Tasks 経由で非同期処理
- **Rationale:** ADK の LLM 推論は数秒〜十数秒かかる。LINE はリトライが発生するため同期処理は不可。
- **Implementation:** LINE Reply API の `replyToken` は 1 分有効。それを超える場合は Push API に切り替える。

### ADL-007: 2 コンテナ分離（FastAPI + ADK Agent）

- **Decision:** FastAPI（REST API + 画像前処理）と ADK Agent（LLM 推論・ツールコール）を分離
- **Rationale:** スケール特性が異なる。Agent はメモリ・CPU 集約的なので独立スケールが必要。FastAPI は軽量で高スループット。
- **Trade-off:** コンテナ間通信のオーバーヘッドが発生するが、Cloud Run 内で内部 HTTP 通信なので許容範囲。

### ADL-008: CandidateItem スキーマを共通化

- **Decision:** `ClothingSource`（CLOSET / RAKUTEN）に関わらず `CandidateItem` スキーマを統一
- **Rationale:** コーディネート生成 Use Case がソースを意識しない設計。将来のソース追加でも Use Case 以降の変更が不要。

### ADL-011: ADK Event Stream → Flutter SSE の中継方式

- **Decision:** ADK コンテナが Firestore の `sessions/{sessionId}/agentEvents/{eventId}` サブコレクションにイベントを書き込み、FastAPI コンテナが Firestore の `on_snapshot` リスナーで変更を受け取り SSE として Flutter に配信する
- **Alternatives:**
  - B: ADK → FastAPI コールバック HTTP POST（in-memory Queue 経由）
  - C: ADK → Redis Pub/Sub → FastAPI SSE
- **Rationale:** Firestore はすでにスタックに存在し新インフラ不要。Cloud Run の水平スケール時に「SSE を張っているインスタンスと ADK コールバック先が異なる」問題（選択肢 B の致命的欠陥）を自動的に回避できる。Accordion UI 用途ではイベント表示に +200〜500ms の追加レイテンシは体感上許容範囲。
- **Trade-off:** Firestore の読み書きコスト（イベント数 × 課金）と `agentEvents` サブコレクションの TTL 削除が必要（**TTL=24h**、§8.1 `ttlAt` / ADL-021）。レイテンシが将来問題になる場合は Redis Pub/Sub（選択肢 C）に移行する。
- **書き込み主体:** イベントおよび実行中のセッション状態遷移は `adk-agent-service` が `FirestoreStyleSessionRepository` 経由で直接書き込む（ADL-021）。
- **Early PoC required:** ADK の `runner.run_async()` から取得できるイベントの粒度・形式を着手前に確認する（M1-4 で完了済み）。

### ADL-010: 共有デモクローゼットの導入

- **Decision:** CC BY-SA 4.0 の Kaggle データセットを使った全ユーザー共通クローゼット（`shared_closet`）を Firestore + Elasticsearch + R2 に配置する
- **Rationale:** ハッカソンデモで初回ユーザーが服をアップロードせずに即体験できる。`ClothingSearchPort` 抽象化（ADL-003）を活かし、既存 Port に `SharedClosetSearchAdapter` を追加するだけで対応可能。
- **License:** CC BY-SA 4.0 — 商用利用可、帰属表示が必要。UI に Attribution を表示する。
- **Trade-off:** シーディングスクリプトの初期セットアップコストと R2/Elasticsearch への2,000〜3,000件のデータ投入が必要。ただし一度実行すれば静的データとして維持できる。
- **Elasticsearch:** `user_id: "__shared__"` / `is_shared: true` フラグで同一インデックスに共存させ、クエリ時にフィルタリング。

### ADL-009: セッション管理とタイムアウト（LINE & Web GUI）

- **Decision:** 「1セッションにつき最終コーディネート画像は1つ」の原則を採用し、Firestore で状態を管理する。セッション完了後またはタイムアウト後の画像アップロードは「新規セッション」として扱う。
- **Rationale:** 
  - LINE自体にはセッションという概念がなく、状態はすべてバックエンド（Firestore）で管理する必要があるため、数時間後のアクセスでもFirestore上の状態が有効なら再開自体は可能とする。この確認として、専用のAgentを配置して、ユーザーに確認を促すメッセージを送る。
  - しかし、LINEという単一タイムラインのUIで複数セッションが並行したり、画像生成後に同じセッションで別の服を追加したりすると、エージェントのコンテキストやUXが複雑化する。
  - Web GUI側でもLINEの体験と統一感を持たせるため、MVPでは「新しい服の画像アップロード＝新しいコーディネートの開始（新規セッション）」と明確に区別する。
- **Implementation (LINEの仕様対応):** LINEからのWebhook要求に対する `replyToken` は発行後数分で無効になるため、エージェントの処理が長引き `replyToken` がタイムアウトした場合は、ユーザーの `userId` を使った **Push API** に切り替えてメッセージや画像を送信するフォールバックを実装する。

### ADL-012: シークレット管理に Secret Manager を採用

- **Decision:** 機密情報（LINE トークン、R2 アクセスキー、楽天 App ID、Elasticsearch API キー）は Google Cloud Secret Manager で管理し、Cloud Run デプロイ時に `--set-secrets` で環境変数としてマウントする。非機密の設定値は `--set-env-vars` で直接設定する。
- **Alternatives:** Cloud Run の環境変数に機密情報を直接設定する案。
- **Rationale:** 環境変数に機密情報を直接設定すると Cloud Run のコンソール・デプロイ設定・ログに平文で露出する。Secret Manager はバージョン管理・アクセス制御（IAM）・監査ログを提供する。アプリ側はすべて環境変数として読むため、コードは管理方法を意識しない。
- **Gemini / Firestore 認証:** API キーを発行せず、Cloud Run のサービスアカウントに IAM ロールを付与し ADC 経由で認証する。これにより管理すべきシークレットの数を削減する。
- **Trade-off:** Secret Manager のセットアップと IAM 付与の初期コストが発生するが、ハッカソン後の運用・公開を考慮すると機密情報の平文露出を避けることが優先される。

### ADL-013: Elasticsearch は Compute Engine e2-medium 単一ノードで Self-hosted

- **Decision:** Elasticsearch を Google Compute Engine の `e2-medium` VM（2 vCPU, 4GB RAM）に単一ノード構成でセルフホストする
- **Alternatives:**
  - A: Cloud Run サイドカー（状態永続化が複雑）
  - B: GCP Marketplace マネージドサービス（月額コスト）
  - C: Elastic Cloud SaaS（外部依存、ネットワークレイテンシ）
- **Rationale:** ハッカソン MVP のデータ量（shared_closet 2,000 件 + user closet 数十件）は e2-medium で十分。Basic ライセンスは無料。セットアップ時間 15-20 分。ハッカソン終了後に VM 削除で廃止できる。
- **Implementation:** `sudo apt-get install elasticsearch` でインストール、`systemctl enable elasticsearch` で自動起動。Cloud Run との通信は VPC Peering または Cloud NAT 経由でプライベートに接続。
- **Trade-off:** 脆弱性管理・バージョン管理は手動。ただし MVP 期間（1-2 日）ではハッカソン終了後に廃止されるため、長期保守の負担はない。
- **Early PoC required:** Compute Engine 上での Elasticsearch 起動、Cloud Run からのプライベート接続確認。

### ADL-014: R2 署名付き URL + CORS で Flutter Web からの直接アップロード

- **Decision:** FastAPI の `GetUploadUrlUseCase` が R2 SDK で 15 分 TTL の署名付き PUT URL を発行。Flutter Web はその URL に直接 PUT リクエストを送信。R2 バケットに CORS ルールを設定し、プリフライト（OPTIONS）と PUT 両方を許可。
- **Alternatives:**
  - A: FastAPI 経由でファイルアップロード（ネットワークトラフィック増加、FastAPI に I/O 負荷）
  - B: R2 STS AssumeRole（複雑、Cloudflare 側の設定が少ない）
- **Rationale:** 署名付き URL は AWS S3 標準パターン。Cloudflare R2 は S3 互換性を持つため実装が最小化される。Flutter から R2 への直接アップロードにより FastAPI の I/O 負荷を削減。
- **CORS 設定:** R2 バケットに `AllowedMethods: [PUT, OPTIONS]`、`AllowedOrigins: [Flutter Web ドメイン]` を設定。ブラウザからのプリフライトに対応。
- **Trade-off:** HTTPS 必須（署名付き URL は HTTP では無効）。CORS 設定はドメインごとに更新が必要。

### ADL-016: Cloud Run コンテナの最小インスタンス数設定

- **Decision:**
  - `adk-agent-service`: `--min-instances=1`（常時 1 インスタンス温かい状態）
  - `fastapi-service`: `--min-instances=0`（コールドスタート許容）
- **Alternatives:**
  - A: 両方 min-instances: 0（コスト最小化）
  - B: 両方 min-instances: 1（高 SLA、高コスト）
- **Rationale:** ADK の LLM 推論（Gemini API 呼び出し）はコールドスタートで 10-30 秒かかり、ユーザーの待ち時間に直結する。ハッカソンデモではレイテンシが重要。一方 FastAPI は HTTP リクエストの多くが軽量で 1 秒以内のコールドスタートで許容可能。`adk-agent-service` のみ温かく保つことで、コスト（月 ~$15）と体験のバランスを取る
- **Trade-off:** 常時 1 インスタンス起動による月額追加コスト vs. ユーザー体験（レイテンシ削減）。MVP では後者を優先。

### ADL-017: ローカル開発環境を Docker Compose + Makefile で標準化

- **Decision:** docker-compose.yml で Elasticsearch + Firestore Emulator を隔離。FastAPI・ADK はローカル Python 環境で起動。Makefile で `make dev`/`make test` コマンドを統一
- **Alternatives:**
  - A: Skaffold でマイクロサービスのローカル開発を完全自動化（学習コスト高）
  - B: 全てを docker-compose で管理（初回ビルドが重い、Hot Reload が複雑）
  - C: 各メンバーが手作業でセットアップ（再現性なし）
- **Rationale:** FastAPI・ADK の開発ループは頻繁に再起動・code reloading が必要。コンテナ内での開発は反復速度が低下。一方 Elasticsearch・Firestore Emulator は「状態を持つ外部依存」なので docker-compose で隔離することで、各メンバーが同じ状態で開発できる。Makefile で `make dev` を叩くだけで全体が起動する設計により、オンボーディングが迅速
- **Files to Create:**
  - `docker-compose.yml` — Elasticsearch 8.x + Firestore Emulator
  - `Makefile` — 開発コマンド
  - `.env.example` — テンプレート（ダミー値）
  - `README_LOCAL_DEV.md` — 詳細手順

### ADL-015: クローゼット一覧・削除・セッション作成の Use Case 判断

- **Decision:**
  - `GetClosetItemsUseCase` は定義しない。Flutter が Firebase SDK で `users/{uid}/closet` コレクションをリアルタイムリスナーで直接購読する
  - `DeleteClosetItemUseCase` を FastAPI `DELETE /closet/items/{item_id}` として定義する
  - `GetSharedClosetItemsUseCase` は Phase 1 スコープ外とする
  - `CreateSessionUseCase` を FastAPI `POST /sessions` として定義する。初期 `status` は `SOURCE_SELECTING`
- **Rationale:**
  - クローゼット一覧はロジックを持たない純粋な read。Firebase Security Rules で認証を担保しつつフロントエンドで直接取得することで FastAPI のホップを排除できる。また `ProcessUploadedClothingItemUseCase` による `status` 更新がリアルタイムで Flutter に反映され、アップロード処理中の UX が自然になる
  - 削除は Firestore・R2・Elasticsearch の 3 ストレージを整合的に削除する副作用があるため、バックエンド Use Case として定義する
  - `CreateSessionUseCase` は `AnalyzeClothingImageUseCase`（6.1）の Input である `sessionId` の前提となるセッションを作成する致命的欠落であった。Web GUI Phase 1a ではクローゼットに服が登録済みの状態でコーディネートを開始するため、初期状態を `SOURCE_SELECTING` とする
- **Trade-off:** Firestore への直接アクセスを Flutter に許可することで Firebase Security Rules の管理が必要になるが、そのトレードオフは Use Case を 1 つ削減できることで相殺される

### ADL-018: エージェント出力に A2UI を採用し、Flutter レンダリングは `genui` スパイク後に確定

- **Decision:** エージェント（ClosetAgent / StylingAgent）の**ユーザー向け結果 UI**（候補カード・好み入力フォーム・最終コーディネート画像）を、独自スキーマではなく **A2UI（Agent-to-UI）標準のペイロード**として出力する。ADK の `A2uiSchemaManager` で LLM に妥当な A2UI JSON を生成させる。クライアント側のレンダリングは Flutter 公式の `genui` パッケージを第一候補とするが、**採否は Flutter Web 上でのスパイク検証後に確定する**。
- **Alternatives:** 独自 `ui_payload` スキーマ + 自前 Flutter レンダラー（bespoke）。
- **Rationale:**
  - **拡張性:** 標準カタログ + 再利用可能なレンダラーにより、エージェント／コンポーネント種別が増えても描画コードを線形に書き足さずに済む。bespoke は多エージェント化で破綻する。
  - **既存設計との整合:** A2UI は transport-agnostic のため、ADL-011 の Firestore リレー（`sessions/{sessionId}/agentEvents`）にそのまま乗る。**A2A は不要。**
  - **クロスチャネル再利用:** 同一の A2UI 出力を Phase 1a の Flutter と Phase 1b の LINE Flex 等、複数レンダラーで再利用できる。
  - **タイミング:** M5（Accordion UI・候補カード）は未着手のため、いま採用するのが最も低コスト（後から bespoke を移行すると二重実装）。
- **検証事実（2026-06-08, Web/OSS 調査）:** A2UI は Google のオープン標準（Apache 2.0）。Flutter 公式レンダラー `genui`（旧 `flutter_genui`、発行元 verified `labs.flutter.dev`、A2UI v0.9 実装）が実在し Web 対応。「Flutter には埋め込みづらい」という当初懸念は否定された。
- **Trade-off / リスク:** `genui` は "highly experimental, API will change drastically"（pre-1.0）。Web は対応するが primary focus ではない。→ churn/成熟度リスクが本質的論点。
- **Early spike required:** `genui` を Flutter **Web** で静的 A2UI ペイロード1枚描画して採否判断。Web がガタつく場合は MVP は bespoke フォールバックとするが、**エージェント出力は A2UI のまま維持**しレンダラーを差し替え可能にする。
- **設計原則:** 「ユーザーが見る／操作する結果 UI」（A2UI）と、`tool_call` / `tool_result` の**思考トレース**（Accordion = 観測用、別ストリーム）を概念分離する。
- **影響:** ADL-011 はそのまま（ペイロード形式が A2UI になるだけ）。§11 と M5-10（Flutter Accordion / 結果 UI）の方針を改訂する（feature-matrix の同期は M4/M5 ExecPlan 着手時）。
- **Date/Author:** 2026-06-08 / Ran

### ADL-019: エージェント間連携は MVP で ADK ネイティブ委譲、A2A は将来の分割パス

- **Decision:** Phase 1 ではエージェント間連携を **ADK ネイティブの sub-agent delegation**（単一 `adk-agent-service` プロセス内）で実装する。**A2A（Agent2Agent）プロトコルは MVP では採用しない。**
- **Rationale:**
  - ADK は「エージェントの実装フレームワーク（プロセス内委譲）」、A2A は「サービス/ベンダーをまたぐエージェント間通信プロトコル」で、レイヤーが異なる（競合しない）。
  - 全エージェントが 1 プロセス内に存在する現構成では ADK 委譲で十分。A2A はネットワークホップ・シリアライズ・Agent Card インフラを足すだけで利点がない。
- **将来の適用条件:** ClosetAgent（検索系・IO 寄り・高速）と StylingAgent（画像生成・~13–30s・高コスト）を**別 Cloud Run サービスに分割**する場合（ADL-007 の延長）、または外部エージェントとの interop が必要になった場合に A2A を導入する。
- **A2A-ready の設計規律（今から守る）:** エージェント起動時にコンテキストを明示的に受け渡す（共有インメモリ状態を持たない）、サブエージェント単位でツールセットを分離する、状態の源泉は Firestore。これにより「サブエージェントを A2A サービスに切り出す」のが設定変更レベルで済む。
- **Date/Author:** 2026-06-08 / Ran

### ADL-020: Web GUI のエージェント実行トリガーは FastAPI → adk-agent-service の直接 HTTP（Cloud Tasks は LINE のみ）

- **Decision:** Web GUI（Phase 1a）のコーディネート実行は、ソース選択（`SelectClothingSourceUseCase`、§6.2）完了後に **FastAPI が `adk-agent-service` を直接 HTTP 呼び出し**（`POST /internal/run-session`、§5.1 `AgentRunInputPort`）して起動する。`adk-agent-service` は実行を非同期（バックグラウンド）で開始して即時 `202` を返し、進捗は `agentEvents` 経由で SSE 配信する（ADL-011）。**Cloud Tasks 経由の起動は LINE（Phase 1b）のみ**とする。
- **Alternatives:** A: Web も Cloud Tasks 経由で起動（LINE とフロー統一だがキュー遅延が増える）。
- **Rationale:** LINE の 5 秒 Webhook タイムアウト制約（ADL-006）は Web には存在しない。Web ではユーザーが Accordion UI を見ながら待つため、Cloud Tasks のキュー遅延をデモのクリティカルパスから外す方が体感が良い。
- **Trade-off:** 起動経路が Web（直接 HTTP）と LINE（Cloud Tasks）の 2 種類になるが、`adk-agent-service` 側のエージェント実行本体は共通で、各チャネルの制約に最適化される。
- **Date/Author:** 2026-06-08 / Ran

### ADL-021: セッション状態遷移と agentEvents の Firestore 書き込みは adk-agent-service が直接行う

- **Decision:** エージェント実行中のセッション状態遷移（`SEARCHING` / `PROPOSING` / `GENERATING` / `COMPLETED` / `ERROR`）と、`sessions/{sessionId}/agentEvents` への実行イベント書き込みは、**`adk-agent-service` が `FirestoreStyleSessionRepository` 経由で Firestore へ直接書き込む**。すなわち `adk-agent-service` は自前の Firestore 書き込み経路を持つ。
- **Rationale:** ADL-011 のリレー方式では ADK コンテナがイベントの発生源であり、FastAPI を経由せず直接 Firestore に書く方がホップが少なく、`on_snapshot` → SSE 配信（FastAPI）と責務が自然に分離する。状態遷移もエージェント実行の進行に同期するため、実行主体（ADK）が書くのが整合的。
- **agentEvents TTL:** `agentEvents` サブコレクションは Firestore TTL ポリシーで **24h** 後に自動削除する（§8.1 `ttlAt`）。
- **Trade-off:** `adk-agent-service` と `fastapi-service` の双方が `StyleSessionRepositoryPort` の書き込み権限を持つが、書き込み対象は明確に分かれる（FastAPI=セッション作成 §6.11、ADK=実行中の状態遷移・イベント）。
- **Date/Author:** 2026-06-08 / Ran

### ADL-022: `adk-agent-service` は Python ADK で実装する（TypeScript 骨組みを置換）

- **Decision:** `adk-agent-service` を **Python ADK（`google-adk`）** で実装する。M0 で先行配置されていた TypeScript の骨組み（`adk-agent-service/src/*.ts`、全メソッド `throw new Error("Implement in M4-x")`、ADK 依存なし）は M4 着手時に破棄・置換する。
- **Alternatives:** A: 既存の TS 骨組みを土台に TS ADK で実装する。
- **Rationale:**
  - §2 技術スタックは「AI Agent = Google ADK」かつバックエンドを Python/FastAPI と規定しており、Python 前提。
  - M1-4 の ADK イベント PoC（`poc/adk_event_stream/run_poc.py`）は **Python ADK の `runner.run_async()`** でイベント形式・粒度を確定済み。TS では再検証が必要になる。
  - ADL-021 は `adk-agent-service` が `fastapi-service` と**同一の `FirestoreStyleSessionRepository`**（Python）でセッション状態・`agentEvents` を書き込むことを要求する。
  - M4 のツールが再利用する実装（Gemini 構造化分析・Embedding＝`fastapi-service/app/adapters/gemini_analysis.py`、Elasticsearch `clothing_items` スキーマ＝`elasticsearch_embedding_repo.py`、Nano Banana 画像生成 PoC＝`poc/image_generation/run_poc.py`）はすべて Python で既存。TS にすると同等処理の再実装か HTTP 越し呼び出しが必要になり、利点がない。
- **Container 整合:** 2 コンテナ分離（ADL-007）と Cloud Run 設定（§9.1、min-instances=1 ほか ADL-016）は不変。言語を Python に統一するのみ。`docker-compose.yml` の `adk-agent-service` は Python ベース（`adk api_server`）に置き換える。
- **Trade-off:** M0 の TS 骨組みを捨てる（git 履歴に残る）。ただし骨組みは実装ゼロのため損失は最小。
- **影響:** `architecture-overview.md` §8 の乖離メモ #1（TS/Python 未確定）は本 ADL で解消。M4 ExecPlan（`docs/plans/20260609-m4-adk-agents-core.md`）がこの決定に基づき実装する。
- **Date/Author:** 2026-06-09 / Ran（M4 ExecPlan 起票時に提案）

### ADL-023: Cloud Run → Compute Engine Elasticsearch のプライベート接続は Serverless VPC Access Connector

- **Decision:** Cloud Run（`fastapi-service` / `adk-agent-service`）から Compute Engine の Elasticsearch VM への接続は **Serverless VPC Access connector**（`--vpc-egress=private-ranges-only`）経由で行う。ES VM は外部 IP を持たず（`--no-address`）、ファイアウォールで `tcp:9200` を connector の `/28` レンジからのみ許可する。
- **Alternatives:** ADL-013 が挙げた VPC Peering / Cloud NAT。Cloud NAT は egress のみで Cloud Run → 私設 VM の ingress 経路にはならず、Peering は単一 VPC では過剰。
- **Rationale:** 単一 VPC・単一 VM 構成では connector が最小構成で、ES を公開せずに Cloud Run から到達できる。ハッカソン終了後は connector ごと削除して廃止できる（ADL-013 の使い捨て方針と整合）。
- **Trade-off:** connector のわずかな月額コストと `/28` レンジ枯渇に注意。ES URL には VM 名でなく内部 IP を使う。
- **影響:** feature-matrix `M1-3` の "Cloud Run プライベート接続" を本決定で具体化。MD デプロイ ExecPlan（`docs/plans/20260615-md-phase1a-production-deployment.md`、MD-3/MD-4）が実装する。
- **Date/Author:** 2026-06-15 / Ran（デプロイ ExecPlan 起票時に提案）

### ADL-024: 本番の `/internal/*` ワーカールート保護は OIDC + 共有シークレット（`fastapi-service` の ingress=internal は不採用）

- **Decision:** 本番では service-to-service 呼び出しを **Cloud Run OIDC ID トークン**で認証する。`adk-agent-service` は `--no-allow-unauthenticated` で公開せず、`fastapi-sa` のみ `roles/run.invoker` を持つ。`fastapi-service` はブラウザ向けに公開のまま（ingress=all）とし、`/internal/tasks/process-upload` ワーカールートは **OIDC ベアラ検証 + 既存の `X-Internal-Secret`（Secret Manager 値）**の二重で保護する。共有シークレットは defense-in-depth として残す。
- **Rationale:** feature-matrix `M2-5` の旧注記「`fastapi-service` ingress=internal」は成立しない — 同サービスが SPA 向けの公開 `/closet/*`・`/sessions/*` も配信するため。公開を保ったままワーカールートのみを暗号学的に保護する手段が OIDC 検証。
- **Implementation note:** `process-upload` の Cloud Task は **`fastapi-service` 自身の URL** を OIDC audience とする（ワーカールートが `fastapi-service` 実装にあるため。`adk-agent-service` ではない — `cloud_tasks_adapter.py` の旧 `# TODO(deploy)` が audience を ADK と書いていた点を訂正）。`ADK_INTERNAL_BASE_URL`（run-session 用）と `FASTAPI_INTERNAL_BASE_URL`（process-upload 用）を分離する。
- **Trade-off:** ワーカールートを別の internal-only Cloud Run サービスへ分離すればより厳格だが、MVP では公開サービス内 OIDC 検証で十分。
- **Date/Author:** 2026-06-15 / Ran（デプロイ ExecPlan 起票時に提案）

### ADL-025: Flutter Web のホスティングは Firebase Hosting

- **Decision:** Phase 1a の Flutter Web クライアントは **Firebase Hosting**（`<project>.web.app`）でホストする。Firebase 設定値はビルド時に `--dart-define` で注入し（`flutter-web-app/lib/config.dart` が全値を `--dart-define` から読む）、`USE_EMULATORS=false` でビルドする。
- **Alternatives:** Vercel（req §8.4 の CORS 例に `your-flutter-web-domain.vercel.app` が登場するのみで、ホスティング先は未確定だった）。
- **Rationale:** アプリは既に Firebase Auth + Firestore に依存しており、Firebase Hosting は安定した HTTPS オリジンと自動的な authorized domain を提供する。生成物 `firebase_options.dart` は意図的に git-ignore 済みで、本番値は `--dart-define` で渡す方針と整合。
- **Trade-off:** R2 CORS と Firebase Auth authorized domains にホスティングオリジンを追加する運用が必要。
- **Date/Author:** 2026-06-15 / Ran（デプロイ ExecPlan 起票時に提案）

### ADL-026: 性別・年代ディメンションの導入（共有はヒューリスティック付与、個人はギャラリー編集可）

- **Decision:** `UserPreference` に `gender`（`male` / `female` / `common`）を追加し、検索・スタイリング・画像生成へ性別と `closetKind`（adult / child）を伝播する。共有クローゼットの `gender` は Kaggle データセットに無いため `run_seed.py` のカテゴリ別ヒューリスティックでシード時に付与する。個人クローゼットは分析時にヒューリスティックで自動付与し、ユーザーはギャラリーで編集できる（ADL-028）。
- **Alternatives:** (a) シード時の Gemini 画像再分析で性別推定（精度↑・トークンコスト・実装増）、(b) 全アイテム unisex 固定でユーザー選択のみで駆動（誤ラベルゼロだが検索の絞り込みが弱い）。
- **Rationale:** ヒューリスティックは追加 API コストゼロ・決定的で冪等。誤りはユーザーがギャラリーで補正でき（個人クローゼットのみ）、共有は読み取り専用のため全体最適。`child-01` が大人画像を生成する既存欠陥（feature-matrix ME-3）の是正に必須。
- **Trade-off:** ヒューリスティックは粗く、共有アイテムの性別は近似。ユーザー編集は自分のクローゼットのみ（共有はグローバル読み取り専用）。
- **Date/Author:** 2026-06-21 / Ran（ME プレデプロイ監査）

### ADL-027: Web GUI の候補選択は `PROPOSING` の明示的一時停止（同意なき自動生成禁止の実装）

- **Decision:** 検索完了後セッションを `PROPOSING` で一時停止し、候補承認エンドポイント（例: `POST /sessions/{id}/select`）で `selectedItems` を確定してから `GENERATING` に遷移する。空選択での生成は禁止。
- **Alternatives:** 現状の自動生成（`StylingAgent` が `style_synthesizer` を即時呼び出し）。req §3 / §15 Phase 1a #6 違反のため不採用。
- **Rationale:** req §3「同意なき自動生成禁止」と §15 Phase 1a #6「候補提示 → 選択 → 画像生成」を満たす。候補データは `search_closet` の結果に既に含まれる。
- **Trade-off:** マルチターンの一時停止/再開を SSE と状態機械で扱う必要がある（タイムアウトは ADL-009 に従う）。
- **Date/Author:** 2026-06-21 / Ran（ME プレデプロイ監査）

### ADL-028: クローゼットメタデータはユーザー編集可能（個人クローゼットのみ）、共有は読み取り専用

- **Decision:** 個人クローゼットアイテムの `gender` ほか検索用メタデータをギャラリーで編集可能にし、Firestore と Elasticsearch をミラー更新する。共有クローゼットは読み取り専用（§16.5）。
- **Alternatives:** 分析結果を固定（編集不可）。ヒューリスティック付与（ADL-026）の誤りを補正できないため不採用。
- **Rationale:** キーワード検索の精度をユーザーが改善でき、自動付与を補完する。
- **Trade-off:** メタデータ編集 API と Firestore / ES の整合（ベストエフォート同期、M2 の削除パスと同様）。
- **Date/Author:** 2026-06-21 / Ran（ME プレデプロイ監査）

### ADL-029: Agent 実行履歴は時系列ギャラリー、天気・重複回避は将来拡張

- **Decision:** 完了セッション（選択アイテム ＋ 生成画像 ＋ 日時）を一覧する API（`FirestoreStyleSessionRepository` に list を追加）と時系列ギャラリーを提供する。天気シグナルと直近着用の重複回避は設計に残すが Phase 1a の必須範囲外。
- **Alternatives:** 履歴を持たない（現状）。ユーザーが過去のコーデを確認できないため UX 不足。
- **Rationale:** セッションは既に Firestore に永続化済み。一覧と履歴 UI の追加で実現でき、将来の重複回避の土台になる。
- **Trade-off:** 履歴の保持方針が必要（`agentEvents` の 24h TTL とは別に、履歴は結果のみ長期保持する設計）。
- **Date/Author:** 2026-06-21 / Ran（ME プレデプロイ監査）

### ADL-030: CI/CD は GitHub Actions + Workload Identity Federation（キーレス OIDC）

- **Decision:** Phase 1a の CI/CD は **GitHub Actions** で実装し、GCP への認証は **Workload Identity Federation（WIF）** による短命 OIDC トークンで行う（SA の JSON 鍵をリポジトリ／GitHub Secrets に保存しない）。Workload Identity Pool / Provider を作成し、デプロイ用 SA（例: `github-deployer`）に必要ロール（`roles/run.admin`、`roles/artifactregistry.writer`、`roles/iam.serviceAccountUser`、`roles/firebasehosting.admin` 等）を付与して、リポジトリ／ブランチを属性条件で限定してバインドする。
- **Alternatives:** (a) Cloud Build トリガー（GCP ネイティブだがパイプライン定義がリポジトリ外で可視性が低い）、(b) SA JSON 鍵を GitHub Secrets に保存（鍵の漏洩・ローテーション運用のリスク）。
- **Rationale:** GitHub Actions はパイプラインをリポジトリ内 YAML として可視化でき（PR の green check）、ポータブル。WIF は長命鍵を排除し、MD の OIDC + Secret Manager 方針（ADL-012 / ADL-024）と整合する。
- **Trade-off:** WIF の初期セットアップ（Pool / Provider / SA バインド）が必要。リポジトリ／ブランチを限定する属性条件を正しく設定しないと過剰権限になる。
- **Date/Author:** 2026-06-26 / Ran（CI/CD 計画起票時に提案）

### ADL-031: CI ゲートはサービス別の並列ジョブ（PR + main push でテスト/解析/ビルド検証）

- **Decision:** PR と `main` への push をトリガーに、サービス別の並列ジョブを実行する: `fastapi-service`（`pytest`、基準 68）、`adk-agent-service`（`pytest`、基準 41）、`flutter-web-app`（`flutter analyze` + `flutter test`、基準 14）、および両イメージの Docker ビルド検証。全ジョブ green を merge ゲートとする。Firestore Emulator / Elasticsearch を要する統合テストは GitHub Actions の service container で用意するか、不可分なものは単体に絞る（CI/CD ExecPlan 着手時に確定）。
- **Alternatives:** (a) 単一直列ジョブ（遅く、失敗の切り分けが弱い）、(b) テストゲート無し（現状、品質が保証されない）。
- **Rationale:** 既存テスト資産（fastapi 68 / adk 41 / flutter 14）をそのままゲート化でき、並列で高速。
- **Trade-off:** CI 上での統合テスト環境（Emulator / ES）の用意が必要。`make test` は docker-compose 前提のため CI 用に分離する。
- **Date/Author:** 2026-06-26 / Ran（CI/CD 計画起票時に提案）

### ADL-032: CD は main マージで Artifact Registry → Cloud Run / Firebase Hosting に自動デプロイ、失敗時はリビジョンロールバック

- **Decision:** `main` マージで、両イメージを **Artifact Registry** にビルド/プッシュ → 両 **Cloud Run** サービスをデプロイ → **Flutter Web** をビルドし **Firebase Hosting** にデプロイ → **デプロイ後スモーク**（`GET /health` ＋ deployed URL に対する認証付き coordination smoke）を実行する。スモーク失敗時は Cloud Run のトラフィックを直前のリビジョンへ戻す（`gcloud run services update-traffic --to-revisions=<prev>=100`）。デプロイ処理は MD が定義する `scripts/deploy/deploy_fastapi.sh` / `deploy_adk.sh` をワークフローから呼ぶ薄いラッパとし、アプリの振る舞いは変えない。秘密は Secret Manager（`--set-secrets`）経由でのみ注入し、ワークフローログに出さない。
- **Alternatives:** (a) 手動デプロイのみ（MD 現状）、(b) 本番反映前に手動承認ゲートを置く（より安全だがデモ速度が落ちる。単一の使い捨て環境では過剰）。
- **Rationale:** 「デプロイ後の CI/CD」を満たす。MD がコマンドを既に確定しているため、CD はその自動化に集約できる。
- **Trade-off:** ステージング環境は持たない（単一環境）。品質の最後の砦はデプロイ後スモークであり、本番へ自動反映するぶん CI ゲートの厳格さが重要。
- **Date/Author:** 2026-06-26 / Ran（CI/CD 計画起票時に提案）

---

## 14. Out of Scope (Phase 1)

- **LINE 統合（Phase 1a では対象外）:** Web GUI Accordion UI が完成するまで LINE 実装は開始しない
- 背景削除（Background Removal）: MVP では不要
- 明示的フィードバック以外のユーザー評価・スコアリング機能
- 管理者ダッシュボード
- ベクトル検索の Ranking スコアを使った推薦最適化（Phase 2 想定）
- OMO（Online Merges Offline）機能
- BtoB 機能

---

## 15. 実装フェーズ（優先順位）

### Phase 1a — Web GUI エージェントオーケストレーション（最優先）

| # | タスク | 完了条件 |
|---|---|---|
| 1 | ADK Agent（StylingOrchestratorAgent + ClosetAgent + StylingAgent）の基本実装 | ローカルで ADK Web UI 上で動作確認 |
| 2 | ADK Event Stream を SSE で FastAPI から配信するエンドポイント実装 | `GET /sessions/{id}/stream` が ADK イベントを SSE で返す |
| 3 | Flutter Accordion UI — SSE を受信してリアルタイム表示 | エージェントの思考ステップが折りたたみ可能な UI でリアルタイム表示される |
| 4 | Firebase Auth によるログイン（Google Sign-In のみ） | 未認証ユーザーはアクセス不可 |
| 5 | クローゼット画像アップロード（Web GUI 経由、R2 保存） | 画像が R2 に保存され Firestore にメタデータが記録される |
| 6 | コーディネート提案フロー End-to-End（Web GUI） | 画像アップロード → エージェント思考表示 → 候補提示 → 選択 → 画像生成。**注（2026-06-21）:** 「選択」は必須の明示的承認ステップであり、`PROPOSING` 状態で一時停止してユーザーが候補を選ぶまで生成しない（§18.2 / ADL-027）。思考トレース（Accordion）と候補カード（結果UI）は別表示とする（§18.4 / ADL-018）。生成画像は着用者の性別・年代に一致させる（§18.1 / ADL-026） |
| 7 | 共有デモクローゼットのシーディング（`scripts/seed_shared_closet/run_seed.py`） | `shared_closet` がシードされ、`SHARED_CLOSET` ソースで検索・コーディネート提案が動作する。**注（2026-06-24）:** M3 re-scope（ADL-010 / feature-matrix M3-2）により「1つの巨大クローゼット 2,000+件」は **現実的規模の3デモクローゼット（各70着＝計210着）に置換済み**。本項の "2,000件以上" は旧基準。**完了条件は件数ではなく「`--with-embeddings` で 768 次元ベクトルが投入され、本番 ES でハイブリッド/kNN 検索が動作すること」**（MD-10 で実施） |

### Phase 1b — LINE チャネル統合（Phase 1a 完了後）

| # | タスク | 完了条件 |
|---|---|---|
| 1 | LINE Webhook エンドポイント実装（即時 200 返却） | LINE からの署名検証が通り 200 を即時返却する |
| 2 | Cloud Tasks 経由での非同期 Agent 実行 | Webhook 受信 → Cloud Tasks 投入 → Agent 非同期実行のフローが動作 |
| 3 | LINE Reply / Push API でのコーディネート返信 | Agent 完了後に LINE トーク画面にコーディネート画像が届く |
| 4 | 楽天 API 検索ツール実装（Cloud Tasks レート制限） | 1 秒 1 リクエスト制限の遵守を Cloud Tasks で保証 |

---

## 16. Shared Demo Closet（全ユーザー共通クローゼット）

### 16.1 概要

全ユーザーが即座にアプリを体験できるよう、パブリックドメインのデータセットを使ったデモ用クローゼットを提供する。ユーザーは自分の服をアップロードしなくても、`SHARED_CLOSET` を選択することでコーディネート提案を試すことができる。

1つの巨大な共有クローゼットではなく、**現実的な規模（各70着）のデモ用クローゼットを複数用意する**。年代は `kids` フラグで **Adult / Child** に区分し、**Adult×2 + Child×1 の計3クローゼット**を作成する（`adult-01` / `adult-02` / `child-01`）。**性別（`male` / `female` / `common`）はデータセットに無いため、シード時にカテゴリ別ヒューリスティックで `gender` を付与する（§18.1 / ADL-026）。ユーザーは自分のクローゼットのアイテムについてはギャラリーで性別・メタデータをキーワード検索向けに編集できる（共有は読み取り専用、§18.3 / ADL-028）。**各アイテムは `user_id: "__shared__"` を維持しつつ `closetId` / `closetKind` を持ち、M5 のクローゼット選択 UI が `closetId` で絞り込む。M3-3 `SharedClosetSearchAdapter` は全 `__shared__` アイテムを返す現行実装のままで影響を受けない（クローゼット選択は M5 で追加）。

### 16.2 データソース

| 項目 | 内容 |
|---|---|
| **データセット** | [Clothing Dataset Full (Kaggle)](https://www.kaggle.com/datasets/agrigorev/clothing-dataset-full) |
| **ライセンス** | CC BY-SA 4.0（商用利用可、帰属表示・同一条件配布が必要） |
| **使用する画像** | `images_original/`（原寸・高画質）を使用。`images_compressed/`（低解像度）は不使用。採用枚数が少数のため圧縮版は不要で、デモ表示は高画質を優先する |
| **採用カテゴリ** | コーデで見た目の差が出る衣服のみ採用。**下着・インナー系（`Undershirt`, `Body`）と低品質ラベル（`Other` / `Others` / `Not sure` / `Skip` / 空）は除外**。`Hat` / `Shoes` などの小物は採用（採用例: Blazer, Blouse, Dress, Hoodie, Longsleeve, Outwear, Pants, Polo, Shirt, Shorts, Skirt, T-Shirt, Top ＋ Hat / Shoes） |
| **クローゼット構成** | Adult×2 + Child×1 の計3クローゼット。既存50着のカテゴリ配分を先に確定し、その後にトップス10 / ボトムス10を追加して各70着とする。最終配分はAdultがトップス22 / アウター7 / ボトムス20 / ワンピ・スカート8 / 靴8 / 帽子5、Childがトップス25 / アウター6 / ボトムス22 / ワンピ・スカート4 / 靴8 / 帽子5。同区分のクローゼット同士はアイテム重複なし（決定的サンプリングで冪等） |
| **採用枚数** | 3クローゼット × 各70着 ＝ **合計210着**。既存150着を保持し、トップス/ボトムスのみ60着追加 |
| **品質フィルタ** | データセット同梱の `images.csv`（列 `image` / `label` ほか）のラベルを採用（旧仕様で想定した `image_labels_merged.csv` は実在せず、実体は `images.csv`） |

### 16.3 帰属表示（Attribution）要件

CC BY-SA 4.0 に基づき、以下を実装する：

- Web GUI のフッターまたは「共有クローゼットについて」モーダルに以下を表示：
  > 共有クローゼットの画像は [Clothing Dataset (CC BY-SA 4.0)](https://www.kaggle.com/datasets/agrigorev/clothing-dataset-full) を使用しています。
- `CandidateItem.attribution` フィールドに `"Clothing Dataset (CC BY-SA 4.0)"` を設定する。

### 16.4 シーディングスクリプト要件

| 項目 | 仕様 |
|---|---|
| **配置場所** | `gen-fashion/scripts/seed_shared_closet/`（アプリリポジトリ内で管理。チームが同条件で再現できるよう、データ準備スクリプトもバージョン管理する方針） |
| **スクリプト** | `run_seed.py`（単一ファイル、`python run_seed.py` で即起動） |
| **処理フロー** | Kaggle API でダウンロード → カテゴリ別サンプリング → R2 アップロード → Gemini で Embedding 生成 → Elasticsearch インデクシング → Firestore への `shared_closet` ドキュメント書き込み |
| **冪等性** | 再実行しても重複しない（`item_id` を元画像ファイル名のハッシュから生成） |
| **依存関係** | `pip install -r requirements.txt`、Kaggle API トークン（`~/.kaggle/kaggle.json`）、`GOOGLE_CLOUD_PROJECT` 環境変数 |
| **クローゼット生成** | `_CLOSETS`（adult-01 / adult-02 / child-01）と区分別 `_CLOSET_QUOTAS` で既存50着を先に構成し、全クローゼット確定後に `_CLOSET_ADDITIONS`（tops 10 / bottoms 10）を追加する。`kids` フラグで adult/child プールに分割し、同区分は重複なく決定的に抽出。アイテムに `closetId` / `closetKind` を付与し、`shared_closets/{closetId}` にメタデータ（kind / displayName / itemCount）を書き込む |
| **カテゴリ除外** | §16.2「採用カテゴリ」のとおり、下着・インナー系（`Undershirt`, `Body`）と低品質ラベル（`Other` 等）をスクリプトの除外リストで弾く |
| **使用ディレクトリ** | 展開後の `images_original/` を読み込む。`images_compressed/` は使用しない |

### 16.5 ドメインルール

- `shared_closet` への書き込みはシーディングスクリプトのみ（一般ユーザーは読み取り専用）。共有アイテムの `gender` はシード時のヒューリスティック値で全ユーザー共通・読み取り専用。ユーザーによる性別・メタデータ編集（§18.3 / ADL-028）は**自分のクローゼット**アイテムにのみ適用する。
- `shared_closet` アイテムは `MAX_CLOSET_IMAGES_PER_USER` の制限対象外。
- ユーザーが自分のクローゼットを持っていない場合でも `SHARED_CLOSET` は常に選択可能とし、初回ユーザーの体験を保証する。
- Phase 1a のコーディネート提案フローでは、ソース選択肢として `SHARED_CLOSET` / `CLOSET`（クローゼットデータがある場合のみ）/ `RAKUTEN` の順に提示する。

---

## 17. Open Questions / PoC Items

| 項目 | 優先度 | 内容 |
|---|---|---|
| コーディネート画像生成 | HIGH | Imagen 4 / Gemini 2.0 Flash で服画像を入力した際のコーディネート画像生成が実現可能か PoC |
| Elasticsearch Compute Engine セットアップ | MEDIUM | Compute Engine e2-medium VM への Elasticsearch インストール・起動・Cloud Run プライベート接続の動作検証（セットアップ時間目安: 20 分） |
| LINE Reply Token 有効期限 | MEDIUM（Phase 1b） | Cloud Tasks の遅延が 1 分を超えた場合の Push API へのフォールバック設計 |
| 共有クローゼットの性別付与 | 解決済み（2026-06-21） | データセットに性別が無いため**カテゴリ別ヒューリスティック**でシード付与。ユーザーは自分のクローゼットでギャラリー編集可（§18.1 / ADL-026 / ADL-028） |
| 実行履歴の天気・重複回避 | LOW（将来拡張） | 天気シグナル取り込みと直近着用との重複回避。Phase 1a 必須範囲外（§18.5 / ADL-029） |
| CI の統合テスト環境 | MEDIUM | GitHub Actions 上で Firestore Emulator / Elasticsearch を service container で用意するか、統合テストを単体に絞るか（§19.2 / ADL-031、CI/CD ExecPlan 着手時に確定） |

---

## 18. Pre-Deployment Experience & Domain Hardening (ME)

> MD（本番デプロイ）着手前に解消する 6 つのユーザー向け / ドメインギャップ。feature-matrix の **ME-1…ME-7** に対応。**ME-3（子供クローゼット → 大人画像の欠陥）と ME-6（必須の候補選択ステップ欠落）は要件違反であり、本番カットオーバーのゲート条件**。本節は §3〜§16 のベース仕様への差分を定義する（実装は MD 完了後に起票する別 ExecPlan）。

### 18.1 性別・年代ディメンション（ME-2 / ME-3 / ME-4）

- **モデル:** `UserPreference` に `gender`（`male` / `female` / `common`）を追加（§4.2）。年代は対象クローゼットの `closetKind`（adult / child）で表す。
- **データ:** `clothing_items`（ES, §8.2）と `users/{userId}/closet/{itemId}` / `shared_closet/{itemId}`（Firestore, §8.1）に `gender` を追加。
- **共有クローゼットの付与:** データセットに性別が無いため、`run_seed.py` がカテゴリ別ヒューリスティック（例: Dress / Skirt / Blouse → `female` 寄り、その他多数 → `common`）で `gender` を付与する（ADL-026）。
- **個人クローゼットの付与と編集:** アップロード分析時にヒューリスティックで `gender` を自動付与し、ユーザーはクローゼットギャラリーで自分のアイテムの `gender` ほかキーワード検索用メタデータを編集できる（§18.3 / ADL-028）。
- **伝播:** `SearchCandidateItemsUseCase`（§6.3）/ `search_closet` は `gender` と `closetKind` でフィルタ/バイアスし、`GenerateCoordinateUseCase`（§6.5）/ `style_synthesizer` は両者を画像生成プロンプトに渡す。**`child-01` 選択時は子供のコーディネート画像を生成する。**
- **受け入れ:** `child-01` を選択して生成した画像が子供であること。male / female / common の選択が検索結果と生成画像に反映されること。

### 18.2 必須の候補選択ステップ（ME-6、要件違反の是正）

- **不変条件:** §4.3「同意なき自動生成禁止」/ §15 Phase 1a #6「候補提示 → 選択 → 画像生成」を満たす。
- **状態:** 検索完了後、セッションは `PROPOSING` で**一時停止**し、ユーザーが候補を選択・承認するまで `GENERATING` に遷移しない（ADL-027）。現状は `StylingAgent` が `style_synthesizer` を自動呼び出ししており違反。
- **API:** 候補承認用エンドポイント（例: `POST /sessions/{id}/select`）を追加し、`sessions.selectedItems` を確定する。空のまま生成に進んではならない。
- **UI:** 検索/抽出された候補（`search_closet` の結果に既に含まれる）を**候補カード**（上位数件 ＋ 最上位の推薦）として表示し、ユーザーが選択する（§18.4 / ADL-018）。
- **受け入れ:** ユーザーが選択するまで画像生成が開始されないこと。

### 18.3 クローゼットギャラリー＋編集可能メタデータ（ME-1）

- **自分のクローゼット:** 既存グリッド（`closet_screen.dart`）にメタデータ（category / colors / season / tags / gender）を表示し、**ユーザーがキーワード検索向けに編集できる**（編集は Firestore と ES をミラー、ADL-028）。
- **共有クローゼット:** `adult-01` / `adult-02` / `child-01` の中身を**ギャラリーで閲覧**できるようにする（現状は ID のドロップダウンのみ）。`shared_closet` アイテムを `closetId` で列挙する読み取り専用エンドポイントを追加。共有アイテムは読み取り専用（§16.5）。
- **受け入れ:** 各クローゼット（共有含む）の中身がメタデータ付きで閲覧でき、自分のアイテムは編集が検索に反映されること。

### 18.4 Agent Trace の整理＋結果UIの分離（ME-5、ADL-018）

- **思考トレース（Accordion）:** 低価値イベント（`transfer_to_agent` や生の args / result ダンプ）を最上位タイルとして出さない。エージェントターン単位でまとめ、要約を表示する。`events.py`（出力内容）と `AgentEventTile`（`coordination_screen.dart`）を調整。
- **結果UI:** 候補カード・好み入力・最終画像は思考トレースと**別ストリーム / 別表示**として扱う（ADL-018、§18.2 の候補選択と統合）。
- **受け入れ:** Accordion が読みやすい思考トレースになり、候補・結果は結果UIへ分離されること。

### 18.5 Agent 実行履歴（ME-7、将来拡張）

- **永続化と一覧:** 完了したセッション（選択アイテム ＋ 生成画像 ＋ 日時）を一覧する API（`FirestoreStyleSessionRepository` に list を追加）と**時系列の履歴ギャラリー**を提供する。
- **将来拡張:** 天気シグナルの取り込みと、直近数日〜数週間に着用した服との**重複回避**（"なるべく" 重複しない提案）。本項の天気・重複回避は **Phase 1a の必須範囲外**（ME の中でも将来拡張、ADL-029）。
- **受け入れ:** 過去の実行が時系列ギャラリーで再確認できること。

---

## 19. Continuous Delivery / CI-CD (MF)

> MD（手動 `gcloud` デプロイ）の上に構築する自動化レイヤ。feature-matrix の **MF-1…MF-6** に対応。MD（手動 `gcloud` デプロイ）の**上に**構築する自動化であり、アプリの振る舞いは変えない。プラットフォームは **GitHub Actions + Workload Identity Federation**（ADL-030 / ADL-031 / ADL-032）。**MD 依存**であり、**MD 完了後に起票する別 ExecPlan で実装する**（「one ExecPlan at a time」: 本節は req レベルの追跡のみで、ExecPlan は未起票）。本節着手時点の現状として、リポジトリには CI/CD 資産が一切無い（`.github/` / Cloud Build トリガー / `cloudbuild.yaml` / `scripts/deploy/` のいずれも未作成）。

### 19.1 認証基盤（Workload Identity Federation、MF-1）

- **構成:** Workload Identity Pool / Provider を作成し、GitHub Actions の OIDC トークンを GCP のデプロイ用 SA（`github-deployer`）にフェデレートする。SA の JSON 鍵は使わない（ADL-030）。
- **権限:** リポジトリ＋ブランチ（`main` 等）を属性条件で限定。`github-deployer` に `roles/run.admin`、`roles/artifactregistry.writer`、`roles/iam.serviceAccountUser`（Cloud Run のランタイム SA を `actAs`）、`roles/firebasehosting.admin` を付与。
- **受け入れ:** GitHub Actions のジョブが鍵なしで `gcloud` / `firebase` を認証実行できること。

### 19.2 CI ゲート（MF-2）

- **トリガー:** PR と `main` への push。
- **並列ジョブ:** fastapi `pytest`（基準 68）、adk `pytest`（基準 41）、flutter `analyze` + `test`（基準 14）、両 `Dockerfile` のビルド検証。
- **統合テスト:** Firestore Emulator / Elasticsearch を要するものは GitHub Actions の service container で用意するか、不可分でないものは単体に絞る（ADL-031、§17 Open Questions）。全 green を merge ゲートとする。
- **受け入れ:** テストが落ちる PR が merge ブロックされること。

### 19.3 CD パイプライン（MF-3 / MF-4）

- **MF-3（バックエンド）:** `main` マージで両イメージを Artifact Registry にビルド/プッシュ → Cloud Run ×2 をデプロイ（MD の `scripts/deploy/deploy_*.sh` を呼ぶ薄いラッパ）。非機密は `--set-env-vars`、機密は `--set-secrets`（ADL-032 / ADL-012）。
- **MF-4（フロントエンド）:** `flutter build web --release`（本番 `--dart-define`）→ `firebase deploy --only hosting`。Authorized domains / R2 CORS は MD-9 / MD-12 の設定を流用。
- **受け入れ:** `main` マージのみで両 Cloud Run サービスと Firebase Hosting が更新されること。

### 19.4 デプロイ後スモーク & ロールバック（MF-5）

- **スモーク:** デプロイ後に `GET /health` と、deployed URL に対する認証付き coordination smoke（`scripts/m5_coordination_smoke.py` の deployed 版）を実行し `COMPLETED` を確認する。
- **ロールバック:** スモーク失敗時は Cloud Run のトラフィックを直前の正常リビジョンへ戻す（`gcloud run services update-traffic --to-revisions=<prev>=100`）。
- **受け入れ:** スモーク失敗時に本番が直前の正常リビジョンへ自動的に戻ること。

### 19.5 ランブック & 同期（MF-6）

- **文書化:** パイプラインのランブック（トリガー、必要権限、ロールバック手順、秘密の扱い）を記載する。
- **同期:** CI/CD ExecPlan の着手・完了時に feature-matrix（MF-*）と ExecPlan を同期する（本リポジトリの sync ルール）。
- **受け入れ:** 新規参加者がランブックだけで CI/CD を運用できること。
