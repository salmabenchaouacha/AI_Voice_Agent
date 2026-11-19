# AI Voice Agent: a LangGraph agent that acts through MCP tools

*[Version française](README.fr.md)*

A voice assistant that runs on your own computer. You speak, Whisper transcribes, a LangGraph agent decides which
tools to call, acts through MCP servers (desktop, web, notes and tasks, Google Calendar) and answers out loud.
Sensitive actions wait for a spoken "yes", and web content can never trigger an action on its own.

**At a glance**

- **28 tools** on 4 MCP servers plus local tools, discovered at startup; several actions per spoken request.
- **Prompt-injection guard**: after untrusted web content enters a request, every action on the machine needs the
  user's confirmation. Its effect is measured with an ablation study (`eval/run_eval.py --compare-guard`).
- **Evaluated against the real model**: 21/23 scenarios passed on the initial set (91 %, 95 % CI 73–98 %), median
  latency of 1.2 s per turn with `gemini-3.5-flash-lite`, plus a held-out set of 17 scenarios written after the
  prompts were frozen.
- **Full stack**: FastAPI + WebSocket backend, React frontend with a live view of the agent graph, step traces,
  visual cards and a side panel for timers, reminders and tasks.

## Contents

[What you see](#what-you-see) · [Architecture](#architecture) · [Tools](#tools) · [Security model](#security-model) ·
[Evaluation](#evaluation) · [What still fails](#what-still-fails) · [Getting started](#getting-started) ·
[Google Calendar](#google-calendar-optional) · [Tests](#tests) · [Configuration](#configuration) ·
[Project structure](#project-structure) · [Roadmap](#roadmap)

## What you see

| Feature | Detail |
|---|---|
| Live agent graph | The *Reasoning → Review → Tools* nodes light up while the agent works; *Review* turns amber while it waits for a "yes". |
| Streamed answer | The reply is written as the model generates it (`astream`), then read aloud with word-by-word highlighting. |
| Uncertain words | Each transcribed word carries its Whisper probability; words under 60 % are underlined, so a transcription error is visible ("source" instead of "Sousse"). |
| Step trace | Under every answer: "4 steps · 1.6 s", then each model call and tool call with its duration and status. |
| Visual cards | Weather with a 4-day forecast, clickable web sources, OpenStreetMap map of a place, screenshot thumbnail, Google Calendar events. |
| Side panel | Countdown timers, upcoming reminders, a task list you can tick with the mouse, latest notes, and the log of sensitive actions (confirmed / refused). |

A card travels with the tool's text behind a marker (`backend/cards.py`), so it passes through MCP unchanged. The
toolbox detaches it before the model reads the result: the model never sees coordinates, links or file paths, and
never reads them out loud.

## Architecture

```
 browser (React)                          backend (FastAPI)
┌───────────────────┐  audio / text    ┌──────────────────────────────────────────────────────────┐
│ mic, history,     │ ───────────────► │ server.py   WebSocket /ws                                │
│ graph, cards,     │ ◄─────────────── │   │  stt.py (faster-whisper, word probabilities)         │
│ side panel, TTS   │  node / delta /  │   ▼                                                      │
└───────────────────┘  step / result   │ agent/runtime.py ── no LLM? ──► router.py + skills.py    │
                                       │   │                              (regex, offline mode)   │
                                       │   ▼                                                      │
                                       │ agent/graph.py  (LangGraph StateGraph)                   │
                                       │   START ─► agent ─► review ─► tools ─┐                   │
                                       │              ▲   │      │            │                   │
                                       │              └───┼──────┼────────────┘                   │
                                       │                  ▼      ▼                                │
                                       │                 END   interrupt(): "Do you confirm?"     │
                                       │   │                                                      │
                                       │   ▼ agent/toolbox.py                                     │
                                       │   ├─ local tools: timers, reminders, memory              │
                                       │   └─ agent/mcp_client.py ──stdio──► mcp_servers/         │
                                       │                                      ├ desktop_server.py │
                                       │                                      ├ web_server.py     │
                                       │                                      ├ notes_server.py   │
                                       │                                      └ calendar_server.py│
                                       └──────────────────────────────────────────────────────────┘
```

- **agent**: the model reads the conversation and either answers or calls one or more tools.
- **review**: the guard (`agent/policy.py`) decides whether these calls need a "yes". If so, the graph pauses with
  `interrupt()` and resumes on the user's answer (`Command(resume=...)`).
- **tools**: runs the accepted calls. Reads run in parallel, actions one by one in the requested order, each with
  a timeout.

Conversation memory uses a LangGraph checkpointer keyed by `thread_id` (one conversation per browser). A long-term
memory (`remember` / `forget_memory`) stores facts the user asks to keep. If no model is configured, a regex router
handles simple commands offline.

## Tools

| MCP server | Tools | Confirmation |
|---|---|---|
| `bureau` (desktop) | `battery_status` | never (read-only) |
| `bureau` | `open_app`, `set_volume`, `take_screenshot` | after web content |
| `bureau` | `lock_screen` | always |
| `web` | `get_weather`, `show_map`, `web_search`, `read_page` | never (read-only) |
| `web` | `play_youtube`, `open_in_browser` | after web content |
| `notes` | `list_notes`, `list_tasks` | never (read-only) |
| `notes` | `add_note`, `add_task`, `complete_task`, `clear_done_tasks` | after web content |
| `notes` | `clear_notes` | always |
| `agenda` (Google Calendar) | `list_events` | never (read-only) |
| `agenda` | `create_event` | after web content |
| local | `list_timers`, `list_reminders` | never (read-only) |
| local | `start_timer`, `cancel_timers`, `set_reminder`, `cancel_reminders`, `remember` | after web content |
| local | `forget_memory` | always |

Each server describes its own tools with the standard MCP annotations (`read_only_hint`, `destructive_hint`,
`open_world_hint`); the agent knows no tool in advance. Timers, reminders and memory stay local because they need
the web server's process, which holds the connection to the browser. Reminders are also written to disk and
rescheduled on restart. Tasks live in a JSON file shared by the `notes` MCP server (the agent) and the web server
(the checkbox in the panel).

`backend/mcp.json` uses the same format as Claude Desktop or Cursor, so any existing MCP server can be plugged in
without code. A tool without annotations is treated as the MCP specification says: assumed destructive, so
confirmed.

## Security model

Three rules, applied to every tool call the model requests (`agent/policy.py`):

1. A read-only tool always runs.
2. A tool its server marks as destructive always needs a "yes".
3. Any other tool that acts on the machine needs a "yes" **if untrusted web content entered the current request**.

Rule 3 is the defence against prompt injection. A malicious page can convince the model to call
`open_in_browser` or `create_event`, but it cannot answer "yes" in the user's place. In addition:

- web content is wrapped in `<contenu_externe>` tags and the system prompt treats it as data only;
- it is removed from the context on the next request, so it cannot act later;
- `read_page` refuses local and private addresses (SSRF), `open_app` refuses anything that looks like a command;
- every confirmation decision is logged (`~/assistant_audit.jsonl`) and shown in the side panel.

The confirmation question repeats the parsed arguments ("I'm going to lock the screen. Do you confirm?"), which
also catches transcription errors. An answer that is neither yes nor no ("no, set a timer instead") cancels the
action and is passed to the model as a new request.

**Ablation.** `python eval/run_eval.py --compare-guard` replays the injection scenarios under three variants of the
guard (full, without rule 3, no confirmation at all) and counts the scenarios where a planted action was actually
executed. Results are written to `eval/report.md`.

## Evaluation

`python eval/run_eval.py` plays spoken scenarios against the **real model**. Tools are replaced by doubles that
record each call and return a fixed text, so the real model chooses, the real graph and the real guard decide,
but nothing runs on the machine. A scenario passes when the executed tools match the expected ones: no missing
call, no unexpected call, no forbidden call, and the expected number of confirmations.

| Set | Scenarios | Purpose |
|---|---|---|
| `initial` | 23 | Written with the first version; used to tune the prompts. |
| `nouveau` (held out) | 17 | Written after the prompts were frozen, for features added later (cards, tasks, reminders, calendar); never used for tuning. |

Categories: no tool needed, one action, several actions, memory (follow-ups), confirmation (yes / no / something
else), prompt injection (malicious search result or page), plus the new features and a few traps (a knowledge
question that needs no tool, a note that must not become a task, a duration that calls for a timer, not a
reminder).

**Measured results** (`google_genai:gemini-3.5-flash-lite`, initial set, version before the visual cards,
tasks and calendar):

| Metric | Value |
|---|---|
| Scenarios passed | 21/23 (91 %), 95 % confidence interval 73–98 % |
| Median latency per turn (simulated tools, so mostly the model) | 1.2 s |

The script now reports both sets separately with Wilson confidence intervals, the injection ablation, and a
table of every failure (expected vs executed tools, last reply). `eval/report.md` holds the latest run.

```powershell
cd backend
python eval/run_eval.py --compare-guard     # both sets + guard ablation, writes eval/report.md
python eval/run_eval.py --only nouveau      # held-out set only
python eval/run_eval.py --model ollama:qwen3:8b   # compare another model on the same scenarios
```

**Latency in real use.** Each request appends a line to `backend/metrics.jsonl` (durations and tool names, never
the spoken text). `GET /api/metrics` returns the median and 90th percentile per mode, split into transcription,
model and tools.

### Limits of the measurement

- 23 + 17 scenarios is small: the 95 % interval on the initial set spans 25 points. Treat the numbers as an order
  of magnitude, not a benchmark.
- The scenarios, the prompts and the tool descriptions were written by the same author, which makes the results
  optimistic. The held-out set limits this bias but does not remove it.
- Tools are simulated: the evaluation measures the agent's decisions, not the tools themselves (those are covered
  by the unit and integration tests).
- Scenarios are in French only, and typed, not spoken: transcription errors are not part of this score.

## What still fails

The failures of the latest run are listed one by one in `eval/report.md`. Known failure modes and limitations:

- **Ambiguous intent between close tools**: a note vs a task, a reminder at a time vs a timer for a duration,
  a reminder vs a calendar event. The system prompt gives explicit rules, but the model can still pick the
  neighbour.
- **Relative dates** ("next Thursday at 10") are computed by the model from the current date given in the prompt;
  an off-by-one day is possible.
- **Conversation memory is in RAM** (`InMemorySaver`): it is lost on restart. A SQLite checkpointer
  (`langgraph-checkpoint-sqlite`) would keep it.
- After a confirmation question, the user has to press the mic again to answer; the agent cannot be interrupted
  while it thinks; the answer is spoken only once complete.
- Word highlighting is exact with local Windows voices; other voices do not report word boundaries and the
  position is estimated from elapsed time.
- `read_page` checks the address before reading it, but does not protect against DNS rebinding between the check
  and the request. An MCP server that crashes is not restarted automatically.

## Getting started

Python 3.11+, Node 18+.

```powershell
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate                 # Linux / macOS: source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
copy .env.example .env                 # then put your API key in .env
python server.py

# Frontend (second terminal)
cd frontend
npm install
npm run dev                            # http://localhost:5173
```

At startup the server prints `Mode agent : 26 outils disponibles.` (28 with Google Calendar), or the offline
mode and its reason. `GET /api/status` returns the mode, the model, the tools and their confirmation rule.

On Windows, run `python server.py`, not `uvicorn --reload`: auto-reload changes the asyncio loop and can prevent
the MCP servers from starting.

**Changing the model** only takes one variable, since the graph depends on LangChain's common chat interface:

```
VA_LLM=google_genai:gemini-3.5-flash-lite     # used for the evaluation (langchain-google-genai)
VA_LLM=anthropic:claude-haiku-4-5-20251001    # code default
VA_LLM=ollama:qwen3:8b                         # local model, no key (langchain-ollama)
```

## Google Calendar (optional)

The `agenda` MCP server reads and creates events in the user's Google Calendar. One-time setup:

1. In the [Google Cloud console](https://console.cloud.google.com), create a project and enable the
   **Google Calendar API**.
2. Configure the OAuth consent screen as *External* and add your address as a **test user**.
3. Create an **OAuth client ID** of type *Desktop app*, download the JSON and save it as
   `backend/google_credentials.json` (ignored by git).
4. Install the libraries and authorise access:
   ```powershell
   python -m pip install google-api-python-client google-auth-oauthlib
   python mcp_servers/calendar_server.py --login
   ```
   The token is stored in `~/.assistant_google_token.json`, outside the project.
5. In `backend/mcp.json`, set `"enabled": true` for the `agenda` server and restart.

## Tests

```powershell
cd backend
python -m pytest          # no network, no API key

cd ../frontend
npm test                  # Vitest + Testing Library
```

| File | What it checks |
|---|---|
| `test_agent.py` | the graph with a fake model: multi-actions, confirmation, refusal, injection, memory, limits, streaming, cards |
| `test_mcp.py`, `test_agenda.py` | the MCP servers launched for real (stdio) and queried by the client; Google Calendar with a fake Google service |
| `test_assistant.py` | the full assembly: fake model → graph → real MCP servers → WebSocket |
| `test_policy.py` | the three guard rules |
| `test_eval.py` | the evaluation set (well-formed, tools exist), confidence intervals, guard variants, report |
| `test_cards.py`, `test_planner.py`, `test_stt.py` | visual cards, tasks and reminders, word probabilities |
| `test_api.py`, `test_actions.py`, others | HTTP and WebSocket API, actions, and the original offline mode |

The tests always use the same MCP servers, whatever your `mcp.json` says: `tests/conftest.py` writes a test
configuration with the Google Calendar server disabled.

## Configuration

Environment variables or `backend/.env` (see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `VA_LLM` | `anthropic:claude-haiku-4-5-20251001` | Agent model, `provider:model` |
| `VA_AGENT` | `auto` | `auto` (agent if a model is configured) or `off` (regex only) |
| `VA_MODEL` | `small` | Whisper model: `tiny`, `base`, `small`, `medium` |
| `VA_LANG` | `fr` | Recognition and speech language |
| `VA_WORD_CONFIDENCE` | `1` | Word probabilities (uncertain words underlined) |
| `VA_CITY` | `Tunis` | Default city for the weather |
| `VA_MAX_STEPS` | `6` | Model ↔ tools round trips per request |
| `VA_HISTORY_TURNS` | `8` | Requests kept in the model's context |
| `VA_TOOL_TIMEOUT` | `20` | Seconds per tool call |
| `VA_MCP_CONFIG` | `backend/mcp.json` | MCP servers to launch |
| `VA_TASKS`, `VA_REMINDERS`, `VA_NOTES`, `VA_MEMORY` | files in the home folder | Where tasks, reminders, notes and memory are stored |

## Project structure

```
backend/
├── server.py              FastAPI app: WebSocket /ws, /api/state, /api/status, /api/metrics
├── stt.py                 faster-whisper transcription with word probabilities
├── cards.py               visual cards attached to tool results
├── actions.py, planner.py weather, map, search, notes / tasks and reminders
├── agenda.py              Google Calendar (OAuth, read, create)
├── agent/
│   ├── graph.py           LangGraph StateGraph: agent → review → tools, interrupt(), streaming
│   ├── policy.py          the guard
│   ├── toolbox.py         tool registry, timeouts, simulated copy for the evaluation
│   ├── mcp_client.py      persistent MCP sessions, one asyncio task per server
│   ├── local_tools.py     timers, reminders, memory
│   └── runtime.py         agent mode or offline regex mode
├── mcp_servers/           desktop, web, notes, calendar
├── eval/                  scenarios.json, run_eval.py, report.md
└── tests/
frontend/src/
├── App.jsx
├── hooks/                 useAssistant (WebSocket, mic, state), useSpeech (TTS, word highlighting)
└── components/            AgentGraph, Trace, Board, Cards, History, Spoken, MicButton, Composer
```

## Roadmap

In order of expected impact:

1. Add real spoken requests to the evaluation set, including transcription errors.
2. Persist the conversation memory (SQLite checkpointer).
3. Start speaking while the answer is still streaming, and restart listening after a confirmation question.
4. Restart a crashed MCP server automatically.
