# Gen Fashion

[English](README.md)

Gen Fashion は、手持ち服の写真からデジタルクローゼットを作り、AI エージェントが提案した
コーディネート候補をユーザーが確認し、承認したアイテムだけを使って最終コーディネート画像を生成する
ファッション支援サービスです。自分の服を起点に、楽天の商品検索で不足アイテムを補う Assisted Coordinate
にも対応しています。

公開アプリ: https://gen-fashion-app.web.app

![gen-fashion system architecture](docs/assets/system-architecture.svg)

## サービスの流れ

中心となる体験は、ユーザーの選択を明示的に挟む設計にしています。

1. Firebase Authentication でログインする。
2. 手持ち服の写真をアップロードし、自分のクローゼットを作る。
3. Gemini で各アイテムを分析し、Firestore と Elasticsearch に検索用メタデータを保存する。
4. 自分のクローゼット、共有デモクローゼット、または Assisted Coordinate からスタイリングを開始する。
5. ADK エージェントが候補アイテムを検索し、そのツール実行の流れを SSE で Flutter の Accordion UI に表示する。
6. 候補選択ゲートで一時停止し、ユーザーが使うアイテムを承認する。
7. 承認済みアイテムだけを使って Nano Banana が最終コーディネート画像を生成し、履歴に保存する。

候補選択ゲートは UI 上の演出ではなく、ドメイン上の制約として扱っています。ユーザーが候補アイテムを承認するまで、
最終コーディネート画像は生成されません。

## アーキテクチャ

リポジトリは ports-and-adapters 構成を意識して分割しています。ユーザー向け API、長時間実行される
agent runtime、storage adapter、外部 service integration を分離し、それぞれを個別に検証・デプロイできるようにしています。

- `flutter-web-app/`: Flutter Web クライアント。認証、クローゼット管理、スタイリングセッション、履歴、共有クローゼット、Assisted Coordinate。
- `fastapi-service/`: REST API、セッション制御、クローゼット Use Case、署名付き upload/download URL、Cloud Tasks worker route、Firestore / Elasticsearch / R2 adapters。
- `adk-agent-service/`: Python Google ADK runtime。オーケストレーション agent、ClosetAgent、StylingAgent、Rakuten search、画像生成 tool、event persistence。
- `scripts/seed_shared_closet/`: 共有デモクローゼットを Firestore、Elasticsearch、R2/MinIO に投入する seed pipeline。
- `scripts/deploy/`: Cloud Run、Firebase Hosting、Firestore indexes、teardown の deployment helpers。

詳細な構成は [docs/architecture-overview.md](docs/architecture-overview.md) にまとめています。README では、リポジトリに残している
2 つの Draw.io export、[system-architecture.svg](docs/assets/system-architecture.svg) と
[agent-flow.svg](docs/assets/agent-flow.svg) を掲載しています。

### エージェントオーケストレーション

agent flow は、提案と生成を分けています。検索・推薦 tool が先に動き、session はユーザー選択で一時停止し、
画像生成は承認済みアイテムだけを入力として実行されます。

![gen-fashion agent orchestration](docs/assets/agent-flow.svg)

## 技術スタック

| Area | Technology | Role |
|---|---|---|
| Frontend | Flutter Web, Dart | 認証済み Web UI、クローゼット管理、スタイリングフロー |
| Auth / Hosting | Firebase Authentication, Firebase Hosting | ログインと Web 配信 |
| API | Python 3.11, FastAPI, Pydantic | REST API、Use Case、Adapter |
| Agent runtime | Google ADK, google-genai | 複数エージェントの orchestration と tool call |
| AI models | Gemini, Nano Banana | 画像分析、embedding、コーディネート画像生成 |
| Search | Elasticsearch 8.x | 服アイテムの keyword + vector hybrid search |
| Database | Cloud Firestore | ユーザー、クローゼット metadata、sessions、agent events |
| Object storage | Cloudflare R2, MinIO locally | 服画像と生成画像 |
| Async work | Cloud Tasks, local HTTP queue | アップロード後の非同期分析 |
| External API | Rakuten Ichiba API | Assisted shopping suggestions |
| Infrastructure | Cloud Run, Compute Engine, Secret Manager | 本番 runtime と secret 管理 |
| CI/CD | GitHub Actions, Workload Identity Federation | test gate と本番 deploy workflow |
| Local dev | Docker Compose, Firebase emulators, MinIO | 再現可能なローカル stack |

## 本番構成

本番は Firebase Hosting と 2 つの Cloud Run service で構成しています。

- `fastapi-service` は public API です。Web client から呼ばれる route は Firebase Auth で保護し、内部 worker route は別途保護しています。
- `adk-agent-service` は private service です。FastAPI から agent run を起動します。

状態とメディアは責務ごとに分離しています。

- Firestore: クローゼット metadata、session state、proposed candidates、selected items、generated results、agent events。
- Elasticsearch: 外部 IP を持たない Compute Engine VM 上で稼働。Cloud Run から Direct VPC egress と制限した firewall rule で到達する。
- Cloudflare R2: アップロード服画像と生成コーディネート画像。
- Secret Manager / GitHub Actions secrets: 本番 credential。

運用コマンドは [docs/gcp-cheatsheet.md](docs/gcp-cheatsheet.md) にまとめています。公開デモ期間中は、可用性を優先して
Elasticsearch VM の夜間停止スケジュールを 2026-08-31 まで外しています。

## ローカル開発

ローカルのフル stack を起動します。

```bash
cp .env.example .env
make dev
make web
```

主な local services:

- FastAPI: `localhost:8000`
- ADK agent service: `localhost:3000`
- Elasticsearch: `localhost:9200`
- Firestore emulator: `localhost:8080`
- Firebase Auth emulator: `localhost:9099`
- MinIO: `localhost:9000` / console `localhost:9001`
- Flutter Web: `localhost:8088`

詳細は [README_LOCAL_DEV.md](README_LOCAL_DEV.md) を参照してください。

## 検証

代表的な検証コマンドです。

```bash
# Backend tests
cd fastapi-service && pytest -q

# Agent service tests
cd adk-agent-service && pytest -q

# Flutter checks
cd flutter-web-app && flutter analyze && flutter test

# Firestore security rules
cd firebase && npm install && firebase emulators:exec --only firestore --project gen-fashion-local "npm test"
```

CI/CD workflow には FastAPI tests、ADK tests、Flutter analyze/test、deployment-script tests を定義しています。
本番 deploy job は、両 service image の build、Cloud Run deploy、Firestore index deploy、Flutter Web build、
Firebase Hosting deploy、post-deploy smoke check までを行う構成です。直近確認した `main` workflow run は成功済みで、
残る CI/CD work は MF-5 と MF-6 で追跡しています。CI での認証付き coordination smoke と、専用 pipeline runbook です。

## 開発と設計記録

設計判断と実装状況は docs-as-code で管理しています。

- [docs/feature-matrix-phase01.md](docs/feature-matrix-phase01.md): Phase 1 requirements and status。
- [docs/feature-matrix-phase02.md](docs/feature-matrix-phase02.md): Phase 2 requirements and status。
- [docs/architecture-overview.md](docs/architecture-overview.md): system architecture と implemented/planned の境界。
- [docs/plans/](docs/plans): 大きめの機能、deployment、hardening の ExecPlans。
- [CONTRIBUTING.md](CONTRIBUTING.md): branch model、PR flow、CI expectations。

変更は Use Case 境界に寄せ、Cloud Tasks、Firestore access、Elasticsearch mappings、frontend session recovery など、
障害になりやすい経路には regression coverage を追加しています。

## リポジトリ構成

| Path | Purpose |
|---|---|
| `flutter-web-app/` | Flutter Web client |
| `fastapi-service/` | Public API and application use cases |
| `adk-agent-service/` | Google ADK agent runtime and tools |
| `firebase/` | Firebase emulator and security rules tests |
| `scripts/deploy/` | Deployment and teardown helpers |
| `scripts/seed_shared_closet/` | Shared closet dataset seeding |
| `docs/` | Requirements, architecture, plans, operations |
| `poc/` | AI and connectivity proof-of-concept scripts |

## License

このリポジトリには open-source license を設定していません。個別に明記されたファイルやディレクトリを除き、
source code と project documentation は [all rights reserved](LICENSE) です。

Third-party datasets、sample inputs、generated media、external service assets は、このリポジトリによって再ライセンスされません。
共有デモクローゼットの seed は Alexey Grigorev's Clothing Dataset（CC BY-SA 4.0）を使用しています。帰属表示については
[seed script README](scripts/seed_shared_closet/README.md) を参照してください。

外部提出物には別条件が適用される場合があります。このプロジェクトの ProtoPedia submission は ProtoPedia 上で
Creative Commons Attribution CC BY 4.0 or later としてライセンスされていますが、それは ProtoPedia に提出した素材に適用されるもので、
このリポジトリの source code には適用されません。
