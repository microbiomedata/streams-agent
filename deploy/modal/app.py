"""Modal backend for STREAMS Agent prototype."""

import modal
import uuid
import time
import math

image = modal.Image.debian_slim().pip_install("fastapi[standard]")

app = modal.App("streams-agent-prototype")

# In-memory stores (ephemeral — fine for prototype)
job_store = modal.Dict.from_name("streams-jobs", create_if_missing=True)
job_index = modal.Dict.from_name("streams-job-index", create_if_missing=True)
rate_store = modal.Dict.from_name("streams-rate-limits", create_if_missing=True)

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

INDEX_KEY = "_all_jobs"
ANON_LIMIT = 3  # jobs per hour for anonymous users


def _hour_bucket() -> str:
    """Current hour bucket key for rate limiting."""
    return str(math.floor(time.time() / 3600))


@app.function(image=image)
@modal.fastapi_endpoint(method="POST")
def submit(data: dict) -> dict:
    """Accept a job submission, spawn async evaluation, return job ID.

    Expects data with:
      - paper_id: str
      - user_id: str (ORCID iD or "anon:<ip>")
    """
    user_id = data.get("user_id", "anon:unknown")
    is_anon = user_id.startswith("anon:")

    # Rate limit anonymous users
    if is_anon:
        bucket = _hour_bucket()
        rate_key = f"rate:{user_id}:{bucket}"
        count = rate_store.get(rate_key, 0)
        if count >= ANON_LIMIT:
            return {
                "error": "Rate limit exceeded. Sign in with ORCID for unlimited access.",
                "limit": ANON_LIMIT,
                "remaining": 0,
            }
        rate_store[rate_key] = count + 1

    job_id = str(uuid.uuid4())
    job_store[job_id] = {
        "status": "running",
        "paper_id": data.get("paper_id", "unknown"),
        "user_id": user_id,
        "submitted_at": time.time(),
        "results": None,
    }
    # Append to index
    ids = job_index.get(INDEX_KEY, [])
    ids.append(job_id)
    job_index[INDEX_KEY] = ids

    evaluate.spawn(job_id)

    resp = {"job_id": job_id}
    if is_anon:
        bucket = _hour_bucket()
        rate_key = f"rate:{user_id}:{bucket}"
        resp["remaining"] = ANON_LIMIT - rate_store.get(rate_key, 0)
    return resp


@app.function(image=image)
@modal.fastapi_endpoint(method="GET")
def status(job_id: str) -> dict:
    """Check job status and return results if complete."""
    if job_id not in job_store:
        return {"error": "Job not found", "job_id": job_id}
    return job_store[job_id]


@app.function(image=image)
@modal.fastapi_endpoint(method="GET")
def jobs(user_id: str = "") -> dict:
    """List jobs, optionally filtered by user_id."""
    ids = job_index.get(INDEX_KEY, [])
    job_list = []
    for jid in ids:
        if jid in job_store:
            job = job_store[jid]
            if user_id and job.get("user_id") != user_id:
                continue
            job_list.append({
                "job_id": jid,
                "paper_id": job.get("paper_id", "unknown"),
                "status": job.get("status", "unknown"),
                "user_id": job.get("user_id", ""),
                "submitted_at": job.get("submitted_at"),
                "completed_at": job.get("completed_at"),
            })
    return {"jobs": job_list}


@app.function(image=image)
def evaluate(job_id: str):
    """Mock evaluation — sleep then store results."""
    time.sleep(5)  # Simulate agent work
    job = job_store[job_id]
    job["status"] = "complete"
    job["results"] = MOCK_RESULTS
    job["completed_at"] = time.time()
    job_store[job_id] = job
