#!/usr/bin/env python3
"""Deploy Flutter web build to Firebase Hosting via REST API.

firebase-tools does not support WIF external-account credentials.
This script uses gcloud auth print-access-token (which does work with WIF)
and calls the Firebase Hosting REST API directly.
"""

import gzip
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path


BASE = "https://firebasehosting.googleapis.com/v1beta1"
UPLOAD_BASE = "https://upload.firebasehosting.googleapis.com/upload/v1beta1"

# Rewrites for Flutter web SPA: all paths → /index.html
HOSTING_CONFIG = {
    "rewrites": [{"glob": "**", "path": "/index.html"}],
    # REST API expects `headers` as a string->string map (not the CLI's
    # list-of-{key,value} format used in firebase.json).
    "headers": [
        {
            "glob": "**/*.@(js|css|wasm|map)",
            "headers": {"Cache-Control": "max-age=3600"},
        },
        {
            "glob": "index.html",
            "headers": {"Cache-Control": "no-cache"},
        },
    ],
}


def gcloud_token() -> str:
    result = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def api(method: str, url: str, token: str, body=None, raw_body: bytes = None,
        content_type: str = "application/json") -> dict:
    data = raw_body if raw_body is not None else (json.dumps(body).encode() if body else None)
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": content_type},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} {method} {url}: {e.read().decode()}", file=sys.stderr)
        raise


def sha256_gz(path: Path) -> tuple[str, bytes]:
    """Return (hex sha256, gzipped bytes) for a file."""
    raw = path.read_bytes()
    gz = gzip.compress(raw, compresslevel=9)
    digest = hashlib.sha256(raw).hexdigest()
    return digest, gz


def deploy(site: str, build_dir: str) -> None:
    build_path = Path(build_dir)
    if not build_path.is_dir():
        sys.exit(f"Build dir not found: {build_dir}")

    token = gcloud_token()
    print(f"Authenticated. Deploying to Firebase Hosting site: {site}")

    # 1. Create version
    version_resp = api("POST", f"{BASE}/sites/{site}/versions", token,
                       body={"config": HOSTING_CONFIG})
    version_name = version_resp["name"]  # projects/.../sites/.../versions/ID
    version_id = version_name.split("/")[-1]
    print(f"Created version: {version_id}")

    # 2. Collect files and compute hashes
    files: dict[str, str] = {}  # hosting path → sha256
    file_data: dict[str, bytes] = {}  # sha256 → gzipped bytes
    for f in sorted(build_path.rglob("*")):
        if f.is_file():
            hosting_path = "/" + f.relative_to(build_path).as_posix()
            digest, gz = sha256_gz(f)
            files[hosting_path] = digest
            file_data[digest] = gz

    print(f"Files to process: {len(files)}")

    # 3. Populate files — API tells us which files need uploading
    # populateFiles is a custom method → addressed with ':' not '/'.
    pop_resp = api("POST", f"{BASE}/sites/{site}/versions/{version_id}:populateFiles",
                   token, body={"files": files})
    upload_url = pop_resp.get("uploadUrl", "")
    required_hashes = set(pop_resp.get("uploadRequiredHashes", []))
    print(f"Files to upload: {len(required_hashes)}")

    # 4. Upload missing files
    for i, digest in enumerate(required_hashes, 1):
        gz_bytes = file_data[digest]
        api("POST", f"{upload_url}/{digest}", token,
            raw_body=gz_bytes, content_type="application/octet-stream")
        if i % 20 == 0 or i == len(required_hashes):
            print(f"  Uploaded {i}/{len(required_hashes)}")

    # 5. Finalize version
    api("PATCH", f"{BASE}/sites/{site}/versions/{version_id}?updateMask=status",
        token, body={"status": "FINALIZED"})
    print("Version finalized.")

    # 6. Create release
    rel = api("POST", f"{BASE}/sites/{site}/releases?versionName={version_name}", token)
    print(f"Release created: {rel.get('name', '?')}")
    print(f"✅ Firebase Hosting deploy complete: https://{site}.web.app")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True, help="Firebase Hosting site ID")
    parser.add_argument("--build-dir", required=True, help="Path to flutter build/web")
    args = parser.parse_args()
    deploy(args.site, args.build_dir)
