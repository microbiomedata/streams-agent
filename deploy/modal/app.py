"""Modal backend for STREAMS Agent prototype."""

import modal
import uuid
import time
import os

image = modal.Image.debian_slim().pip_install("fastapi[standard]")

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


@app.function(image=image)
@modal.fastapi_endpoint(method="POST")
def submit(data: dict) -> dict:
    """Accept a job submission, spawn async evaluation, return job ID."""
    job_id = str(uuid.uuid4())
    job_store[job_id] = {
        "status": "running",
        "paper_id": data.get("paper_id", "unknown"),
        "submitted_at": time.time(),
        "results": None,
    }
    evaluate.spawn(job_id)
    return {"job_id": job_id}


@app.function(image=image)
@modal.fastapi_endpoint(method="GET")
def status(job_id: str) -> dict:
    """Check job status and return results if complete."""
    if job_id not in job_store:
        return {"error": "Job not found", "job_id": job_id}
    return job_store[job_id]


@app.function(image=image)
def evaluate(job_id: str):
    """Mock evaluation — sleep then store results."""
    time.sleep(5)  # Simulate agent work
    job = job_store[job_id]
    job["status"] = "complete"
    job["results"] = MOCK_RESULTS
    job["completed_at"] = time.time()
    job_store[job_id] = job
