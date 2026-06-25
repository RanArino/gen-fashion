# Shared Closet Seed Script (M3-1)

Seeds the gen-fashion **demo closets** from the [Clothing Dataset (CC BY-SA 4.0)](https://www.kaggle.com/datasets/agrigorev/clothing-dataset-full) into the three data stores used by the app.

Instead of one giant shared closet, the script builds **3 realistic ~30-item wardrobes** (req §16):
`adult-01`, `adult-02` (from `kids=false`) and `child-01` (from `kids=true`) — gender is not in the
dataset, so we segment by the `kids` flag. Each closet is composed automatically by category quota
(tops/outer/bottoms/dress/shoes/hat). All items keep `user_id:"__shared__"` and carry `closetId`/
`closetKind`; per-closet metadata is written to Firestore `shared_closets/{closetId}`. The M5 picker
filters by `closetId`; the M3-3 adapter (returns all `__shared__`) is unchanged. Uses the high-res
`images_original/`.

## Requirements

- Python 3.11+
- Kaggle API token at `~/.kaggle/kaggle.json` (skip with `--source-dir`)
- `make dev` running locally (ES :9200, MinIO :9000, Firestore emulator :8080)

## Setup

```bash
cd scripts/seed_shared_closet
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # adjust if needed; defaults match make dev
```

## Seed (recommended for dev)

```bash
python run_seed.py
```

Builds the 3 demo closets (~90 items total). Expected summary:
`{"created": 90, "skipped": 0, "errors": 0, "closets": {"adult-01": 30, "adult-02": 30, "child-01": 30}}`.

Verify the three stores:

```bash
# ES: shared docs by closet (expect adult-01 / adult-02 / child-01, ~30 each)
curl -s 'http://localhost:9200/clothing_items/_search' -H 'Content-Type: application/json' \
  -d '{"size":0,"query":{"term":{"user_id":"__shared__"}},
       "aggs":{"by_closet":{"terms":{"field":"closetId"}}}}'

# MinIO objects: open http://localhost:9001 (minioadmin / minioadmin)
#   -> gen-fashion-images bucket -> __shared__/closet/

# Firestore (no UI; the google/cloud-sdk emulator exposes REST on :8080):
curl -s 'http://localhost:8080/v1/projects/gen-fashion-local/databases/(default)/documents/shared_closets'
```

Idempotency check — second run should show `created: 0`:

```bash
python run_seed.py
```

## Offline / CI (no Kaggle creds)

```bash
python run_seed.py --source-dir /path/to/local/images --max-items-per-category 20
```

The directory may be flat (all `.jpg` files) or structured as `<category>/image.jpg`.
Drop an `image_labels_merged.csv` alongside the images for accurate labels.

## Deployment-phase full seed (GCE Elasticsearch + embeddings)

```bash
# Set GOOGLE_APPLICATION_CREDENTIALS or ensure ADC is configured for Vertex AI
python run_seed.py --max-items-per-category 150 --with-embeddings
```

This is the M1-3 deferred full seed; the script is unchanged — only config differs.

## Purge

```bash
python run_seed.py --purge    # deletes all __shared__ data from ES, MinIO, Firestore
```

## Data written

| Store     | Key / Path                                  | Notes                              |
|-----------|---------------------------------------------|------------------------------------|
| MinIO/R2  | `__shared__/closet/{item_id}.jpg`           | JPEG, normalized to RGB            |
| ES index  | `clothing_items` with `user_id:"__shared__"`| + `closetId` / `closetKind`. Same index as personal closet |
| Firestore | `shared_closet/{item_id}`                   | `imageUrl`, `closetId`, `closetKind`, `category`, `tags`, … |
| Firestore | `shared_closets/{closetId}`                 | closet metadata: `kind`, `displayName`, `itemCount` |

`item_id` is `uuid5(NAMESPACE_URL, "kaggle:agrigorev/clothing-dataset-full:{filename}")` —
deterministic so all three writes are idempotent upserts.

## Attribution

Images are from the [Clothing Dataset](https://www.kaggle.com/datasets/agrigorev/clothing-dataset-full)
by Alexey Grigorev, licensed under **CC BY-SA 4.0**.
The app surfaces this attribution as required by the licence.
