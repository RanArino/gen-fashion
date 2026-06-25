"""
M1-3 Elasticsearch Connectivity Test — gen-fashion

Minimal FastAPI service deployed to Cloud Run to verify that Cloud Run can
reach the self-hosted Elasticsearch VM over the VPC connector.

Deploy command (from the gen-fashion/ repo root):
    gcloud run deploy es-connectivity-test \
      --project=${GOOGLE_CLOUD_PROJECT} \
      --region=asia-northeast1 \
      --source=poc/es_connectivity_test/ \
      --set-env-vars=ELASTICSEARCH_HOST=http://<vm-internal-ip>:9200 \
      --vpc-connector=gen-fashion-connector \
      --vpc-egress=private-ranges-only \
      --allow-unauthenticated

Delete after confirming:
    gcloud run services delete es-connectivity-test \
      --project=${GOOGLE_CLOUD_PROJECT} \
      --region=asia-northeast1
"""

import os
import httpx
from fastapi import FastAPI

app = FastAPI(title="ES Connectivity Test")

ES_HOST = os.environ.get("ELASTICSEARCH_HOST", "http://localhost:9200")


@app.get("/")
def check_connectivity():
    """
    GET /  — hit Elasticsearch cluster health endpoint and return the result.
    Success: HTTP 200 with body containing 'tagline': 'You Know, for Search'.
    Failure: HTTP 502 with the error detail.
    """
    try:
        r = httpx.get(f"{ES_HOST}", timeout=5.0)
        r.raise_for_status()
        return {
            "elasticsearch_host": ES_HOST,
            "status": r.status_code,
            "body": r.json(),
        }
    except httpx.ConnectError as exc:
        return {
            "elasticsearch_host": ES_HOST,
            "status": "connect_error",
            "error": str(exc),
            "hint": (
                "Cannot reach ES. Check that the VPC connector is attached, "
                "the firewall rule allow-es-from-vpc exists, "
                "and the VM internal IP in ELASTICSEARCH_HOST is correct."
            ),
        }
    except Exception as exc:
        return {
            "elasticsearch_host": ES_HOST,
            "status": "error",
            "error": str(exc),
        }


@app.get("/health")
def health():
    return {"status": "ok"}
