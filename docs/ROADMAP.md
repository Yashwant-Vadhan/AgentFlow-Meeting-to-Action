# ROADMAP — Meeting-to-Action

## Overview
Timeline: **Thursday, Aug 13, 2026 → first week of September 2026** (~3.5 weeks). Nothing is set up yet (confirmed: no n8n, LLM API, Trello, or Whisper access exists today), so Milestone 0 is intentionally short but non-negotiable — the whole team is blocked until it's done. The plan is deliberately front-loaded: individual components in parallel first, integration next, then a buffer for testing/eval/demo prep, since a live agentic pipeline demo is the highest-risk part of this project.

## Milestone Structure

### Milestone 0 — Foundation & Setup
**Dates:** Aug 13 – Aug 16 (4 days)
- **Objective:** Every team member has working local access to every tool they personally need, and the repo skeleton exists.
- **Tasks/Features:**
  - Create GitHub repo, push folder structure from TECH_RULES.md, add `.gitignore` and `.env.example`.
  - Each member creates their own accounts: LLM API key (OpenAI or Anthropic), Trello account + API key, Google Cloud project for Calendar API, n8n (self-hosted via Docker or n8n Cloud free tier).
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
**Dates:** Aug 17 – Aug 27 (11 days)
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
**Dates:** Aug 28 – Aug 31 (4 days)
- **Objective:** Connect every stage into one continuous pipeline (upload → routed task, no manual steps in between) and add the Should Have features.
- **Features (Should Have):**
  - Full pipeline wired end-to-end (no manual triggering between stages).
  - Google Calendar event creation for deadline-bearing tasks (n8n node) — Sushil.
  - Owner notification (Discord/Slack webhook or email) via n8n — Sushil.
  - Manual Approve/Reject buttons on dashboard for `needs_review` items, wired to backend — Yaashwanth SKP.
  - Error/failed states surfaced clearly on the dashboard instead of silent failures — Yaashwanth SKP + Yashwant.
- **Dependencies:** Milestone 1 fully complete (all stages working in isolation).
- **Estimated Complexity:** Medium (mostly integration glue, some n8n debugging expected).
- **Acceptance Criteria:**
  - [ ] Uploading one audio file with zero manual intervention results in Trello cards, calendar events (where applicable), and notifications appearing.
  - [ ] `needs_review` items can be approved/rejected from the dashboard and the change reflects in the DB and UI.
  - [ ] A deliberately broken stage (e.g., Verifier Agent forced to error) shows a clear "Failed" state on the dashboard instead of hanging or crashing the app.

### Milestone 3 — Growth Features (Optional / Time-Permitting)
**Dates:** Sept 1 – Sept 2 (2 days, buffer — only attempt if Milestone 2 finished early)
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
**Dates:** Sept 3 – Sept 7 (5 days, includes 1-day buffer before submission)
- **Objective:** Prove the system works with numbers, not just a live click-through, and have a rehearsed, reliable demo ready.
- **Features:**
  - Build a labeled test set of 5–10 short meeting snippets with ground-truth action items — Yogesh.
  - Run precision/recall evaluation of the Extractor + Verifier against the test set; write up results — Yogesh.
  - Full integration test pass across the pipeline (Vishal) + bug fixes from findings (whole team).
  - Deploy backend, frontend, and n8n to their hosting targets (Render/Railway/Vercel) — Yogesh.
  - Demo dry-run at least twice on the deployed (not localhost) version — whole team.
  - Finalize README.md, and ensure PRD/DESIGN/TECH_RULES/ROADMAP/todo.md are all accurate to what was actually built (update anything that drifted).
- **Dependencies:** Milestone 2 acceptance criteria fully met (Milestone 3 optional).
- **Estimated Complexity:** Medium — deployment environment differences are the main risk here.
- **Acceptance Criteria:**
  - [ ] Precision ≥ 80% and recall ≥ 75% achieved on the labeled test set (per PRD KPI), or a documented explanation of the gap and mitigation.
  - [ ] Deployed (non-localhost) version completes the full pipeline successfully in ≥ 3 consecutive dry runs.
  - [ ] README.md lets a stranger clone the repo and run the project without asking the team a question.
  - [ ] Submission package (repo + docs + demo recording/link, per course requirements) finalized at least 1 day before the deadline.

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Nobody has used n8n before; webhook/Trello/Calendar node setup takes longer than expected | High | High | Time-boxed in Milestone 0/1 explicitly; Yashwant + Sushil pair on the first working webhook→Trello round-trip before splitting further work |
| LLM hallucinates action items despite Verifier Agent | Medium | High | Hard schema requirement (`source_quote` must match transcript) is non-negotiable in both agents' prompts; caught in Milestone 4 evaluation with real precision/recall numbers |
| Local Whisper (`faster-whisper`) is too slow on team laptops (no GPU) | Medium | Medium | Use the smallest viable Whisper model size first (e.g., `base`/`small`); fall back to OpenAI Whisper API for the demo machine only if local transcription can't keep up |
| Free-tier hosting (Render/Railway) sleeps/cold-starts and breaks the live demo | Medium | High | Rehearse the demo dry run at least twice in Milestone 4 against the actual deployed URLs, not localhost, with enough lead time to catch cold-start issues |
| Scope creep into Milestone 3 (Nice to Have) eats into Milestone 4's evaluation/demo-prep time | Medium | High | Milestone 3 is explicitly optional and time-boxed to 2 days with a hard stop; Milestone 4 acceptance criteria take priority over any unfinished stretch feature |
| Team members' individual components don't integrate cleanly (schema mismatches between Extractor → Verifier → n8n) | Medium | High | Shared JSON schemas defined and agreed on in Milestone 0/1 before agent work starts (see TECH_RULES.md `models/schema.py`); integration tested continuously through Milestone 1, not left until the end |
