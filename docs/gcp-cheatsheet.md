# GCP 運用コマンド集 — gen-fashion

このドキュメントはプロジェクトに対してよく使う `gcloud` コマンドをまとめたもの。
作業のたびに随時追加・更新すること。

## 前提設定

```bash
# プロジェクトとデフォルトリージョンを設定（これをやっておくと --project / --region を毎回省略できる）
gcloud config set project your-project-id
gcloud config set compute/region asia-northeast1
gcloud config set compute/zone asia-northeast1-a

# 現在の設定を確認
gcloud config list
```

---

## Compute Engine — Elasticsearch VM

VM 名: `gen-fashion-es` / ゾーン: `asia-northeast1-a`

> **コスト方針:** 使っていないときは止めることを推奨。課金は `pd-balanced` ディスク（約 $3/月）のみになる。
> 通常運用では夜間 (JST 02:00) に `es-night-off` スケジュールで自動停止、08:00 に自動起動。
> ただし公開デモ期間中は、2026-08-31 までは全時間帯で使えるように `es-night-off` を VM から外している。

### 起動 / 停止

```bash
# 起動（Milestone C の ES 疎通確認や再シード時など）
gcloud compute instances start gen-fashion-es --zone=asia-northeast1-a

# 停止（作業終了後は必ず実行）
gcloud compute instances stop gen-fashion-es --zone=asia-northeast1-a

# 状態確認
gcloud compute instances describe gen-fashion-es \
  --zone=asia-northeast1-a --format='value(status)'
```

### 夜間停止スケジュール

2026-07-10 時点では、公開デモ期間（2026-08-31 まで）の可用性を優先し、
`es-night-off` resource policy は存在させたまま VM から外している。

```bash
# VM に夜間停止スケジュールが付いていないことを確認
gcloud compute instances describe gen-fashion-es \
  --zone=asia-northeast1-a \
  --format='value(resourcePolicies)'

# 温存しているスケジュール本体を確認（JST 02:00 停止 / 08:00 起動）
gcloud compute resource-policies describe es-night-off \
  --region=asia-northeast1 \
  --format='yaml(status,instanceSchedulePolicy)'

# 2026-09-01 以降、夜間停止を再開する場合
gcloud compute instances add-resource-policies gen-fashion-es \
  --zone=asia-northeast1-a \
  --resource-policies=es-night-off

# 再び公開期間を延長する場合
gcloud compute instances remove-resource-policies gen-fashion-es \
  --zone=asia-northeast1-a \
  --resource-policies=es-night-off
```

### SSH 接続

```bash
# 通常接続（VM に外部 IP がある間のみ）
gcloud compute ssh gen-fashion-es --zone=asia-northeast1-a

# IAP 経由（外部 IP 削除後はこちらを使う — Milestone B 完了後はこちらが必須）
gcloud compute ssh gen-fashion-es --zone=asia-northeast1-a --tunnel-through-iap

# コマンドを直接渡す場合（--quiet でホスト確認プロンプトをスキップ）
gcloud compute ssh gen-fashion-es --zone=asia-northeast1-a --tunnel-through-iap --quiet \
  --command="<コマンド>"
```

### Elasticsearch の状態確認

VM に SSH してから実行する。

```bash
# サービス状態
sudo systemctl status elasticsearch

# クラスタ健全性（green / yellow が正常）
ES_API=$(gcloud secrets versions access latest --secret=ELASTICSEARCH_API_KEY --project=your-project-id)
curl -sk -H "Authorization: ApiKey $ES_API" https://localhost:9200/_cluster/health | python3 -m json.tool

# インデックス内のドキュメント数（210 以上あれば seed 完了済み）
curl -sk -H "Authorization: ApiKey $ES_API" https://localhost:9200/clothing_items/_count

# embedding フィールドの存在確認（768次元ベクトルが入っていることを確認）
curl -sk -H "Authorization: ApiKey $ES_API" -H 'Content-Type: application/json' \
  https://localhost:9200/clothing_items/_search \
  -d '{"query":{"term":{"user_id":"__shared__"}},"_source":["embedding"],"size":1}' \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); e=d["hits"]["hits"][0]["_source"].get("embedding",[]); print(f"dim={len(e)}")'
```

### VM の外部 IP 状態確認

```bash
# 空文字が返れば外部 IP なし（正常な本番状態）
gcloud compute instances describe gen-fashion-es \
  --zone=asia-northeast1-a --format='value(networkInterfaces[0].accessConfigs)'
```

---

## Secret Manager

シークレットの値をコードやコマンドに渡す場合はここから取得する。
**シークレットの値はチャットやログに貼らないこと。**

```bash
# 最新バージョンを取得して変数に格納
ES_API=$(gcloud secrets versions access latest --secret=ELASTICSEARCH_API_KEY --project=your-project-id)
R2_KEY=$(gcloud secrets versions access latest --secret=R2_ACCESS_KEY_ID --project=your-project-id)
R2_SECRET=$(gcloud secrets versions access latest --secret=R2_SECRET_ACCESS_KEY --project=your-project-id)
TASK_SECRET=$(gcloud secrets versions access latest --secret=INTERNAL_TASK_SECRET --project=your-project-id)
ES_SSL_FINGERPRINT=$(gcloud secrets versions access latest --secret=ELASTICSEARCH_SSL_FINGERPRINT --project=your-project-id)
RAKUTEN_APPLICATION_ID=$(gcloud secrets versions access latest --secret=RAKUTEN_APPLICATION_ID --project=your-project-id)
RAKUTEN_ACCESS_KEY=$(gcloud secrets versions access latest --secret=RAKUTEN_ACCESS_KEY --project=your-project-id)
RAKUTEN_AFFILIATE_ID=$(gcloud secrets versions access latest --secret=RAKUTEN_AFFILIATE_ID --project=your-project-id)
RAKUTEN_APPLICATION_URL=$(gcloud secrets versions access latest --secret=RAKUTEN_APPLICATION_URL --project=your-project-id)

# 登録済みシークレット一覧
gcloud secrets list --project=your-project-id

# 楽天連携シークレットの存在確認
gcloud secrets list --project=your-project-id --filter='name~RAKUTEN' --format='value(name)'

# 新しいシークレットを登録（値はファイル経由で渡す — echo でパイプするとシェル履歴に残る）
printf '%s' "<値>" | gcloud secrets create <SECRET_NAME> --data-file=- --project=your-project-id

# 既存シークレットに新しいバージョンを追加
printf '%s' "<新しい値>" | gcloud secrets versions add <SECRET_NAME> --data-file=- --project=your-project-id
```

---

## ファイアウォールルール

```bash
# 現在のルール一覧（gen-fashion 関連のみ）
gcloud compute firewall-rules list --filter="name:gen-fashion OR name:allow-es" \
  --format="table(name,direction,sourceRanges,allowed)"

# ES への許可ルール詳細確認
gcloud compute firewall-rules describe allow-es-from-cloudrun

# ES VM にだけ tcp:9200 許可/拒否を適用するタグを確認
gcloud compute instances describe gen-fashion-es \
  --zone=asia-northeast1-a \
  --format='value(tags.items)'

# Cloud Run Direct VPC egress subnet から ES への tcp:9200 だけ許可
gcloud compute firewall-rules describe allow-es-from-cloudrun \
  --format='yaml(priority,sourceRanges,targetTags,allowed,logConfig)'

# default-allow-internal より優先して、その他の内部 tcp:9200 を拒否
gcloud compute firewall-rules describe deny-es-other-internal \
  --format='yaml(priority,sourceRanges,targetTags,denied,logConfig)'

# 外部 IP なしの VM へ IAP SSH するための最小許可
gcloud compute firewall-rules describe allow-iap-ssh \
  --format='yaml(sourceRanges,targetTags,allowed,logConfig)'
```

---

## Cloud Run（Milestone C 以降）

```bash
# サービス一覧
gcloud run services list --region=asia-northeast1

# サービスの URL を取得
gcloud run services describe fastapi-service --region=asia-northeast1 --format='value(status.url)'
gcloud run services describe adk-agent-service --region=asia-northeast1 --format='value(status.url)'

# ヘルスチェック
FASTAPI_URL=$(gcloud run services describe fastapi-service --region=asia-northeast1 --format='value(status.url)')
curl -f "$FASTAPI_URL/health"

# SSE 用のリクエストタイムアウト確認（D.5 以降は 300 秒必須）
gcloud run services describe fastapi-service \
  --region=asia-northeast1 \
  --format='value(spec.template.spec.timeoutSeconds)'

# ログを確認（直近 20 件）
gcloud logging read 'resource.labels.service_name="fastapi-service"' \
  --limit=20 --format='value(timestamp,textPayload)'
gcloud logging read 'resource.labels.service_name="adk-agent-service"' \
  --limit=20 --format='value(timestamp,textPayload)'

# リビジョン一覧（ロールバック対象を探す場合）
gcloud run revisions list --service=fastapi-service --region=asia-northeast1

# 特定リビジョンにトラフィックを戻す（ロールバック）
gcloud run services update-traffic fastapi-service \
  --region=asia-northeast1 --to-revisions=<REVISION_NAME>=100
```

### 本番の休止 / 一時再開

通常は、Cloud Run の最小インスタンスを 0 に保ち、公開 API、Cloud Tasks、ES VM
を休止する。Cloud Run のサービス定義や Firestore データは削除しないため、保存容量
などの課金は残る。

```bash
# 休止: 外部リクエスト、非同期ワーカー、ES VM を止める
gcloud tasks queues pause gen-fashion-embed --location=asia-northeast1 --quiet
gcloud run services remove-iam-policy-binding fastapi-service \
  --region=asia-northeast1 --member=allUsers --role=roles/run.invoker --quiet
gcloud compute instances stop gen-fashion-es --zone=asia-northeast1-a --quiet

# 一時再開: main への push による CI/CD が自動で実行する内容
gcloud compute instances start gen-fashion-es --zone=asia-northeast1-a --quiet
gcloud tasks queues resume gen-fashion-embed --location=asia-northeast1 --quiet
# fastapi-service の次回 deploy は --allow-unauthenticated により allUsers を復元する

# ADK にサービスレベルの最小インスタンスが残っていないことを確認する
gcloud run services describe adk-agent-service --region=asia-northeast1 \
  --format='value(metadata.annotations.run.googleapis.com/minScale)'
```

---

## Artifact Registry（Milestone C 以降）

```bash
REPO=asia-northeast1-docker.pkg.dev/your-project-id/gen-fashion

# イメージ一覧
gcloud artifacts docker images list $REPO/fastapi-service --include-tags
gcloud artifacts docker images list $REPO/adk-agent-service --include-tags

# ローカルから Docker 認証（初回のみ）
gcloud auth configure-docker asia-northeast1-docker.pkg.dev
```

### Cloud Build でイメージをビルド & プッシュ

```bash
REPO=asia-northeast1-docker.pkg.dev/your-project-id/gen-fashion
IMAGE_TAG=md-$(date +%Y%m%d-%H%M)

# 両サービスを並行ビルド（ターミナル2枚で同時実行 or & でバックグラウンド）
gcloud builds submit fastapi-service --tag $REPO/fastapi-service:$IMAGE_TAG --project=your-project-id
gcloud builds submit adk-agent-service --tag $REPO/adk-agent-service:$IMAGE_TAG --project=your-project-id
```

### イメージタグを使った再デプロイ（コード修正後のロールアウト）

```bash
# 現在のタグを確認してから最新イメージで更新
REPO=asia-northeast1-docker.pkg.dev/your-project-id/gen-fashion
NEW_TAG=md-$(date +%Y%m%d-%H%M)

bash scripts/deploy/deploy_adk.sh \
  --project your-project-id --region asia-northeast1 \
  --image "$REPO/adk-agent-service:$NEW_TAG" \
  --es-internal-ip 10.146.0.2 \
  --es-ssl-fingerprint "$ES_SSL_FINGERPRINT" \
  --r2-endpoint-url https://251f1f3bfe0fba6b30914150579f34b5.r2.cloudflarestorage.com \
  --r2-public-endpoint-url https://251f1f3bfe0fba6b30914150579f34b5.r2.cloudflarestorage.com \
  --r2-bucket-name gen-fashion-images

ADK_URL=$(gcloud run services describe adk-agent-service --region=asia-northeast1 --format='value(status.url)')
FASTAPI_URL=$(gcloud run services describe fastapi-service --region=asia-northeast1 --format='value(status.url)')
bash scripts/deploy/deploy_fastapi.sh \
  --project your-project-id --region asia-northeast1 \
  --image "$REPO/fastapi-service:$NEW_TAG" \
  --adk-url "$ADK_URL" --fastapi-url "$FASTAPI_URL" \
  --es-internal-ip 10.146.0.2 \
  --es-ssl-fingerprint "$ES_SSL_FINGERPRINT" \
  --cors-allow-origins "https://gen-fashion-app.web.app" \
  --r2-endpoint-url https://251f1f3bfe0fba6b30914150579f34b5.r2.cloudflarestorage.com \
  --r2-public-endpoint-url https://251f1f3bfe0fba6b30914150579f34b5.r2.cloudflarestorage.com \
  --r2-bucket-name gen-fashion-images
```

### クリーンアップポリシー（最新 3 タグのみ保持）

```bash
gcloud artifacts repositories set-cleanup-policies gen-fashion \
  --project=your-project-id --location=asia-northeast1 \
  --policy='[{"name":"keep-recent","action":{"type":"Keep"},"mostRecentVersions":{"keepCount":3}}]'
```

---

## Cloud Tasks（Milestone C 以降）

```bash
# キュー一覧・状態確認
gcloud tasks queues list --location=asia-northeast1 --project=your-project-id

# キュー詳細（バックログ件数、レート制限など）
gcloud tasks queues describe gen-fashion-embed \
  --location=asia-northeast1 --project=your-project-id

# タスク一覧（滞留しているタスクがないか確認）
gcloud tasks list --queue=gen-fashion-embed \
  --location=asia-northeast1 --project=your-project-id
```

---

## Flutter Web ビルド & Firebase Hosting（Milestone D 以降）

```bash
# 本番ビルド（credentials/firebase-sdk.md の値を使う）
cd flutter-web-app
flutter build web --release \
  --dart-define=API_BASE_URL=https://fastapi-service-hvwhpzcehq-an.a.run.app \
  --dart-define=USE_EMULATORS=false \
  --dart-define=FIREBASE_PROJECT_ID=your-project-id \
  --dart-define=FIREBASE_API_KEY="$FIREBASE_API_KEY" \
  --dart-define=FIREBASE_APP_ID=1:789766161934:web:e894240fca5dc80b9ede5f \
  --dart-define=FIREBASE_MESSAGING_SENDER_ID=789766161934 \
  --dart-define=FIREBASE_AUTH_DOMAIN=your-project-id.firebaseapp.com \
  --dart-define=FIREBASE_STORAGE_BUCKET=your-project-id.firebasestorage.app
cd ..

# Firebase Hosting にデプロイ
firebase deploy --only hosting --project your-project-id

# デプロイ後の公開 URL
# https://gen-fashion-app.web.app
```

Legacy default Hosting site `your-project-id` is disabled. Re-enable it only if
the old `https://your-project-id.web.app` URL is intentionally restored:

```bash
npx -y firebase-tools@latest hosting:disable \
  --site your-project-id --project your-project-id --force
```

Firebase Auth authorized domains are separate from `FIREBASE_AUTH_DOMAIN`.
If Google sign-in fails with `unauthorized-domain` after adding a Hosting
site, add the bare host name (no protocol or port) to Firebase Auth:

```bash
node - <<'NODE'
const { requireAuth } = require('/opt/homebrew/lib/node_modules/firebase-tools/lib/requireAuth');
const firebaseAuth = require('/opt/homebrew/lib/node_modules/firebase-tools/lib/auth');
const { addAuthDomains } = require('/opt/homebrew/lib/node_modules/firebase-tools/lib/hosting/api');
const { getAuthDomains } = require('/opt/homebrew/lib/node_modules/firebase-tools/lib/gcp/auth');
const project = 'your-project-id';
const projectRoot = process.cwd();
const target = 'gen-fashion-app.web.app';
(async () => {
  const selected = firebaseAuth.selectAccount(undefined, projectRoot);
  const options = { project, projectRoot };
  if (selected) {
    options.user = selected.user;
    options.tokens = selected.tokens;
  }
  await requireAuth(options);
  const updated = await addAuthDomains(project, [`https://${target}`]);
  console.log(updated.includes(target) ? `authorized: ${target}` : `missing: ${target}`);
  console.log((await getAuthDomains(project)).join('\n'));
})().catch((err) => {
  console.error(err.message || err);
  process.exit(1);
});
NODE
```

Remove a retired Hosting domain from Firebase Auth authorized domains:

```bash
node - <<'NODE'
const { requireAuth } = require('/opt/homebrew/lib/node_modules/firebase-tools/lib/requireAuth');
const firebaseAuth = require('/opt/homebrew/lib/node_modules/firebase-tools/lib/auth');
const { getAuthDomains, updateAuthDomains } = require('/opt/homebrew/lib/node_modules/firebase-tools/lib/gcp/auth');
const project = 'your-project-id';
const target = 'your-project-id.web.app';
(async () => {
  const projectRoot = process.cwd();
  const selected = firebaseAuth.selectAccount(undefined, projectRoot);
  const options = { project, projectRoot };
  if (selected) options.account = selected.user.email;
  await requireAuth(options);
  const domains = await getAuthDomains(project);
  await updateAuthDomains(project, domains.filter((domain) => domain !== target));
})();
NODE
```

### R2 CORS cleanup for the active Hosting origin

`wrangler` requires a valid Cloudflare login or `CLOUDFLARE_API_TOKEN`. Keep only
the active Firebase Hosting origin in the R2 browser-upload CORS rule:

```bash
cat > /tmp/gen-fashion-r2-cors.json <<'JSON'
[
  {
    "AllowedOrigins": ["https://gen-fashion-app.web.app"],
    "AllowedMethods": ["GET", "PUT", "POST", "OPTIONS"],
    "AllowedHeaders": ["*"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  }
]
JSON

wrangler r2 bucket cors set gen-fashion-images --file /tmp/gen-fashion-r2-cors.json
wrangler r2 bucket cors list gen-fashion-images
```

---

## Firestore

```bash
# TTL ポリシーの確認（agentEvents コレクションの ttlAt フィールド）
gcloud firestore fields ttls list --project=your-project-id

# TTL ポリシーを有効化（Milestone E）
gcloud firestore fields ttls update ttlAt \
  --collection-group=agentEvents --enable-ttl --project=your-project-id

# 現在デプロイ済みの複合インデックス一覧（firestore.indexes.json との差分確認用）
gcloud firestore indexes composite list --project=your-project-id \
  --format='table(collectionGroup,fields)'

# firestore.indexes.json を本番に同期（CI/CD の deploy ジョブが毎回自動実行するが、
# 手動で先にインデックスを温めたい/緊急修正したい場合はこれを直接叩く）
bash scripts/deploy/deploy_firestore_indexes.sh --project=your-project-id
```

**落とし穴 (2026-07-04 の障害):** Firestore はクエリが `.where()` の等価条件2つ以上
+ 範囲条件 (`>=`, `<=` 等) や `.order_by()` を組み合わせると複合インデックスが必要になるが、
Firestore エミュレータはこの要件を一切検証しない（インデックス無しでもエミュレータ上は成功する）。
そのため新しいクエリ形状を追加したら、必ず `firestore.indexes.json` に対応するインデックスを
追加し、`fastapi-service/tests/adapters/test_firestore_composite_indexes.py` を通すこと
(このテストは実際の `.where()`/`.order_by()` 呼び出しから必要なインデックス形状を導出し、
宣言済みインデックスと突き合わせる。CI の `test-fastapi` ジョブで main/develop へのマージ前に
必ず実行される)。さらに `firestore.indexes.json` を更新しただけでは本番には反映されない
— 本番反映は `ci-cd.yml` の deploy ジョブが `deploy_firestore_indexes.sh` を実行して行う。

---

## よく使う確認コマンド（ワンライナー）

```bash
# VM の状態・内部 IP・外部 IP をまとめて確認
gcloud compute instances describe gen-fashion-es --zone=asia-northeast1-a \
  --format='table(name,status,networkInterfaces[0].networkIP,networkInterfaces[0].accessConfigs[0].natIP)'

# Secret Manager の全シークレット名と更新日時
gcloud secrets list --project=your-project-id \
  --format='table(name,updateTime)'

# 有効な API 一覧（デプロイに必要な API が全部 enabled か確認）
gcloud services list --enabled --project=your-project-id \
  --filter="name:(run OR artifactregistry OR cloudbuild OR secretmanager OR cloudtasks OR compute OR firestore OR aiplatform OR logging OR iamcredentials)" \
  --format='value(name)'

# Cloud Run サービス 2 本の稼働状況まとめ確認
gcloud run services list --region=asia-northeast1 --project=your-project-id \
  --format='table(metadata.name,status.url,status.conditions[0].status,status.conditions[0].message)'

# fastapi + adk の /health を一発確認
FASTAPI_URL=$(gcloud run services describe fastapi-service --region=asia-northeast1 --format='value(status.url)')
ADK_URL=$(gcloud run services describe adk-agent-service --region=asia-northeast1 --format='value(status.url)')
echo "fastapi: $(curl -sf $FASTAPI_URL/health)" && echo "adk (expect 403): $(curl -s -o /dev/null -w '%{http_code}' $ADK_URL/health)"
```

---

## CI/CD — Workload Identity Federation 設定（MF-1）

GitHub Actions が SA の JSON 鍵なしで GCP にデプロイするための WIF 設定手順。
**一度だけ実行すれば OK。** `<GITHUB_ORG>/<GITHUB_REPO>` は実際のリポジトリ名に替えること。

```bash
PROJECT=your-project-id
PROJECT_NUMBER=789766161934
GITHUB_REPO="<GITHUB_ORG>/<GITHUB_REPO>"

# 1. Workload Identity Pool を作成
gcloud iam workload-identity-pools create github-pool \
  --project=${PROJECT} --location=global \
  --display-name="GitHub Actions Pool"

# 2. GitHub OIDC プロバイダを追加
gcloud iam workload-identity-pools providers create-oidc github-provider \
  --project=${PROJECT} --location=global \
  --workload-identity-pool=github-pool \
  --display-name="GitHub Actions Provider" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
  --attribute-condition="assertion.repository=='${GITHUB_REPO}' && assertion.ref=='refs/heads/main'"

# 3. デプロイ用 SA を作成してロールを付与
gcloud iam service-accounts create github-deployer \
  --display-name="GitHub Actions Deployer" \
  --project=${PROJECT}

# Cloud Run デプロイ + IAM バインディング変更
gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:github-deployer@${PROJECT}.iam.gserviceaccount.com" \
  --role=roles/run.admin

# main push 後の一時起動・休止に必要な最小権限
gcloud iam roles create githubDeployerPauseProduction \
  --project=${PROJECT} \
  --title="GitHub Deployer Pause Production" \
  --description="Pause and resume the production ES VM and Cloud Tasks queue." \
  --permissions="compute.instances.get,compute.instances.start,compute.instances.stop,cloudtasks.queues.get,cloudtasks.queues.pause,cloudtasks.queues.resume" \
  --stage=GA
gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:github-deployer@${PROJECT}.iam.gserviceaccount.com" \
  --role="projects/${PROJECT}/roles/githubDeployerPauseProduction"

# Artifact Registry へのイメージプッシュ
gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:github-deployer@${PROJECT}.iam.gserviceaccount.com" \
  --role=roles/artifactregistry.writer

# Firebase Hosting デプロイ（ADC 経由）
gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:github-deployer@${PROJECT}.iam.gserviceaccount.com" \
  --role=roles/firebasehosting.admin

# Cloud Run 各 SA として振る舞う権限（gcloud run deploy --service-account に必要）
for SA in fastapi-sa adk-sa tasks-invoker-sa; do
  gcloud iam service-accounts add-iam-policy-binding \
    ${SA}@${PROJECT}.iam.gserviceaccount.com \
    --member="serviceAccount:github-deployer@${PROJECT}.iam.gserviceaccount.com" \
    --role=roles/iam.serviceAccountUser
done

# 4. WIF プロバイダから github-deployer SA へのバインド（このリポジトリ限定）
gcloud iam service-accounts add-iam-policy-binding \
  github-deployer@${PROJECT}.iam.gserviceaccount.com \
  --project=${PROJECT} \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/attribute.repository/${GITHUB_REPO}"

# 5. WIF_PROVIDER の値を確認（GitHub Secrets に登録する）
echo "WIF_PROVIDER: projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/providers/github-provider"
echo "WIF_SA: github-deployer@${PROJECT}.iam.gserviceaccount.com"
```

### GitHub Secrets 登録リスト（Settings → Secrets and variables → Actions → Secrets）

| Secret 名 | 値 |
|---|---|
| `WIF_PROVIDER` | `projects/789766161934/locations/global/workloadIdentityPools/github-pool/providers/github-provider` |
| `WIF_SA` | `github-deployer@your-project-id.iam.gserviceaccount.com` |
| `ES_INTERNAL_IP` | `10.146.0.2` |
| `ES_SSL_FINGERPRINT` | ES VM が `:9200` で提示する leaf certificate の SHA-256 fingerprint |
| `R2_ENDPOINT_URL` | `https://251f1f3bfe0fba6b30914150579f34b5.r2.cloudflarestorage.com` |
| `R2_PUBLIC_ENDPOINT_URL` | `https://251f1f3bfe0fba6b30914150579f34b5.r2.cloudflarestorage.com` |
| `R2_BUCKET_NAME` | `gen-fashion-images` |
| `FIREBASE_API_KEY` | Firebase SDK config の `apiKey`（credentials/firebase-sdk.md 参照） |
| `FIREBASE_APP_ID` | Firebase SDK config の `appId` |
| `FIREBASE_MESSAGING_SENDER_ID` | `789766161934` |
| `FIREBASE_AUTH_DOMAIN` | `your-project-id.firebaseapp.com` |
| `FIREBASE_STORAGE_BUCKET` | `your-project-id.firebasestorage.app` |

### GitHub Actions 環境（production）の設定

GitHub repo → Settings → Environments → New environment → 名前: `production`。
現在の GitHub plan では Required reviewers が使えないため、production 環境は
deployment branch policy で `main` のみに制限する。WIF provider 側も
`assertion.ref=='refs/heads/main'` に制限している。CI/CD の production deploy も
`main` への `push` 時だけ実行する。

```bash
# 現在の WIF 条件を確認
gcloud iam workload-identity-pools providers describe github-provider \
  --project=your-project-id --location=global \
  --workload-identity-pool=github-pool \
  --format='value(attributeCondition)'

# 条件を main branch のみに再適用
gcloud iam workload-identity-pools providers update-oidc github-provider \
  --project=your-project-id --location=global \
  --workload-identity-pool=github-pool \
  --attribute-condition="assertion.repository=='RanArino/gen-fashion' && assertion.ref=='refs/heads/main'"
```

### Firebase Web API key の referrer 制限

Firebase Web API key は公開クライアント設定だが、濫用を抑えるため実ドメインと
ローカル開発 URL のみに制限する。

```bash
gcloud services api-keys update f185ac73-ab70-486d-a139-3b821854afdf \
  --project=your-project-id \
  --allowed-referrers='https://gen-fashion-app.web.app/*,https://your-project-id.firebaseapp.com/*,http://localhost:8088/*'
```

---

## トラブルシューティング

### Elasticsearch が起動しない

```bash
# ログを確認
sudo journalctl -xeu elasticsearch.service --no-pager | tail -50

# 設定ファイルの競合を確認（cluster.initial_master_nodes と discovery.type:single-node は共存不可）
sudo grep -E "cluster.initial_master_nodes|discovery.type" /etc/elasticsearch/elasticsearch.yml
```

### シードスクリプトが Firestore エミュレータに接続しようとする

VM の `scripts/seed_shared_closet/.env` に `FIRESTORE_EMULATOR_HOST` が設定されている可能性がある。
本番シード時はコメントアウトする。

```bash
# VM 上で確認・修正
grep "FIRESTORE_EMULATOR" /home/ran/seed_shared_closet/.env
sed -i 's/^FIRESTORE_EMULATOR_HOST=/#FIRESTORE_EMULATOR_HOST=/' /home/ran/seed_shared_closet/.env
```

### Cloud Run が ES に接続できない

原因の多くは以下の 3 点。

1. `ELASTICSEARCH_URL` に内部 IP（静的割当）ではなく VM 名を使っている → 内部 IP を使うこと
2. Cloud Run のデプロイ時に `--network`/`--subnet`/`--vpc-egress=private-ranges-only` を省略している
3. ファイアウォールルール `allow-es-from-cloudrun` のソース範囲が subnet の CIDR と一致していない
4. ES 証明書を再生成したのに `ES_SSL_FINGERPRINT` / `ELASTICSEARCH_SSL_ASSERT_FINGERPRINT` を更新していない

```bash
# subnet の CIDR を確認（ファイアウォールルールと照合）
gcloud compute networks subnets describe default \
  --region=asia-northeast1 --format='value(ipCidrRange)'

# ES が :9200 で提示する leaf certificate fingerprint を IAP SSH 経由で取得
gcloud compute ssh gen-fashion-es \
  --zone=asia-northeast1-a --tunnel-through-iap \
  --command="echo | openssl s_client -connect localhost:9200 -servername 10.146.0.2 2>/dev/null | openssl x509 -fingerprint -sha256 -noout"

# Cloud Run に入っている fingerprint env を確認
gcloud run services describe fastapi-service \
  --region=asia-northeast1 \
  --format='value(spec.template.spec.containers[0].env[?name=ELASTICSEARCH_SSL_ASSERT_FINGERPRINT].value)'
```
