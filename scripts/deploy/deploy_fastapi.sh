#!/usr/bin/env bash
# Deploy fastapi-service to Cloud Run (public, browser-facing).
#
# Two-pass deploy is required because fastapi-service needs its own URL as
# FASTAPI_INTERNAL_BASE_URL for the OIDC audience (the URL is only known after
# the first deploy). Use --bootstrap on the first pass, then run again with
# --fastapi-url once the URL is known.
#
# Usage (first pass — bootstrap, no OIDC yet):
#   bash scripts/deploy/deploy_fastapi.sh \
#     --project <PROJECT_ID> --region asia-northeast1 \
#     --image <REPO>/fastapi-service:<TAG> \
#     --adk-url https://adk-agent-service-xxxxx-an.a.run.app \
#     --bootstrap \
#     --es-internal-ip <IP> \
#     --r2-endpoint-url ... --r2-public-endpoint-url ... --r2-bucket-name ...
#
# Usage (second pass — full OIDC):
#   FASTAPI_URL=$(gcloud run services describe fastapi-service --region=asia-northeast1 --format='value(status.url)')
#   bash scripts/deploy/deploy_fastapi.sh \
#     --project <PROJECT_ID> --region asia-northeast1 \
#     --image <REPO>/fastapi-service:<TAG> \
#     --adk-url https://adk-agent-service-xxxxx-an.a.run.app \
#     --fastapi-url "$FASTAPI_URL" \
#     --es-internal-ip <IP> \
#     --r2-endpoint-url ... --r2-public-endpoint-url ... --r2-bucket-name ...
set -euo pipefail

PROJECT=""
REGION="asia-northeast1"
IMAGE=""
ADK_URL=""
FASTAPI_URL=""
BOOTSTRAP=false
ES_INTERNAL_IP=""
R2_ENDPOINT_URL=""
R2_PUBLIC_ENDPOINT_URL=""
R2_BUCKET_NAME="gen-fashion-images"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)            PROJECT="$2";               shift 2 ;;
    --region)             REGION="$2";                shift 2 ;;
    --image)              IMAGE="$2";                 shift 2 ;;
    --adk-url)            ADK_URL="$2";               shift 2 ;;
    --fastapi-url)        FASTAPI_URL="$2";           shift 2 ;;
    --bootstrap)          BOOTSTRAP=true;             shift 1 ;;
    --es-internal-ip)     ES_INTERNAL_IP="$2";        shift 2 ;;
    --r2-endpoint-url)    R2_ENDPOINT_URL="$2";       shift 2 ;;
    --r2-public-endpoint-url) R2_PUBLIC_ENDPOINT_URL="$2"; shift 2 ;;
    --r2-bucket-name)     R2_BUCKET_NAME="$2";        shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

: "${PROJECT:?--project is required}"
: "${IMAGE:?--image is required}"
: "${ADK_URL:?--adk-url is required}"
: "${ES_INTERNAL_IP:?--es-internal-ip is required}"
: "${R2_ENDPOINT_URL:?--r2-endpoint-url is required}"
: "${R2_PUBLIC_ENDPOINT_URL:?--r2-public-endpoint-url is required}"

# Build env-vars string
ENV_VARS="GOOGLE_CLOUD_PROJECT=${PROJECT}"
ENV_VARS+=",FIREBASE_PROJECT_ID=${PROJECT}"
ENV_VARS+=",GOOGLE_GENAI_USE_VERTEXAI=true"
ENV_VARS+=",GOOGLE_CLOUD_LOCATION=us-central1"
ENV_VARS+=",ELASTICSEARCH_URL=https://${ES_INTERNAL_IP}:9200"
ENV_VARS+=",R2_ENDPOINT_URL=${R2_ENDPOINT_URL}"
ENV_VARS+=",R2_PUBLIC_ENDPOINT_URL=${R2_PUBLIC_ENDPOINT_URL}"
ENV_VARS+=",R2_BUCKET_NAME=${R2_BUCKET_NAME}"
ENV_VARS+=",TASK_QUEUE_MODE=cloud_tasks"
ENV_VARS+=",CLOUD_TASKS_QUEUE_EMBED=gen-fashion-embed"
ENV_VARS+=",CLOUD_TASKS_LOCATION=${REGION}"
ENV_VARS+=",ADK_INTERNAL_BASE_URL=${ADK_URL}"

if [[ "${BOOTSTRAP}" == "false" ]]; then
  : "${FASTAPI_URL:?--fastapi-url is required (omit only with --bootstrap)}"
  ENV_VARS+=",FASTAPI_INTERNAL_BASE_URL=${FASTAPI_URL}"
  ENV_VARS+=",INTERNAL_INVOKER_SA=tasks-invoker-sa@${PROJECT}.iam.gserviceaccount.com"
fi

echo "==> Deploying fastapi-service (public) to ${REGION}..."

gcloud run deploy fastapi-service \
  --image="${IMAGE}" \
  --project="${PROJECT}" \
  --region="${REGION}" \
  --service-account="fastapi-sa@${PROJECT}.iam.gserviceaccount.com" \
  --allow-unauthenticated \
  --min-instances=0 \
  --max-instances=10 \
  --memory=1Gi \
  --cpu=1 \
  --timeout=60 \
  --vpc-connector="gen-fashion-conn" \
  --vpc-egress=private-ranges-only \
  --set-env-vars="${ENV_VARS}" \
  --set-secrets="ELASTICSEARCH_API_KEY=ELASTICSEARCH_API_KEY:latest,R2_ACCESS_KEY_ID=R2_ACCESS_KEY_ID:latest,R2_SECRET_ACCESS_KEY=R2_SECRET_ACCESS_KEY:latest,INTERNAL_TASK_SECRET=INTERNAL_TASK_SECRET:latest"

if [[ "${BOOTSTRAP}" == "false" ]]; then
  echo "==> Granting tasks-invoker-sa roles/run.invoker on fastapi-service..."
  gcloud run services add-iam-policy-binding fastapi-service \
    --project="${PROJECT}" \
    --region="${REGION}" \
    --member="serviceAccount:tasks-invoker-sa@${PROJECT}.iam.gserviceaccount.com" \
    --role=roles/run.invoker
fi

DEPLOYED_URL=$(gcloud run services describe fastapi-service \
  --project="${PROJECT}" --region="${REGION}" --format='value(status.url)')
echo "==> fastapi-service deployed: ${DEPLOYED_URL}"
