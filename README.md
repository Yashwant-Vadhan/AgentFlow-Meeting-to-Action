# AgentFlow: Meeting-to-Action

**An Agentic AI Pipeline for Automated Meeting-to-Action Extraction**

Turn raw meeting audio into verified, routed tasks — automatically. No manual note-taking, no lost follow-ups.

---

## The Problem

Meetings generate decisions and action items that routinely get lost — buried in notes, forgotten after the call ends, or inconsistently followed up on. Manually transcribing, extracting tasks, and assigning them to the right tools is tedious and error-prone, especially in academic or small-team settings with no dedicated ops support.

## The Solution

AgentFlow is an **agentic AI pipeline, orchestrated in n8n**, that converts meeting audio into verified, actionable tasks in real time:

```
Audio Upload
    │
    ▼
Whisper Transcription
    │
    ▼
Extractor Agent (LLM)  →  pulls candidate decisions/action items, grounded in a source quote
    │
    ▼
Verifier Agent (LLM)   →  cross-checks each item against the transcript, rejects hallucinations/duplicates
    │
    ▼
n8n Orchestration      →  routes verified tasks to Trello, Google Calendar, and notifications
    │
    ▼
Live Dashboard         →  shows transcript + task pipeline status in real time
```

Two LLM agents (Extractor + Verifier) give the system a self-checking loop, so tasks reaching your board are grounded in what was actually said — not hallucinated. n8n handles all downstream routing, making the workflow visible and demoable end-to-end.

## Key Features

- 🎙️ **Speech-to-text** via local Whisper (`faster-whisper`) — no per-minute API cost
- 🤖 **Dual-agent extraction** — an Extractor Agent proposes tasks, a Verifier Agent grounds each one against the transcript before it's trusted
- 🔗 **n8n-orchestrated routing** — verified tasks flow to Trello, Google Calendar, and notifications automatically
- 📊 **Live dashboard** — watch the pipeline work end-to-end: transcript → extracted → verified → routed
- ✅ **Human-in-the-loop** — low-confidence items are flagged `needs_review` with manual approve/reject controls, never silently dropped or silently auto-approved

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React (Vite) + Tailwind CSS |
| Backend | Python + FastAPI |
| Speech-to-Text | `faster-whisper` (local) |
| LLM (Extractor + Verifier) | Configurable — OpenAI `gpt-4o-mini` or Anthropic `claude-haiku` |
| Orchestration | n8n (self-hosted via Docker, or n8n Cloud) |
| Database | SQLite |
| Task Board | Trello |
| Calendar | Google Calendar API |
| Notifications | Discord/Slack webhook or SMTP email |
| Hosting | Vercel (frontend) · Render/Railway (backend + n8n) |

Full architecture rationale and alternatives considered: [`docs/TECH_RULES.md`](docs/TECH_RULES.md).

## Project Structure

```
meeting-to-action/
├── backend/          # FastAPI app, pipeline stages, agents, eval scripts
├── frontend/          # React dashboard
├── n8n/               # Exported n8n workflow
├── docs/              # PRD, Design, Tech Rules, Roadmap
├── .env.example
├── docker-compose.yml
└── README.md
```

## Getting Started

> Setup instructions will be finalized once the backend/frontend skeletons are scaffolded (Milestone 0 — see [`docs/ROADMAP.md`](docs/ROADMAP.md)).

```bash
# Clone the repo
git clone https://github.com/Yashwant-Vadhan/AgentFlow-Meeting-to-Action
cd AgentFlow-Meeting-to-Action

# Copy env template and fill in your API keys
cp .env.example .env

# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev

# n8n
docker-compose up n8n
```

Required keys (see `.env.example`): LLM provider API key, Trello API key, Google Calendar credentials, notification webhook URL.

## Evaluation

The pipeline is evaluated against a labeled test set of meeting snippets rather than judged purely by live demo:

- **Extraction precision** ≥ 80%
- **Extraction recall** ≥ 75%
- **Verifier false-negative rate** < 10%
- **End-to-end latency** < 60s for a 10-minute meeting

Full methodology: [`docs/PRD.md`](docs/PRD.md) → Success Metrics.

## Documentation

| Doc | Contents |
|---|---|
| [`docs/PRD.md`](docs/PRD.md) | Problem statement, user stories, functional requirements, MVP scope |
| [`docs/DESIGN.md`](docs/DESIGN.md) | UX flows, screen specs, design system |
| [`docs/TECH_RULES.md`](docs/TECH_RULES.md) | Architecture, tech stack rationale, coding/security/testing standards |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Milestones, timeline, risk register |

## Team

| Member | Focus |
|---|---|
| Yashwant Vadhan M | Extractor Agent · n8n input-side workflow |
| M A Sushil Kumar | Verifier Agent · n8n output-side workflow (routing) |
| Yaashwanth SKP | Whisper integration · Dashboard UI |
| Vishal Khanna Chandra Sekaran | Audio preprocessing · Integration testing |
| Yogesh U | Evaluation (precision/recall) · Deployment |

## Status

🚧 In development — see [`docs/ROADMAP.md`](docs/ROADMAP.md) for current milestone.
