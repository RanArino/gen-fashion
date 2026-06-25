# Phase 1a ローカル実機検証チェックリスト（デプロイ前ゲート）

このドキュメントは ExecPlan ではなく、`docs/plans/20260615-md-phase1a-production-deployment.md`
の **"Local pre-deploy gate"** をあなた自身の手で実際に走らせて確認するための作業タスクリストです。

デプロイ ExecPlan は M0–M5 を「verified locally」と記述していますが、**あなた自身はまだローカルで
通しテストをしていない**ため、本番デプロイに進む前に `make dev` スタックで全フローが実際に動くことを
確認します。

## 進め方（このループを各タスクで回す）

1. **あなた**: 該当タスクのコマンドを実行する。
2. **あなた**: 「貼るもの」に書かれた出力・ログをそのまま私に貼る（成功でも失敗でも）。
3. **私**: ログを解析し、期待結果と照合する。バグがあればその場で原因を特定し、最小修正を入れる。
4. 修正後はそのタスクを再実行し、green になってから次へ進む。

> 失敗したログこそ価値があります。エラーは要約せず、ターミナル出力をそのまま貼ってください。
> どのタスク番号か（例: 「T3-2 失敗」）を一言添えてください。

各タスクは前のタスクが green であることを前提に並んでいます（依存順）。途中で詰まったら止めて構いません。

---

## フェーズ 0 — 前提とスタック起動

- [x] **T0-1 認証情報の確認**
  - 実行: `ls -la credentials/ && grep -v '^#' .env | grep -v '^$'`
  - 確認: `credentials/` に Vertex AI 用 SA JSON があり、`.env` の
    `GOOGLE_APPLICATION_CREDENTIALS_HOST` がそのファイルを指しているか。
    （現状 `.env` は `GOOGLE_GENAI_USE_VERTEXAI` 系が設定済み。`credentials/gen-fashion-sa.json`
    が存在する一方 `.env.example` の既定は `./credentials/___-sa.json` プレースホルダなので、
    実値の指し先が合っているかをここで確定させる。）
  - 貼るもの: 上記コマンドの出力（**秘密値は不要**。キー名と指し先パスだけで十分）。

- [x] **T0-2 ビルド**
  - 実行: `make build`
  - 貼るもの: 最後の 30 行程度（成功なら "Successfully built/tagged"、失敗ならエラー全体）。

- [x] **T0-3 スタック起動**（別ターミナルで起動しっぱなしにする）
  - 実行: `make dev`
  - 確認: 60 秒ほど待ち、6 サービス（elasticsearch / firestore-emulator /
    firebase-auth-emulator / minio / fastapi-service / adk-agent-service）が起動するか。
  - 貼るもの: 起動が落ち着いた後の `docker-compose ps` 出力。どれかが `unhealthy`/`Exit` なら
    `docker-compose logs <service>` も貼る。

- [x] **T0-4 ヘルスチェック**
  - 実行:
    ```bash
    curl -s http://localhost:8000/health
    curl -s http://localhost:3000/health
    curl -s http://localhost:9200/_cluster/health
    ```
  - 期待: fastapi `{"status":"ok"}` 相当、adk が応答、ES が `status: green|yellow`。
  - 貼るもの: 3 つの出力。

---

## フェーズ 1 — 自動テスト（デプロイ前ゲート本体）

ExecPlan の "Local pre-deploy gate" に対応。コード変更前のベースラインが green であることを確認する。

- [x] **T1-1 FastAPI ユニットテスト**（期待: 約 59 passed）— 59 passed。`test_local_task_queue` の env 分離バグを1件修正。
  - 実行: `docker-compose run --rm fastapi-service pytest`
  - 貼るもの: pytest の最終サマリ行（`xx passed` ...）。failed があればその FAILED ブロック全体。

- [x] **T1-2 ADK ユニットテスト**（期待: 約 25 passed）— コンテナ内実行で 28 passed。
  - 実行: `cd adk-agent-service && pytest -q`（依存が未導入ならコンテナ内実行に切替: 私が指示する）
  - 貼るもの: 最終サマリ行と、あれば failure。

- [x] **T1-3 Flutter 解析 + テスト**— analyze: No issues / test: 11 passed。
  - 実行: `cd flutter-web-app && flutter analyze && flutter test`
  - 期待: analyze は "No issues found!"、test は all passed。
  - 貼るもの: analyze の末尾とテストサマリ。

- [~] **T1-4 Firestore セキュリティルール ユニットテスト**（M2-12）— ⏭️ スキップ: ローカルに Java ランタイム無し（`firebase-cli` は導入済み）。Java 11+ JRE 導入後に実行可能。
  - 実行: `cd firebase && npm install && firebase emulators:exec --only firestore --project gen-fashion-local "npm test"`
  - 注: `firebase-tools` と Java 11+ JRE が必要。未導入ならスキップ可（私に伝えてください）。
  - 貼るもの: テストサマリ、または環境不足のエラー。

---

## フェーズ 2 — 共有クローゼットのシード

M5 の `SHARED_CLOSET` フロー（スモーク/E2E）は事前にシード済みデータを必要とする。

- [x] **T2-1 シード実行**— created=90（adult-01/02/03 各30）。`with_embeddings=false`（ローカル検索はキーワード優先＋kNNフェイルソフトのため埋め込み不要）。
  - 実行:
    ```bash
    cd scripts/seed_shared_closet
    python -m venv .venv && source .venv/bin/activate   # 初回のみ
    pip install -r requirements.txt                      # 初回のみ
    cp .env.example .env                                 # 既存 .env があればスキップ
    python run_seed.py
    ```
  - 注: Kaggle トークン（`~/.kaggle/kaggle.json`）が無ければ `--source-dir <PATH>` でローカル画像を
    指定するオフライン経路がある（README 参照）。詰まったら私に相談。
  - 期待サマリ: `{"created": 90, "skipped": 0, "errors": 0, "closets": {"adult-01":30,"adult-02":30,"child-01":30}}`
  - 貼るもの: 最後の JSON サマリ。エラーがあれば末尾のスタックトレース。

- [x] **T2-2 3 ストアの検証**— ES total 90 / adult-01:30, adult-02:30, child-01:30。
  - 実行（集計フィールドは `closetId.keyword`）:
    ```bash
    curl -s 'http://localhost:9200/clothing_items/_search' -H 'Content-Type: application/json' \
      -d '{"size":0,"query":{"term":{"user_id":"__shared__"}},
           "aggs":{"by_closet":{"terms":{"field":"closetId.keyword"}}}}'
    ```
  - 期待: `by_closet` に adult-01 / adult-02 / child-01 が各 ~30。MinIO（http://localhost:9001,
    minioadmin/minioadmin）に `gen-fashion-images/__shared__/closet/` が見えること。
  - 貼るもの: 上記 ES 集計レスポンス。

- [x] **T2-3 冪等性チェック**（任意）— 2回目 created=0, skipped=90。
  - 実行: `python run_seed.py`（2 回目）
  - 期待: `created: 0`。
  - 貼るもの: JSON サマリ。

---

## フェーズ 3 — バックエンド・スモーク（API レベルの通し）

- [x] **T3-1 クローゼット・スモーク（アップロード → READY）**— READY 到達・削除まで完走。バグ#1（base-url取り違え）・#2（Firestoreプロジェクト分離）を修正（下記「修正ログ」）。
  - 何を確認するか: 署名付きアップロード → MinIO 配置 → ローカルタスクキュー
    （`TASK_QUEUE_MODE=local`）が `/internal/tasks/process-upload` を叩く → 画像解析 + 埋め込み生成 →
    Firestore が `status: READY`。これはデプロイ ExecPlan が指摘する「内部 base-url 取り違え」の
    ローカル健全性も併せて確認する。
  - 実行: `python scripts/m2_closet_smoke.py`
  - 期待: 最終 `status: READY` で正常終了。
  - 貼るもの: スクリプトの標準出力全体。失敗時は **同時に**
    `docker-compose logs --tail=80 fastapi-service` も貼る（ワーカー経路の解析に必要）。

- [x] **T3-2 コーディネーション・スモーク（SHARED_CLOSET → COMPLETED）**— COMPLETED 到達。`modelUsed=gemini-2.5-flash-image`（実Nano Banana, ~1.15MB画像）。バグ#3（closetId が text マッピングで検索常時0件）を修正。所見: 主LLM経路は45秒タイムアウトし決定論フォールバックで完走（下記「所見」）。
  - 何を確認するか: セッション作成 → ソース選択（SHARED_CLOSET / adult-01）→ SSE で thinking-trace を
    受信 → ADK オーケストレーション → `status: COMPLETED`。
  - ⚠️ **落とし穴**: スクリプトの `--project` 既定値は `animation-agent` だが、ローカルの Firestore は
    `gen-fashion-local` プロジェクトに書かれる。**必ず `--project gen-fashion-local` を渡す**こと
    （渡さないと最後の Firestore 照合だけが失敗する）。
  - 実行:
    ```bash
    python scripts/m5_coordination_smoke.py --project gen-fashion-local --shared-closet-id adult-01
    ```
  - 期待: `status: COMPLETED` の JSON。`event_kinds` にツールイベントが並ぶ。
  - 貼るもの: スクリプト出力 + `docker-compose logs --tail=120 adk-agent-service`。
    画像生成について `gemini-2.5-flash-image`（Nano Banana）経路か **collage fallback** かを
    ログで確認したい（ローカルはフォールバックの可能性が高く、それ自体は想定内＝MD-11 で本番確認）。

---

## フェーズ 4 — フロントエンド / ブラウザ通し E2E

- [x] **T4-1 手動ブラウザ E2E**（実体験フロー）— サインイン→SHARED_CLOSET→SSE→`COMPLETED`、実Nano Banana画像(gemini-2.5-flash-image)生成、CC BY-SA帰属表示OK。今回は主LLM経路がタイムアウトせず完走（45秒以内）。先のT3-2スモークのタイムアウトはコールドスタート起因と推定。
  - 実行: `make web`（`make dev` は起動したまま）。Chrome が http://localhost:8088 で開く。
  - 操作: Firebase Auth エミュレータのポップアップで Google サインイン → セッション開始 →
    `SHARED_CLOSET`（adult-01）選択 → Accordion がツールイベントをストリーム → `COMPLETED` と
    生成画像が表示されるまで。
  - 貼るもの: 詰まった画面の説明 or スクショ、ブラウザのコンソールエラー、
    その時刻の `docker-compose logs --tail=120 fastapi-service adk-agent-service`。

---

## フェーズ 5 — 結果の確定

- [x] **T5-1 ローカル検証の所見をまとめる**
  - **結論**: ローカルで実行可能なタスクはすべて green（T0–T4-1。T1-4 のみ Java ランタイム無しでスキップ）。
    判明した不具合・修正点は下記「修正ログ」#1〜#6 に集約済み。
  - **画像生成 = 実 Nano Banana**（`modelUsed=gemini-2.5-flash-image`, ~1.15MB）。collage フォールバックではなく
    主経路で生成されたことを T3-2 / T4-1 で確認（タイムアウト整合後は fallback/timeout ログ0件で完走）。
  - **ローカル対象外（本番でのみ確認可能）として切り分け**:
    - MD-11: Nano Banana 経路自体はローカルで検証済み。残るは本番環境での品質/クォータ/リージョン検証のみ。
    - MD-3/4: Elasticsearch on Compute Engine の private 経路（ローカルは docker の ES に直結）。
    - MD-2/8: Secret Manager / OIDC（ローカルは平文 env と共有シークレットで代替）。

---

## 修正ログ（ローカル検証で発見・修正した実バグ）

これらは「M0–M5 verified locally」の主張に反して**ローカルで実際には壊れていた**経路です。
本番では各プロジェクト/設定が同一になるため一部は顕在化しませんが、修正はすべて本番でも有効。

1. **内部ワーカー base-url 取り違え**（アップロード処理が常に404）
   - 症状: `Local task ... /internal/tasks/process-upload returned HTTP 404`。ワーカールートは
     fastapi-service にあるのに、ローカルキューが `ADK_INTERNAL_BASE_URL`(=adk:3000) に POST していた。
   - 修正: `fastapi_internal_base_url` 設定を追加（[config.py](../../fastapi-service/app/config.py)）、
     [local_task_queue.py](../../fastapi-service/app/adapters/local_task_queue.py) で使用、
     [docker-compose.yml](../../docker-compose.yml) に `FASTAPI_INTERNAL_BASE_URL=http://fastapi-service:8000`。
   - デプロイ計画の "Surprises" / MD-8 が予告していた問題の**ローカル分**。OIDC等のクラウド分は MD-8 に残置。
2. **Firestore プロジェクト分離**（バックエンドとフロント/Authで別名前空間 → UIがデータを見られない）
   - 症状: バックエンドは Vertex 用 `GOOGLE_CLOUD_PROJECT=animation-agent` を Firestore にも流用し
     `animation-agent` 名前空間へ書込。フロント/Auth は `gen-fashion-local`。エミュレータ上で不一致。
   - 修正: `firestore_project_id`（= Firebase プロジェクト）を両サービスに追加し Firestore クライアントへ適用
     （[fastapi config](../../fastapi-service/app/config.py) / [adk config](../../adk-agent-service/styling_app/config.py) /
     3つの firestore アダプタ）、adk compose に `FIREBASE_PROJECT_ID` を追加。本番は3プロジェクト同一のためno-op。
3. **`closetId` が text マッピング**（SHARED_CLOSET 検索が常時0件 → コーディネーションが ERROR）
   - 症状: `clothing_items` を fastapi が先に作成し、その明示マッピングに `closetId` が無く動的 text 化。
     `{"term":{"closetId":"adult-01"}}` が解析済みトークンに当たらず0件 → 候補ゼロ → ERROR。
   - 修正: fastapi の `ensure_index` に `closetId`/`closetKind`/`imageUrl` を keyword 追加
     （[elasticsearch_embedding_repo.py](../../fastapi-service/app/adapters/elasticsearch_embedding_repo.py)）。
     インデックス削除＋再シードで keyword 化を確認。seed 側マッピングと整合。
4. **テスト分離**: `test_local_task_queue` が env を分離しておらず `make dev` 環境で誤検知（#1修正に伴い再調整）。

## 修正ログ（続き・2026-06-21 第2弾：上記「所見」2件を解消）

5. **埋め込みモデル `gemini-embedding-2` が Vertex 不在 → `gemini-embedding-001` + テキスト埋め込みに是正**
   - 根本問題: モデル名が不在（404）なだけでなく、**インデックス側が画像、クエリ側がテキスト**を埋め込んで
     おり、同じモデルでも別空間で kNN が原理的に成立しない設計だった。
   - 修正: モデルを **`gemini-embedding-001`**（GA・`output_dimensionality=768`・`embed_content`）に統一し、
     **インデックス側も解析テキスト（category/colors/tags/season）を埋め込む**よう変更（クエリと同一空間）。
     `task_type` は index=`RETRIEVAL_DOCUMENT` / query=`RETRIEVAL_QUERY`。ES は `similarity: cosine` のため
     手動正規化は不要。変更箇所: 両 `config.py`、`ports/gemini_analysis.py`（`embed`→`embed_text`）、
     `adapters/gemini_analysis.py`、`use_cases/closet/process_uploaded_item.py`（`_embedding_text`）、
     `adapters/gemini.py`（ADK クエリ）、`scripts/seed_shared_closet/run_seed.py`（`_embed_image`→`_embed_text`）、
     `adk-agent-service/.env(.example)` の `EMBEDDING_MODEL`、テストの `FakeGemini`。
   - シードの Vertex 403 も是正: seed が Vertex を `gen-fashion-local`（権限なし）で呼んでいた。
     アプリと同じく **Vertex=`GOOGLE_CLOUD_PROJECT`(animation-agent) / Firestore=`FIREBASE_PROJECT_ID`(gen-fashion-local)**
     に分離（`run_seed.py` + seed `.env(.example)`）。
   - 検証: `run_seed.py --with-embeddings` で 90件すべて 200 OK・768次元、kNN プローブで
     「casual blue summer t-shirt」→ 青いシャツ/Tシャツが上位ヒット（意味的に的確）。
6. **ADK 主経路タイムアウト → タイムアウトを config 化＋SSE 上限と整合**
   - `ADK_RUN_TIMEOUT_SECONDS=45`（ハードコード）を adk config の `adk_run_timeout_seconds`（既定 **90**）に。
   - ⚠️ 一度 120 に上げたら **fastapi の SSE 上限 `STREAM_MAX_SECONDS=120` と衝突**し、裏で COMPLETED でも
     クライアントには `TIMEOUT` 終端が返る不整合が発生。**SSE 上限を 150 に引き上げ**（ADK タイムアウト＋
     フォールバック時間を必ず内包）して解消。変更箇所: `adk config.py`、`server.py`、`session_routes.py`。
   - 検証: T3-2 再実行で **主LLM経路が完走**（fallback/timeout ログ0件）、`COMPLETED`＋実 Nano Banana 画像。

修正後の最終確認: fastapi pytest **59 passed** / adk pytest **28 passed**。

## メモ

- 本チェックリストは検証作業であり、追跡対象要件（MD-x）のステータスは変更しないため、
  `feature-matrix-phase01.md` / `architecture-overview.md` の更新は不要。
  バグ修正でアプリ挙動やコードを実際に変えた場合のみ、その変更に応じて同期する。
- サービス停止/初期化は `make clean`（ボリュームごと削除）。シードは再投入が必要になる点に注意。
