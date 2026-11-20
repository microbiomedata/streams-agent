"""Modal backend for STREAMS Agent — real agentic review via Claude Agent SDK."""

import math
import io
import json
import os
import re
import sys
import time
import uuid

import modal

# ---------------------------------------------------------------------------
# Image: Python deps + Node.js 20 + claude-code CLI
# ---------------------------------------------------------------------------
image = (
    modal.Image.debian_slim()
    .apt_install("git")
    .pip_install(
        "fastapi[standard]",
        "pymupdf",
        "python-docx",
        "claude-agent-sdk",
        "pydantic",
        "pyyaml",
        "linkml-runtime",
        "anyio",
    )
    .run_commands(
        # Create non-root user — Claude Code refuses bypassPermissions as root
        "useradd -m -s /bin/bash agent",
        # Pre-init a git repo in agent home (CLI hangs in non-git dirs)
        "su - agent -c 'git init /home/agent/workspace'",
    )
    .env({
        "ADMIN_ORCIDS": "0000-0002-6601-2165",
        "DISABLE_AUTOUPDATER": "1",
    })
    .add_local_dir("../../src", remote_path="/home/agent/src")
)

app = modal.App("streams-agent-prototype")

# ---------------------------------------------------------------------------
# Stores
# ---------------------------------------------------------------------------
job_store = modal.Dict.from_name("streams-jobs", create_if_missing=True)
job_index = modal.Dict.from_name("streams-job-index", create_if_missing=True)
rate_store = modal.Dict.from_name("streams-rate-limits", create_if_missing=True)
budget_store = modal.Dict.from_name("streams-budgets", create_if_missing=True)
trace_store = modal.Dict.from_name("streams-traces", create_if_missing=True)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
INDEX_KEY = "_all_jobs"
ANON_LIMIT = 3          # jobs per hour for anonymous users
MAX_RUNNING = 3          # max concurrent running jobs per user
CREDIT_LIMIT = 5.0       # $5 per user
CREDITS_PER_DOLLAR = 100  # 1 credit = $0.01
TOTAL_ITEMS = 67          # total STREAMS checklist items (numeric IDs only)
EVAL_TIMEOUT = 900       # seconds — must match @app.function timeout
VALID_MODELS = {"haiku", "sonnet", "opus"}
MODEL_COST_ESTIMATES = {"haiku": 0.15, "sonnet": 0.90, "opus": 0.80}
ADMIN_ORCIDS = set(
    orcid.strip()
    for orcid in os.environ.get("ADMIN_ORCIDS", "").split(",")
    if orcid.strip()
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _hour_bucket() -> str:
    """Current hour bucket key for rate limiting."""
    return str(math.floor(time.time() / 3600))


def _count_running_jobs(user_id: str) -> int:
    """Count how many jobs are currently running for a user."""
    ids = job_index.get(INDEX_KEY, [])
    count = 0
    for jid in ids:
        if jid in job_store:
            job = _expire_if_stale(jid, job_store[jid])
            if job.get("user_id") == user_id and job.get("status") == "running":
                count += 1
    return count


def _expire_if_stale(job_id: str, job: dict) -> dict:
    """Mark a running job as failed if it has exceeded the timeout.

    When Modal kills a function on timeout, the except block never runs,
    leaving the job stuck as 'running' forever.
    """
    if job.get("status") != "running":
        return job
    submitted = job.get("submitted_at", 0)
    if submitted and (time.time() - submitted) > EVAL_TIMEOUT + 60:
        job["status"] = "failed"
        job["progress"] = "Error: job timed out (exceeded 15 min limit)"
        job["error_log"] = (
            "Job exceeded the maximum runtime of 15 minutes.\n"
            "The Modal function was likely killed by the platform timeout.\n"
            f"Last known progress: {job.get('progress', 'unknown')}"
        )
        job_store[job_id] = job
    return job


def _get_budget(user_id: str) -> dict:
    """Get or initialize budget for a user."""
    budget = budget_store.get(user_id, None)
    if budget is None:
        budget = {"credits_spent": 0.0, "jobs_completed": 0}
        budget_store[user_id] = budget
    credits_total = CREDIT_LIMIT * CREDITS_PER_DOLLAR
    credits_spent = budget.get("credits_spent", 0.0)
    return {
        "credits_total": credits_total,
        "credits_spent": credits_spent,
        "credits_remaining": credits_total - credits_spent,
        "jobs_completed": budget.get("jobs_completed", 0),
    }


def _extract_title_from_pdf(data: bytes) -> str:
    """Extract title from PDF using pymupdf."""
    import pymupdf

    if len(data) < 10 or not data[:5].startswith(b"%PDF-"):
        return ""

    doc = pymupdf.open(stream=data, filetype="pdf")

    meta = doc.metadata
    if meta and meta.get("title") and meta["title"].strip():
        title = meta["title"].strip()
        doc.close()
        return title

    if doc.page_count > 0:
        page = doc[0]
        blocks = page.get_text("blocks")
        for block in sorted(blocks, key=lambda b: (b[1], b[0])):
            text = block[4].strip() if len(block) > 4 else ""
            if 10 < len(text) < 300:
                doc.close()
                return text.split("\n")[0].strip()

    doc.close()
    return ""


def _extract_title_from_docx(data: bytes) -> str:
    """Extract title from DOCX — first heading or first paragraph."""
    from docx import Document

    if len(data) < 10 or data[:2] != b"PK":
        return ""

    doc = Document(io.BytesIO(data))
    for para in doc.paragraphs:
        if para.style.name.startswith("Heading") and para.text.strip():
            return para.text.strip()
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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
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
    """Accept a job submission with PDF and model, spawn async evaluation."""
    user_id = data.get("user_id", "anon:unknown")
    is_anon = user_id.startswith("anon:")
    model = data.get("model", "haiku")
    pdf_base64 = data.get("pdf_base64", "")
    filename = data.get("filename", "paper.pdf")
    item_ids = data.get("item_ids", None)  # e.g. ["1.1", "1.2"] for quick test

    # Validate model
    if model not in VALID_MODELS:
        return {"error": f"Invalid model '{model}'. Choose from: {', '.join(sorted(VALID_MODELS))}"}

    # Validate PDF presence
    if not pdf_base64:
        return {"error": "A paper file is required. Please upload a file."}

    # Check budget (skip if user provided their own OAuth token)
    has_own_key = bool(data.get("oauth_token", ""))
    user_budget = _get_budget(user_id)
    if not has_own_key and user_budget["credits_remaining"] <= 0:
        return {
            "error": "No credits remaining. Contact the project team for more credits.",
            "credits_remaining": 0,
        }

    # Limit concurrent running jobs for all users
    running = _count_running_jobs(user_id)
    if running >= MAX_RUNNING:
        return {
            "error": f"You already have {running} running jobs. Please wait for one to finish.",
            "running": running,
            "max_running": MAX_RUNNING,
        }

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
    estimated_cost = MODEL_COST_ESTIMATES.get(model, 0.50)
    estimated_credits = estimated_cost * CREDITS_PER_DOLLAR

    job_store[job_id] = {
        "status": "running",
        "progress": "Starting agentic review...",
        "paper_id": data.get("paper_id", "unknown"),
        "user_id": user_id,
        "model": model,
        "submitted_at": time.time(),
        "results": None,
        "rated_count": 0,
        "total_items": len(item_ids) if item_ids else TOTAL_ITEMS,
        "cost_usd": None,
    }
    ids = job_index.get(INDEX_KEY, [])
    ids.append(job_id)
    job_index[INDEX_KEY] = ids

    oauth_token = data.get("oauth_token", "")
    evaluate.spawn(job_id, pdf_base64, filename, model, oauth_token, item_ids)

    resp = {
        "job_id": job_id,
        "credits_remaining": user_budget["credits_remaining"],
        "estimated_cost_credits": estimated_credits,
    }
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
    job = job_store[job_id]
    return _expire_if_stale(job_id, job)


@app.function(image=image)
@modal.fastapi_endpoint(method="GET")
def jobs(user_id: str = "") -> dict:
    """List jobs filtered to the requesting user. Admins see all jobs."""
    is_admin = user_id in ADMIN_ORCIDS
    ids = job_index.get(INDEX_KEY, [])
    job_list = []
    for jid in ids:
        if jid in job_store:
            job = _expire_if_stale(jid, job_store[jid])
            if not is_admin and user_id and job.get("user_id") != user_id:
                continue
            job_list.append({
                "job_id": jid,
                "paper_id": job.get("paper_id", "unknown"),
                "status": job.get("status", "unknown"),
                "user_id": job.get("user_id", ""),
                "model": job.get("model", ""),
                "submitted_at": job.get("submitted_at"),
                "completed_at": job.get("completed_at"),
            })
    return {"jobs": job_list}


@app.function(image=image)
@modal.fastapi_endpoint(method="GET")
def budget(user_id: str) -> dict:
    """Get credit budget for a user."""
    return _get_budget(user_id)


@app.function(image=image)
@modal.fastapi_endpoint(method="GET")
def trace(job_id: str) -> dict:
    """Download trace JSON for a completed job."""
    if job_id not in trace_store:
        return {"error": "Trace not found", "job_id": job_id}
    return trace_store[job_id]


# ---------------------------------------------------------------------------
# Evaluate — real agentic review
# ---------------------------------------------------------------------------
@app.function(
    image=image,
    timeout=900,
    memory=4096,
    secrets=[modal.Secret.from_name("claude-oauth-token")],
)
def evaluate(job_id: str, pdf_base64: str, filename: str, model: str, oauth_token: str = "", item_ids: list[str] | None = None):
    """Run a real STREAMS agentic review using Claude Agent SDK.

    If oauth_token is provided (for testing), it is set as
    CLAUDE_CODE_OAUTH_TOKEN so the Claude Code CLI authenticates via
    OAuth instead of requiring an ANTHROPIC_API_KEY secret.

    If item_ids is provided, only those checklist items are evaluated
    (useful for quick testing).
    """
    import base64
    import tempfile
    import threading
    from pathlib import Path

    import yaml

    # Use OAuth token for Claude Code CLI if provided (per-request override)
    if oauth_token:
        os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = oauth_token

    # Pre-flight auth check — fail fast with a clear message
    has_api_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_oauth = bool(os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"))
    if not has_api_key and not has_oauth:
        raise RuntimeError(
            "No authentication configured. Set one of:\n"
            "  - ANTHROPIC_API_KEY (via Modal secret 'anthropic-api-key')\n"
            "  - CLAUDE_CODE_OAUTH_TOKEN (via Modal secret 'claude-oauth-token' "
            "or the testing input in the UI)"
        )

    # Make streams_agent importable
    sys.path.insert(0, "/home/agent/src")
    from streams_agent.agentic_review.engine import run_review

    # Switch to non-root user so Claude Code allows bypassPermissions
    import pwd
    import subprocess
    agent_user = pwd.getpwnam("agent")
    os.setgid(agent_user.pw_gid)
    os.setuid(agent_user.pw_uid)
    os.environ["HOME"] = agent_user.pw_dir

    # Verify CLI is findable
    from claude_agent_sdk._internal.transport.subprocess_cli import SubprocessCLITransport
    transport = SubprocessCLITransport.__new__(SubprocessCLITransport)
    cli_path = transport._find_cli()
    print(f"[evaluate] CLI binary: {cli_path}", flush=True)
    # Quick version check (timeout after 5s in case it hangs)
    result = subprocess.run(
        [cli_path, "--version"], capture_output=True, text=True, timeout=10,
        cwd="/home/agent/workspace",
    )
    print(f"[evaluate] CLI version: {result.stdout.strip()}", flush=True)

    t0 = time.time()
    # Work dir must be inside a git repo — CLI hangs in non-git dirs
    workspace = Path("/home/agent/workspace")
    workspace.mkdir(exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(prefix="streams_review_", dir=str(workspace)))
    template_path = Path("/home/agent/src/streams_agent/template/streams.csv")
    paper_id = job_store[job_id].get("paper_id", "unknown")

    # Decode PDF to a temp file
    pdf_data = base64.b64decode(pdf_base64)
    pdf_path = work_dir / filename
    with open(pdf_path, "wb") as f:
        f.write(pdf_data)

    trace_path = work_dir / "trace.json"
    checklist_yaml = work_dir / "checklist.yaml"
    stderr_log = work_dir / "stderr.log"

    # --- Progress monitor thread ---
    stop_event = threading.Event()

    def _monitor_progress():
        """Poll work_dir every 3s to track rated items and capture live logs."""
        while not stop_event.is_set():
            stop_event.wait(3)
            if stop_event.is_set():
                break
            job = job_store[job_id]

            # Count rated checklist items
            if checklist_yaml.exists():
                rated = 0
                with open(checklist_yaml) as f:
                    raw = f.read()
                items = yaml.safe_load(raw)
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict) and item.get("rating") is not None:
                            rated += 1
                job["rated_count"] = rated
                pct = int(100 * rated / TOTAL_ITEMS) if TOTAL_ITEMS > 0 else 0
                job["progress"] = f"Evaluated {rated}/{TOTAL_ITEMS} items... ({pct}%)"

            # Capture live stderr log (tool calls, agent activity)
            if stderr_log.exists():
                job["live_log"] = stderr_log.read_text()[-10000:]  # last 10KB

            # Snapshot work_dir contents
            files = {}
            for p in work_dir.iterdir():
                files[p.name] = p.stat().st_size
            job["work_dir_files"] = files
            job["elapsed_s"] = round(time.time() - t0, 1)

            job_store[job_id] = job

    monitor = threading.Thread(target=_monitor_progress, daemon=True)
    monitor.start()

    job = job_store[job_id]
    job["progress"] = "Reading PDF and preparing checklist..."
    job_store[job_id] = job

    # Redirect stderr to a file so we can capture Claude Code CLI output
    stderr_file = open(stderr_log, "w")
    old_stderr = sys.stderr
    sys.stderr = stderr_file

    try:
        assessment = run_review(
            pdf_path=pdf_path,
            template_path=template_path,
            paper_id=paper_id,
            work_dir=work_dir,
            model=model,
            verbosity=1,
            trace_path=trace_path,
            item_ids=item_ids,
        )
    except Exception as exc:
        import traceback

        sys.stderr = old_stderr
        stderr_file.close()

        stop_event.set()
        monitor.join(timeout=5)

        # Build a useful error log from the exception
        error_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
        error_log = "".join(error_lines)
        # Include captured stderr from the CLI subprocess
        if stderr_log.exists():
            captured = stderr_log.read_text().strip()
            if captured:
                error_log += f"\n--- stderr ---\n{captured}"

        # Short message for the status column
        short_msg = str(exc).split("\n")[0][:200]

        job = job_store[job_id]
        job["status"] = "failed"
        job["progress"] = f"Error: {short_msg}"
        job["error_log"] = error_log
        job_store[job_id] = job
        raise

    # Restore stderr after successful run
    sys.stderr = old_stderr
    stderr_file.close()

    # Stop monitor
    stop_event.set()
    monitor.join(timeout=5)

    # Read trace for cost metadata and store it
    cost_usd = None
    if trace_path.exists():
        with open(trace_path) as f:
            trace_data = json.load(f)
        cost_usd = trace_data.get("metadata", {}).get("total_cost_usd")
        trace_store[job_id] = trace_data

    # Update user budget with actual cost
    if cost_usd is not None:
        user_id = job_store[job_id].get("user_id", "anon:unknown")
        user_budget = budget_store.get(user_id, {"credits_spent": 0.0, "jobs_completed": 0})
        user_budget["credits_spent"] = user_budget.get("credits_spent", 0.0) + (cost_usd * CREDITS_PER_DOLLAR)
        user_budget["jobs_completed"] = user_budget.get("jobs_completed", 0) + 1
        budget_store[user_id] = user_budget

    # Build results from assessment
    all_assessments = []
    for a in assessment.assessments:
        all_assessments.append({
            "item_id": a.item_id,
            "rating": a.rating.value if a.rating else None,
            "comments": a.comments or "",
        })

    ratings = [a["rating"] for a in all_assessments if a["rating"]]
    summary = {
        "total_items": len(all_assessments),
        "yes": ratings.count("Yes"),
        "no": ratings.count("No"),
        "partial": ratings.count("Partial"),
        "na": ratings.count("NA"),
    }

    duration = time.time() - t0
    job = job_store[job_id]
    job["status"] = "complete"
    job["progress"] = "Complete"
    job["results"] = {"assessments": all_assessments, "summary": summary}
    job["completed_at"] = time.time()
    job["rated_count"] = summary["total_items"]
    job["total_items"] = TOTAL_ITEMS
    job["cost_usd"] = cost_usd
    job["duration_s"] = round(duration, 1)
    job_store[job_id] = job
