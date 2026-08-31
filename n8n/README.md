# 🔗 n8n Workflow — Meeting-to-Action Pipeline Orchestrator

This workflow handles the output-side routing of verified tasks from the FastAPI backend to **Trello**, **Google Calendar** (optional), and **Discord Webhooks**.

---

## 🏗️ Workflow Diagram

```
[ POST /webhook/verified-task ]
              │
              ▼
    [ Validate Description ] ──(empty)──► [ Respond 400 Bad Request ]
              │ (valid)
              ▼
    [ Trello — Create Card ]
              │
              ▼
    [ Check Has Deadline ]
       ├──(yes)──► [ Google Calendar — Create Event ] ──┐
       └──(no)──────────────────────────────────────────┴──► [ Discord — Notification ]
                                                                      │
                                                                      ▼
                                                            [ Respond 200 Success ]
```

---

## 📥 How to Import into n8n

1. Start self-hosted n8n via Docker:
   ```bash
   docker run -d --name n8n -p 5678:5678 -v n8n_data:/home/node/.n8n n8nio/n8n
   ```
2. Open **[http://localhost:5678](http://localhost:5678)** in your browser.
3. In the left navigation, click **Workflows** → **Import from File**.
4. Select `n8n/workflow-export.json`.
5. Click **Activate** (top-right toggle) so the webhook URL receives requests.

---

## 🔑 Credential & Environment Setup

### 1. Trello Credentials (TS-003)
- In n8n, navigate to **Credentials** → **New** → **Trello API**.
- Enter your `API Key` and `API Token` (get them from [https://trello.com/power-ups/admin](https://trello.com/power-ups/admin)).
- Set Environment Variables in `.env`:
  - `TRELLO_BOARD_ID`: ID of your target Trello board
  - `TRELLO_LIST_ID`: ID of your target list (e.g. "To Do")

### 2. Discord Webhook Setup (TS-004)
- In Discord: **Server Settings** → **Integrations** → **Webhooks** → **New Webhook**.
- Copy the Webhook URL.
- Add to `.env`:
  ```env
  DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
  ```

### 3. Google Calendar API Setup (Optional, TS-004)
- In Google Cloud Console: Enable **Google Calendar API** and create OAuth 2.0 Credentials.
- In n8n: Add **Google Calendar OAuth2 API** credentials.

---

## 🧪 Testing with curl

### Test Valid Task (200 Success):
```bash
curl -X POST http://localhost:5678/webhook/verified-task \
  -H "Content-Type: application/json" \
  -d '{
    "status": "approved",
    "reason": "Clear commitment by Bob",
    "final_task": {
      "id": "task-123",
      "description": "Send the design document to the team",
      "owner": "Bob",
      "deadline": "2026-09-05",
      "type": "action_item"
    }
  }'
```
**Expected Response:**
```json
{
  "status": "success",
  "message": "Task routed successfully to Trello, notifications, and calendar."
}
```

### Test Invalid Task (400 Bad Request):
```bash
curl -X POST http://localhost:5678/webhook/verified-task \
  -H "Content-Type: application/json" \
  -d '{
    "status": "approved",
    "reason": "Missing description test",
    "final_task": {
      "id": "task-456",
      "description": "",
      "owner": "Alice"
    }
  }'
```
**Expected Response:**
```json
{
  "error": "Bad Request",
  "message": "final_task.description is required and cannot be empty."
}
```
