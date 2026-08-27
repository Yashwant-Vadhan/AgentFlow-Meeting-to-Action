# PRD — Meeting-to-Action

## Executive Summary
- **Project Name:** Meeting-to-Action
- **Problem Statement:** Meetings generate decisions and action items that routinely get lost — buried in notes, forgotten after the call ends, or inconsistently followed up on. Manual transcription and task extraction is tedious and error-prone, especially in academic/small-team settings with no dedicated ops support.
- **Solution Overview:** An agentic AI pipeline, orchestrated in n8n, that converts raw meeting audio into verified, actionable tasks in real time — using Whisper for transcription, an Extractor Agent (LLM) to pull candidate tasks, a Verifier Agent (LLM) to catch hallucinations/duplicates, and n8n to route confirmed tasks to Trello, Calendar, and notifications.
- **Target Audience:** Small teams and academic project groups (5–10 people) running recurring meetings with no dedicated project manager.

## Goals & Objectives

### Business/Academic Goals
- Deliver a fully working, live-demoable pipeline by the submission deadline (first week of September 2026).
- Demonstrate a coherent multi-agent + workflow-automation system (not a single script) for evaluation purposes.

### User Goals
- Attend a meeting and, within minutes of it ending, see a clean, correct list of action items already routed to a task board, calendar, and notifications — with zero manual re-reading of notes.

### Success Metrics (KPIs)
- **Extraction precision ≥ 80%** on the test set (correctly identified action items / total items flagged by Extractor Agent).
- **Extraction recall ≥ 75%** (correctly identified action items / total actual action items in transcript, per human-labeled ground truth).
- **Verifier false-negative rate < 10%** (valid tasks incorrectly rejected).
- **End-to-end latency:** transcript-ready → task-on-board in under 60 seconds for a 10-minute meeting.
- **Demo reliability:** pipeline completes without manual intervention in ≥ 3 consecutive live test runs before submission.

## User Personas

**Persona 1 — Team Lead / Meeting Organizer ("Priya")**
- Pain Points: Ends every meeting unsure who owns what; chases people over WhatsApp for follow-ups; notes get lost across devices.
- Goals: Walk out of a meeting and trust that tasks are already assigned and tracked without her doing it manually.

**Persona 2 — Team Member ("Arjun")**
- Pain Points: Forgets verbal commitments made mid-meeting; misses deadlines because nothing was written down in a place he checks.
- Goals: Get a notification with exactly what he committed to and by when, without re-listening to the recording.

## User Stories

### Transcription
- As a meeting organizer, I want to start recording/streaming audio so that the system can begin processing the meeting live.
- As a user, I want the raw transcript to be reasonably accurate and speaker-attributable (if possible) so extraction quality is high.

### Extraction
- As a user, I want the system to identify candidate decisions and action items (with owner and deadline where stated) so I don't have to re-read the transcript.
- As a user, I want vague statements ("we should probably look into that") to be flagged as low-confidence rather than turned into a hard task.

### Verification
- As a user, I want a second pass to cross-check each candidate task against the transcript so hallucinated or duplicate tasks don't reach my task board.
- As a user, I want only high-confidence, well-formed tasks (clear action + owner or deadline) passed downstream.

### Routing / Orchestration
- As a user, I want verified tasks automatically created on Trello so I don't have to manually enter them.
- As a user, I want tasks with a deadline to also create a calendar entry.
- As a user, I want the assigned owner to get a notification (e.g., a chat message) summarizing their task.

### Dashboard
- As a user, I want to see the live transcript and the extracted/verified action items in one place during and right after the meeting, so the pipeline is visibly working (this is also the primary demo surface).
- As a user, I want to see the status of each item (extracted → verified → routed) so I can trust the system did its job.

## Functional Requirements

### Module: Audio Capture & Preprocessing
- **Description:** Accept meeting audio (uploaded file or streamed input for MVP: uploaded file), preprocess (noise reduction, chunking into manageable segments) before sending to Whisper.
- **Inputs:** Audio file (.wav/.mp3/.m4a) or live stream chunk.
- **Outputs:** Cleaned, chunked audio segments (e.g., 30–60s each) ready for transcription.
- **User Actions:** Upload audio / start recording.
- **Validation Rules:** Reject files > 200MB or > 2 hours for MVP; reject unsupported formats with a clear error.
- **Edge Cases:** Silence-only audio, multiple overlapping speakers, very noisy audio, corrupted file upload.

### Module: Transcription (Whisper)
- **Description:** Convert audio chunks into text transcript, stream partial results to the dashboard as they complete.
- **Inputs:** Preprocessed audio chunks.
- **Outputs:** Timestamped transcript segments (JSON: `{start, end, speaker?, text}`).
- **User Actions:** None (automatic).
- **Validation Rules:** Flag segments with low Whisper confidence for manual review.
- **Edge Cases:** Non-English speech, heavy accents, background music/noise, empty segments.

### Module: Extractor Agent
- **Description:** LLM reads the transcript (full or incrementally, per chunk) and outputs structured candidate items: decisions, action items, owner (if named), deadline (if stated), and a confidence score.
- **Inputs:** Transcript text (chunk or full).
- **Outputs:** JSON array of candidate items: `{id, type: "decision"|"action_item", description, owner, deadline, source_quote, confidence}`.
- **User Actions:** None (automatic); optional manual re-trigger from dashboard.
- **Validation Rules:** Every candidate item must include a `source_quote` traceable to the transcript — items without a grounding quote are rejected before reaching the Verifier.
- **Edge Cases:** No action items in transcript (return empty array, not hallucinated tasks), multiple owners for one task, relative deadlines ("by next Friday") needing date resolution against the meeting date.

### Module: Verifier Agent
- **Description:** LLM cross-checks each candidate item's `source_quote` against the actual transcript, flags hallucinations (quote not found or misrepresented), merges/flags duplicates, and rejects vague/incomplete items (no clear action or no owner+deadline).
- **Inputs:** Candidate items (from Extractor) + full transcript.
- **Outputs:** JSON array of verified items: `{id, status: "approved"|"rejected"|"needs_review", reason, final_task}`.
- **User Actions:** None (automatic); manual override on dashboard for "needs_review" items.
- **Validation Rules:** An item can only be `approved` if its source quote is found verbatim (or near-verbatim) in the transcript AND it has either a named owner or an explicit deadline.
- **Edge Cases:** Two candidate items describing the same task with different wording (duplicate detection), an item that's valid but low-confidence (route to `needs_review`, not auto-reject).

### Module: n8n Orchestration Layer
- **Description:** Webhook-triggered workflow that receives verified tasks and routes each to the correct downstream system based on task properties.
- **Inputs:** Verified task JSON (from Verifier Agent, via webhook).
- **Outputs:** Trello card created, Calendar event created (if deadline present), notification sent (if owner present).
- **User Actions:** None (automatic); n8n workflow visible for demo purposes.
- **Validation Rules:** Retry failed API calls (Trello/Calendar/notification) up to 3 times before flagging as failed on the dashboard.
- **Edge Cases:** Trello API rate limit hit, owner has no known chat handle/contact mapping, duplicate webhook delivery (idempotency needed).

### Module: Dashboard
- **Description:** Web UI showing live transcript, extracted/verified items with status, and links to created Trello cards/calendar events.
- **Inputs:** WebSocket/polling updates from backend pipeline.
- **Outputs:** Rendered transcript feed, task list with status badges (extracted / verified / routed / rejected).
- **User Actions:** Upload audio, view live status, manually approve/reject `needs_review` items, click through to Trello card.
- **Validation Rules:** N/A (read-mostly UI).
- **Edge Cases:** Pipeline failure mid-run (show partial results, don't hang UI), very long transcripts (paginate/virtualize list).

## Non-Functional Requirements
- **Performance:** End-to-end (audio-ready → task routed) under 60s for a 10-minute meeting on the demo machine; dashboard updates within 2s of a backend state change.
- **Scalability:** MVP targets single-meeting, single-session use (no multi-tenant requirement); design should not block adding concurrent sessions later.
- **Security:** All API keys and connection settings (Trello, Calendar, notification webhook, local LLM endpoint) stored as environment variables, never committed to the repo or exposed to the frontend.
- **Accessibility:** Dashboard should meet basic keyboard-navigable and readable-contrast standards (WCAG AA is a stretch goal, not a hard MVP requirement given the timeline).
- **Reliability:** Pipeline should degrade gracefully — if the Verifier Agent fails, extracted items still show on the dashboard as "needs_review" rather than the whole run failing silently.
- **Maintainability:** Each agent (Extractor, Verifier) is a standalone, independently testable module with a documented prompt and JSON schema.

## Assumptions & Constraints
- Team has **no existing accounts/setup** for n8n, Trello, or the local LLM/Whisper environment — all setup starts from zero (confirmed by team).
- Timeline: **~3.5 weeks from project kickoff to submission** — MVP scope must be realistic for this window (see ROADMAP.md for the day-by-day breakdown).
- MVP uses **uploaded audio files**, not true real-time streaming (live streaming is a stretch goal / future enhancement given the time budget).
- LLM choice: a locally-hosted open-source model served via Ollama (e.g., `llama3.1` or `mistral`) — exact model finalized in TECH_RULES.md, abstracted behind a thin client so it can be swapped without code changes.
- Whisper runs locally via `faster-whisper` — keeps transcription self-contained with no external dependency (see TECH_RULES.md).
- No dedicated backend infra/hosting budget assumed — the guaranteed setup is local Docker Compose (backend + self-hosted n8n); cloud hosting is an optional convenience layer on top, not a requirement.

## MVP Scope

### Must Have
- Upload audio → Whisper transcription → Extractor Agent → Verifier Agent → n8n routes to Trello.
- Dashboard shows live transcript + task list with status.
- End-to-end demo works on at least one real recorded meeting snippet.

### Should Have
- Calendar event creation for deadline-bearing tasks.
- Notification (chat message, e.g. Discord or Telegram) to task owner.
- Manual approve/reject on dashboard for `needs_review` items.

### Nice To Have
- True live audio streaming instead of file upload.
- Speaker diarization (who said what).
- Multi-meeting history view on dashboard.

## Future Enhancements
- Real-time streaming transcription during live calls (Zoom/Meet bot integration).
- Slack/Teams native integration instead of generic notifications.
- Analytics on task completion rates over time.
