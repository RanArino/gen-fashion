#!/usr/bin/env bash
# Tear down all GCP resources created by the Phase 1a production deployment.
# By default runs in --dry-run mode (prints commands without executing them).
# Pass --execute to actually delete resources.
#
# Usage:
#   bash scripts/deploy/teardown.sh --project <PROJECT_ID> [--region asia-northeast1] [--execute]
#   bash scripts/deploy/teardown.sh --project <PROJECT_ID> --dry-run   # (default)
set -euo pipefail

PROJECT=""
REGION="asia-northeast1"
ZONE="asia-northeast1-a"
DRY_RUN=true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)   PROJECT="$2"; shift 2 ;;
    --region)    REGION="$2";  shift 2 ;;
    --execute)   DRY_RUN=false; shift 1 ;;
    --dry-run)   DRY_RUN=true;  shift 1 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

: "${PROJECT:?--project is required}"

run() {
  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "[dry-run] $*"
  else
    echo "[execute] $*"
    "$@"
  fi
}

echo "=== Phase 1a teardown (project=${PROJECT}, region=${REGION}, dry_run=${DRY_RUN}) ==="
echo ""
echo "--- Cloud Run services ---"
run gcloud run services delete fastapi-service     --project="${PROJECT}" --region="${REGION}" --quiet
run gcloud run services delete adk-agent-service   --project="${PROJECT}" --region="${REGION}" --quiet

echo ""
echo "--- Cloud Tasks queue ---"
run gcloud tasks queues delete gen-fashion-embed   --project="${PROJECT}" --location="${REGION}"

echo ""
echo "--- Artifact Registry repo ---"
run gcloud artifacts repositories delete gen-fashion \
  --project="${PROJECT}" --location="${REGION}" --quiet

echo ""
echo "--- Firewall rule (Direct VPC egress, ADL-023) ---"
run gcloud compute firewall-rules delete allow-es-from-cloudrun \
  --project="${PROJECT}" --quiet

echo ""
echo "--- Compute Engine ES VM ---"
run gcloud compute instances delete gen-fashion-es \
  --project="${PROJECT}" --zone="${ZONE}" --quiet

echo ""
echo "--- Static internal IP (release after the VM is gone) ---"
run gcloud compute addresses delete gen-fashion-es-ip \
  --project="${PROJECT}" --region="${REGION}" --quiet

echo ""
echo "--- Optional night-stop instance schedule (no-op if it was never created) ---"
run gcloud compute resource-policies delete es-night-off \
  --project="${PROJECT}" --region="${REGION}" --quiet

echo ""
echo "--- Secret Manager secrets ---"
for SECRET in R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY ELASTICSEARCH_API_KEY INTERNAL_TASK_SECRET; do
  run gcloud secrets delete "${SECRET}" --project="${PROJECT}" --quiet
done

echo ""
echo "--- Service accounts ---"
for SA in fastapi-sa adk-sa tasks-invoker-sa; do
  run gcloud iam service-accounts delete "${SA}@${PROJECT}.iam.gserviceaccount.com" \
    --project="${PROJECT}" --quiet
done

echo ""
if [[ "${DRY_RUN}" == "true" ]]; then
  echo "=== Dry run complete. Pass --execute to actually delete these resources. ==="
else
  echo "=== Teardown complete. ==="
fi
