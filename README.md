# Aurora

[![CI](https://github.com/nellozieee/aurora/actions/workflows/ci.yml/badge.svg)](https://github.com/nellozieee/aurora/actions/workflows/ci.yml)

Aurora is a modular, JARVIS-style personal AI assistant that runs on your
own machine. It talks to you in natural language, remembers what matters,
searches the web, reads and edits your files, writes and runs code, sees
and controls your screen when you let it, and schedules reminders and
recurring tasks -- all through a single conversational interface, with
every risky action gated behind an explicit, centralized permission check.

It was built incrementally across 12 completed phases (foundation → AI →
memory → tools → agents → voice → vision → computer control → automation →
security hardening → testing → finalization), each implemented,
live-tested, and fixed before the next began. See
[docs/architecture.md](docs/architecture.md) for the full phase-by-phase
history, including the real bugs found and fixed along the way.

> **Status:** All 12 phases complete. 130 pytest tests passing (1
> environment-limited skip) against both the native and the fully
> containerized backend, `ruff`/`mypy` clean, `docker compose up --build`
> verified healthy end to end. See [docs/architecture.md](docs/architecture.md)
> for full implementation status (including every real bug found and
> fixed) and [docs/security.md](docs/security.md) for the security model.

## Features

- **Conversation** -- streaming chat over WebSocket or REST, with
  conversation history, search, and multi-turn context.
- **Memory** -- long-term memory backed by pgvector semantic search, plus
  short-term per-conversation history.
- **Web research** -- search, fetch, and extract readable content from
  pages, with active prompt-injection detection on retrieved content.
- **Files & documents** -- search/read/create/write/rename/move/copy/delete
  within an explicit allow-list of directories; reads PDF/DOCX/XLSX/CSV/JSON/plain text.
- **Coding** -- a sandboxed Python execution tool (denylisted, isolated,
  timeout-bounded) for the Coding Agent to write and actually run code.
- **Computer control** -- system info, process listing, launching/closing
  registered applications, window focus, screenshots, OCR, vision-model
  screen description, and mouse/keyboard control -- the last of these
  behind a hard off-by-default flag *and* per-action confirmation.
- **Automation** -- a persistent, DB-polling scheduler for one-off,
  interval, and cron-style reminders and chat-triggered tasks, with desktop
  (Windows toast) and Telegram notifications.
- **Multi-agent orchestration** -- intent classification routes each
  message to a specialized agent (General/Research/Coding/Computer), with
  a Planning → Steps → Reviewer pipeline for multi-step requests.
- **Security** -- centralized permission engine, secret redaction, SSRF
  guard, sandboxed code execution, path-traversal-proof file access,
  active prompt-injection detection, per-tool audit logging, and rate
  limiting. See [docs/security.md](docs/security.md).
- **Local or cloud AI** -- Ollama (local, no API key) by default, OpenAI or
  OpenRouter as optional cloud providers, with automatic fallback.
- **Voice** -- local speech-to-text (faster-whisper) and text-to-speech
  (pyttsx3/SAPI5), no API key required; OpenAI's hosted STT/TTS as an
  optional alternative.

## Architecture

```text
Frontend
    ↓
API / WebSocket Layer
    ↓
Assistant Orchestrator
    ↓
Intent / Planning / Agent System
    ↓
Memory + Context System
    ↓
Tool Router
    ↓
Permission Engine
    ↓
Execution Layer
    ↓
External Services / Operating System
```

Every major subsystem (AI providers, voice, memory, tools, agents,
notifications) sits behind an abstraction so implementations can be
swapped without touching the core. Full detail, including every phase's
implementation and the bugs found while building it, is in
[docs/architecture.md](docs/architecture.md).

## Requirements

- Python 3.12+
- Node.js 20+
- Docker + Docker Compose (recommended) -- or a local PostgreSQL 16 (with
  the `pgvector` extension) and Redis 7 instance
- [Ollama](https://ollama.com) if you want local AI (recommended, no API
  key) -- see **Ollama setup** below
- Windows is the primary target for computer-control/voice; the rest of
  the stack is cross-platform

## Installation

```bash
git clone <this repository's URL>
cd aurora
cp .env.example .env       # then edit .env -- see Configuration below
```

Then either **Docker** or **native** setup (below).

## Quick start (Docker)

```bash
docker compose up --build
```

- Backend: http://localhost:8000 (interactive API docs at `/docs`, see
  **API documentation** below)
- Frontend: http://localhost:4173

Ollama is deliberately **not** containerized (see `docker-compose.yml`):
forcing GPU passthrough into a container for local inference adds real
complexity for no benefit when Ollama runs natively just as well. Install
it on the host (see **Ollama setup**) and the backend container reaches it
via `OLLAMA_BASE_URL=http://host.docker.internal:11434` (already set for
you when running the AI provider against Docker Desktop's host gateway --
adjust if your Docker networking differs).

## Quick start (native)

Startup scripts are provided for convenience (they check prerequisites,
start Postgres/Redis via Docker if available, then launch backend +
frontend each in their own window):

```bash
./start.sh          # macOS/Linux/WSL/Git Bash
start.bat           # Windows cmd
./start.ps1         # Windows PowerShell
```

Or by hand:

Backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows; use `source .venv/bin/activate` elsewhere
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Postgres + Redis (if not already running natively):

```bash
docker compose up -d postgres redis
```

## Configuration

All configuration lives in a single `.env` file at the repository root;
see [.env.example](.env.example) for every supported variable, grouped by
subsystem, each with an explanatory comment. Any optional provider
(OpenAI, Telegram, voice, ...) left unconfigured is reported as
`not_configured`/`UNAVAILABLE` rather than crashing the application --
check `GET /api/system/status` any time to see what's actually live.

### AI provider setup

Set `AI_DEFAULT_PROVIDER` (and optionally `AI_FALLBACK_PROVIDER`) to
`ollama`, `openai`, or `openrouter`. If the default provider fails, the
fallback (if configured) is tried automatically before giving up.

- **OpenAI**: set `OPENAI_API_KEY` (and optionally `OPENAI_MODEL`,
  default `gpt-4o-mini`).
- **OpenRouter**: set `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` (no
  default -- OpenRouter hosts many models; pick one that supports tool
  calling, e.g. any recent Claude/GPT/Qwen model on the platform).

### Ollama setup

1. Install from [ollama.com](https://ollama.com) and make sure it's
   running (`ollama serve`, or it starts automatically on most installs).
2. Pull a model that supports tool calling -- this project was built and
   tested against `qwen2.5:3b` (reliable tool calling on modest hardware)
   and `llama3.2:1b` (fast, plain-conversation only -- don't attach tools
   to it). For vision, pull `moondream`. For memory embeddings, pull
   `all-minilm`.
   ```bash
   ollama pull qwen2.5:3b
   ollama pull moondream
   ollama pull all-minilm
   ```
3. Set `OLLAMA_MODEL=qwen2.5:3b`, `VISION_MODEL=moondream`,
   `MEMORY_EMBEDDING_MODEL=all-minilm` (with `MEMORY_EMBEDDING_DIMENSIONS=384`
   to match).
4. A large model (e.g. a 30B-class coder model) may simply not fit your
   GPU's VRAM -- if tool calls silently fail or Ollama errors on load, try
   a smaller model first.

### Voice setup

Voice is off by default (`VOICE_ENABLED=false`) even though the local
providers need no API key -- it's an explicit opt-in. Set
`VOICE_ENABLED=true` and `VOICE_MODE` to `push_to_talk` or `wake_word`.

- **STT**: `STT_PROVIDER=local` uses faster-whisper (`STT_MODEL=tiny.en`
  by default; downloads once on first use into `VOICE_MODELS_DIR`, no key
  needed) or `STT_PROVIDER=openai` (needs `OPENAI_API_KEY`).
- **TTS**: `TTS_PROVIDER=local` uses pyttsx3 (Windows SAPI5 voices, no key)
  or `TTS_PROVIDER=openai` (needs `OPENAI_API_KEY`).
- Wake word and voice-activity detection run in the browser (Web Speech
  API / Web Audio), not the backend.

### Telegram setup

Optional -- powers `send_notification`/reminder Telegram delivery.

1. Message [@BotFather](https://t.me/BotFather) on Telegram, `/newbot`,
   and copy the token it gives you into `TELEGRAM_BOT_TOKEN`.
2. Message your new bot once (anything), then fetch
   `https://api.telegram.org/bot<TOKEN>/getUpdates` and find `message.chat.id`
   in the response -- that's your `TELEGRAM_CHAT_ID`.
3. Leave both blank to run without Telegram; `GET /api/system/status` will
   report `notifications.telegram: "not_configured"` rather than erroring.

### Database setup

- **Docker** (recommended): `docker compose up -d postgres` uses the
  `pgvector/pgvector:pg16` image -- the `vector` extension is already
  available, no manual setup.
- **Native**: install PostgreSQL 16, then `CREATE EXTENSION vector;` in
  your database (the [pgvector](https://github.com/pgvector/pgvector)
  extension must be installed first -- see its README for your OS).
- Either way, apply migrations from `backend/`:
  ```bash
  cd backend
  alembic upgrade head
  ```

## Docker setup

`docker-compose.yml` defines four services: `postgres` (pgvector-enabled),
`redis`, `backend`, and `frontend`. `docker compose up --build` builds and
starts all four. Named volumes (`aurora_postgres_data`, `aurora_redis_data`)
persist data across restarts. Ollama runs natively on the host, not in
Docker (see **Quick start (Docker)** above for why).

## Running development mode

Native quick start (above) runs the backend with `--reload` and the
frontend with Vite's dev server (hot module reload) -- the normal
day-to-day development loop.

## Running production mode

```bash
docker compose up --build -d
```

runs the backend without `--reload` and serves the frontend as a static
production build via `serve` (see `frontend/Dockerfile`). For a real
deployment, also: set `APP_ENV=production`, set a real `APP_SECRET_KEY`,
review `APP_CORS_ORIGINS` (the development-only permissive localhost regex
is skipped outside `APP_ENV=development`), and put a reverse proxy (nginx,
Caddy, Traefik) in front for TLS.

## Testing

```bash
cd backend
.venv\Scripts\activate         # Windows; `source .venv/bin/activate` elsewhere
pytest tests/                  # everything: unit + integration + security + E2E
pytest tests/unit              # fast -- no server/DB/network needed
pytest tests/integration tests/security   # needs the backend running
pytest tests/e2e                          # needs the backend + Ollama running
```

Integration/security/E2E tests exercise the real running backend and real
Postgres/Redis (and, for E2E, a real local Ollama model) rather than
mocks -- consistent with how every phase of this project was verified.
They skip cleanly with a clear reason if a dependency isn't reachable,
rather than failing. See [docs/architecture.md](docs/architecture.md)'s
Phase 11 section for what each test category covers.

## Security

See [docs/security.md](docs/security.md) for the full security model:
threat model, the centralized permission engine, filesystem/network/code-
execution sandboxing, active prompt-injection detection, secret redaction,
audit logging, and rate limiting -- plus what's explicitly *not* yet
implemented (a stateful, expiring confirmation-token flow), stated
honestly rather than glossed over.

## Troubleshooting

- **`GET /api/system/status` is your first stop** -- it reports the real,
  live state of every subsystem (`online`/`not_configured`/`error`), not a
  static assumption.
- **Backend won't start / DB errors**: confirm Postgres is reachable at
  `DATABASE_URL` and migrations are applied (`alembic upgrade head` from
  `backend/`). If using Docker, `docker compose ps` and
  `docker compose logs postgres`.
- **A tool call returns `PERMISSION_REQUIRED`**: that tool is HIGH/CRITICAL
  risk and needs `confirm=true` -- this is enforced centrally and is not a
  bug; the agent should ask you to confirm, then retry with `confirm=true`.
- **Computer-control tools return `COMPUTER_CONTROL_DISABLED`**: set
  `SECURITY_COMPUTER_CONTROL_ENABLED=true` -- it's off by default as the
  single riskiest capability in the system.
- **File tools return `PATH_DENIED`**: the path falls outside every entry
  in `SECURITY_ALLOWED_FILESYSTEM_PATHS`. Add the directory you need there
  (comma-separated) -- file tools refuse everything if this is left empty.
- **Ollama tool calls seem to silently fail or the model ignores tools**:
  some small models don't reliably support tool calling -- this project
  was verified against `qwen2.5:3b`; try that if another model struggles.
- **A response is HTTP 429**: you've hit the rate limiter
  (`RATE_LIMIT_REQUESTS_PER_MINUTE`, default 120/min per client) -- raise
  it or wait a minute.
- **Docker Desktop won't start / hangs on Windows**: if it's stuck on a
  locked runtime socket file after a crash, a full restart of Windows
  usually clears it (a soft Docker Desktop restart alone may not).

## Plugin development

Every capability the AI can call is a `ToolDefinition` registered with the
central `ToolRegistry` (`app/tools/registry.py`) -- there is no separate
"plugin" loading mechanism yet; a new tool is a new Python module under
`app/tools/<area>/tools.py` with a `register(registry)` function, wired up
in `app/tools/bootstrap.py`. To add one:

1. Define a pydantic args model (this becomes the tool's JSON schema, and
   the only shape of input its handler will ever see -- `ToolRouter`
   validates raw model-generated arguments against it before your handler
   runs).
2. Write an `async def handler(args: YourArgsModel) -> ToolResult` that
   returns `ToolResult.ok(data=...)` or `ToolResult.fail(code, message)` --
   never raises for an expected failure case.
3. Register it with an honest `risk_level` and `permission_level`
   (`safe`/`low`/`medium`/`high`/`critical` and `safe`/`user`/`confirm`
   respectively -- see [docs/security.md](docs/security.md) for how
   `confirm` is enforced centrally, not inside your handler).
4. Add it to the `allowed_tools` list of whichever agent(s) in
   `app/agents/` should be able to call it.

## API documentation

The backend is FastAPI, which generates interactive API docs
automatically from the actual route/schema definitions -- no separate doc
to keep in sync:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Raw OpenAPI schema: http://localhost:8000/openapi.json

## Development

This project is implemented in phases (foundation → AI → memory → tools →
agents → voice → vision → computer control → automation → security
hardening → testing → finalization). Each phase is verified working
before the next starts. See [docs/architecture.md](docs/architecture.md)
for the full history, including every real bug found and fixed along the
way.

Lint/type-check (not needed at runtime, only for development):

```bash
cd backend
pip install -r requirements-dev.txt
ruff check app tests
mypy app --ignore-missing-imports
```

## License

MIT -- see [LICENSE](LICENSE).
