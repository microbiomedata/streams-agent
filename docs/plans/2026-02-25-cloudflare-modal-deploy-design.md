# Cloudflare Pages + Modal Deployment Prototype

**Date:** 2026-02-25
**Status:** Approved

## Goal

Validate the Cloudflare Pages + Modal architecture with a minimal dummy app.
No real agent logic, no real ORCID auth — just enough to prove the pattern works end-to-end.

## Architecture

```
User Browser
    │
    ▼
Cloudflare Pages (static HTML + edge functions)
    │  POST /api/submit        GET /api/status/:id
    │  [verify auth]           [verify auth]
    ▼
Modal (serverless Python)
    │  submit() → job_id       status(id) → results
    │  spawn evaluate()
    ▼
mock results returned after ~5s
```

## Directory Layout

```
deploy/
├── frontend/                 # Cloudflare Pages
│   ├── index.html            # Single page: form + results
│   └── functions/            # CF Pages Functions
│       └── api/
│           ├── submit.js     # Auth check, proxy to Modal
│           └── status/
│               └── [id].js   # Auth check, proxy status from Modal
│
└── modal/
    └── app.py                # Modal app with mock evaluation
```

## Components

### Frontend (Cloudflare Pages)

Single HTML page with:
- File upload for PDF
- Paper ID text input
- Submit button
- Status/results area that polls after submission

### Edge Functions (CF Pages Functions)

Two endpoints:
- `POST /api/submit` — validates auth token, forwards PDF + metadata to Modal, returns job ID
- `GET /api/status/:id` — validates auth token, proxies job status from Modal

Auth: mock token (`Authorization: Bearer test-token`) for prototype. Replace with ORCID JWT later.

Communication with Modal: shared secret via environment variable (`MODAL_API_SECRET`).

### Backend (Modal)

Modal app with:
- `modal.Dict` for job storage (in-memory, ephemeral)
- `submit` web endpoint: stores job, spawns async `evaluate` function, returns job ID
- `status` web endpoint: returns job status and results
- `evaluate` function: sleeps ~5s, returns mock STREAMS-shaped results

Mock results: JSON matching `ChecklistAssessment` shape with a handful of items rated Yes/No/Partial/NA.

## Auth Flow (Prototype)

Hardcoded bearer token. CF Functions check `Authorization` header.
No user database, no sessions. Swap for ORCID OAuth later.

## Dev & Test Workflow

1. `modal serve deploy/modal/app.py` — local Modal dev server
2. `wrangler pages dev deploy/frontend/` — local CF dev server, MODAL_URL env var points to Modal
3. `modal deploy deploy/modal/app.py` — deploy backend
4. `wrangler pages deploy deploy/frontend/` — deploy frontend

No Docker, no git push, no CI required.

## What This Defers

- Real ORCID OAuth
- Real agent logic / Claude Code SDK
- Real PDF processing
- Persistent storage (database)
- Streaming progress updates (SSE)
- Rate limiting
