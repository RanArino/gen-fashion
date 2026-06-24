#!/usr/bin/env python3
"""
Seed the gen-fashion shared closet (M3-1, M3-2).

Usage:
    python run_seed.py [--max-items-per-category N] [--with-embeddings]
                       [--source-dir /path/to/images] [--purge]

Requires .env (copy from .env.example) or exported env vars.
Kaggle credentials: ~/.kaggle/kaggle.json  (skipped when --source-dir is given).
Vertex AI auth: ADC (gcloud auth application-default login) or
                GOOGLE_APPLICATION_CREDENTIALS pointing at a service-account JSON.
"""

import argparse
import csv
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("seed")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DATASET_SLUG = "agrigorev/clothing-dataset-full"
DATASET_KEY = f"kaggle:{DATASET_SLUG}"
ATTRIBUTION = "Clothing Dataset (CC BY-SA 4.0)"

# Labels to drop: low-quality/junk and non-styling innerwear.
# "Other" (singular) is the real dataset label; "Others" kept for safety.
# Undershirt/Body are underwear/innerwear with no styling value (per req §16.2).
_SKIP_LABELS = {"Not sure", "Skip", "Others", "Other", "null", "",
                "Undershirt", "Body"}

# Lightweight label → (category, season, colors) mapping
_LABEL_MAP: dict[str, dict] = {
    "Blazer":    {"category": "Blazer",   "season": "autumn", "colors": ["navy", "black"]},
    "Blouse":    {"category": "Blouse",   "season": "spring", "colors": ["white", "pink"]},
    "Dress":     {"category": "Dress",    "season": "summer", "colors": ["floral", "white"]},
    "Hoodie":    {"category": "Hoodie",   "season": "winter", "colors": ["grey", "black"]},
    "Longsleeve":{"category": "Longsleeve","season": "autumn","colors": ["white", "grey"]},
    "Outwear":   {"category": "Outwear",  "season": "winter", "colors": ["black", "brown"]},
    "Pants":     {"category": "Pants",    "season": "all",    "colors": ["black", "blue", "beige"]},
    "Polo":      {"category": "Polo",     "season": "spring", "colors": ["white", "navy"]},
    "Shirt":     {"category": "Shirt",    "season": "spring", "colors": ["white", "blue"]},
    "Shorts":    {"category": "Shorts",   "season": "summer", "colors": ["khaki", "navy"]},
    "Skirt":     {"category": "Skirt",    "season": "spring", "colors": ["black", "floral"]},
    "T-Shirt":   {"category": "T-Shirt",  "season": "summer", "colors": ["white", "black", "grey"]},
    "Top":       {"category": "Top",      "season": "spring", "colors": ["white", "stripes"]},
    "Undershirt":{"category": "Undershirt","season": "all",   "colors": ["white", "grey"]},
    "Hat":       {"category": "Hat",      "season": "summer", "colors": ["beige", "black"]},
    "Shoes":     {"category": "Shoes",    "season": "all",    "colors": ["white", "black"]},
}

# ---------------------------------------------------------------------------
# Demo closets (M3 re-scope, req §16). Instead of one large shared closet, seed
# a few realistic wardrobes. Gender is not in the dataset, so segment
# by the `kids` flag into adult/child. Items keep user_id="__shared__" and gain
# closetId/closetKind so the M5 picker can filter; the M3-3 adapter (queries all
# __shared__ items) is unaffected. Composition is automatic via category quotas.
# ---------------------------------------------------------------------------
_CLOSETS = [
    {"id": "adult-01", "kind": "adult", "displayName": "Adult Closet A"},
    {"id": "adult-02", "kind": "adult", "displayName": "Adult Closet B"},
    {"id": "child-01", "kind": "child", "displayName": "Kids Closet"},
]

# Base category-group quotas preserve the original 50-item wardrobes. Additions
# run only after every base wardrobe is built, so increasing frequently used
# separates never reassigns an existing item between the two adult closets.
_CLOSET_QUOTAS = {
    "adult": {"tops": 12, "outer": 7, "bottoms": 10, "dress": 8, "shoes": 8, "hat": 5},
    "child": {"tops": 15, "outer": 6, "bottoms": 12, "dress": 4, "shoes": 8, "hat": 5},
}

_CLOSET_ADDITIONS = {"tops": 10, "bottoms": 10}

# group → dataset labels feeding it (round-robined within a group for variety)
_CATEGORY_GROUPS = {
    "tops":    ["T-Shirt", "Shirt", "Longsleeve", "Polo", "Blouse", "Top"],
    "outer":   ["Outwear", "Blazer", "Hoodie"],
    "bottoms": ["Pants", "Shorts"],
    "dress":   ["Dress", "Skirt"],
    "shoes":   ["Shoes"],
    "hat":     ["Hat"],
}


def _label_meta(label: str) -> dict:
    entry = _LABEL_MAP.get(label, {})
    return {
        "category": entry.get("category", label),
        "season": entry.get("season", "all"),
        "colors": entry.get("colors", []),
        "tags": [entry.get("category", label).lower()],
    }


def _label_gender(label: str) -> str:
    return "female" if label.lower() in {"dress", "skirt", "blouse"} else "common"


def _item_id(filename: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{DATASET_KEY}:{filename}"))


# ---------------------------------------------------------------------------
# Dataset acquisition
# ---------------------------------------------------------------------------

def _find_images_dir(cache_dir: Path) -> Optional[Path]:
    """Locate the extracted images dir. clothing-dataset-full ships
    images_original/ (high-res, used per req §16.2) and images_compressed/
    (low-res, unused). Prefer the original."""
    for candidate in (cache_dir / "images_original", cache_dir / "images",
                      cache_dir / "images_compressed", cache_dir):
        if candidate.is_dir() and any(candidate.glob("*.jpg")):
            return candidate
    return None


def _download_kaggle(cache_dir: Path) -> Path:
    try:
        import kaggle  # noqa: F401 — triggers auth check
    except Exception as exc:
        log.error("Kaggle import failed: %s", exc)
        sys.exit(1)
    import subprocess
    cache_dir.mkdir(parents=True, exist_ok=True)
    # Cache hit must use the same probe as post-download: --unzip removes the
    # zip, so a name-mismatched check would re-download the whole (6.5 GB) set.
    cached = _find_images_dir(cache_dir)
    if cached is not None:
        log.info("Kaggle cache hit: %s", cached)
        return cached
    log.info("Downloading %s …", DATASET_SLUG)
    subprocess.run(
        ["kaggle", "datasets", "download", "-d", DATASET_SLUG,
         "--unzip", "-p", str(cache_dir)],
        check=True,
    )
    found = _find_images_dir(cache_dir)
    return found if found is not None else cache_dir


def _find_label_csv(*dirs: Path) -> Path:
    """Locate the dataset label CSV, trying the known names across candidate dirs.

    clothing-dataset-full ships labels as images.csv (columns: image, label, …).
    """
    names = ("images.csv", "image_labels_merged.csv", "image_labels.csv")
    for d in dirs:
        for name in names:
            p = d / name
            if p.exists():
                return p
    return dirs[0] / names[0]  # non-existent → _load_labels warns + falls back


def _load_labels(csv_path: Path) -> dict[str, str]:
    """Return {filename: label} from image_labels_merged.csv."""
    mapping: dict[str, str] = {}
    if not csv_path.exists():
        log.warning("Label CSV not found at %s; labels will be inferred from directory names", csv_path)
        return mapping
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fname = row.get("image") or row.get("filename") or row.get("image_id") or ""
            label = row.get("label") or row.get("category") or ""
            if fname and label and label not in _SKIP_LABELS:
                mapping[fname.strip()] = label.strip()
    log.info("Loaded %d labelled entries from CSV", len(mapping))
    return mapping


def _collect_samples(images_dir: Path, label_csv: Path, max_per_category: int) -> list[dict]:
    """Return list of {path, label, filename} capped per category."""
    labels = _load_labels(label_csv)
    by_category: dict[str, list[Path]] = {}

    if labels:
        for fname, label in labels.items():
            if label in _SKIP_LABELS:
                continue
            path = images_dir / fname
            if not path.exists():
                # Try with .jpg extension
                path = images_dir / (fname.rsplit(".", 1)[0] + ".jpg")
            if path.exists():
                by_category.setdefault(label, []).append(path)
    else:
        # Fallback: walk subdirectories as categories
        for sub in images_dir.iterdir():
            if sub.is_dir():
                label = sub.name
                if label in _SKIP_LABELS:
                    continue
                for img in sub.glob("*.jpg"):
                    by_category.setdefault(label, []).append(img)
        # Fallback: flat directory of .jpg files, use filename as label
        if not by_category:
            for img in sorted(images_dir.glob("*.jpg")):
                label = img.stem.rsplit("_", 1)[0] if "_" in img.stem else "Unknown"
                if label not in _SKIP_LABELS:
                    by_category.setdefault(label, []).append(img)

    samples = []
    for label, paths in sorted(by_category.items()):
        for p in sorted(paths)[:max_per_category]:
            samples.append({"path": p, "label": label, "filename": p.name})
    log.info("Collected %d samples across %d categories", len(samples), len(by_category))
    return samples


def _resolve_image_path(images_dir: Path, fname: str) -> Optional[Path]:
    p = images_dir / fname
    if p.exists():
        return p
    p = images_dir / (fname.rsplit(".", 1)[0] + ".jpg")
    return p if p.exists() else None


def _load_labels_full(csv_path: Path) -> dict[str, tuple[str, bool]]:
    """Return {filename: (label, is_kids)} from images.csv (cols: image, label, kids)."""
    mapping: dict[str, tuple[str, bool]] = {}
    if not csv_path.exists():
        log.warning("Label CSV not found at %s; cannot segment by adult/child", csv_path)
        return mapping
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fname = row.get("image") or row.get("filename") or row.get("image_id") or ""
            label = row.get("label") or row.get("category") or ""
            kids = str(row.get("kids", "")).strip().lower() in {"true", "1", "yes", "t"}
            if fname and label and label not in _SKIP_LABELS:
                mapping[fname.strip()] = (label.strip(), kids)
    log.info("Loaded %d labelled entries from CSV", len(mapping))
    return mapping


def _build_closets(images_dir: Path, label_csv: Path) -> list[dict]:
    """Build the _CLOSETS demo wardrobes with auto category-quota composition.

    Images are split by the dataset `kids` flag into adult/child pools and drawn
    deterministically (sorted, cursor-advanced) so closets of the same kind do
    not overlap. Returns a flat sample list, each tagged with closetId/closetKind.
    Idempotent: item_id derives from the filename, and each file maps to exactly
    one closet, so re-runs reproduce the same assignment.
    """
    labels = _load_labels_full(label_csv)
    if not labels:
        # Offline / no CSV: fall back to a single adult closet.
        flat = _collect_samples(images_dir, label_csv, max_per_category=30)[:30]
        log.warning("No CSV labels; built a single fallback closet of %d items", len(flat))
        return [{**s, "closetId": "adult-01", "closetKind": "adult"} for s in flat]

    pool: dict[str, dict[str, list[Path]]] = {"adult": {}, "child": {}}
    for fname, (label, kids) in labels.items():
        path = _resolve_image_path(images_dir, fname)
        if path is None:
            continue
        kind = "child" if kids else "adult"
        pool[kind].setdefault(label, []).append(path)
    for kind in pool:
        for paths in pool[kind].values():
            paths.sort()

    cursor: dict[tuple[str, str], int] = {}  # (kind, label) -> next unused index
    samples: list[dict] = []

    def append_groups(closet: dict, quotas: dict[str, int]) -> int:
        kind = closet["kind"]
        before = len(samples)
        for group, quota in quotas.items():
            group_labels = [l for l in _CATEGORY_GROUPS[group] if pool[kind].get(l)]
            picked = 0
            while picked < quota and group_labels:
                progressed = False
                for label in group_labels:
                    if picked >= quota:
                        break
                    idx = cursor.get((kind, label), 0)
                    paths = pool[kind][label]
                    if idx < len(paths):
                        p = paths[idx]
                        cursor[(kind, label)] = idx + 1
                        samples.append({
                            "path": p, "label": label, "filename": p.name,
                            "closetId": closet["id"], "closetKind": kind,
                        })
                        picked += 1
                        progressed = True
                if not progressed:
                    break  # group exhausted for this kind
        return len(samples) - before

    for closet in _CLOSETS:
        count = append_groups(closet, _CLOSET_QUOTAS[closet["kind"]])
        log.info("Closet %s (%s) base: %d items", closet["id"], closet["kind"], count)

    for closet in _CLOSETS:
        count = append_groups(closet, _CLOSET_ADDITIONS)
        log.info("Closet %s (%s) added separates: %d items", closet["id"], closet["kind"], count)

    log.info("Built %d closets, %d items total", len(_CLOSETS), len(samples))
    return samples


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def _make_s3(endpoint: str, access_key: str, secret_key: str):
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
    )


def _ensure_bucket(s3, bucket: str) -> None:
    from botocore.exceptions import ClientError
    try:
        s3.create_bucket(Bucket=bucket)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
            raise
    try:
        s3.put_bucket_cors(
            Bucket=bucket,
            CORSConfiguration={
                "CORSRules": [{
                    "AllowedHeaders": ["*"],
                    "AllowedMethods": ["GET", "PUT", "HEAD"],
                    "AllowedOrigins": ["*"],
                    "ExposeHeaders": ["ETag"],
                    "MaxAgeSeconds": 3000,
                }]
            },
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code != "NotImplemented":
            raise


def _r2_key(item_id: str) -> str:
    return f"__shared__/closet/{item_id}.jpg"


def _upload_image(s3, bucket: str, item_id: str, image_bytes: bytes) -> str:
    key = _r2_key(item_id)
    s3.put_object(Bucket=bucket, Key=key, Body=image_bytes, ContentType="image/jpeg")
    return key


def _normalize_jpeg(path: Path) -> bytes:
    from PIL import Image
    with Image.open(path) as img:
        img = img.convert("RGB")
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()


# ---------------------------------------------------------------------------
# Elasticsearch helpers
# ---------------------------------------------------------------------------

def _make_es_client(url: str, api_key: Optional[str] = None):
    from elasticsearch import Elasticsearch
    kwargs: dict = {"hosts": [url]}
    if api_key:
        kwargs["api_key"] = api_key
    return Elasticsearch(**kwargs)


def _ensure_es_index(es, index: str, dims: int = 768) -> None:
    if es.indices.exists(index=index):
        return
    es.indices.create(
        index=index,
        mappings={
            "properties": {
                "item_id":   {"type": "keyword"},
                "user_id":   {"type": "keyword"},
                "is_shared": {"type": "boolean"},
                "closetId":  {"type": "keyword"},
                "closetKind":{"type": "keyword"},
                "imageUrl":  {"type": "keyword"},
                "tags":      {"type": "keyword"},
                "category":  {"type": "keyword"},
                "colors":    {"type": "keyword"},
                "season":    {"type": "keyword"},
                "gender":    {"type": "keyword"},
                "embedding": {
                    "type": "dense_vector",
                    "dims": dims,
                    "index": True,
                    "similarity": "cosine",
                },
            }
        },
    )
    log.info("Created ES index: %s", index)


def _es_upsert(es, index: str, item_id: str, doc: dict) -> bool:
    """Return True if newly created, False if updated."""
    result = es.index(index=index, id=item_id, document=doc)
    return result.get("result") == "created"


# ---------------------------------------------------------------------------
# Firestore helpers
# ---------------------------------------------------------------------------

def _make_firestore(project: str, emulator_host: Optional[str]):
    from google.cloud import firestore
    if emulator_host:
        os.environ["FIRESTORE_EMULATOR_HOST"] = emulator_host
    return firestore.Client(project=project)


def _firestore_set(db, item_id: str, doc: dict) -> None:
    db.collection("shared_closet").document(item_id).set(doc)


def _firestore_set_closet_meta(db, closet_id: str, meta: dict) -> None:
    db.collection("shared_closets").document(closet_id).set(meta)


# ---------------------------------------------------------------------------
# Embedding helper (Vertex AI)
# ---------------------------------------------------------------------------

def _embed_text(text: str, project: str, location: str) -> list[float]:
    # Embed the item's text attributes (not the image): the M5 search query is a
    # text description, so index vectors must share the text embedding space.
    # gemini-embedding-001 is text-only; ES `cosine` similarity needs no manual
    # normalization. RETRIEVAL_DOCUMENT pairs with the query's RETRIEVAL_QUERY.
    import google.genai as genai
    import google.genai.types as gtypes
    client = genai.Client(vertexai=True, project=project, location=location)
    response = client.models.embed_content(
        model="gemini-embedding-001",
        contents=[text],
        config=gtypes.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=768,
        ),
    )
    return response.embeddings[0].values


def _embedding_text(meta: dict) -> str:
    parts = [
        meta.get("category", ""),
        " ".join(meta.get("colors", [])),
        " ".join(meta.get("tags", [])),
        meta.get("season", ""),
    ]
    return ". ".join(part for part in parts if part)


# ---------------------------------------------------------------------------
# Purge
# ---------------------------------------------------------------------------

def _purge(es, index: str, s3, bucket: str, db) -> None:
    log.info("Purging __shared__ data …")
    # ES: delete by query
    if es.indices.exists(index=index):
        result = es.delete_by_query(
            index=index,
            body={"query": {"term": {"user_id": "__shared__"}}},
        )
        log.info("ES deleted: %s", result.get("deleted", 0))
    else:
        log.info("ES index %s does not exist; nothing to purge", index)
    # MinIO: list + delete objects under __shared__/closet/
    paginator = s3.get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=bucket, Prefix="__shared__/closet/"):
        keys += [obj["Key"] for obj in page.get("Contents", [])]
    if keys:
        s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": k} for k in keys]})
        log.info("R2/MinIO deleted: %d objects", len(keys))
    # Firestore: clear both the item collection and the closet-metadata collection
    count = 0
    for coll_name in ("shared_closet", "shared_closets"):
        coll = db.collection(coll_name)
        batch = db.batch()
        n = 0
        for doc in coll.list_documents():
            batch.delete(doc)
            n += 1
            if n % 400 == 0:
                batch.commit()
                batch = db.batch()
        batch.commit()
        count += n
    log.info("Firestore deleted: %d docs", count)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the gen-fashion shared closet.")
    parser.add_argument("--max-items-per-category", type=int,
                        default=int(os.getenv("MAX_ITEMS_PER_CATEGORY", "150")))
    parser.add_argument("--with-embeddings", action="store_true",
                        help="Generate Gemini embeddings via Vertex AI (deployment only by default)")
    parser.add_argument("--source-dir", type=Path,
                        help="Skip Kaggle download; read images from this directory")
    parser.add_argument("--purge", action="store_true",
                        help="Delete all __shared__ data and exit")
    args = parser.parse_args()

    # --- Config ---
    es_url        = os.environ["ELASTICSEARCH_URL"]
    es_api_key    = os.getenv("ELASTICSEARCH_API_KEY")
    r2_endpoint   = os.environ["R2_ENDPOINT_URL"]
    r2_access_key = os.environ["R2_ACCESS_KEY_ID"]
    r2_secret_key = os.environ["R2_SECRET_ACCESS_KEY"]
    r2_bucket     = os.getenv("R2_BUCKET_NAME", "gen-fashion-images")
    firestore_emu = os.getenv("FIRESTORE_EMULATOR_HOST")
    # Vertex AI (embeddings) needs a project with aiplatform access. Firestore
    # data must land in the Firebase project (same emulator namespace the app +
    # frontend use), which differs from the Vertex project in local dev. In
    # production all three are the same project, so this collapses to one value.
    gcp_project       = os.getenv("GOOGLE_CLOUD_PROJECT", "gen-fashion-local")
    firestore_project = os.getenv("FIREBASE_PROJECT_ID") or gcp_project
    gcp_location      = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    es_index      = "clothing_items"

    # --- Clients ---
    es = _make_es_client(es_url, es_api_key)
    s3 = _make_s3(r2_endpoint, r2_access_key, r2_secret_key)
    _ensure_bucket(s3, r2_bucket)
    db = _make_firestore(firestore_project, firestore_emu)

    if args.purge:
        _purge(es, es_index, s3, r2_bucket, db)
        return

    _ensure_es_index(es, es_index)

    # --- Dataset acquisition ---
    if args.source_dir:
        images_dir = args.source_dir.resolve()
        label_csv = _find_label_csv(images_dir, images_dir.parent)
    else:
        cache_dir = Path(__file__).parent / ".dataset_cache"
        images_dir = _download_kaggle(cache_dir)
        label_csv = _find_label_csv(cache_dir, images_dir, images_dir.parent)

    samples = _build_closets(images_dir, label_csv)
    if not samples:
        log.error("No samples found. Check --source-dir or Kaggle download.")
        sys.exit(1)

    # --- Seeding loop ---
    created = skipped = errors = 0
    total = len(samples)
    for i, sample in enumerate(samples, 1):
        item_id = _item_id(sample["filename"])
        label   = sample["label"]
        meta    = _label_meta(label)
        gender  = _label_gender(label)

        try:
            image_bytes = _normalize_jpeg(sample["path"])
        except Exception as exc:
            log.warning("[%d/%d] Skip %s (image error: %s)", i, total, sample["filename"], exc)
            errors += 1
            continue

        # R2 / MinIO upload (idempotent by key)
        try:
            _upload_image(s3, r2_bucket, item_id, image_bytes)
            r2_key = _r2_key(item_id)
        except Exception as exc:
            log.warning("[%d/%d] R2 upload failed for %s: %s", i, total, item_id, exc)
            errors += 1
            continue

        # Embedding (deployment only)
        embedding = None
        if args.with_embeddings:
            try:
                embedding = _embed_text(_embedding_text(meta), gcp_project, gcp_location)
            except Exception as exc:
                log.warning("[%d/%d] Embedding failed for %s: %s", i, total, item_id, exc)
                # Degrade gracefully — still index without vector

        # ES upsert
        es_doc: dict = {
            "item_id":    item_id,
            "user_id":    "__shared__",
            "is_shared":  True,
            "closetId":   sample["closetId"],
            "closetKind": sample["closetKind"],
            "imageUrl":   r2_key,
            "tags":       meta["tags"],
            "category":   meta["category"],
            "colors":     meta["colors"],
            "season":     meta["season"],
            "gender":     gender,
        }
        if embedding is not None:
            es_doc["embedding"] = embedding
        is_new = _es_upsert(es, es_index, item_id, es_doc)

        # Firestore set (idempotent)
        fs_doc = {
            "imageUrl":      r2_key,
            "closetId":      sample["closetId"],
            "closetKind":    sample["closetKind"],
            "category":      meta["category"],
            "tags":          meta["tags"],
            "season":        meta["season"],
            "colors":        meta["colors"],
            "gender":        gender,
            "embeddingId":   item_id,
            "datasetSource": f"kaggle:{DATASET_SLUG}",
            "originalLabel": label,
            "createdAt":     datetime.now(timezone.utc).isoformat(),
        }
        _firestore_set(db, item_id, fs_doc)

        if is_new:
            created += 1
        else:
            skipped += 1

        if i % 50 == 0 or i == total:
            log.info("[%d/%d] created=%d skipped=%d errors=%d", i, total, created, skipped, errors)

    # --- Closet metadata (for the M5 picker) ---
    per_closet: dict[str, int] = {}
    for s in samples:
        per_closet[s["closetId"]] = per_closet.get(s["closetId"], 0) + 1
    for closet in _CLOSETS:
        cid = closet["id"]
        if per_closet.get(cid):
            _firestore_set_closet_meta(db, cid, {
                "kind":          closet["kind"],
                "displayName":   closet["displayName"],
                "itemCount":     per_closet[cid],
                "datasetSource": f"kaggle:{DATASET_SLUG}",
                "createdAt":     datetime.now(timezone.utc).isoformat(),
            })

    summary = {
        "total_samples": total,
        "created":  created,
        "skipped":  skipped,
        "errors":   errors,
        "closets":  per_closet,
        "with_embeddings": args.with_embeddings,
    }
    print(json.dumps(summary, indent=2))
    log.info("Done. %s", summary)


if __name__ == "__main__":
    main()
