# M1 — PoC & Infrastructure Validation

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows `PLANS.md` at `/Users/ran/my-app/PLANS.md`.


## Purpose / Big Picture


M1 de-risks three architectural decisions before M2–M5 commit to them. All work in this milestone is PoC and validation code, not production code. Nothing built here is wired into the main application.

The three de-risked decisions are:

1. **Image generation model choice** (M1-1, M1-2). The requirements (§6.5, ADL-005) mandate that coordinate outfit images must come from Imagen 4 or Nano Banana 2, not Gemini 2.0 Flash. Before M4 implements `style_synthesizer`, this PoC verifies that at least one of these two models can synthesize a wearable outfit image from multiple clothing photos. A passing PoC confirms the `GenerateCoordinateUseCase` approach; a failing one triggers the collage fallback.

2. **Elasticsearch on Compute Engine** (M1-3). The plan calls for a self-hosted single-node ES on an `e2-medium` VM in `asia-northeast1` (ADL-013, §9.2). Before M2 builds the `ElasticsearchEmbeddingRepository`, this PoC proves ES installs, starts, and is reachable privately from Cloud Run.

3. **ADK event stream granularity** (M1-4). ADL-011 proposes that the ADK container writes agent events to Firestore, which FastAPI then relays as SSE to Flutter. Before M5 implements this relay, this PoC inspects `runner.run_async()` output in practice to confirm the event format and granularity are suitable for the Accordion UI.

**Acceptance:** Image gen model chosen (or collage fallback confirmed) with the decision written in this plan's Decision Log; Elasticsearch reachable from Cloud Run at `http://<internal-ip>:9200` returning a 200 health response; ADK event schema documented in Artifacts with a captured sample event log.


## Progress


- [x] (2026-06-03) Phase 1: Image generation PoC script (M1-1)
  - `poc/image_generation/run_poc.py` — feeds the garment photos to a Gemini image model (Nano Banana) and saves the try-on image to `results/`; collage fallback (ADL-005) on failure.
  - `requirements.txt` switched to `google-genai`; `.env.example`, `samples/README.md` updated. Runs on real garment photos in `samples/`.
  - Imagen path and `make_placeholders.py` removed (see Decision Log / Surprises).
- [x] (2026-06-03) Phase 2: Model decision recorded (M1-2) — Nano Banana chosen, Imagen dropped. See Decision Log.
- [ ] Phase 3: Provision ES on Compute Engine, configure VPC access, verify Cloud Run connectivity (M1-3) — requires GCP access
- [x] (2026-06-04) Phase 4: Write minimal ADK agent PoC, capture `runner.run_async()` events, document schema (M1-4)
  - `poc/adk_event_stream/run_poc.py` written — minimal agent with `get_clothing_tags` tool, captures all events to `sample_events.jsonl`
  - `requirements.txt`, `.env.example` created (updated to include `GOOGLE_GENAI_USE_VERTEXAI=True`)
  - Run 2026-06-04 with `gemini-2.5-flash` on Vertex AI `us-central1`; `sample_events.jsonl` generated and committed
  - Event schema documented in Artifacts; see Decision Log for model name correction


## Surprises & Discoveries


- (2026-06-03, M1-1/M1-2) **Imagen is the wrong tool for multi-garment try-on, and it is not a prompt problem.** With the *same* prompt and *same* reference photos, Nano Banana (Gemini image model) faithfully reproduced both garments worn on a person, while Imagen `imagen-3.0-capability-001` subject-customization ignored the references and synthesised a generic outfit. Imagen subject-customization is designed to recontextualise a *single* product, not to dress a person in multiple reference garments. → Imagen dropped from the image-gen approach.
- (2026-06-03) **Region quirk:** `gemini-3-pro-image-preview` (Nano Banana 2/Pro) returns 404 from `us-central1` but generates from `GOOGLE_CLOUD_LOCATION=global`. Vertex `models.get()` lists it in both regions, but generation is global-only. `gemini-2.5-flash-image` generates from `us-central1`.
- (2026-06-04, M1-4) **ADK 2.1.0 defaults to Gemini API (API key) mode, not Vertex AI.** Setting `GOOGLE_GENAI_USE_VERTEXAI=True` is required to use application default credentials via Vertex AI. Without it, ADK raises `ValueError: No API key was provided`.
- (2026-06-04, M1-4) **`gemini-2.0-flash` is not available on Vertex AI for this project.** The model is absent from `models.list()` output. `gemini-2.5-flash` is available and was used for the ADK PoC. Teams using Vertex AI backend should use `gemini-2.5-flash`; `gemini-2.0-flash` is only accessible via the direct Gemini API (`GOOGLE_GENAI_API_KEY`).
- (2026-06-04, M1-4) **ADK 2.1.0 uses a single `Event` class** — there are no distinct `LlmRequest`, `LlmResponse`, `ToolCall`, `ToolResult` subtypes. Content type is identified by inspecting `payload.content.parts[*].function_call` / `function_response` / `text` fields. The `thought_signature` field contains raw bytes that serialize as a Python bytes literal string — Firestore must store this as a base64 string or bytes field rather than raw JSON string.


## Decision Log


(Empty at plan creation. Populate as decisions are made during execution.)

- Decision: **Use Nano Banana (Gemini image model) for coordinate image generation; Imagen is not used.** The PoC and `style_synthesizer` (M4-7) standardise on `gemini-2.5-flash-image` (Nano Banana 1); `gemini-3-pro-image-preview` (Nano Banana 2/Pro, requires `location=global`) is the quality-upgrade option.
  - Quality: Nano Banana faithfully reproduces both input garments worn on a person. Imagen `imagen-3.0-capability-001` ignored the references (generic output) — wrong tool for multi-garment try-on, not a prompt issue.
  - Speed: `gemini-2.5-flash-image` ~12–14s; `gemini-3-pro-image-preview` ~30s (observed in PoC).
  - Cost: per-image Gemini image pricing — confirm on the pricing page before M4-7 ships.
  - Rollback: collage of input garments (ADL-005), implemented in `run_poc.py` (`_build_collage`).
  - Date/Author: 2026-06-03 / Ran


## Outcomes & Retrospective


(To be completed at milestone end.)


## Context and Orientation


### Current State

M0 is complete. The repository at `/Users/ran/my-app/gen-fashion/` contains a working hexagonal skeleton with empty adapters. `make dev` boots Elasticsearch (in Docker, for local use only), the Firestore emulator, FastAPI, and the ADK service. All domain models, ports, and use case stubs are in place.

M1 produces no changes to the main application code. All PoC work lives under `poc/` at the repository root. The `poc/` directory does not exist yet and must be created.

### Architecture Glossary

- **Imagen 4** — Google Vertex AI image generation model. Must be invoked via the `google-cloud-aiplatform` Python SDK. Requires a GCP project with Vertex AI enabled and a service account with `roles/aiplatform.user`.
- **Nano Banana 2** — Image generation model referenced in the project requirements as the second candidate. The exact Python SDK, endpoint, and authentication method must be verified against the model's documentation before the PoC script can be written for this model. If no public API exists, this model is treated as unavailable and the PoC proceeds with Imagen 4 only.
- **Compute Engine `e2-medium`** — A GCP VM with 2 vCPU and 4 GB RAM. Used to self-host Elasticsearch. Cheaper than managed ES options; suitable for the hackathon MVP data volume (~2,000 clothing items).
- **Serverless VPC Access connector** — A GCP resource that lets Cloud Run services egress traffic into a VPC, enabling them to reach GCE VMs by private IP without exposing the VM to the internet.
- **`runner.run_async()`** — The Google ADK Python method that drives an agent turn asynchronously and yields events. ADL-011 proposes writing these events to Firestore; this PoC confirms whether the events have enough granularity to populate the Accordion UI.
- **Accordion UI** — The Flutter frontend component (M5) that displays step-by-step agent thinking as collapsible panels in real time, similar to how Claude Code shows tool calls.

### Key Files and Paths

- `docs/feature-matrix-phase01.md` — Milestone tracker. **Must be updated in the same change as any M1 completion**: flip the row from 🟡 to ✅ when the acceptance criteria for that item are met.
- `docs/plans/20260518-m1-poc-infrastructure-validation.md` (this file) — **Must also be updated in the same change**: tick the matching Progress checkbox, add a timestamp, and record any findings in Surprises & Discoveries or Decision Log. Both files change together — never update one without the other.
- `docs/req-phase01.md` §6.5, §9.2, ADL-005, ADL-011, ADL-013, §17 — Source requirements for all four M1 items.
- `poc/` — New directory. All PoC code lives here; it is never imported by the main application.
- `fastapi-service/` and `adk-agent-service/` — Main application code. Do not modify during M1.


## Plan of Work


### Phase 1: Image Generation PoC Script (M1-1)

The goal is a self-contained Python script that anyone on the team can run with `python run_poc.py` after `pip install -r requirements.txt`, without Docker, to see side-by-side outputs from Imagen 4 and Nano Banana 2.

Create the following directory layout:

    poc/
    └── image_generation/
        ├── run_poc.py
        ├── requirements.txt
        ├── samples/          ← placeholder clothing images checked in here
        │   ├── shirt.jpg
        │   └── pants.jpg
        └── results/          ← git-ignored; generated images written here

The `samples/` directory must contain at least two clothing item images (a top and a bottom). These can be freely-licensed placeholder images (e.g., downloaded from Unsplash or similar) committed to the repository so any team member can run the PoC cold. Do not use images that require login or are behind a paywall.

The `results/` directory is git-ignored (add `poc/image_generation/results/` to `.gitignore`). The script writes `imagen4_result.jpg` and `nanobanana2_result.jpg` there.

`run_poc.py` must do the following in order:

1. Load `.env` from the same directory using `python-dotenv` if present, then read `GOOGLE_CLOUD_PROJECT` from the environment. Exit with a clear error message if the variable is missing.
2. Load the sample images from `samples/` as bytes.
3. Call the Imagen 4 API and the Nano Banana 2 API in parallel using `concurrent.futures.ThreadPoolExecutor`, each in its own function (`run_imagen4` and `run_nanobanana2`). The prompt asks the model to show an outfit combining the sample clothing items.
4. Write both output images to `results/` and print a one-line summary per model: the file path and wall-clock time taken.
5. If either model call fails, print the error and write a placeholder error file (`imagen4_error.txt` or `nanobanana2_error.txt`) rather than crashing the whole script.

**Imagen 4 implementation.** Use `google-cloud-aiplatform`. The model name for Imagen 4 in Vertex AI must be confirmed from the Vertex AI model garden at the time of implementation (the latest Imagen model identifier as of mid-2026 may differ from `imagen-3.0-generate-001`). Initialize with `vertexai.init(project=project_id, location="us-central1")`. Call `ImageGenerationModel.from_pretrained("<model-name>").generate_images(prompt=..., number_of_images=1)`.

**Nano Banana 2 implementation.** Before writing this function, look up the Nano Banana 2 model's Python SDK and endpoint. If a public API is not available, stub `run_nanobanana2` to raise `NotImplementedError("Nano Banana 2 API not found — see Decision Log")` and document the finding in this plan's Decision Log. Do not block Phase 1 completion on Nano Banana 2; proceed with Imagen 4 alone if needed.

`requirements.txt` for `poc/image_generation/`:

    google-cloud-aiplatform>=1.60.0
    python-dotenv>=1.0.0
    Pillow>=10.0.0

Add a `.env.example` in `poc/image_generation/` with:

    GOOGLE_CLOUD_PROJECT=your-gcp-project-id


### Phase 2: Image Generation Model Decision (M1-2)

After the PoC script produces results, evaluate both outputs on three axes: visual quality (does the image show a recognizable outfit?), generation time (wall-clock seconds), and cost (per-image pricing from the model's pricing page).

Document the decision in this plan's Decision Log with the following structure:

- Decision: which model is chosen (Imagen 4, Nano Banana 2, or collage fallback)
- Rationale: one sentence per axis (quality, cost, speed) based on observed PoC results
- Rollback: if neither model produces an acceptable coordinate image, the collage fallback is adopted per ADL-005

The Decision Log entry from this phase directly informs M4-7 (`style_synthesizer` tool) and the `ImageGenerationPort` implementation in M4.

Save representative result images in `poc/image_generation/results/` as-is. Do not commit generated images to git.


### Phase 3: Elasticsearch on Compute Engine (M1-3)

This phase is infrastructure work performed in GCP, not local code. The goal is to prove the ADL-013 design before M2-9 (`ElasticsearchEmbeddingRepository`) is implemented.

**Step A — Provision the VM.** Create a GCE VM named `es-gen-fashion` in `asia-northeast1-a` with machine type `e2-medium`, 30 GB SSD boot disk, Debian 12, and the tag `elasticsearch`. Note the VM's internal IP address.

**Step B — Install and configure Elasticsearch.** SSH into the VM. Import the Elastic GPG key, add the Elastic 8.x apt repository, and run `sudo apt-get install elasticsearch`. Edit `/etc/elasticsearch/elasticsearch.yml` to set `network.host: 0.0.0.0`, `discovery.type: single-node`, and `xpack.security.enabled: false` (acceptable for a private-VPC-only hackathon deployment; not production-safe). Enable and start the service with `systemctl`. Verify locally with `curl http://localhost:9200` — expect a JSON response with `"tagline": "You Know, for Search"`.

**Step C — Configure VPC firewall.** Add a firewall rule that allows TCP 9200 from the internal RFC-1918 address range (`10.0.0.0/8`) to VMs tagged `elasticsearch`. Do not open port 9200 to the internet.

**Step D — Serverless VPC Access.** Create a Serverless VPC Access connector in `asia-northeast1` (if one does not already exist in the project). This is what lets Cloud Run services reach the GCE VM by internal IP. Note the connector name for later use in Cloud Run deployments (`--vpc-connector`).

**Step E — Verify Cloud Run connectivity.** Deploy a minimal Cloud Run service (a single Python `httpx.get` call to `http://<vm-internal-ip>:9200`) with the VPC connector attached and `--vpc-egress=private-ranges-only`. The service must return the ES cluster health JSON. A 200 response from this test service proves the full connectivity path.

**Step F — Verify Japanese analyzer is not needed.** Create a test index with the default `standard` analyzer. Index a sample document with a Japanese clothing tag (e.g., `"ワンピース"`). Run a match query for the same tag. If the match succeeds, the standard analyzer is sufficient for MVP and no Japanese-specific plugin is required. Document the outcome in Surprises & Discoveries.

**Step G — Record outputs.** Capture the ES VM's internal IP, the VPC connector name, and the test Cloud Run service URL. These values go into `.env.example` (as `ELASTICSEARCH_HOST=http://<internal-ip>:9200`) and into the Artifacts section of this plan.


### Phase 4: ADK Event Stream Granularity (M1-4)

The goal is to understand exactly what events `runner.run_async()` yields so the M5 Firestore relay (ADL-011) can be designed correctly.

Create a second PoC script at:

    poc/
    └── adk_event_stream/
        ├── run_poc.py
        ├── requirements.txt
        └── sample_events.jsonl   ← git-tracked output captured from a real run

`run_poc.py` must:

1. Initialize a minimal Google ADK `Agent` with `model="gemini-2.0-flash"` and a simple instruction.
2. Create an `InMemorySessionService`, initialize a `Runner`, and open a session.
3. Invoke `runner.run_async()` with a simple two-step task that triggers at least one tool call (for example, a tool that returns a fixed string, so the agent must reason, call a tool, and then produce a final answer).
4. Iterate over every yielded event. For each event, print and append to `sample_events.jsonl`: the event type name, the timestamp, and the full JSON-serializable representation of the event payload.
5. After the run completes, print a summary: total events, list of distinct event types, and the wall-clock time for the full run.

`requirements.txt` for `poc/adk_event_stream/`:

    google-adk>=0.5.0
    python-dotenv>=1.0.0

After running the script, copy the printed `sample_events.jsonl` output into the Artifacts section of this plan. The file is also committed to git so teammates can review it without re-running the script.

The findings from this phase directly answer the question in ADL-011: "ADK の `runner.run_async()` から取得できるイベントの粒度・形式を着手前に確認する." Specifically, document:

- Which event types are emitted (e.g., `LlmRequest`, `LlmResponse`, `ToolCall`, `ToolResult`, `Error`, and any others).
- Whether partial/streaming tokens are exposed as separate events or batched into a single response event.
- The typical event count per agent turn.
- Whether each event is JSON-serializable as-is or requires custom serialization.

These findings determine the schema for `sessions/{sessionId}/agentEvents/{eventId}` in Firestore and whether the relay in ADL-011 (Option A: Firestore relay) needs any transformation step.


## Concrete Steps


### Working directory

All commands run from `/Users/ran/my-app/gen-fashion/` unless noted otherwise.

### Step 1: Create poc/ directory structure

    mkdir -p poc/image_generation/samples
    mkdir -p poc/image_generation/results
    mkdir -p poc/adk_event_stream

Add the results directory to `.gitignore` by appending the following line:

    poc/image_generation/results/

### Step 2: Add sample clothing images

Download two freely-licensed placeholder images (one shirt, one pair of pants) and save them as `poc/image_generation/samples/shirt.jpg` and `poc/image_generation/samples/pants.jpg`. Both must be JPEG, under 1 MB each, and under a license that permits redistribution.

### Step 3: Write `poc/image_generation/run_poc.py`

Create the file as described in Plan of Work Phase 1. The script structure in plain terms:

    import os, time, concurrent.futures
    from pathlib import Path
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parent / ".env")
    project = os.environ["GOOGLE_CLOUD_PROJECT"]

    SAMPLES = Path(__file__).parent / "samples"
    RESULTS = Path(__file__).parent / "results"
    RESULTS.mkdir(exist_ok=True)

    def run_imagen4(shirt_bytes, pants_bytes):
        import vertexai
        from vertexai.preview.vision_models import ImageGenerationModel
        vertexai.init(project=project, location="us-central1")
        model = ImageGenerationModel.from_pretrained("<imagen-4-model-id>")
        # ... call API, return image bytes

    def run_nanobanana2(shirt_bytes, pants_bytes):
        raise NotImplementedError("Verify Nano Banana 2 API before implementing")

    def main():
        shirt = (SAMPLES / "shirt.jpg").read_bytes()
        pants = (SAMPLES / "pants.jpg").read_bytes()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            f1 = ex.submit(run_imagen4, shirt, pants)
            f2 = ex.submit(run_nanobanana2, shirt, pants)
            # ... collect results, write to RESULTS, print summary

    if __name__ == "__main__":
        main()

Fill in the actual Imagen 4 model ID and Nano Banana 2 API call once confirmed. Wrap each `ex.submit` result in a try/except so one model failure does not stop the other.

### Step 4: Write `poc/image_generation/requirements.txt` and `.env.example`

    # requirements.txt
    google-cloud-aiplatform>=1.60.0
    python-dotenv>=1.0.0
    Pillow>=10.0.0

    # .env.example
    GOOGLE_CLOUD_PROJECT=your-gcp-project-id

### Step 5: Run the image generation PoC

    cd poc/image_generation
    pip install -r requirements.txt
    python run_poc.py

Expected console output (example — fill in actual times after running):

    [imagen4]   results/imagen4_result.jpg  (12.4s)
    [nanobanana2]  results/nanobanana2_result.jpg  (9.1s)

If either call fails, a `*_error.txt` file appears in `results/` instead. Open both output images in a viewer and compare. Fill in the Decision Log entry in this plan.

### Step 6: Provision Elasticsearch VM

Run from a terminal with `gcloud` authenticated to the target GCP project:

    gcloud compute instances create es-gen-fashion \
      --project=${GOOGLE_CLOUD_PROJECT} \
      --zone=asia-northeast1-a \
      --machine-type=e2-medium \
      --boot-disk-size=30 \
      --boot-disk-type=pd-ssd \
      --image-family=debian-12 \
      --image-project=debian-cloud \
      --tags=elasticsearch

Note the `INTERNAL_IP` printed in the output. Set it as `ES_INTERNAL_IP` for subsequent steps.

### Step 7: Install Elasticsearch on the VM

SSH into the VM and run the following as root or with sudo:

    wget -qO - https://artifacts.elastic.co/GPG-KEY-elasticsearch \
      | sudo gpg --dearmor -o /usr/share/keyrings/elasticsearch-keyring.gpg
    sudo apt-get install -y apt-transport-https
    echo "deb [signed-by=/usr/share/keyrings/elasticsearch-keyring.gpg] \
      https://artifacts.elastic.co/packages/8.x/apt stable main" \
      | sudo tee /etc/apt/sources.list.d/elastic-8.x.list
    sudo apt-get update && sudo apt-get install -y elasticsearch

Edit `/etc/elasticsearch/elasticsearch.yml` to add:

    network.host: 0.0.0.0
    discovery.type: single-node
    xpack.security.enabled: false

Then:

    sudo systemctl enable elasticsearch
    sudo systemctl start elasticsearch
    curl -s http://localhost:9200 | python3 -m json.tool

Expected: JSON response with `"tagline": "You Know, for Search"`.

### Step 8: Configure firewall and VPC connector

    gcloud compute firewall-rules create allow-es-from-vpc \
      --project=${GOOGLE_CLOUD_PROJECT} \
      --network=default \
      --allow=tcp:9200 \
      --source-ranges=10.0.0.0/8 \
      --target-tags=elasticsearch \
      --description="Allow Elasticsearch from internal VPC only"

    gcloud compute networks vpc-access connectors create gen-fashion-connector \
      --project=${GOOGLE_CLOUD_PROJECT} \
      --region=asia-northeast1 \
      --range=10.8.0.0/28

Wait for the connector to reach READY state:

    gcloud compute networks vpc-access connectors describe gen-fashion-connector \
      --region=asia-northeast1 \
      --project=${GOOGLE_CLOUD_PROJECT}

### Step 9: Verify Cloud Run → Elasticsearch connectivity

Deploy a minimal test service. Create `poc/es_connectivity_test/main.py`:

    import httpx, os
    from fastapi import FastAPI
    app = FastAPI()

    @app.get("/")
    def check():
        es_url = os.environ["ELASTICSEARCH_HOST"]
        r = httpx.get(es_url, timeout=5)
        return {"status": r.status_code, "body": r.json()}

Deploy to Cloud Run in `asia-northeast1` with the VPC connector:

    gcloud run deploy es-connectivity-test \
      --project=${GOOGLE_CLOUD_PROJECT} \
      --region=asia-northeast1 \
      --source=poc/es_connectivity_test/ \
      --set-env-vars=ELASTICSEARCH_HOST=http://${ES_INTERNAL_IP}:9200 \
      --vpc-connector=gen-fashion-connector \
      --vpc-egress=private-ranges-only \
      --allow-unauthenticated

Invoke the deployed service URL. Expected: `{"status": 200, "body": {"tagline": "You Know, for Search", ...}}`.

Delete the test service after confirming:

    gcloud run services delete es-connectivity-test \
      --project=${GOOGLE_CLOUD_PROJECT} \
      --region=asia-northeast1

### Step 10: Verify Japanese analyzer is not needed

From the VM or any machine that can reach ES (e.g., via the Cloud Run test above):

    # Create index with default analyzer
    curl -X PUT "http://${ES_INTERNAL_IP}:9200/test_jp_analyzer" \
      -H "Content-Type: application/json" \
      -d '{"settings":{"number_of_shards":1}}'

    # Index a document with a Japanese tag
    curl -X POST "http://${ES_INTERNAL_IP}:9200/test_jp_analyzer/_doc/1" \
      -H "Content-Type: application/json" \
      -d '{"tag":"ワンピース"}'

    # Query it back
    curl "http://${ES_INTERNAL_IP}:9200/test_jp_analyzer/_search?q=tag:ワンピース"

    # Clean up
    curl -X DELETE "http://${ES_INTERNAL_IP}:9200/test_jp_analyzer"

If the document appears in the search results, the standard analyzer is sufficient. Record the outcome in Surprises & Discoveries.

### Step 11: Update `.env.example` with ES host

Append to the root `.env.example`:

    # Elasticsearch — Compute Engine VM internal IP (set after M1-3 PoC)
    ELASTICSEARCH_HOST=http://<vm-internal-ip>:9200
    ELASTICSEARCH_VPC_CONNECTOR=gen-fashion-connector

### Step 12: Write `poc/adk_event_stream/run_poc.py`

Create the PoC script as described in Plan of Work Phase 4. The script must define a minimal tool (e.g., `get_weather` returning a fixed string) and drive the agent through one complete turn that triggers the tool. Capture every event from `runner.run_async()` and serialize it to `sample_events.jsonl` in the same directory.

Sample `requirements.txt`:

    google-adk>=0.5.0
    python-dotenv>=1.0.0

### Step 13: Run the ADK event stream PoC

    cd poc/adk_event_stream
    pip install -r requirements.txt
    python run_poc.py

After the run completes, copy the contents of `sample_events.jsonl` into the Artifacts section of this plan. Commit `sample_events.jsonl` to git.

Answer the following questions based on the output and record them in Artifacts:

- What distinct event type names appeared?
- Did any event type carry partial/streaming token data or only final responses?
- How many events occurred for a single two-step turn (reason → tool call → reason → answer)?
- Is each event directly JSON-serializable, or does it need custom handling (e.g., `datetime` objects, proto messages)?


## Validation and Acceptance


### M1-1 acceptance

Running `cd poc/image_generation && python run_poc.py` completes without an uncaught exception. The `results/` directory contains `imagen4_result.jpg` (or `imagen4_error.txt` if the API call failed) and the equivalent for Nano Banana 2.

### M1-2 acceptance

The Decision Log in this file contains a model choice entry with rationale. The chosen model is one of: Imagen 4, Nano Banana 2, or collage fallback (the last is valid and does not count as a failure).

### M1-3 acceptance

All four of these must be true:

- `curl http://localhost:9200` on the VM returns `"tagline": "You Know, for Search"`.
- `systemctl status elasticsearch` shows `active (running)` on the VM.
- The Cloud Run connectivity test service returns `{"status": 200, ...}` when invoked.
- `ELASTICSEARCH_HOST` is added to the root `.env.example` with the VM's internal IP.

### M1-4 acceptance

`sample_events.jsonl` exists at `poc/adk_event_stream/sample_events.jsonl` and is committed to git. The Artifacts section of this plan contains the event type summary and answers to the four questions in Step 13.


## Idempotence and Recovery


**Phase 1/2 (image gen PoC):** The script can be re-run any number of times. It overwrites `results/` files on each run. If a model call returns an error one run, fix the API call and re-run; the other model's result is also re-generated.

**Phase 3 (ES on GCE):**

- The `gcloud compute instances create` command will fail if a VM named `es-gen-fashion` already exists. Check with `gcloud compute instances describe es-gen-fashion --zone=asia-northeast1-a`. If it already exists, skip creation and proceed from Step 7.
- ES installation via apt is idempotent (`apt-get install` is a no-op if already installed).
- The firewall rule creation will fail if a rule with the same name exists. Check with `gcloud compute firewall-rules describe allow-es-from-vpc`.
- The VPC connector creation will fail if `gen-fashion-connector` already exists. Check with `gcloud compute networks vpc-access connectors describe gen-fashion-connector --region=asia-northeast1`.
- The test Cloud Run service must be deleted after use (Step 9 includes the delete command) so it does not incur idle cost.

**Phase 4 (ADK event stream PoC):** The script can be re-run freely. Each run overwrites `sample_events.jsonl`. Re-running after a failure is safe.

**Recovery for GCE VM failure:** If the VM becomes unresponsive, `gcloud compute instances reset es-gen-fashion --zone=asia-northeast1-a` performs a hard restart. If ES fails to start after reset, SSH in and check `journalctl -u elasticsearch -n 50` for the failure reason.


## Artifacts and Notes


(Populate during execution. Include VM internal IP, VPC connector name, PoC run timestamps, image gen decision evidence, and the full `sample_events.jsonl` content once captured.)

**Image gen (M1-1/M1-2):** `poc/image_generation/run_poc.py` run 2026-06-03 on `gemini-2.5-flash-image` @ `us-central1`, project `gen-story-496911`, 2 garment inputs → faithful two-garment try-on in ~13.6s. Output `results/nanobanana_result.jpg` (git-ignored). Imagen comparison: `imagen-3.0-capability-001` produced a non-faithful generic outfit and was dropped.

**ES VM internal IP:** (TBD)

**VPC connector name:** `gen-fashion-connector`

**ADK event schema (M1-4):** Run 2026-06-04, model `gemini-2.5-flash` on Vertex AI `us-central1`, project `gen-story-496911`. Elapsed: 3.27s. `sample_events.jsonl` committed at `poc/adk_event_stream/sample_events.jsonl`.

Schema questions answered:

1. **Distinct event types:** Only `Event` (single class in ADK 2.1.0). No distinct `LlmRequest`, `LlmResponse`, `ToolCall`, `ToolResult` subtypes. Content type is determined by inspecting `payload.content.parts[*]` fields:
   - `function_call` present → model-initiated tool call (seq 1)
   - `function_response` present → tool result injected into context (seq 2)
   - `text` present + `is_final_response()` → final answer (seq 3)

2. **Streaming vs batched:** Tokens are **batched** — no partial/streaming token events. Each `Event` delivers a complete payload. The `partial` field is always `null`. Accordion UI must wait for the final event (`is_final_response()`) before displaying the answer; intermediate events (ToolCall, ToolResponse) can be displayed as they arrive.

3. **Event count per turn:** **3 events** for one complete turn: reason→tool call (1) → tool result (2) → final answer (3). Turns without tool calls would be 1 event.

4. **JSON serialisability:** `model_dump()` (Pydantic) works. However: `thought_signature` contains raw bytes serialized as a Python bytes literal string (e.g., `"b'\\n\\xce...'"`) — this is not valid JSON for Firestore and must be base64-encoded or stored as a Firestore `Bytes` field. All other fields are natively JSON-serializable.

   **ADL-011 Firestore relay implication:** A minimal transformation step is needed — strip or base64-encode `thought_signature` before writing to `sessions/{sessionId}/agentEvents/{eventId}`.


## Interfaces and Dependencies


**Imagen 4 (M1-1):**

- Library: `google-cloud-aiplatform` ≥ 1.60.0 and `vertexai`
- Auth: Application Default Credentials with `roles/aiplatform.user` on the GCP project
- Region: `us-central1` (Vertex AI image generation is only available in select regions; verify Imagen 4 region availability)
- Model name: confirm the exact model ID from the Vertex AI model garden — the requirements reference "Imagen 4", which maps to the latest `imagegeneration` model version

**Nano Banana 2 (M1-1):**

- API endpoint, SDK, and authentication method must be confirmed from the model's documentation before the PoC function can be implemented. If unavailable, stub the function and document in Decision Log.

**Google ADK Python SDK (M1-4):**

- Library: `google-adk` ≥ 0.5.0
- The `Runner`, `Agent`, `InMemorySessionService` classes are the minimal surface needed for this PoC
- Auth: same ADC / GCP project credentials used for Gemini API calls
- The exact import paths should be verified against the installed package version at the time of implementation

**GCP APIs to enable before starting:**

- Vertex AI API (`aiplatform.googleapis.com`) — for Imagen 4 calls
- Compute Engine API (`compute.googleapis.com`) — for VM creation
- Serverless VPC Access API (`vpcaccess.googleapis.com`) — for VPC connector
- Cloud Run API (`run.googleapis.com`) — for the connectivity test service

**Downstream milestones unblocked by M1:**

- M2-9 (`ElasticsearchEmbeddingRepository`) requires the ES host URL confirmed in M1-3.
- M4-7 (`style_synthesizer` tool) requires the model decision from M1-2.
- M5-8 (ADK → Firestore event relay) requires the event schema confirmed in M1-4.
- M5-9 (SSE streaming endpoint) depends on M5-8, which depends on M1-4.
