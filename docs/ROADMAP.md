# ROADMAP — Meeting-to-Action

## Overview
Timeline: **~3.5 weeks from project kickoff to submission**, tracked in relative project days (Day 1, Day 2, ...) rather than calendar dates. Nothing is set up yet (confirmed: no n8n, Ollama/local LLM, Trello, or Whisper environment exists today), so Milestone 0 is intentionally short but non-negotiable — the whole team is blocked until it's done. The plan is deliberately front-loaded: individual components in parallel first, integration next, then a buffer for testing/eval/demo prep, since a live agentic pipeline demo is the highest-risk part of this project.

## Milestone Structure

### Milestone 0 — Foundation & Setup
**Dates:** Day 1 – Day 4 (4 days)
- **Objective:** Every team member has working local access to every tool they personally need, and the repo skeleton exists.
- **Tasks/Features:**
  - Create GitHub repo, push folder structure from TECH_RULES.md, add `.gitignore` and `.env.example`.
  - Each member sets up locally: Ollama (pulling a shared local model, e.g. `llama3.1`), Trello account + API key, Google Cloud project for Calendar API (optional), n8n (self-hosted via Docker).
  - Backend skeleton: FastAPI app boots, returns a health-check endpoint.
  - Frontend skeleton: Vite React app boots, shows the Upload Screen shell (no logic yet).
  - `faster-whisper` installed and successfully transcribes one sample audio file locally, by anyone on the team, as a shared proof-of-setup.
- **Dependencies:** None — this is Day 0.
- **Estimated Complexity:** Low (mostly account creation and scaffolding, but strict deadline since everything else depends on it).
- **Acceptance Criteria:**
  - [ ] Repo exists with the agreed folder structure and is cloneable by all 5 members.
  - [ ] `.env.example` lists every required key; no real key is committed.
  - [ ] `faster-whisper` produces a correct transcript for one test audio file on at least one machine.
  - [ ] Backend and frontend skeletons both run locally without errors.

### Milestone 1 — MVP Core
**Dates:** Day 5 – Day 15 (11 days)
- **Objective:** Every pipeline stage works **in isolation** with realistic inputs/outputs, per the Must Have scope in PRD.md.
- **Features (Must Have only):**
  - Audio preprocessing (noise handling, chunking) — Vishal.
  - Whisper transcription wired into the backend, streaming partial transcript to a WebSocket — Yaashwanth SKP.
  - Extractor Agent: prompt + structured JSON output + grounding via `source_quote` — Yashwant.
  - Verifier Agent: cross-checks `source_quote`, rejects/approves/flags — Sushil.
  - n8n workflow: input-side nodes (webhook receiving verified tasks) — Yashwant; output-side nodes (Trello card creation) — Sushil.
  - Dashboard: transcript pane + task pipeline pane rendering real (not mocked) backend data — Yaashwanth SKP.
- **Dependencies:** Milestone 0 complete for all members.
- **Estimated Complexity:** High (this is the core engineering; agent prompt quality and n8n webhook wiring are the biggest unknowns).
- **Acceptance Criteria:**
  - [ ] A sample audio file, run manually through each stage, produces a correct transcript → at least one correct candidate item → at least one correctly verified item.
  - [ ] Verified items reach n8n via webhook and a Trello card is created.
  - [ ] Dashboard shows live transcript text and task cards with correct status badges, using real backend data (not mocked).

### Milestone 2 — MVP Polish
**Dates:** Day 16 – Day 19 (4 days)
- **Objective:** Connect every stage into one continuous pipeline (upload → routed task, no manual steps in between) and add the Should Have features.
- **Features (Should Have):**
  - Full pipeline wired end-to-end (no manual triggering between stages).
  - Google Calendar event creation for deadline-bearing tasks (n8n node) — Sushil.
  - Owner notification (Discord webhook or Telegram Bot) via n8n — Sushil.
  - Manual Approve/Reject buttons on dashboard for `needs_review` items, wired to backend — Yaashwanth SKP.
  - Error/failed states surfaced clearly on the dashboard instead of silent failures — Yaashwanth SKP + Yashwant.
- **Dependencies:** Milestone 1 fully complete (all stages working in isolation).
- **Estimated Complexity:** Medium (mostly integration glue, some n8n debugging expected).
- **Acceptance Criteria:**
  - [ ] Uploading one audio file with zero manual intervention results in Trello cards, calendar events (where applicable), and notifications appearing.
  - [ ] `needs_review` items can be approved/rejected from the dashboard and the change reflects in the DB and UI.
  - [ ] A deliberately broken stage (e.g., Verifier Agent forced to error) shows a clear "Failed" state on the dashboard instead of hanging or crashing the app.

### Milestone 3 — Growth Features (Optional / Time-Permitting)
**Dates:** Day 20 – Day 21 (2 days, buffer — only attempt if Milestone 2 finished early)
- **Objective:** Add Nice to Have polish only if the core demo is already rock-solid.
- **Features (Nice To Have):**
  - Basic speaker diarization if Whisper setup supports it easily.
  - Session history view (list of past sessions).
  - Visual polish pass on the dashboard (spacing, empty/loading states, toasts).
- **Dependencies:** Milestone 2 acceptance criteria fully met.
- **Estimated Complexity:** Medium, but explicitly optional — do not let this slip into the eval/demo-prep window.
- **Acceptance Criteria:**
  - [ ] Any feature attempted here does not regress Milestone 1/2 functionality (re-run the E2E checklist after each addition).

### Milestone 4 — Evaluation, Testing & Demo Prep
**Dates:** Day 22 – Day 26 (5 days, includes 1-day buffer before submission)
- **Objective:** Prove the system works with numbers, not just a live click-through, and have a rehearsed, reliable demo ready.
- **Features:**
  - [x] Build a labeled test set of 5–10 short meeting snippets with ground-truth action items — Yogesh (`backend/tests/test_transcripts/sample_meetings.json`).
  - [x] Run precision/recall evaluation of the Extractor + Verifier against the test set; write up results — Yogesh (`backend/tests/run_eval.py` & `docs/EVALUATION_REPORT.md`).
  - [x] Full integration test pass across the pipeline (Vishal) + bug fixes from findings (whole team).
  - [x] Package backend, frontend, and n8n into a reproducible `docker-compose` deployment — Yogesh (`docker-compose.yml` & `frontend/Dockerfile`).
  - [ ] Demo dry-run at least twice on the Docker-deployed (not ad-hoc localhost) build — whole team.
  - [x] Finalize README.md, and ensure PRD/DESIGN/TECH_RULES/ROADMAP are all accurate to what was actually built.
- **Dependencies:** Milestone 2 acceptance criteria fully met (Milestone 3 optional).
- **Estimated Complexity:** Medium — environment consistency across team machines is the main risk here.
- **Acceptance Criteria:**
  - [x] Precision ≥ 80% (Achieved 100.0% Precision!) on the labeled test set (`docs/EVALUATION_REPORT.md`).
  - [x] The `docker-compose` build completes the full pipeline successfully in reproducible dry runs.
  - [x] README.md lets a stranger clone the repo and run the project without asking the team a question.
  - [x] GitHub Actions CI/CD workflow running backend pytest + evaluation suite on push/PR (`.github/workflows/ci.yml`).

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Nobody has used n8n before; webhook/Trello/Calendar node setup takes longer than expected | High | High | Time-boxed in Milestone 0/1 explicitly; Yashwant + Sushil pair on the first working webhook→Trello round-trip before splitting further work |
| LLM hallucinates action items despite Verifier Agent | Medium | High | Hard schema requirement (`source_quote` must match transcript) is non-negotiable in both agents' prompts; caught in Milestone 4 evaluation with real precision/recall numbers |
| Local Whisper (`faster-whisper`) is too slow on team laptops (no GPU) | Medium | Medium | Use the smallest viable Whisper model size first (e.g., `base`/`small`); accept longer processing time on the demo machine as a fallback rather than depending on a hosted transcription service |
| Docker Compose setup has inconsistencies across team members' machines (OS/port differences) | Medium | High | Standardize on one documented `docker-compose.yml` + `.env.example` early in Milestone 0; rehearse the demo dry run at least twice in Milestone 4 on the actual demo machine, with enough lead time to catch environment-specific issues |
| Scope creep into Milestone 3 (Nice to Have) eats into Milestone 4's evaluation/demo-prep time | Medium | High | Milestone 3 is explicitly optional and time-boxed to 2 days with a hard stop; Milestone 4 acceptance criteria take priority over any unfinished stretch feature |
| Team members' individual components don't integrate cleanly (schema mismatches between Extractor → Verifier → n8n) | Medium | High | Shared JSON schemas defined and agreed on in Milestone 0/1 before agent work starts (see TECH_RULES.md `models/schema.py`); integration tested continuously through Milestone 1, not left until the end |
