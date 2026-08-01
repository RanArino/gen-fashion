# Production Pause Rollback Runbook — gen-fashion

This runbook restores production availability after the cost-control change
that pauses the Elasticsearch VM, Cloud Tasks queue, and public FastAPI
invocation outside a `main`-push deployment. It does not delete data.

## Preconditions

- Use an identity with Cloud Run Admin, Compute instance start, Cloud Tasks
  queue resume, and IAM policy permissions in the production project.
- Set `PROJECT` to the production project ID. Never print Secret Manager values.
- Do not restore public invocation before the VM is running and the queue is
  resumed; otherwise browser requests can reach a partially unavailable API.

```bash
PROJECT=your-project-id
REGION=asia-northeast1
ZONE=asia-northeast1-a
```

## Temporary restoration for a production check

Use this when the cost-control workflow remains in place, but a short live
test is necessary. A later push to `main` will pause the environment again.

1. Start Elasticsearch and wait for `RUNNING`.

   ```bash
   gcloud compute instances start gen-fashion-es \
     --project="${PROJECT}" --zone="${ZONE}" --quiet
   gcloud compute instances describe gen-fashion-es \
     --project="${PROJECT}" --zone="${ZONE}" --format='value(status)'
   ```

2. Resume asynchronous work, then restore the public API invoker.

   ```bash
   gcloud tasks queues resume gen-fashion-embed \
     --project="${PROJECT}" --location="${REGION}" --quiet
   gcloud run services add-iam-policy-binding fastapi-service \
     --project="${PROJECT}" --region="${REGION}" \
     --member='allUsers' --role='roles/run.invoker' --quiet
   ```

3. Verify only after both dependencies are available.

   ```bash
   gcloud tasks queues describe gen-fashion-embed \
     --project="${PROJECT}" --location="${REGION}" --format='value(state)'
   gcloud run services get-iam-policy fastapi-service \
     --project="${PROJECT}" --region="${REGION}" --format='yaml(bindings)'
   FASTAPI_URL=$(gcloud run services describe fastapi-service \
     --project="${PROJECT}" --region="${REGION}" --format='value(status.url)')
   curl -f "${FASTAPI_URL}/health"
   ```

4. After the test, return to the paused state using the commands in
   [`docs/gcp-cheatsheet.md`](../gcp-cheatsheet.md#本番の休止--一時再開).

## Permanently remove the cost-control automation

Use this only when production should remain available continuously.

1. Revert the commit that introduced the `shutdown-production` workflow job
   and main-push-only deploy condition. Prefer a Git revert over manually
   deleting workflow fragments so the rollback is reviewable. Merge that
   revert into `main`.

2. Restore the live dependencies with the three commands in “Temporary
   restoration for a production check.” Verify `RUNNING`, `RUNNING`, and
   `/health` success before considering the rollback complete.

3. Only after the workflow rollback is merged, remove the no-longer-needed
   least-privilege role. Removing it first makes the still-active workflow
   fail when it tries to start or pause infrastructure.

   ```bash
   gcloud projects remove-iam-policy-binding "${PROJECT}" \
     --member="serviceAccount:github-deployer@${PROJECT}.iam.gserviceaccount.com" \
     --role="projects/${PROJECT}/roles/githubDeployerPauseProduction" \
     --quiet
   gcloud iam roles delete githubDeployerPauseProduction \
     --project="${PROJECT}" --quiet
   ```

4. Keep the ADK Cloud Run minimum-instance setting at 0. The removed
   `run.googleapis.com/minScale: 1` setting was stale configuration and is not
   part of the intended deployment scripts. Reintroduce a minimum instance
   only after explicitly accepting its idle cost and updating the deployment
   configuration to match.

## Failure recovery

- If the ES VM does not become `RUNNING`, leave `allUsers` removed from
  `fastapi-service`; investigate the VM before exposing the API.
- If the queue cannot resume, the browser API can still be checked, but uploads
  and background processing will remain delayed. Keep the limitation explicit
  and pause the environment again after the test.
- If a `main` deployment fails, inspect the `Pause Production Infrastructure`
  job. It is intentionally independent of deploy success and should still
  restore the paused state.
