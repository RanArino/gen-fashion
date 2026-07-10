# Security

This repository is a public demo / portfolio codebase. Do not commit secrets,
service account JSON files, `.env` files, private keys, generated credentials,
or production data.

## Reporting

Please report security issues privately to the repository owner instead of
opening a public issue with exploit details.

## Operational Notes

- Production secrets are expected to live in Google Cloud Secret Manager or
  GitHub Actions secrets / variables.
- Local `.env` files and `credentials/` are intentionally ignored.
- The Elasticsearch VM has no external IP in the production posture; Cloud Run
  reaches it through Direct VPC egress.
