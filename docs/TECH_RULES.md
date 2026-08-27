# TECH_RULES — Meeting-to-Action

## Architecture Overview

- **Frontend Architecture:** React (Vite) single-page app, talks to the backend over REST (upload, session state) + WebSocket (live transcript/task updates).
- **Backend Architecture:** Python FastAPI service. Owns: audio ingestion endpoint, Whisper transcription job, calls to Extractor Agent and Verifier Agent (as internal functions/services, not separate microservices — keep it a modular monolith given the timeline) using a locally-hosted LLM via Ollama, and a webhook call out to n8n once a task is verified.
- **Database Architecture:** SQLite for MVP (zero-ops, file-based, sufficient for single-session demo scale). Stores sessions, transcript segments, candidate items, verified items, and their routing status.
- **Deployment Architecture:** Local Docker Compose is the primary deployment target — a single `docker-compose up` runs the FastAPI backend and self-hosted n8n (Community Edition) together, with n8n's workflow/credential data persisted to a named volume (`n8n_data/`) so workflows survive container restarts. Cloud hosting (e.g., Render, Railway, Vercel for the frontend) is an optional convenience layer for demo purposes on top of the same Docker setup, not a dependency the pipeline requires.
- **Architecture Diagram (text):**

```
 [Browser: React Dashboard]
        |  REST (upload) + WebSocket (live updates)
        v
 [FastAPI Backend]
        |-- audio preprocessing (pydub/ffmpeg, noise reduction, chunking)
        |-- Whisper transcription (faster-whisper, local CPU/GPU)
        |-- Extractor Agent (Ollama LLM call, structured JSON out)
        |-- Verifier Agent (Ollama LLM call, cross-checks against transcript)
        |-- SQLite (sessions, transcript, items, status)
        |
        v  webhook POST (verified task JSON)
 [n8n workflow]
        |-- Trello node (create card)
        |-- Google Calendar node (create event, if deadline present)
        |-- Notification node (email via SMTP/Resend, or Discord/Slack webhook)
        |
        v
 [n8n -> webhook back to FastAPI] -- updates routing status --> [WebSocket push to Dashboard]
```

## Tech Stack

| Layer | Technology | Purpose | Why Chosen | Alternatives Considered |
|-------|-----------|---------|-----------|------------------------|
| Frontend | React + Vite + Tailwind CSS | Dashboard UI | Fast setup, huge community, team likely already familiar; Tailwind avoids writing custom CSS under time pressure | Next.js (overkill — no SSR need), plain HTML/JS (slower to build stateful UI) |
| Realtime | Socket.IO (or native WebSocket) | Push live transcript/task updates to dashboard | Simple client/server API, works well with FastAPI via `python-socketio` | Polling (simpler but laggy demo; acceptable fallback if Socket.IO setup stalls) |
| Backend | Python + FastAPI | API server, orchestration of Whisper + agent calls | Async support, auto-generated docs (`/docs`), Python is the natural home for Whisper | Node/Express (would split the team across two languages unnecessarily since Whisper is Python-native) |
| Speech-to-Text | `faster-whisper` (local) | Transcription | Runs entirely on CPU with no external API dependency, good accuracy/speed tradeoff for meeting-length audio | OpenAI Whisper API (simpler setup, but adds a network dependency — usable as a fallback if local setup blocks the team past Day 3) |
| Audio preprocessing | `pydub` + `ffmpeg` | Noise handling, chunking | Lightweight, well-documented, sufficient for MVP-level cleanup | `librosa` (more powerful but heavier for the scope needed) |
| LLM (Extractor + Verifier) | Ollama, running a configurable open-source model (e.g., `llama3.1` or `mistral`) | Structured extraction + verification | Runs locally with no external network dependency, keeping the whole pipeline self-contained; strong at structured JSON output for the model sizes tested; abstracted behind one thin client (`llm_client.py`) so the team can swap models without code changes | A hosted LLM API (rejected as a hard dependency — a locally-run model keeps the pipeline self-contained, though the client abstraction makes swapping in a hosted provider later a one-line change if ever needed) |
| Database | SQLite | Store sessions, transcript, items, status | Zero setup, file-based, matches single-session MVP scale | Postgres (better for concurrency, unnecessary complexity for a 3.5-week single-demo project) |
| Orchestration | n8n (self-hosted via Docker) | Route verified tasks to Trello/Calendar/notifications | Explicitly required by the project brief; visual workflow doubles as a demo artifact; self-hosting keeps the whole stack runnable offline/locally | Custom backend routing code only (rejected — the brief specifically wants n8n as the visible orchestration layer); n8n Cloud (viable alternative if the team prefers a hosted instance, but not required) |
| Task board | Trello (REST API) | Task tracking | Simple REST API, fast to integrate via n8n's built-in Trello node | Notion, Asana (both viable, but Trello's n8n node is simplest) |
| Calendar | Google Calendar API | Deadline events | n8n has a built-in node, team likely already has Google accounts | Outlook Calendar (viable alt if the team prefers) |
| Notifications | Discord webhook or Telegram Bot, via n8n | Owner notifications | Fastest to set up with no domain/DNS or SMTP configuration required — a webhook URL or bot token is enough | Email (SMTP) via n8n's Send Email node (viable fallback, but adds domain/deliverability setup for little benefit at MVP scale) |
| Frontend hosting | Docker/local build (Vercel optional) | Serve React app | Docker build works anywhere with zero setup dependency; Vercel remains a convenient optional layer for a shareable live demo link | Netlify (equally viable if the team wants a hosted demo link) |
| Backend hosting | Docker Compose (local); Render/Railway optional | Serve FastAPI + WebSocket, run n8n container | Docker Compose runs the full backend + n8n stack with one command and no external account required; cloud hosting is a nice-to-have for a shareable demo, not a requirement | Vercel serverless (rejected — doesn't support persistent WebSocket connections or a long-running n8n container well) |

## Folder Structure

```
meeting-to-action/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app entrypoint
│   │   ├── api/
│   │   │   ├── sessions.py         # upload / session endpoints
│   │   │   └── websocket.py        # live update socket handlers
│   │   ├── pipeline/
│   │   │   ├── audio_preprocess.py # noise handling, chunking (Vishal)
│   │   │   ├── transcribe.py       # Whisper integration (Yaashwanth SKP)
│   │   │   ├── extractor_agent.py  # Extractor Agent (Yashwant)
│   │   │   └── verifier_agent.py   # Verifier Agent (Sushil)
│   │   ├── models/
│   │   │   └── schema.py           # SQLite models (SQLAlchemy)
│   │   ├── llm_client.py           # thin LLM provider abstraction
│   │   └── config.py                # env var loading
│   ├── tests/                      # unit + integration tests (Vishal, Yogesh)
│   ├── eval/
│   │   ├── test_transcripts/       # labeled meeting snippets (Yogesh)
│   │   └── run_eval.py             # precision/recall scoring script (Yogesh)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── UploadScreen.jsx
│   │   │   ├── TranscriptPane.jsx
│   │   │   └── TaskPipelinePane.jsx
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
├── n8n/
│   └── workflow-export.json        # exported n8n workflow (input + output side nodes)
├── docs/
│   ├── PRD.md
│   ├── DESIGN.md
│   ├── TECH_RULES.md
│   ├── ROADMAP.md
│   └── todo.md
├── .env.example
├── docker-compose.yml               # spins up backend + n8n together; n8n data persisted to a named volume (n8n_data:/home/node/.n8n, gitignored)
└── README.md
```

## Coding Standards
- **Naming Conventions:** Python — `snake_case` for files/functions, `PascalCase` for classes. React — `PascalCase` for components, `camelCase` for functions/variables. API routes: `/api/v1/<resource>` (e.g., `/api/v1/sessions`, `/api/v1/sessions/{id}/tasks`).
- **Component Structure:** One React component per file; keep components under ~150 lines — extract subcomponents (e.g., `TaskCard.jsx`) rather than growing one file.
- **API Standards:** REST, JSON in/out, versioned under `/api/v1/`. All list endpoints support basic pagination (`?limit=&offset=`) even if unused at MVP scale — cheap to add now.
- **Error Handling Strategy:** Every pipeline stage (preprocess, transcribe, extract, verify, route) catches its own exceptions and writes a `status: "failed"` + `error_message` to the session's item/stage record rather than crashing the whole request — the dashboard should always be able to show *something*.
- **Logging Standards:** Structured logging (`logging` module, JSON formatter) with a `session_id` on every log line so a full session's pipeline run can be traced end-to-end.

## Security Rules
- **Authentication:** None required for MVP (single-user, local/demo use) — explicitly out of scope given the timeline; note this as a known limitation in the README.
- **Authorization:** N/A for MVP (no multi-user roles).
- **Data Validation:** All incoming audio uploads validated for file type/size server-side (never trust the frontend check alone). All LLM JSON outputs validated against a strict schema (e.g., Pydantic models) before being written to the DB or forwarded to n8n — reject and log on schema mismatch rather than passing malformed data downstream.
- **Rate Limiting:** Not required for MVP (no public-facing multi-tenant traffic) — revisit if the demo goes public.
- **Secrets Management:** All API keys and connection settings (Trello, Google Calendar, notification webhook) go in a `.env` file, loaded via `python-dotenv`, and listed (with dummy values) in `.env.example`. LLM access uses `OLLAMA_HOST` (e.g. `http://localhost:11434`) and `OLLAMA_MODEL` (e.g. `llama3.1`) rather than an API key. **Never commit `.env` to git** — it must be in `.gitignore` from the first commit.
- **HTTPS/TLS:** Not required for the local Docker setup (localhost demo). If optional cloud hosting is used, Vercel/Render/Railway handle TLS automatically with no manual cert setup needed.

## Performance Rules
- **Frontend Optimization:** Virtualize the task list if it exceeds ~50 items (unlikely at demo scale, but cheap to add with `react-window` if needed); lazy-load nothing else — the app is small enough not to need code splitting for MVP.
- **Backend Optimization:** Run Whisper transcription and LLM calls as background tasks (FastAPI `BackgroundTasks` or a simple async queue) so the upload endpoint returns immediately and the dashboard shows progress via WebSocket rather than blocking.
- **Database Optimization:** Index `session_id` on the transcript/items tables (the only query pattern that matters at this scale).
- **Caching Strategy:** Not needed for MVP — no repeated expensive queries at this scale.

## Testing Rules
- **Unit Tests:** `pytest` for backend modules — at minimum, one test per pipeline stage (audio_preprocess, transcribe, extractor_agent, verifier_agent) using a small fixed sample input and asserting the output shape/schema.
- **Integration Tests:** At least one test that runs a short sample audio file through the full backend pipeline (preprocess → transcribe → extract → verify) and asserts a non-empty, schema-valid task list comes out the other end (owned by Vishal).
- **End-to-End Tests:** Manual E2E script/checklist (documented, not necessarily automated given the timeline): upload a real meeting snippet → confirm transcript appears live → confirm at least one task appears on Trello → confirm dashboard shows "Routed" status. Automate with Playwright only if time remains after MVP is stable.

## Git Workflow
- **Branch Naming Convention:** `feature/<short-description>` (e.g., `feature/extractor-agent`, `feature/dashboard-transcript-pane`), `fix/<short-description>` for bugfixes.
- **Commit Message Convention:** Conventional Commits — `feat:`, `fix:`, `docs:`, `test:`, `chore:` prefixes (e.g., `feat: add verifier duplicate detection`).
- **Pull Request Rules:** Every feature branch merges to `main` via PR, even solo — at minimum, self-review the diff before merging, since there's no dedicated reviewer role on a 5-person team under time pressure. Squash-merge to keep `main` history clean for the demo/submission.

## Deployment Rules
- **CI/CD Pipeline:** Not required to be fully automated for MVP given the timeline — `docker-compose up` locally is the primary deploy path. A GitHub Actions workflow that just runs `pytest` on every PR is a cheap, worthwhile addition if time allows (owned by Yogesh alongside eval work).
- **Environment Management:** Two environments only — `local` (each member's machine, using `.env`) and `demo` (the same Docker Compose stack run on the demo machine for the live submission; an optional cloud instance if the team sets one up). No separate staging environment needed at this scale.
- **Monitoring & Alerting:** Not required for MVP — this is a demo/academic deliverable, not a production service. Console/structured logs are sufficient.
- **Backup Strategy:** Commit the SQLite DB schema (not the data file) to git; no data backup needed since sessions are demo/test data, not production data.
