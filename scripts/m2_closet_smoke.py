#!/usr/bin/env python3
import argparse
import json
import time
from io import BytesIO
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError
from PIL import Image, ImageDraw


def build_sample_jpeg() -> bytes:
    image = Image.new("RGB", (160, 160), "white")
    draw = ImageDraw.Draw(image)
    shirt = [
        (58, 36),
        (76, 24),
        (84, 24),
        (102, 36),
        (130, 52),
        (118, 76),
        (106, 68),
        (106, 134),
        (54, 134),
        (54, 68),
        (42, 76),
        (30, 52),
    ]
    draw.polygon(shirt, fill=(45, 105, 190), outline=(20, 60, 130))
    draw.rectangle((66, 31, 94, 47), fill="white")
    draw.line((64, 84, 96, 84), fill=(20, 60, 130), width=2)
    output = BytesIO()
    image.save(output, format="JPEG", quality=90)
    return output.getvalue()


SAMPLE_JPEG = build_sample_jpeg()


def request_json(method, url, *, body=None, headers=None, expected=(200,)):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urlopen(request, timeout=30) as response:
            payload = response.read().decode("utf-8")
            if response.status not in expected:
                raise RuntimeError(f"{method} {url} returned {response.status}: {payload}")
            return json.loads(payload) if payload else {}
    except HTTPError as exc:
        payload = exc.read().decode("utf-8")
        if exc.code in expected:
            return json.loads(payload) if payload else {}
        raise RuntimeError(f"{method} {url} returned {exc.code}: {payload}") from exc


def request_bytes(method, url, *, body=None, headers=None, expected=(200,)):
    request = Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urlopen(request, timeout=60) as response:
            payload = response.read()
            if response.status not in expected:
                raise RuntimeError(f"{method} {url} returned {response.status}: {payload!r}")
            return payload
    except HTTPError as exc:
        payload = exc.read()
        if exc.code in expected:
            return payload
        raise RuntimeError(f"{method} {url} returned {exc.code}: {payload!r}") from exc


def ensure_bucket(args):
    s3 = boto3.client(
        "s3",
        endpoint_url=args.storage_endpoint,
        aws_access_key_id=args.storage_access_key,
        aws_secret_access_key=args.storage_secret_key,
        region_name="auto",
    )
    try:
        s3.create_bucket(Bucket=args.bucket)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
            raise
    try:
        s3.put_bucket_cors(
            Bucket=args.bucket,
            CORSConfiguration={
                "CORSRules": [
                    {
                        "AllowedHeaders": ["*"],
                        "AllowedMethods": ["GET", "PUT", "HEAD"],
                        "AllowedOrigins": ["*"],
                        "ExposeHeaders": ["ETag"],
                        "MaxAgeSeconds": 3000,
                    }
                ]
            },
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code != "NotImplemented":
            raise
    return s3


def auth_token(args):
    response = request_json(
        "POST",
        f"{args.auth_emulator}/identitytoolkit.googleapis.com/v1/accounts:signUp?key=fake-api-key",
        body={"returnSecureToken": True},
        headers={"Content-Type": "application/json"},
    )
    return response["idToken"], response["localId"]


def firestore_document(args, user_id, item_id, expected=(200,)):
    path = f"users/{quote(user_id)}/closet/{quote(item_id)}"
    url = f"{args.firestore_emulator}/v1/projects/{args.project}/databases/(default)/documents/{path}"
    return request_json("GET", url, expected=expected)


def firestore_status(document):
    fields = document.get("fields", {})
    return fields.get("status", {}).get("stringValue")


def firestore_string(document, field_name):
    return document.get("fields", {}).get(field_name, {}).get("stringValue")


def firestore_string_array(document, field_name):
    values = document.get("fields", {}).get(field_name, {}).get("arrayValue", {}).get("values", [])
    return [value.get("stringValue") for value in values if "stringValue" in value]


def poll_firestore_status(args, user_id, item_id):
    deadline = time.time() + args.timeout_seconds
    last_status = None
    while time.time() < deadline:
        document = firestore_document(args, user_id, item_id)
        last_status = firestore_status(document)
        if last_status in {args.expect_status, "ERROR"}:
            return document, last_status
        time.sleep(1)
    raise RuntimeError(f"Timed out waiting for Firestore status {args.expect_status}; last={last_status}")


def elastic_doc(args, item_id, expected=(200,)):
    return request_json("GET", f"{args.elasticsearch}/clothing_items/_doc/{item_id}", expected=expected)


def main():
    parser = argparse.ArgumentParser(description="Run the M2 closet backend smoke test.")
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--auth-emulator", default="http://localhost:9099")
    parser.add_argument("--firestore-emulator", default="http://localhost:8080")
    parser.add_argument("--elasticsearch", default="http://localhost:9200")
    parser.add_argument("--project", default="gen-fashion-local")
    parser.add_argument("--storage-endpoint", default="http://localhost:9000")
    parser.add_argument("--storage-access-key", default="minioadmin")
    parser.add_argument("--storage-secret-key", default="minioadmin")
    parser.add_argument("--bucket", default="gen-fashion-images")
    parser.add_argument("--expect-status", choices=["READY", "ERROR"], default="READY")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args = parser.parse_args()

    item_id = str(uuid4())
    s3 = ensure_bucket(args)
    token, user_id = auth_token(args)
    auth_header = {"Authorization": f"Bearer {token}"}
    image_path = f"{user_id}/closet/{item_id}.jpg"

    upload = request_json(
        "GET",
        f"{args.api}/closet/upload-url?item_id={item_id}",
        headers=auth_header,
    )
    request_bytes(
        "PUT",
        upload["upload_url"],
        body=SAMPLE_JPEG,
        headers={"Content-Type": "image/jpeg"},
        expected=(200,),
    )
    s3.head_object(Bucket=args.bucket, Key=image_path)

    registered = request_json(
        "POST",
        f"{args.api}/closet/items/{item_id}/complete",
        headers=auth_header,
    )
    if registered != {"item_id": item_id, "status": "PROCESSING"}:
        raise RuntimeError(f"Unexpected registration response: {registered}")

    document, status = poll_firestore_status(args, user_id, item_id)
    if status != args.expect_status:
        raise RuntimeError(f"Expected {args.expect_status}, got {status}: {document}")

    if status == "READY":
        metadata = {
            "category": firestore_string(document, "category"),
            "colors": firestore_string_array(document, "colors"),
            "tags": firestore_string_array(document, "tags"),
            "season": firestore_string(document, "season"),
            "embeddingId": firestore_string(document, "embeddingId"),
        }
        missing = [field for field, value in metadata.items() if not value]
        if missing:
            raise RuntimeError(f"Firestore READY document missing {missing}: {document}")
        if metadata["embeddingId"] != item_id:
            raise RuntimeError(f"Firestore embeddingId mismatch: {metadata}")
        source = elastic_doc(args, item_id)["_source"]
        for field in ("category", "colors", "season", "tags"):
            if field not in source:
                raise RuntimeError(f"Elasticsearch document missing {field}: {source}")

    request_bytes(
        "DELETE",
        f"{args.api}/closet/items/{item_id}",
        headers=auth_header,
        expected=(204,),
    )
    firestore_document(args, user_id, item_id, expected=(404,))
    elastic_doc(args, item_id, expected=(404,))
    try:
        s3.head_object(Bucket=args.bucket, Key=image_path)
    except ClientError as exc:
        if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") != 404:
            raise
    else:
        raise RuntimeError(f"Storage object still exists after delete: {image_path}")

    print(
        json.dumps(
            {
                "item_id": item_id,
                "user_id": user_id,
                "final_status": status,
                "deleted": True,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
