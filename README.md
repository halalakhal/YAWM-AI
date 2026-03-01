Here's the updated README with all three additions:

```markdown
# ◈ YAWM AI — 10-Agent Hybrid Daily Planner
### LangChain · LangGraph · ChromaDB · MCP Servers · Custom Python Tools · Ramadan Edition

> Ramadan-focused MAS — 10 agents that plan your day around prayer times, sync to Google Calendar, and email you a curated Islamic podcast + downloadable schedule card.

```
You speak / your calendar syncs
         ↓
┌─────────────────────────────────────┐
│   [0] Router                        │  Agent 0 — Intent classifier · temperature=0
│   Pattern: Agents as Tools          │  Routes: full_plan → pipeline
└──────────┬──────────────────────────┘          direct query → specialist agent
           │ full_plan                  ╔═══════════════════════════════╗
           │                            ║  DIRECT QUERY AGENTS          ║  (bypass)
           │                            ║  Quran · Dhikr · Salah        ║
           ↓                            ║  Sleep · General              ║
┌─────────────────────┐                 ╚═══════════════════════════════╝
│   TaskCollector     │  Agent 1 — Notion MCP + Todoist MCP
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│     Planner         │  Agent 2 — AlAdhan MCP + Ramadan context → routing_config JSON
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│    Supervisor       │  Agent 3 — Pure Python · ZERO LLM · Orchestrator
└──┬───┬───┬──────────┘
   ↓   ↓   ↓          ← PARALLEL fan-out
[Salah][Dhikr][Quran]    Agents 4–6
   ↓   ↓   ↓          ← fan-in  +  RAG (ChromaDB)
┌─────────────────────┐
│    DayPlanner       │  Agent 7 — LLM + Sleep Calculator + SentenceTransformers
└──────────┬──────────┘
           ↓
┌────────────────────────────────────────────┐
│   ConflictChecker                          │  Agent 7.5 — Pure Python · ZERO LLM
│   Pattern: Graph Agent (conditional retry) │  Salah violation → retry (max 2)
└──────────┬─────────────────────────────────┘
           ↓ pass
┌─────────────────────┐
│    CanvaAgent       │  Agent 8 — Pillow PNG · ZERO LLM
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│   DeenPodcast       │  Agent 8.5 — YouTube + Gmail + WhatsApp (CallMeBot)
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│  CalendarAgent      │  Agent 9 — Deletes old events · Batch-writes to Google Calendar
└─────────────────────┘
```

---

## 🔄 Architecture: From Graph Pattern → Hybrid Pattern

The original YAWM AI used a **pure Graph Agent Pattern** — every user message entered the same 9-node DAG. This was correct but inefficient: asking *"what adhkar should I do?"* would trigger the full 30-second pipeline.

The evolved architecture adopts a **Hybrid Pattern**:

| Pattern | Where Used | Why |
|---------|------------|-----|
| **Agents as Tools** | Router (Agent 0) | Bypasses pipeline for direct queries → instant response |
| **Hierarchical Pipeline** | Agents 1–3 | Sequential spine: task collection → planning → supervision |
| **Fan-out / Fan-in** | Agents 4–6 | Three independent agents run in parallel, saving ~30s |
| **Graph Agent (conditional)** | Agent 7.5 | ConflictChecker creates a bounded retry loop (max 2) |

The Router adds the efficiency layer the pure graph lacked, while the graph topology preserves typed state, parallel execution, and conditional edge guarantees.

> 📄 Full architecture diagram and technical report available in [`Architecture_Report/`](./Architecture_Report/)

---

## 🌐 Web Interface — FastAPI + WebSocket

YAWM AI includes a real-time web interface built with **FastAPI** and **WebSockets** — no terminal needed.

```bash
uvicorn app:app --reload
```

Open **http://localhost:8000** and:
- Type how you're feeling → parameters are extracted automatically
- Confirm → the full 10-agent pipeline runs in real time
- Watch every agent complete live in the right panel
- See the full summary: schedule blocks, sleep window, Quran progress, podcast link

The interface uses the **exact same** `graph.astream()` pipeline as `main.py` — no simulation, no shortcuts.

```
app.py          ← FastAPI backend · WebSocket streaming · LLM parameter extraction
ui/index.html   ← Single-page dark UI · real-time agent status · live logs
```

---

## 📊 Observability — LangFuse Tracing

YAWM AI integrates **LangFuse** for full LLM observability across all agents.

Every pipeline run is traced end-to-end:
- Token usage and cost per agent
- Latency breakdown (which agent is slowest)
- Full input/output for every LLM call
- Session-level trace grouping per user run

```bash
# Add to .env
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

LangFuse is optional — if keys are not set, the pipeline runs normally without tracing.

---

## 🚀 Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env — fill in your API keys
```

### 3. Set up Google Calendar OAuth
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Enable the Google Calendar API
3. Create OAuth 2.0 credentials → download as `config/google_credentials.json`
4. First run will open a browser for OAuth consent

### 4. Set up Notion Integration
1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Create integration → copy token to `NOTION_TOKEN`
3. Share your Tasks database with the integration
4. Copy database ID to `NOTION_DATABASE_ID`

### 5. Set up Todoist
1. Go to [todoist.com/app/settings/integrations/developer](https://todoist.com/app/settings/integrations/developer)
2. Copy your API token to `TODOIST_API_TOKEN`

### 6. Seed RAG preferences
```bash
python -m rag.preferences
```

### 7. Run
```bash
# Web interface (recommended)
uvicorn app:app --reload

# CLI
python main.py

# Custom
python main.py --mood tired --ramadan-day 27
python main.py --voice "Don't forget Iftar talk tonight" --ramadan-day 29
```

---

## 📁 Project Structure

```
yawm_ai/
├── main.py                         ← CLI entry point
├── app.py                          ← FastAPI backend · WebSocket streaming
├── settings.py                     ← Root-level settings alias
├── start-mcp.cmd                   ← MCP server launcher
│
├── ui/
│   └── index.html                  ← Web interface · dark theme · real-time agents
│
├── Architecture_Report/            ← Full architecture diagram + technical PDF report
│
├── graph/
│   ├── state.py                    ← LangGraph shared TypedDict state (YawmState)
│   ├── graph_builder.py            ← Wires 10 nodes + edges + conditional retry
│   └── graph_runner.py             ← Streaming runner + rich console UI
│
├── agents/
│   ├── router.py                   ← Agent 0: Intent classifier (temperature=0)
│   ├── task_collector.py           ← Agent 1: Notion + Todoist via MCP
│   ├── planner.py                  ← Agent 2: Context analysis → routing_config JSON
│   ├── supervisor.py               ← Agent 3: Pure Python orchestrator (ZERO LLM)
│   ├── salah_guardian.py           ← Agent 4: Prayer times + build_prayer_blocks()
│   ├── dhikr_agent.py              ← Agent 5: Adhkar schedule blocks
│   ├── quran_wird.py               ← Agent 6: Quran tracker + ceiling division
│   ├── day_planner.py              ← Agent 7: LLM scheduler + RAG enrichment
│   ├── conflict_checker.py         ← Agent 7.5: Pure Python validator (ZERO LLM)
│   ├── canva_agent.py              ← Agent 8: Pillow PNG renderer (ZERO LLM)
│   ├── deen_podcast.py             ← Agent 8.5: YouTube + Gmail + WhatsApp
│   └── calendar_agent.py           ← Agent 9: Google Calendar write
│
├── mcp_servers/                    ← Standalone MCP servers (stdio transport)
│   ├── google_calendar_mcp.py      ← Google Calendar API tools
│   ├── notion_mcp.py               ← Notion database tools
│   ├── todoist_mcp.py              ← Todoist API tools
│   ├── aladhan_mcp.py              ← AlAdhan prayer times (free, no key)
│   ├── deen_notify_mcp.py          ← YouTube + Gmail + WhatsApp notification
│   └── canva_mcp.py                ← Local Pillow schedule card renderer
│
├── tools/
│   ├── mcp_client.py               ← MultiServerMCPClient factory
│   ├── sleep_calculator.py         ← Real 90-min cycle sleep engine
│   ├── quran_tracker.py            ← Persistent JSON Quran progress tracker
│   └── prayer_block_builder.py     ← build_prayer_blocks() deterministic utility
│
├── rag/
│   ├── chroma_store.py             ← ChromaDB vector store setup
│   ├── embeddings.py               ← SentenceTransformers all-MiniLM-L6-v2
│   └── preferences_loader.py       ← Load / query personal preferences
│
├── utils/
│   ├── prayer_times.py             ← Prayer time helpers + Ramadan logic
│   └── schedule_renderer.py        ← Pillow PNG card generator
│
├── config/
│   └── settings.py                 ← Centralised env config
│
├── data/
│   └── quran_progress.json         ← Persistent Quran reading tracker
│
├── output/                         ← Generated PNG cards saved here
├── requirements.txt
└── .env.example
```

---

## 🧠 Architecture: LangGraph Hybrid Graph Pattern

```python
# graph/graph_builder.py — full wiring:

START → router
          │
          ├─── direct_query ──► [specialist agent] → END
          │
          └─── full_plan ──► task_collector → planner → supervisor
                                                             │
                                         ┌───────────────────┼───────────────────┐
                                         ▼                   ▼                   ▼
                                  salah_guardian       dhikr_agent         quran_wird
                                         │                   │                   │
                                         └───────────────────┴───────────────────┘
                                                             │  (fan-in + RAG)
                                                        day_planner
                                                             │
                                                    conflict_checker
                                                      │           │
                                               violation       pass
                                                  │               │
                                              supervisor      canva_agent
                                           (retry, max 2)         │
                                                             deen_podcast
                                                                  │
                                                           calendar_agent → END
```

**Key LangGraph features used:**
- `StateGraph(YawmState)` — typed shared state flows through all nodes
- Router conditional edges — Agents-as-Tools bypass for direct queries
- Fan-out parallelism — Agents 4/5/6 run concurrently after Supervisor
- Fan-in — DayPlanner waits for all three to complete
- ConflictChecker conditional edge — Graph Agent retry loop (max 2)
- `add_messages` reducer — message bus for ReAct agent loops
- `MemorySaver` checkpointer — replay and resume support

---

## 🔌 MCP Servers

Each MCP server runs as a **subprocess** via `stdio` transport.
`MultiServerMCPClient` from `langchain-mcp-adapters` connects all six:

| Server | Tools |
|--------|-------|
| `google_calendar_mcp` | `gcal_list_events`, `gcal_create_event`, `gcal_delete_event` |
| `notion_mcp` | `notion_list_tasks`, `notion_complete_task` |
| `todoist_mcp` | `todoist_list_tasks`, `todoist_complete_task` |
| `aladhan_mcp` | `get_prayer_times`, `get_hijri_date` |
| `deen_notify_mcp` | `search_deen_youtube`, `send_gmail_notify`, `send_whatsapp_notify` |
| `canva_mcp` | `render_schedule_card` |

Agents import **only the tools they need** via `client.get_tools(server_name="...")`.

---

## 🧩 Custom Python Tools (Non-LLM)

| Tool | What it does |
|------|-------------|
| `SleepCalculator` | Works backward from 3:15 AM, fits complete 90-min cycles based on mood |
| `QuranTracker` | Reads/writes `quran_progress.json`; calculates today's pages via ceiling division |
| `build_prayer_blocks()` | Constructs 5 prayer blocks with correct durations; Iftar 60 min, Qadr Isha 120 min |
| `retrieve_preferences()` | Queries ChromaDB for top-8 preferences by semantic similarity |

---

## 🧠 RAG Layer — ChromaDB + SentenceTransformers

Personal preferences are stored as vector embeddings using `all-MiniLM-L6-v2`.

```python
# Example stored preferences
"coding sessions need 2 to 3 hour uninterrupted blocks"
"shower should be scheduled in the evening"
"hair appointment takes 2 hours"
"avoid deep work after Dhuhr when tired"
```

At DayPlanner time, a semantic similarity query retrieves the top-8 most relevant preferences and injects them into the scheduling prompt.

---

## 🗓️ Google Calendar Color Coding

| Block Type | Color | Google Calendar Label |
|------------|-------|-----------------------|
| 🟢 Prayer | `#34D399` | Sage |
| 🔵 Deep Work | `#60A5FA` | Peacock |
| 🔴 Rest Zone | `#F87171` | Tomato |
| 💜 Sleep | `#A78BFA` | Lavender |
| 🟠 Meal / Iftar | `#FB923C` | Tangerine |
| 🟡 Flexible | `#FBBF24` | Banana |
| 🟣 Dhikr / Quran | `#818CF8` | Grape |
| ⚫ Meeting | `#64748B` | Graphite |

---

## 🌙 Ramadan Intelligence

- **Laylat Al-Qadr detection**: Nights 21, 23, 25, 27, 29 → Isha extended to 120 min + extra Quran pages
- **Iftar block**: Maghrib automatically extended to 60 min in Ramadan
- **Suhoor**: Pre-Fajr meal slot (03:30–04:15) added automatically
- **Sleep cycles**: SleepCalculator fits complete 90-min cycles backward from Suhoor — `tired` mood gets 4 cycles, `energized` gets 3
- **Khatm tracking**: Quran pages calculated from persistent JSON, not estimated by LLM
- **ConflictChecker**: Only Salah violations trigger retries — other warnings do not block

---

## 💡 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | ✅ | Claude API key |
| `GOOGLE_CALENDAR_ID` | ✅ | Calendar ID (`primary` or specific) |
| `GOOGLE_CREDENTIALS_PATH` | ✅ | OAuth credentials JSON |
| `NOTION_TOKEN` | ✅ | Notion integration token |
| `NOTION_DATABASE_ID` | ✅ | Tasks database ID |
| `TODOIST_API_TOKEN` | ✅ | Todoist API token |
| `PRAYER_CITY` | ✅ | City for prayer times |
| `PRAYER_COUNTRY` | ✅ | Country for prayer times |
| `PRAYER_METHOD` | ⬜ | Calculation method (default: 2) |
| `RAMADAN_DAY` | ⬜ | Default Ramadan day (CLI overrides) |
| `USER_TIMEZONE` | ⬜ | Your timezone (default: Africa/Casablanca) |
| `CALLMEBOT_PHONE` | ⬜ | WhatsApp number for DeenPodcast alerts |
| `CALLMEBOT_API_KEY` | ⬜ | CallMeBot API key |
| `CHROMA_PERSIST_DIR` | ⬜ | ChromaDB persistence path (default: ./data/chroma) |
| `LANGFUSE_PUBLIC_KEY` | ⬜ | LangFuse public key for tracing |
| `LANGFUSE_SECRET_KEY` | ⬜ | LangFuse secret key for tracing |
| `LANGFUSE_HOST` | ⬜ | LangFuse host (default: https://cloud.langfuse.com) |

---

