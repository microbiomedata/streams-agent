"""Modal backend for STREAMS Agent prototype."""

import modal
import uuid
import time
import math
import io
import re

image = modal.Image.debian_slim().pip_install("fastapi[standard]", "pymupdf", "python-docx")

app = modal.App("streams-agent-prototype")

# In-memory stores (ephemeral — fine for prototype)
job_store = modal.Dict.from_name("streams-jobs", create_if_missing=True)
job_index = modal.Dict.from_name("streams-job-index", create_if_missing=True)
rate_store = modal.Dict.from_name("streams-rate-limits", create_if_missing=True)

MOCK_STEPS = [
    {
        "message": "Reading paper and extracting sections...",
        "assessments": [],
    },
    {
        "message": "Evaluating Section 1: Title and Abstract...",
        "assessments": [
            {"item_id": "1.1", "rating": "Yes", "comments": "Abstract clearly states study design.", "confidence": 0.9},
            {"item_id": "1.2", "rating": "No", "comments": "No mention of environment type in abstract.", "confidence": 0.85},
        ],
    },
    {
        "message": "Evaluating Section 2: Methods...",
        "assessments": [
            {"item_id": "2.1", "rating": "Partial", "comments": "Methods section lacks detail on sample collection.", "confidence": 0.7},
            {"item_id": "2.2", "rating": "Yes", "comments": "DNA extraction protocol well documented.", "confidence": 0.95},
            {"item_id": "2.3", "rating": "Yes", "comments": "Sequencing platform and parameters reported.", "confidence": 0.9},
        ],
    },
    {
        "message": "Evaluating Section 3: Results and Data Availability...",
        "assessments": [
            {"item_id": "3.1", "rating": "NA", "comments": "Not applicable to this study type.", "confidence": 0.8},
            {"item_id": "3.2", "rating": "Yes", "comments": "Raw sequences deposited in public repository.", "confidence": 0.95},
        ],
    },
    {
        "message": "Evaluating Section 4: Statistical Analysis...",
        "assessments": [
            {"item_id": "4.1", "rating": "Partial", "comments": "Alpha diversity reported but beta diversity analysis incomplete.", "confidence": 0.75},
            {"item_id": "4.2", "rating": "No", "comments": "No correction for multiple comparisons.", "confidence": 0.85},
        ],
    },
    {
        "message": "Generating summary...",
        "assessments": [],
    },
]

INDEX_KEY = "_all_jobs"
ANON_LIMIT = 3  # jobs per hour for anonymous users
MAX_RUNNING = 3  # max concurrent running jobs per user


def _hour_bucket() -> str:
    """Current hour bucket key for rate limiting."""
    return str(math.floor(time.time() / 3600))


def _count_running_jobs(user_id: str) -> int:
    """Count how many jobs are currently running for a user."""
    ids = job_index.get(INDEX_KEY, [])
    count = 0
    for jid in ids:
        if jid in job_store:
            job = job_store[jid]
            if job.get("user_id") == user_id and job.get("status") == "running":
                count += 1
    return count


def _extract_title_from_pdf(data: bytes) -> str:
    """Extract title from PDF using pymupdf. Tries metadata first, then first lines.

    Returns empty string if the file cannot be parsed as a valid PDF.
    """
    import pymupdf

    if len(data) < 10 or not data[:5].startswith(b"%PDF-"):
        return ""

    doc = pymupdf.open(stream=data, filetype="pdf")

    # Try metadata title
    meta = doc.metadata
    if meta and meta.get("title") and meta["title"].strip():
        title = meta["title"].strip()
        doc.close()
        return title

    # Fall back to first page text — title is usually the largest/first text
    if doc.page_count > 0:
        page = doc[0]
        blocks = page.get_text("blocks")
        # blocks are (x0, y0, x1, y1, text, block_no, block_type)
        # Take the first non-empty text block
        for block in sorted(blocks, key=lambda b: (b[1], b[0])):
            text = block[4].strip() if len(block) > 4 else ""
            # Skip very short lines (page numbers, headers) and very long ones (abstracts)
            if 10 < len(text) < 300:
                doc.close()
                # Clean up: take first line if multi-line
                return text.split("\n")[0].strip()

    doc.close()
    return ""


def _extract_title_from_docx(data: bytes) -> str:
    """Extract title from DOCX — first heading or first paragraph.

    Returns empty string if the file cannot be parsed as a valid DOCX.
    """
    from docx import Document

    if len(data) < 10 or data[:2] != b"PK":
        return ""

    doc = Document(io.BytesIO(data))
    # Try headings first
    for para in doc.paragraphs:
        if para.style.name.startswith("Heading") and para.text.strip():
            return para.text.strip()
    # Fall back to first non-empty paragraph
    for para in doc.paragraphs:
        text = para.text.strip()
        if 10 < len(text) < 300:
            return text
    return ""


def _slugify(title: str) -> str:
    """Convert a title to a short paper-id-style slug."""
    title = title.lower()
    title = re.sub(r"[^a-z0-9\s]", "", title)
    words = title.split()[:6]
    return "_".join(words) if words else "untitled"


@app.function(image=image)
@modal.fastapi_endpoint(method="POST")
def extract_title(data: dict) -> dict:
    """Extract title from a document. Accepts JSON with base64-encoded file_bytes and filename."""
    import base64
    file_bytes = data.get("file_bytes", "")
    filename = data.get("filename", "")
    decoded = base64.b64decode(file_bytes)
    lower = filename.lower()

    title = ""
    if lower.endswith(".pdf"):
        title = _extract_title_from_pdf(decoded)
    elif lower.endswith(".docx"):
        title = _extract_title_from_docx(decoded)
    else:
        return {"title": "", "slug": "", "error": f"Unsupported file type: {filename}"}

    slug = _slugify(title) if title else ""
    return {"title": title, "slug": slug}


@app.function(image=image)
@modal.fastapi_endpoint(method="POST")
def submit(data: dict) -> dict:
    """Accept a job submission, spawn async evaluation, return job ID."""
    user_id = data.get("user_id", "anon:unknown")
    is_anon = user_id.startswith("anon:")

    # Limit concurrent running jobs for all users
    running = _count_running_jobs(user_id)
    if running >= MAX_RUNNING:
        return {
            "error": f"You already have {running} running jobs. Please wait for one to finish.",
            "running": running,
            "max_running": MAX_RUNNING,
        }

    # Rate limit anonymous users (hourly submission cap)
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
        "progress": "Queued...",
        "paper_id": data.get("paper_id", "unknown"),
        "user_id": user_id,
        "submitted_at": time.time(),
        "results": None,
    }
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


@app.function(image=image, timeout=300)
def evaluate(job_id: str):
    """Mock evaluation — simulate multi-step agent with progress updates."""
    import random

    all_assessments = []

    for step in MOCK_STEPS:
        # Update progress message
        job = job_store[job_id]
        job["progress"] = step["message"]
        job_store[job_id] = job

        # Simulate work (2-5 seconds per step)
        time.sleep(random.uniform(2, 5))

        # Accumulate assessments
        all_assessments.extend(step["assessments"])

    # Compute summary from accumulated assessments
    ratings = [a["rating"] for a in all_assessments]
    summary = {
        "total_items": len(all_assessments),
        "yes": ratings.count("Yes"),
        "no": ratings.count("No"),
        "partial": ratings.count("Partial"),
        "na": ratings.count("NA"),
    }

    job = job_store[job_id]
    job["status"] = "complete"
    job["progress"] = "Complete"
    job["results"] = {"assessments": all_assessments, "summary": summary}
    job["completed_at"] = time.time()
    job_store[job_id] = job
