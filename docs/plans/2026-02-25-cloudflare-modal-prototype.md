# Cloudflare Pages + Modal Prototype Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a minimal end-to-end prototype proving the CF Pages + Modal architecture with mock STREAMS evaluation results.

**Architecture:** Static HTML frontend on Cloudflare Pages, with edge functions proxying authenticated requests to a Modal serverless Python backend. Modal returns mock checklist assessment results after a simulated delay.

**Tech Stack:** Cloudflare Pages + Wrangler, Modal, vanilla HTML/JS, Python

---

### Task 1: Install CLI Tools

**Files:** None (system setup)

**Step 1: Install Modal CLI**

Run:
```bash
uv tool install modal
```

**Step 2: Authenticate Modal**

Run:
```bash
modal setup
```
Expected: Opens browser for Modal account creation/login. Creates `~/.modal.toml`.

**Step 3: Install Wrangler CLI**

Run:
```bash
npm install -g wrangler
```

**Step 4: Authenticate Wrangler**

Run:
```bash
wrangler login
```
Expected: Opens browser for Cloudflare account login.

**Step 5: Verify both CLIs**

Run:
```bash
modal --version && wrangler --version
```
Expected: Both print version numbers.

---

### Task 2: Modal Backend — Mock Evaluation Endpoint

**Files:**
- Create: `deploy/modal/app.py`

**Step 1: Create the Modal app with mock evaluation**

Create `deploy/modal/app.py`:

```python
"""Modal backend for STREAMS Agent prototype."""

import modal
import uuid
import time
import json
import os

app = modal.App("streams-agent-prototype")

# In-memory job store (ephemeral — fine for prototype)
job_store = modal.Dict.from_name("streams-jobs", create_if_missing=True)

MOCK_RESULTS = {
    "assessments": [
        {"item_id": "1.1", "rating": "Yes", "comments": "Abstract clearly states study design.", "confidence": 0.9},
        {"item_id": "1.2", "rating": "No", "comments": "No mention of environment type in abstract.", "confidence": 0.85},
        {"item_id": "2.1", "rating": "Partial", "comments": "Methods section lacks detail on sample collection.", "confidence": 0.7},
        {"item_id": "2.2", "rating": "Yes", "comments": "DNA extraction protocol well documented.", "confidence": 0.95},
        {"item_id": "3.1", "rating": "NA", "comments": "Not applicable to this study type.", "confidence": 0.8},
    ],
    "summary": {
        "total_items": 5,
        "yes": 2,
        "no": 1,
        "partial": 1,
        "na": 1,
    },
}


def _check_secret(headers: dict) -> bool:
    """Verify the shared secret from CF Pages."""
    expected = os.environ.get("API_SECRET", "dev-secret")
    auth = headers.get("x-api-secret", "")
    return auth == expected


@app.function(secrets=[modal.Secret.from_name("streams-agent-secrets", required_modules=[], create_if_missing=True)])
@modal.web_endpoint(method="POST")
def submit(data: dict) -> dict:
    """Accept a job submission, spawn async evaluation, return job ID."""
    # In production, check secret. For local dev, skip if not set.
    job_id = str(uuid.uuid4())
    job_store[job_id] = {
        "status": "running",
        "paper_id": data.get("paper_id", "unknown"),
        "submitted_at": time.time(),
        "results": None,
    }
    # Spawn the async evaluation
    evaluate.spawn(job_id)
    return {"job_id": job_id}


@app.function(secrets=[modal.Secret.from_name("streams-agent-secrets", required_modules=[], create_if_missing=True)])
@modal.web_endpoint(method="GET")
def status(job_id: str) -> dict:
    """Check job status and return results if complete."""
    try:
        job = job_store[job_id]
    except KeyError:
        return {"error": "Job not found", "job_id": job_id}
    return job


@app.function(secrets=[modal.Secret.from_name("streams-agent-secrets", required_modules=[], create_if_missing=True)])
def evaluate(job_id: str):
    """Mock evaluation — sleep then store results."""
    time.sleep(5)  # Simulate agent work
    job = job_store[job_id]
    job["status"] = "complete"
    job["results"] = MOCK_RESULTS
    job["completed_at"] = time.time()
    job_store[job_id] = job
```

**Step 2: Test Modal app locally**

Run:
```bash
modal serve deploy/modal/app.py
```
Expected: Prints URLs for `submit` and `status` endpoints. Keep this running.

**Step 3: Smoke test with curl**

In a separate terminal:
```bash
# Submit a job
curl -X POST <submit-url> -H "Content-Type: application/json" -d '{"paper_id": "test123"}'
# Returns: {"job_id": "some-uuid"}

# Wait 6 seconds, then check status
sleep 6
curl "<status-url>?job_id=<the-uuid>"
# Returns: {"status": "complete", "results": {...}}
```
Expected: Job completes with mock results after ~5s.

**Step 4: Commit**

```bash
git add deploy/modal/app.py
git commit -m "feat: add Modal backend with mock STREAMS evaluation"
```

---

### Task 3: Cloudflare Pages Frontend — Static HTML

**Files:**
- Create: `deploy/frontend/index.html`

**Step 1: Create the single-page frontend**

Create `deploy/frontend/index.html` — a minimal page with:
- Paper ID text input
- File input for PDF (captured but not sent in prototype — just proves the form works)
- Submit button
- Status area that shows "Running..." then results
- JavaScript that POSTs to `/api/submit`, then polls `/api/status/:id` every 2s
- Hardcoded `Authorization: Bearer test-token` header on all API calls
- Clean, minimal styling (no framework needed)

The JS fetch calls go to relative paths (`/api/submit`, `/api/status/...`) — CF Pages Functions will handle routing.

**Step 2: Test static file serves**

Run:
```bash
npx wrangler pages dev deploy/frontend/
```
Expected: Opens local server (default port 8788). Page loads but API calls will 404 (functions not written yet).

**Step 3: Commit**

```bash
git add deploy/frontend/index.html
git commit -m "feat: add static frontend for STREAMS evaluation prototype"
```

---

### Task 4: Cloudflare Pages Functions — Auth Proxy

**Files:**
- Create: `deploy/frontend/functions/api/submit.js`
- Create: `deploy/frontend/functions/api/status/[id].js`

**Step 1: Create the submit proxy function**

Create `deploy/frontend/functions/api/submit.js`:

```javascript
export async function onRequestPost(context) {
  // Mock auth check
  const auth = context.request.headers.get("Authorization");
  if (auth !== "Bearer test-token") {
    return new Response(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  // Forward to Modal
  const modalUrl = context.env.MODAL_SUBMIT_URL;
  if (!modalUrl) {
    return new Response(JSON.stringify({ error: "MODAL_SUBMIT_URL not configured" }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  const body = await context.request.json();
  const resp = await fetch(modalUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-secret": context.env.API_SECRET || "dev-secret",
    },
    body: JSON.stringify(body),
  });

  const result = await resp.json();
  return new Response(JSON.stringify(result), {
    status: resp.status,
    headers: { "Content-Type": "application/json" },
  });
}
```

**Step 2: Create the status proxy function**

Create `deploy/frontend/functions/api/status/[id].js`:

```javascript
export async function onRequestGet(context) {
  // Mock auth check
  const auth = context.request.headers.get("Authorization");
  if (auth !== "Bearer test-token") {
    return new Response(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  const jobId = context.params.id;
  const modalUrl = context.env.MODAL_STATUS_URL;
  if (!modalUrl) {
    return new Response(JSON.stringify({ error: "MODAL_STATUS_URL not configured" }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  const resp = await fetch(`${modalUrl}?job_id=${jobId}`, {
    headers: {
      "x-api-secret": context.env.API_SECRET || "dev-secret",
    },
  });

  const result = await resp.json();
  return new Response(JSON.stringify(result), {
    status: resp.status,
    headers: { "Content-Type": "application/json" },
  });
}
```

**Step 3: Test end-to-end locally**

Terminal 1 (keep Modal running):
```bash
modal serve deploy/modal/app.py
```

Terminal 2 (start CF Pages with Modal URLs):
```bash
npx wrangler pages dev deploy/frontend/ \
  --binding MODAL_SUBMIT_URL=<modal-submit-url> \
  --binding MODAL_STATUS_URL=<modal-status-url> \
  --binding API_SECRET=dev-secret
```

Open browser to http://localhost:8788, enter a paper ID, click Submit.
Expected: Shows "Running...", then after ~5s shows mock results.

**Step 4: Commit**

```bash
git add deploy/frontend/functions/
git commit -m "feat: add CF Pages Functions for auth proxy to Modal"
```

---

### Task 5: Deploy to Production

**Files:** None (CLI operations)

**Step 1: Deploy Modal**

```bash
modal deploy deploy/modal/app.py
```
Expected: Prints production URLs for `submit` and `status` endpoints. Save these.

**Step 2: Create Cloudflare Pages project**

```bash
wrangler pages project create streams-agent-prototype
```

**Step 3: Set environment variables in Cloudflare**

```bash
wrangler pages secret put MODAL_SUBMIT_URL   # paste Modal submit URL
wrangler pages secret put MODAL_STATUS_URL    # paste Modal status URL
wrangler pages secret put API_SECRET          # choose a real secret
```

**Step 4: Deploy frontend**

```bash
wrangler pages deploy deploy/frontend/ --project-name streams-agent-prototype
```
Expected: Prints a `*.pages.dev` URL.

**Step 5: Smoke test production**

Open the `*.pages.dev` URL in a browser. Submit a paper ID. Verify mock results appear after ~5s.

**Step 6: Commit any final tweaks**

```bash
git add -A deploy/
git commit -m "feat: production deployment of CF Pages + Modal prototype"
```

---

## Task Summary

| Task | What | Time |
|------|------|------|
| 1 | Install & auth CLI tools | 5 min |
| 2 | Modal backend with mock eval | 10 min |
| 3 | Static HTML frontend | 10 min |
| 4 | CF Pages Functions (auth proxy) | 10 min |
| 5 | Deploy to production | 5 min |
