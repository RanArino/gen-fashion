# GCP 運用コマンド集 — gen-fashion

このドキュメントはプロジェクトに対してよく使う `gcloud` コマンドをまとめたもの。
作業のたびに随時追加・更新すること。

## 前提設定

```bash
# プロジェクトとデフォルトリージョンを設定（これをやっておくと --project / --region を毎回省略できる）
gcloud config set project animation-agent
gcloud config set compute/region asia-northeast1
gcloud config set compute/zone asia-northeast1-a

# 現在の設定を確認
gcloud config list
```

---

## Compute Engine — Elasticsearch VM

VM 名: `gen-fashion-es` / ゾーン: `asia-northeast1-a`

> **コスト方針:** 使っていないときは止めることを推奨。課金は `pd-balanced` ディスク（約 $3/月）のみになる。
> 夜間 (JST 02:00) は `es-night-off` スケジュールで自動停止、08:00 に自動起動。

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
ES_API=$(gcloud secrets versions access latest --secret=ELASTICSEARCH_API_KEY --project=animation-agent)
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
ES_API=$(gcloud secrets versions access latest --secret=ELASTICSEARCH_API_KEY --project=animation-agent)
R2_KEY=$(gcloud secrets versions access latest --secret=R2_ACCESS_KEY_ID --project=animation-agent)
R2_SECRET=$(gcloud secrets versions access latest --secret=R2_SECRET_ACCESS_KEY --project=animation-agent)
TASK_SECRET=$(gcloud secrets versions access latest --secret=INTERNAL_TASK_SECRET --project=animation-agent)

# 登録済みシークレット一覧
gcloud secrets list --project=animation-agent

# 新しいシークレットを登録（値はファイル経由で渡す — echo でパイプするとシェル履歴に残る）
printf '%s' "<値>" | gcloud secrets create <SECRET_NAME> --data-file=- --project=animation-agent

# 既存シークレットに新しいバージョンを追加
printf '%s' "<新しい値>" | gcloud secrets versions add <SECRET_NAME> --data-file=- --project=animation-agent
```

---

## ファイアウォールルール

```bash
# 現在のルール一覧（gen-fashion 関連のみ）
gcloud compute firewall-rules list --filter="name:gen-fashion OR name:allow-es" \
  --format="table(name,direction,sourceRanges,allowed)"

# ES への許可ルール詳細確認
gcloud compute firewall-rules describe allow-es-from-cloudrun
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

---

## Artifact Registry（Milestone C 以降）

```bash
REPO=asia-northeast1-docker.pkg.dev/animation-agent/gen-fashion

# イメージ一覧
gcloud artifacts docker images list $REPO/fastapi-service --include-tags
gcloud artifacts docker images list $REPO/adk-agent-service --include-tags

# ローカルから Docker 認証（初回のみ）
gcloud auth configure-docker asia-northeast1-docker.pkg.dev
```

### Cloud Build でイメージをビルド & プッシュ

```bash
REPO=asia-northeast1-docker.pkg.dev/animation-agent/gen-fashion
IMAGE_TAG=md-$(date +%Y%m%d-%H%M)

# 両サービスを並行ビルド（ターミナル2枚で同時実行 or & でバックグラウンド）
gcloud builds submit fastapi-service --tag $REPO/fastapi-service:$IMAGE_TAG --project=animation-agent
gcloud builds submit adk-agent-service --tag $REPO/adk-agent-service:$IMAGE_TAG --project=animation-agent
```

### イメージタグを使った再デプロイ（コード修正後のロールアウト）

```bash
# 現在のタグを確認してから最新イメージで更新
REPO=asia-northeast1-docker.pkg.dev/animation-agent/gen-fashion
NEW_TAG=md-$(date +%Y%m%d-%H%M)

bash scripts/deploy/deploy_adk.sh \
  --project animation-agent --region asia-northeast1 \
  --image "$REPO/adk-agent-service:$NEW_TAG" \
  --es-internal-ip 10.146.0.2 \
  --r2-endpoint-url https://251f1f3bfe0fba6b30914150579f34b5.r2.cloudflarestorage.com \
  --r2-public-endpoint-url https://251f1f3bfe0fba6b30914150579f34b5.r2.cloudflarestorage.com \
  --r2-bucket-name gen-fashion-images

ADK_URL=$(gcloud run services describe adk-agent-service --region=asia-northeast1 --format='value(status.url)')
FASTAPI_URL=$(gcloud run services describe fastapi-service --region=asia-northeast1 --format='value(status.url)')
bash scripts/deploy/deploy_fastapi.sh \
  --project animation-agent --region asia-northeast1 \
  --image "$REPO/fastapi-service:$NEW_TAG" \
  --adk-url "$ADK_URL" --fastapi-url "$FASTAPI_URL" \
  --es-internal-ip 10.146.0.2 \
  --r2-endpoint-url https://251f1f3bfe0fba6b30914150579f34b5.r2.cloudflarestorage.com \
  --r2-public-endpoint-url https://251f1f3bfe0fba6b30914150579f34b5.r2.cloudflarestorage.com \
  --r2-bucket-name gen-fashion-images
```

### クリーンアップポリシー（最新 3 タグのみ保持）

```bash
gcloud artifacts repositories set-cleanup-policies gen-fashion \
  --project=animation-agent --location=asia-northeast1 \
  --policy='[{"name":"keep-recent","action":{"type":"Keep"},"mostRecentVersions":{"keepCount":3}}]'
```

---

## Cloud Tasks（Milestone C 以降）

```bash
# キュー一覧・状態確認
gcloud tasks queues list --location=asia-northeast1 --project=animation-agent

# キュー詳細（バックログ件数、レート制限など）
gcloud tasks queues describe gen-fashion-embed \
  --location=asia-northeast1 --project=animation-agent

# タスク一覧（滞留しているタスクがないか確認）
gcloud tasks list --queue=gen-fashion-embed \
  --location=asia-northeast1 --project=animation-agent
```

---

## Flutter Web ビルド & Firebase Hosting（Milestone D 以降）

```bash
# 本番ビルド（credentials/firebase-sdk.md の値を使う）
cd flutter-web-app
flutter build web --release \
  --dart-define=API_BASE_URL=https://fastapi-service-hvwhpzcehq-an.a.run.app \
  --dart-define=USE_EMULATORS=false \
  --dart-define=FIREBASE_PROJECT_ID=animation-agent \
  --dart-define=FIREBASE_API_KEY=AIzaSyDWx1gLxdKy3MHmMlQpWjHtTo5mKEsKyEc \
  --dart-define=FIREBASE_APP_ID=1:789766161934:web:e894240fca5dc80b9ede5f \
  --dart-define=FIREBASE_MESSAGING_SENDER_ID=789766161934 \
  --dart-define=FIREBASE_AUTH_DOMAIN=animation-agent.firebaseapp.com \
  --dart-define=FIREBASE_STORAGE_BUCKET=animation-agent.firebasestorage.app
cd ..

# Firebase Hosting にデプロイ
firebase deploy --only hosting --project animation-agent

# デプロイ後の公開 URL
# https://animation-agent.web.app
# https://gen-fashion-app.web.app
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
const project = 'animation-agent';
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

---

## Firestore

```bash
# TTL ポリシーの確認（agentEvents コレクションの ttlAt フィールド）
gcloud firestore fields ttls list --project=animation-agent

# TTL ポリシーを有効化（Milestone E）
gcloud firestore fields ttls update ttlAt \
  --collection-group=agentEvents --enable-ttl --project=animation-agent
```

---

## よく使う確認コマンド（ワンライナー）

```bash
# VM の状態・内部 IP・外部 IP をまとめて確認
gcloud compute instances describe gen-fashion-es --zone=asia-northeast1-a \
  --format='table(name,status,networkInterfaces[0].networkIP,networkInterfaces[0].accessConfigs[0].natIP)'

# Secret Manager の全シークレット名と更新日時
gcloud secrets list --project=animation-agent \
  --format='table(name,updateTime)'

# 有効な API 一覧（デプロイに必要な API が全部 enabled か確認）
gcloud services list --enabled --project=animation-agent \
  --filter="name:(run OR artifactregistry OR cloudbuild OR secretmanager OR cloudtasks OR compute OR firestore OR aiplatform OR logging OR iamcredentials)" \
  --format='value(name)'

# Cloud Run サービス 2 本の稼働状況まとめ確認
gcloud run services list --region=asia-northeast1 --project=animation-agent \
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
PROJECT=animation-agent
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
  --attribute-condition="assertion.repository=='${GITHUB_REPO}'"

# 3. デプロイ用 SA を作成してロールを付与
gcloud iam service-accounts create github-deployer \
  --display-name="GitHub Actions Deployer" \
  --project=${PROJECT}

# Cloud Run デプロイ + IAM バインディング変更
gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:github-deployer@${PROJECT}.iam.gserviceaccount.com" \
  --role=roles/run.admin

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
| `WIF_SA` | `github-deployer@animation-agent.iam.gserviceaccount.com` |
| `ES_INTERNAL_IP` | `10.146.0.2` |
| `R2_ENDPOINT_URL` | `https://251f1f3bfe0fba6b30914150579f34b5.r2.cloudflarestorage.com` |
| `R2_PUBLIC_ENDPOINT_URL` | `https://251f1f3bfe0fba6b30914150579f34b5.r2.cloudflarestorage.com` |
| `R2_BUCKET_NAME` | `gen-fashion-images` |
| `FIREBASE_API_KEY` | Firebase SDK config の `apiKey`（credentials/firebase-sdk.md 参照） |
| `FIREBASE_APP_ID` | Firebase SDK config の `appId` |
| `FIREBASE_MESSAGING_SENDER_ID` | `789766161934` |
| `FIREBASE_AUTH_DOMAIN` | `animation-agent.firebaseapp.com` |
| `FIREBASE_STORAGE_BUCKET` | `animation-agent.firebasestorage.app` |

### GitHub Actions 環境（production）の設定（任意）

GitHub repo → Settings → Environments → New environment → 名前: `production`
Required reviewers を設定するとマニュアル承認フローになる。

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

```bash
# subnet の CIDR を確認（ファイアウォールルールと照合）
gcloud compute networks subnets describe default \
  --region=asia-northeast1 --format='value(ipCidrRange)'
```
