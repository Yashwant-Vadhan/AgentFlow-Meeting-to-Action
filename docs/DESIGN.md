# DESIGN — Meeting-to-Action

## Design Philosophy
- **Visual Style:** Clean, dense, "ops dashboard" aesthetic — think Linear/Trello, not a marketing site. The point is to visibly prove the pipeline works during a live demo, not to look decorative.
- **Branding Direction:** Minimal — dark-on-light neutral palette with one accent color for status/actions. No custom logo needed for MVP.
- **UX Goals:** At any moment during/after a meeting, a viewer should be able to glance at the screen and understand: (1) what's being said, (2) what's been extracted, (3) what's been verified and routed, and (4) if anything failed.

## Information Architecture
- **Navigation Structure:** Single-page app for MVP — no multi-page routing needed. One "Session" view.
- **Screen Hierarchy:**
  1. Upload/Start screen (enter session, upload audio)
  2. Live Session view (transcript + task pipeline, side by side)
  3. (Stretch) Session History view

- **User Flow (text diagram):**
```
[Start Screen]
   |
   |  upload audio file
   v
[Processing State] -- (Whisper transcribing) --> [Live Session View]
   |                                                   |
   |                                          transcript streams in (left pane)
   |                                                   |
   |                                    Extractor Agent emits candidate items
   |                                                   |
   |                                    Verifier Agent approves/rejects/flags
   |                                                   |
   |                              n8n routes approved items -> Trello / Calendar / Notify
   |                                                   |
   v                                                   v
[Task pipeline pane updates status badges: extracted -> verified -> routed]
   |
   v
[needs_review items show inline Approve/Reject buttons]
```

## Screen Specifications

### Screen 1 — Start Screen
- **Purpose:** Entry point; let the user upload a meeting audio file and kick off the pipeline.
- **Components:** File drop zone, "Start Processing" button, session name input (optional, defaults to timestamp).
- **Layout Structure:** Centered single-column card, max-width 480px.
- **Interactions:** Drag-and-drop or click-to-browse for file; button disabled until a valid file is selected.
- **Empty State:** Default state — drop zone with instructional text ("Drop a meeting recording (.mp3/.wav/.m4a) to begin").
- **Error State:** Red inline message under drop zone for unsupported format / oversized file.
- **Loading State:** Button shows spinner + "Uploading..." while file transfers.
- **Responsive Behavior:** Same single-column layout scales down; touch targets ≥ 44px on mobile.

### Screen 2 — Live Session View
- **Purpose:** Primary demo screen — shows the pipeline working end-to-end in real time.
- **Components:**
  - Left pane: scrolling transcript feed, each line timestamped, new lines auto-appended.
  - Right pane: task pipeline list — one card per candidate/verified item, with a status badge (`Extracted` gray → `Verified` blue → `Routed` green, or `Rejected`/`Needs Review` amber).
  - Top bar: session name, overall pipeline status indicator (Processing / Complete / Error), elapsed time.
- **Layout Structure:** Two-column split (60/40 transcript/tasks) on desktop; stacked (transcript above tasks) on mobile.
- **Interactions:** Click a task card to expand and see the `source_quote` it was grounded in; `needs_review` cards show inline **Approve** / **Reject** buttons; click a `Routed` card to open the linked Trello card in a new tab.
- **Empty State:** Right pane shows "No action items extracted yet" until the Extractor Agent emits its first item.
- **Error State:** If a pipeline stage fails (e.g., Verifier Agent errors out), affected cards show a red "Failed — retrying" or "Failed" badge with an inline retry button; transcript pane keeps working independently.
- **Loading State:** Skeleton/pulse placeholders in the task pane while Whisper is still transcribing and no items exist yet.
- **Responsive Behavior:** Below 768px width, stack transcript and task panes vertically with the task pane first (it's the more demo-relevant content).

### Screen 3 (Stretch) — Session History
- **Purpose:** Browse past sessions and their routed tasks.
- **Components:** List of past sessions (name, date, task count), click-through to a read-only version of the Live Session View.
- Deferred to "Should Have" / "Nice to Have" — build only if MVP is done early.

## Design System
- **Colors:**
  - Primary (accent): `#3B82F6` (blue-500)
  - Neutral background: `#F9FAFB`
  - Neutral surface/card: `#FFFFFF`
  - Neutral text: `#111827` (headings), `#6B7280` (secondary text)
  - Semantic success (Routed): `#10B981`
  - Semantic warning (Needs Review): `#F59E0B`
  - Semantic error (Rejected/Failed): `#EF4444`
- **Typography:** System font stack (`-apple-system, Segoe UI, Roboto, sans-serif`) for speed of build; scale: 12/14/16/20/24px; weights 400 (body) / 600 (headings/labels).
- **Spacing:** 4px base unit; scale 4/8/12/16/24/32px.
- **Grid System:** 12-column CSS grid for the two-pane layout; single breakpoint at 768px for mobile stacking.
- **Component Library:**
  - **Buttons:** Primary (filled blue), Secondary (outline), Danger (filled red for Reject) — each with default/hover/disabled states.
  - **Inputs:** File drop zone (default/dragover/error states), text input (default/focus/error).
  - **Cards:** Task card (default/expanded/failed variants).
  - **Tables:** Not used in MVP (card list preferred over table for task pipeline).
  - **Modals:** None required for MVP — inline expand instead.
  - **Notifications/Toasts:** Small toast on task routed successfully and on pipeline errors.

## Accessibility Requirements
- **WCAG Compliance Level:** Aim for AA on color contrast (all text/background pairs above); full AA audit is a stretch goal given the timeline, not a blocker for submission.
- **Keyboard Navigation:** All interactive elements (upload, approve/reject buttons, task card expand) reachable via Tab and operable via Enter/Space.
- **Screen Reader Support:** Status badges include an `aria-label` (e.g., "Status: Verified") since color alone shouldn't convey state.
- **Color Contrast Ratios:** Text/background pairs above chosen to meet ≥ 4.5:1 for body text.

## Micro-interactions
- **Hover Effects:** Task cards lift slightly (subtle shadow) on hover to indicate they're clickable.
- **Page Transitions:** None needed — single-page app, no route transitions.
- **Loading Animations:** Pulsing skeleton cards while waiting for first extracted item; spinner on the top bar status indicator while "Processing."
- **Success States:** Green checkmark + toast when a task is successfully routed to Trello.
- **Error States:** Red badge + toast with a one-line reason when a stage fails.

## Mobile Responsiveness Strategy
- **Breakpoints:** Single breakpoint at 768px (desktop split-pane vs. mobile stacked).
- **Layout shifts:** Two-column → single-column stack (tasks first, transcript second) below 768px.
- **Touch targets:** Minimum 44x44px for all buttons (Approve/Reject, retry) on mobile.
