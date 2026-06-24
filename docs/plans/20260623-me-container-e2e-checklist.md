# ME ローカル・コンテナ E2E 検証チェックリスト

このドキュメントは ExecPlan ではなく、**ME（Pre-Deployment Experience & Domain Hardening, ME-1…ME-6）**
の未コミット実装を、あなた自身が `make dev` のコンテナスタックで通しテストして確認するための作業
タスクリストです（[20260621-md-phase1a-local-verification-checklist.md](20260621-md-phase1a-local-verification-checklist.md)
の続編）。

## 端末（このセッション）で私がすでに確認したこと

コンテナ不要の自動テストは私の手元で実行済み・全 green。**あなたが再実行する必要はありません**
（コンテナ版が欲しい場合のみ `make test` 等で回してください）。

| 検査 | 実行方法 | 結果 |
|---|---|---|
| FastAPI ユニット | `fastapi-service/.venv/bin/python -m pytest -q` | **63 passed, 1 skipped**（skip は live-ES テストで、ES 未起動のため自動スキップ） |
| ADK ユニット | `adk-agent-service/.venv/bin/python -m pytest -q` | **41 passed** |
| Flutter 解析 | `cd flutter-web-app && flutter analyze` | **No issues found** |
| Flutter テスト | `cd flutter-web-app && flutter test` | **12 passed** |

> メモ: `fastapi-service/.venv` には pytest が無かったので、テスト実行のため
> `pytest==7.4.0` / `pytest-asyncio==0.21.1` をこの venv に入れました（アプリ依存・
> `requirements.txt` は不変更）。コンテナ側の正式テストは `make test` です。

---

## 進め方（このループを各タスクで回す）

1. **あなた**: 該当タスクのコマンドを実行する。
2. **あなた**: 「貼るもの」に書かれた出力・ログをそのまま私に貼る（成功でも失敗でも）。
3. **私**: ログを解析し、期待結果と照合する。バグがあればその場で原因を特定し、最小修正を入れる。
4. 修正後はそのタスクを再実行し、green になってから次へ進む。

> 失敗したログこそ価値があります。要約せず、ターミナル出力をそのまま、タスク番号（例:「ME-T4 失敗」）を
> 添えて貼ってください。各タスクは前のタスクが green である前提で依存順に並んでいます。

---

## フェーズ 0 — スタック起動（前提）

- [ ] **ME-T0 スタック起動＆ヘルス**
  - 実行（別ターミナルで起動しっぱなし）: `make build && make dev`
  - 60 秒ほど待ってから別ターミナルで:
    ```bash
    docker-compose ps
    curl -s http://localhost:8000/health
    curl -s http://localhost:3000/health
    curl -s http://localhost:9200/_cluster/health | python3 -m json.tool
    ```
  - 期待: 6 サービスが Up、fastapi `{"status":"ok"}` 相当、adk 応答、ES `status: green|yellow`。
  - 貼るもの: `docker-compose ps` と 3 つの curl 出力。`unhealthy`/`Exit` があれば
    `docker-compose logs <service>` も。

---

## フェーズ 1 — 共有クローゼットの再シード（ME-4: gender データ）

> ME-4 で seed に gender ヒューリスティック（`Dress`/`Skirt`/`Blouse` → `female`、それ以外 → `common`）と
> ES マッピングの `gender: keyword` を追加。**既存ボリュームは旧データ（gender 無し）なので再シードが必須。**
> child imagery 検証（ME-3）も `child-01` のシードに依存します。

- [ ] **ME-T1a クリーン再シード**
  - 実行:
    ```bash
    cd scripts/seed_shared_closet
    python -m venv .venv && source .venv/bin/activate   # 既存なら source のみ
    pip install -r requirements.txt
    cp .env.example .env    # 既にあればスキップ
    python run_seed.py --purge --source-dir /path/to/clothing-dataset/images_original
    ```
    （Kaggle creds があれば `--source-dir` 無しで可。`--purge` で旧 gender 無しデータを除去。）
  - 期待サマリ: `{"created": 90, ..., "closets": {"adult-01": 30, "adult-02": 30, "child-01": 30}}`
  - 貼るもの: 末尾の JSON サマリ。

- [ ] **ME-T1b gender が 3 ストアに入ったか検証**
  - 実行:
    ```bash
    # ES: gender 別の件数（female / common が出るはず。null/欠落が無いこと）
    curl -s 'http://localhost:9200/clothing_items/_search' -H 'Content-Type: application/json' \
      -d '{"size":0,"query":{"term":{"user_id":"__shared__"}},
           "aggs":{"by_gender":{"terms":{"field":"gender"}}}}' | python3 -m json.tool

    # ES: gender が欠落している共有アイテムが 0 件であること
    curl -s 'http://localhost:9200/clothing_items/_count' -H 'Content-Type: application/json' \
      -d '{"query":{"bool":{"must":[{"term":{"user_id":"__shared__"}}],
           "must_not":[{"exists":{"field":"gender"}}]}}}'
    ```
  - 期待: `by_gender` に `female`/`common`（必要なら `male`）のバケット、合計 90。欠落 `count: 0`。
  - 貼るもの: 2 つの出力。

---

## フェーズ 2 — 共有クローゼット・ギャラリー API（ME-1）

> 新エンドポイント: `GET /shared-closets`（[shared_closet_routes.py:11](../../fastapi-service/app/handlers/shared_closet_routes.py#L11)）
> と `GET /shared-closets/{id}/items`（[同:19](../../fastapi-service/app/handlers/shared_closet_routes.py#L19)）。
> どちらも Firebase ID トークン必須。

- [ ] **ME-T2 ギャラリー API（認証必須）**
  - 実行（トークン取得は `README_LOCAL_DEV.md` の「Local Auth Token」参照）:
    ```bash
    TOKEN=$(curl -s -X POST \
      "http://localhost:9099/identitytoolkit.googleapis.com/v1/accounts:signUp?key=fake-api-key" \
      -H "Content-Type: application/json" -d '{"returnSecureToken":true}' \
      | python3 -c 'import json,sys; print(json.load(sys.stdin)["idToken"])')

    # 認証なし → 401 を期待
    curl -s -o /dev/null -w "no-auth: %{http_code}\n" http://localhost:8000/shared-closets

    # 一覧（3 クローゼット＋メタデータ）
    curl -s http://localhost:8000/shared-closets -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

    # child-01 のアイテム（30 件、gender 入り）
    curl -s "http://localhost:8000/shared-closets/child-01/items" \
      -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -60
    ```
  - 期待: no-auth は `401`。一覧に `adult-01/adult-02/child-01`。`child-01/items` が 30 件で各アイテムに
    `gender` と署名付き画像 URL が付く。
  - 貼るもの: 3 つの出力（items は先頭 1〜2 件で十分）。

---

## フェーズ 3 — 自分のクローゼットのメタデータ編集（ME-1）

> 新エンドポイント: `PATCH /closet/items/{id}`（owner のみ、ES へミラー。
> [closet_routes.py:81](../../fastapi-service/app/handlers/closet_routes.py#L81)）。

- [ ] **ME-T3 メタデータ編集が ES に反映されるか**
  - 手順: まず `scripts/m2_closet_smoke.py`（または `make web` の UI）で 1 アイテムを READY にし、その
    `item_id` を控える。続いて:
    ```bash
    ITEM_ID=<上で得た item_id>
    curl -s -X PATCH "http://localhost:8000/closet/items/$ITEM_ID" \
      -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
      -d '{"category":"shirt","tags":["formal","navy"],"colors":["navy"],"season":"autumn","gender":"male"}' \
      | python3 -m json.tool

    # ES 側に反映されたか
    curl -s "http://localhost:9200/clothing_items/_doc/$ITEM_ID" | python3 -m json.tool | grep -E 'tags|category|gender|season'
    ```
  - 期待: PATCH 200、ES doc の `tags`/`category`/`gender`/`season` が更新値。**他ユーザー item への PATCH は
    403/404**（余裕があれば別トークンで確認）。
  - 貼るもの: PATCH 応答と ES doc の該当フィールド。

---

## フェーズ 4 — 候補選択ゲート＋gender 伝搬（ME-2 / ME-3 / ME-6 must-fix）

> ME-6 で生成が二段化（propose → `PROPOSING` で**一時停止** → `POST /sessions/{id}/select` → generate）。
> `scripts/m5_coordination_smoke.py` は更新済みで、propose 段で `style_synthesizer` が呼ばれていないこと・
> 選択前に画像が生成されていないこと・generate 段の URL が選択した候補と**一致**すること・gender が
> ツール引数に**束縛**されていることまで自動アサートします。

- [ ] **ME-T4a adult 経路（gender=common）**
  - 実行:
    ```bash
    python3 scripts/m5_coordination_smoke.py --shared-closet-id adult-01 --gender common --timeout-seconds 200
    ```
  - 期待: スクリプトが例外なく完走し、最後に session_id と `selected_image_urls`/`synth` 一致の要約を出力。
    内部アサート（propose に synthesizer 無し・選択前生成なし・gender 束縛・URL 一致）が全通過。
  - 貼るもの: スクリプト出力全体（失敗時はトレースバックごと）。

- [ ] **ME-T4b child 経路（gender=female, must-fix の中核）**
  - 実行:
    ```bash
    python3 scripts/m5_coordination_smoke.py --shared-closet-id child-01 --gender female --timeout-seconds 200
    ```
  - 期待: 同上で完走。session が `child` かつ `female` を持って generate まで進む。
  - 貼るもの: スクリプト出力。完走後、生成画像のストレージキー（出力 or Firestore `styleResult`）を控える。

- [ ] **ME-T4c child imagery を目視確認（ME-3 must-fix の確定）**
  - 自動スモークは URL/gender 束縛までしか保証しません。**「`child-01` 選択 → 子ども画像」**は人間の目で確定が必要。
  - 手順: ME-T4b で生成された coordinate 画像を MinIO（http://localhost:9001 、`minioadmin`/`minioadmin`、
    `gen-fashion-images` バケット → `__shared__/coordinates/` か該当ユーザー配下）で開く。
    本物の Nano Banana 経路を見たい場合は、`.env` の Vertex/SA 設定で実モデルが叩かれること（collage
    フォールバックでないこと）を `styleResult.modelUsed=gemini-2.5-flash-image` で確認。
  - 期待: 生成画像が**子ども**の着用イメージ（大人でない）。
  - 貼るもの: 画像のスクリーンショット＋ `modelUsed` の値。

---

## フェーズ 5 — ブラウザ手動 E2E（ME-1 / ME-2 / ME-5 / ME-6 の UI）

> ⚠️ **`scripts/m5_coordination_browser_e2e.py` は二段フロー（選択ゲート）に未対応のまま**です（今回の
> ME 変更で更新されていない＝旧・自動生成フローを前提に `COMPLETED` を待つので、現状ではタイムアウト
> する可能性が高い）。**ブラウザ通しは下記の手動 `make web` で行ってください。**（このスクリプトを
> 二段対応に直すかは別タスク化。下「残課題」参照。）

- [ ] **ME-T5 手動ブラウザ通し（`make web`）**
  - 実行: `make web`（http://localhost:8088）でサインイン。
  - 確認ポイント:
    1. **ME-1 ギャラリー**: Shared タブで 3 クローゼットを閲覧、各アイテムにメタデータ。自分の closet では
       編集ダイアログ → 保存でカードが更新される。
    2. **ME-2 gender**: コーディネーション開始フォームで gender を選べる。
    3. **ME-6 選択ゲート**: 検索後に候補が提示され、**画像生成は始まらず**選択待ちになる。候補を選んで
       初めて生成が走る（同意なき自動生成が無いこと）。
    4. **ME-5 トレース整理**: Agent Trace は要約表示で、展開時のみ raw 詳細。候補/結果は専用パネルに分離
       （トレースに生データが混ざっていない）。
    5. **ME-3 結果**: `child-01` ＋ gender 選択での生成結果が子ども画像。
  - 貼るもの: 各ポイントのスクショ（特に選択ゲートの「候補提示で停止」状態と最終結果）。

---

## フェーズ 6 — 確定

- [ ] **ME-T6 所見まとめ**
  - すべて green なら、`docs/feature-matrix-phase01.md` の ME 行（既に ✅ 表記）に**コンテナ実機の通し
    検証ログ**を一文追記して確定。失敗があれば該当タスク番号で私に共有 → 最小修正 → 再実行。

---

## 残課題（このセッションで判明、コンテナ検証とは別に要対応）

- [ ] **`scripts/m5_coordination_browser_e2e.py` を二段フロー対応に更新**（`select`/`session.proposed`/
  `gender` 未対応。現状は旧・自動生成前提）。ヘッドレス・ブラウザ通しを CI 化したいなら必要。やるなら
  別タスクで（`m5_coordination_smoke.py` の二段ロジックを移植）。
- [ ] **`fastapi-service/.venv` に pytest が無い**（テストは Docker 前提）。ローカルで素早く回したいなら
  `requirements.txt` の dev 依存を venv に入れるか、`uv` で dev グループを定義すると楽。任意。
