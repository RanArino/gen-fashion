#!/usr/bin/env bash
# Deploy adk-agent-service to Cloud Run (private, no-allow-unauthenticated).
# Usage:
#   bash scripts/deploy/deploy_adk.sh \
#     --project <PROJECT_ID> \
#     --region asia-northeast1 \
#     --image <REPO>/adk-agent-service:<TAG> \
#     --es-internal-ip <ES_VM_INTERNAL_IP> \
#     --r2-endpoint-url https://<account_id>.r2.cloudflarestorage.com \
#     --r2-public-endpoint-url https://<account_id>.r2.cloudflarestorage.com \
#     --r2-bucket-name gen-fashion-images
set -euo pipefail

PROJECT=""
REGION="asia-northeast1"
IMAGE=""
ES_INTERNAL_IP=""
R2_ENDPOINT_URL=""
R2_PUBLIC_ENDPOINT_URL=""
R2_BUCKET_NAME="gen-fashion-images"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)           PROJECT="$2";              shift 2 ;;
    --region)            REGION="$2";               shift 2 ;;
    --image)             IMAGE="$2";                shift 2 ;;
    --es-internal-ip)    ES_INTERNAL_IP="$2";       shift 2 ;;
    --r2-endpoint-url)   R2_ENDPOINT_URL="$2";      shift 2 ;;
    --r2-public-endpoint-url) R2_PUBLIC_ENDPOINT_URL="$2"; shift 2 ;;
    --r2-bucket-name)    R2_BUCKET_NAME="$2";       shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

: "${PROJECT:?--project is required}"
: "${IMAGE:?--image is required}"
: "${ES_INTERNAL_IP:?--es-internal-ip is required}"
: "${R2_ENDPOINT_URL:?--r2-endpoint-url is required}"
: "${R2_PUBLIC_ENDPOINT_URL:?--r2-public-endpoint-url is required}"

echo "==> Deploying adk-agent-service (private) to ${REGION}..."

gcloud run deploy adk-agent-service \
  --image="${IMAGE}" \
  --project="${PROJECT}" \
  --region="${REGION}" \
  --service-account="adk-sa@${PROJECT}.iam.gserviceaccount.com" \
  --no-allow-unauthenticated \
  --min-instances=1 \
  --max-instances=5 \
  --memory=2Gi \
  --cpu=1 \
  --timeout=600 \
  --vpc-connector="gen-fashion-conn" \
  --vpc-egress=private-ranges-only \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT},GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_LOCATION=us-central1,AGENT_MODEL=gemini-2.5-flash,ELASTICSEARCH_URL=https://${ES_INTERNAL_IP}:9200,R2_ENDPOINT_URL=${R2_ENDPOINT_URL},R2_PUBLIC_ENDPOINT_URL=${R2_PUBLIC_ENDPOINT_URL},R2_BUCKET_NAME=${R2_BUCKET_NAME}" \
  --set-secrets="ELASTICSEARCH_API_KEY=ELASTICSEARCH_API_KEY:latest,R2_ACCESS_KEY_ID=R2_ACCESS_KEY_ID:latest,R2_SECRET_ACCESS_KEY=R2_SECRET_ACCESS_KEY:latest,INTERNAL_TASK_SECRET=INTERNAL_TASK_SECRET:latest"

echo "==> Granting fastapi-sa roles/run.invoker on adk-agent-service..."
gcloud run services add-iam-policy-binding adk-agent-service \
  --project="${PROJECT}" \
  --region="${REGION}" \
  --member="serviceAccount:fastapi-sa@${PROJECT}.iam.gserviceaccount.com" \
  --role=roles/run.invoker

ADK_URL=$(gcloud run services describe adk-agent-service \
  --project="${PROJECT}" --region="${REGION}" --format='value(status.url)')
echo "==> adk-agent-service deployed: ${ADK_URL}"
