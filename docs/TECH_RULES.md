# TECH_RULES — Meeting-to-Action

## Architecture Overview

- **Frontend Architecture:** React (Vite) single-page app, talks to the backend over REST (upload, session state) + WebSocket (live transcript/task updates).
- **Backend Architecture:** Python FastAPI service. Owns: audio ingestion endpoint, Whisper transcription job, calls to Extractor Agent and Verifier Agent (as internal functions/services, not separate microservices — keep it a modular monolith given the timeline), and a webhook call out to n8n once a task is verified.
- **Database Architecture:** SQLite for MVP (zero-ops, file-based, sufficient for single-session demo scale). Stores sessions, transcript segments, candidate items, verified items, and their routing status.
- **Deployment Architecture:** Backend on Render or Railway (free tier, supports Python + persistent process for WebSocket); frontend on Vercel; n8n self-hosted via Docker on the same Render/Railway instance or n8n Cloud free tier — whichever the team gets working first (see ROADMAP Milestone 0).
- **Architecture Diagram (text):**

```
 [Browser: React Dashboard]
        |  REST (upload) + WebSocket (live updates)
        v
 [FastAPI Backend]
        |-- audio preprocessing (pydub/ffmpeg, noise reduction, chunking)
        |-- Whisper transcription (faster-whisper, local CPU/GPU)
        |-- Extractor Agent (LLM call, structured JSON out)
        |-- Verifier Agent (LLM call, cross-checks against transcript)
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
| Speech-to-Text | `faster-whisper` (local) | Transcription | Free (no per-minute API cost), runs on CPU, good accuracy/speed tradeoff | OpenAI Whisper API (simpler setup, but costs money per meeting — use as fallback if local setup blocks the team past Day 3) |
| Audio preprocessing | `pydub` + `ffmpeg` | Noise handling, chunking | Lightweight, well-documented, sufficient for MVP-level cleanup | `librosa` (more powerful but heavier for the scope needed) |
| LLM (Extractor + Verifier) | Configurable via env var — OpenAI `gpt-4o-mini` or Anthropic `claude-haiku` | Structured extraction + verification | Cheap, fast, strong at structured JSON output; abstracted behind one thin client so the team isn't locked in | A single hardcoded provider (rejected — team should use whichever they get free credits/API access to first) |
| Database | SQLite | Store sessions, transcript, items, status | Zero setup, file-based, matches single-session MVP scale | Postgres (better for concurrency, unnecessary complexity for a 3.5-week single-demo project) |
| Orchestration | n8n (self-hosted via Docker, or n8n Cloud free tier) | Route verified tasks to Trello/Calendar/notifications | Explicitly required by the project brief; visual workflow doubles as a demo artifact | Custom backend routing code only (rejected — the brief specifically wants n8n as the visible orchestration layer) |
| Task board | Trello (REST API) | Task tracking | Free, simple REST API, fast to integrate via n8n's built-in Trello node | Notion, Asana (both viable, but Trello's n8n node is simplest) |
| Calendar | Google Calendar API | Deadline events | Free, n8n has a built-in node, team likely already has Google accounts | Outlook Calendar (viable alt if the team prefers) |
| Notifications | Discord/Slack webhook, or SMTP email via n8n's Email/Send node | Owner notifications | Fastest to set up with no domain/DNS requirements (a webhook URL is enough) | Twilio SMS (unnecessary cost/complexity for MVP) |
| Frontend hosting | Vercel | Serve React app | Free tier, git-push deploy | Netlify (equally fine — pick whichever the team sets up first) |
| Backend hosting | Render or Railway | Serve FastAPI + WebSocket, run n8n container | Free tier supports long-running processes needed for WebSocket + n8n | Vercel serverless (rejected — doesn't support persistent WebSocket connections or a long-running n8n container well) |

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
├── docker-compose.yml              # spins up backend + n8n together
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
- **Secrets Management:** All API keys (LLM provider, Trello, Google Calendar, notification webhook) go in a `.env` file, loaded via `python-dotenv`, and listed (with dummy values) in `.env.example`. **Never commit `.env` to git** — it must be in `.gitignore` from the first commit.
- **HTTPS/TLS:** Handled automatically by Vercel/Render/Railway's default TLS — no manual cert setup needed for MVP.

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
- **CI/CD Pipeline:** Not required to be fully automated for MVP given the timeline — manual deploy (`git push` to Render/Railway/Vercel) is acceptable. A GitHub Actions workflow that just runs `pytest` on every PR is a cheap, worthwhile addition if time allows.
- **Environment Management:** Two environments only — `local` (each member's machine, using `.env`) and `demo` (the deployed Render/Vercel/n8n instances used for the live submission demo). No separate staging environment needed at this scale.
- **Monitoring & Alerting:** Not required for MVP — this is a demo/academic deliverable, not a production service. Console/structured logs are sufficient.
- **Backup Strategy:** Commit the SQLite DB schema (not the data file) to git; no data backup needed since sessions are demo/test data, not production data.
