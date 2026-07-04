#!/usr/bin/env bash
# Deploy Firestore composite indexes declared in firestore.indexes.json.
#
# firebase-tools cannot authenticate with WIF external-account credentials
# (see scripts/deploy/deploy_firebase_hosting.py), so this uses `gcloud
# firestore indexes composite create` directly, which does work with WIF.
# Creation is async and idempotent: an index that already exists is skipped
# rather than erroring, so this is safe to run on every deploy.
#
# Usage:
#   bash scripts/deploy/deploy_firestore_indexes.sh --project <PROJECT_ID>
set -euo pipefail

PROJECT=""
INDEXES_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/firestore.indexes.json"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)       PROJECT="$2";       shift 2 ;;
    --indexes-file)  INDEXES_FILE="$2";  shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

: "${PROJECT:?--project is required}"

echo "==> Fetching existing composite indexes for ${PROJECT}..."
# `collectionGroup` isn't a top-level field on the API response; it's a path
# segment of `name` (.../collectionGroups/<group>/indexes/<id>), so derive it.
EXISTING=$(gcloud firestore indexes composite list \
  --project="${PROJECT}" \
  --format='json(name,fields)' \
  | jq '[.[] | {collectionGroup: (.name | capture("collectionGroups/(?<cg>[^/]+)/indexes") .cg), fields}]')

COUNT=$(jq '.indexes | length' "${INDEXES_FILE}")
for i in $(seq 0 $((COUNT - 1))); do
  ENTRY=$(jq -c ".indexes[$i]" "${INDEXES_FILE}")
  COLLECTION_GROUP=$(echo "${ENTRY}" | jq -r '.collectionGroup')
  FIELDS_JSON=$(echo "${ENTRY}" | jq -c '.fields')

  ALREADY_EXISTS=$(echo "${EXISTING}" | jq --arg cg "${COLLECTION_GROUP}" --argjson fields "${FIELDS_JSON}" '
    any(.[]; .collectionGroup == $cg and (.fields | map(select(.fieldPath != "__name__"))) == $fields)
  ')

  if [[ "${ALREADY_EXISTS}" == "true" ]]; then
    echo "==> Index already exists: ${COLLECTION_GROUP} ${FIELDS_JSON}"
    continue
  fi

  FIELD_CONFIGS=()
  while IFS= read -r field; do
    PATH_NAME=$(echo "${field}" | jq -r '.fieldPath')
    ORDER=$(echo "${field}" | jq -r '.order | ascii_downcase')
    FIELD_CONFIGS+=(--field-config "field-path=${PATH_NAME},order=${ORDER}")
  done < <(echo "${FIELDS_JSON}" | jq -c '.[]')

  echo "==> Creating index: ${COLLECTION_GROUP} ${FIELDS_JSON}"
  gcloud firestore indexes composite create \
    --project="${PROJECT}" \
    --collection-group="${COLLECTION_GROUP}" \
    "${FIELD_CONFIGS[@]}"
done

echo "==> Firestore index sync complete (new indexes build asynchronously in the background)."
