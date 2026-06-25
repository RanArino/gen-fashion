#!/usr/bin/env python3
"""
M1-1 Coordinate Image Generation PoC — gen-fashion

Goal (req-phase01 §6.5 / ADL-005): given the user's own clothing photos as INPUT,
generate an image of a person wearing those clothes as one coordinated outfit
(virtual try-on).

M1-2 outcome (2026-06-03): Nano Banana (Gemini image model) reproduces the input
garments faithfully on a person. Imagen subject-customization does NOT — it
recontextualises a single product and ignores multi-garment try-on — so Imagen was
dropped from the PoC. See the Decision Log in
docs/plans/20260518-m1-poc-infrastructure-validation.md.

Usage:
    pip install -r requirements.txt
    cp .env.example .env                 # fill in GOOGLE_CLOUD_PROJECT
    # put real garment photos in samples/ (e.g. shirt.jpg, pants.jpg)
    python run_poc.py

Auth: gcloud auth application-default login   (Vertex AI — default)
      or set GOOGLE_GENAI_API_KEY             (Gemini Developer API)

Outputs (results/, git-ignored):
    nanobanana_result.jpg   — generated try-on image
    collage_result.jpg      — fallback collage, only if generation fails (ADL-005)
    summary.json            — success + wall-clock time
    nanobanana_error.txt    — error detail if the call fails
"""

import os
import sys
import json
import time
import mimetypes
from pathlib import Path

from dotenv import load_dotenv

_HERE = Path(__file__).parent
load_dotenv(_HERE / ".env")

SAMPLES = _HERE / "samples"
RESULTS = _HERE / "results"
RESULTS.mkdir(exist_ok=True)

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
API_KEY = os.environ.get("GOOGLE_GENAI_API_KEY")

# Nano Banana = Google's Gemini image model (natively accepts reference images).
#   gemini-2.5-flash-image     — Nano Banana 1 (fast, us-central1)        ← PoC default
#   gemini-3-pro-image-preview — Nano Banana 2/Pro (best; needs GOOGLE_CLOUD_LOCATION=global)
NANOBANANA_MODEL = os.environ.get("NANOBANANA_MODEL", "gemini-2.5-flash-image")

_TRYON_PROMPT = (
    "Generate a realistic full-body fashion photo of a single person wearing all of "
    "the provided clothing items together as one coordinated outfit. Keep each "
    "garment's color, pattern, and shape faithful to the reference photos. Studio "
    "background, soft even lighting, natural pose."
)


def _genai_client():
    """Build a google-genai client: Vertex AI when a project is set, else API key."""
    from google import genai
    if PROJECT:
        return genai.Client(vertexai=True, project=PROJECT, location=LOCATION)
    if API_KEY:
        return genai.Client(api_key=API_KEY)
    sys.exit("ERROR: set GOOGLE_CLOUD_PROJECT (Vertex AI) or GOOGLE_GENAI_API_KEY in .env.")


def _load_samples() -> list[tuple[bytes, str]]:
    """Return [(image_bytes, mime_type)] for every garment photo in samples/."""
    files = sorted(
        p for p in SAMPLES.iterdir()
        if p.suffix.lower() in (".jpg", ".jpeg", ".png")
    )
    if not files:
        sys.exit(
            f"ERROR: no garment photos in {SAMPLES}.\n"
            "Add real clothing photos (e.g. shirt.jpg, pants.jpg) before running."
        )
    return [(p.read_bytes(), mimetypes.guess_type(p.name)[0] or "image/jpeg") for p in files]


def run_nanobanana(images: list[tuple[bytes, str]]) -> bytes:
    """Virtual try-on via Gemini image model: garment photos + prompt -> outfit image."""
    from google.genai import types

    client = _genai_client()
    parts = [types.Part.from_bytes(data=data, mime_type=mime) for data, mime in images]
    parts.append(types.Part.from_text(text=_TRYON_PROMPT))

    response = client.models.generate_content(
        model=NANOBANANA_MODEL,
        contents=parts,
        config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
    )
    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.data:
            return part.inline_data.data
    raise RuntimeError("No image part in the model response.")


def _build_collage(images: list[tuple[bytes, str]], out_path: Path) -> None:
    """Lay the input garments side by side — the ADL-005 fallback when generation fails."""
    import io
    from PIL import Image

    pics = [Image.open(io.BytesIO(data)).convert("RGB") for data, _ in images]
    height = min(p.height for p in pics)
    pics = [p.resize((round(p.width * height / p.height), height)) for p in pics]
    canvas = Image.new("RGB", (sum(p.width for p in pics), height), "white")
    x = 0
    for p in pics:
        canvas.paste(p, (x, 0))
        x += p.width
    canvas.save(out_path, "JPEG", quality=90)


def main() -> None:
    images = _load_samples()
    print(f"Project  : {PROJECT or '(using GOOGLE_GENAI_API_KEY)'}")
    print(f"Location : {LOCATION}")
    print(f"Model    : {NANOBANANA_MODEL}")
    print(f"Samples  : {len(images)} image(s)\n")

    out_img = RESULTS / "nanobanana_result.jpg"
    out_err = RESULTS / "nanobanana_error.txt"
    out_err.unlink(missing_ok=True)

    start = time.monotonic()
    try:
        out_img.write_bytes(run_nanobanana(images))
        elapsed = time.monotonic() - start
        result = {"model": NANOBANANA_MODEL, "ok": True,
                  "path": str(out_img), "seconds": round(elapsed, 1)}
        print(f"  OK  {out_img.name}  ({elapsed:.1f}s)")
    except Exception as exc:
        elapsed = time.monotonic() - start
        out_err.write_text(f"{type(exc).__name__}: {exc}")
        collage = RESULTS / "collage_result.jpg"
        _build_collage(images, collage)
        result = {"model": NANOBANANA_MODEL, "ok": False, "error": str(exc),
                  "fallback": str(collage), "seconds": round(elapsed, 1)}
        print(f"  ERROR ({elapsed:.1f}s) — {exc}")
        print(f"  → wrote ADL-005 collage fallback: {collage.name}")

    (RESULTS / "summary.json").write_text(json.dumps(result, indent=2))
    print(f"\nResult → {RESULTS}")


if __name__ == "__main__":
    main()
