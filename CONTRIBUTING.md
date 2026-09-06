# Contributing to Aurora

Thanks for your interest in Aurora. This document covers how to get set
up, what's expected of a change, and the conventions this codebase has
followed since Phase 1.

## Getting set up

See the README's [Installation](README.md#installation) and
[Quick start (native)](README.md#quick-start-native) sections. In short:

```bash
git clone <this repo>
cd aurora
cp .env.example .env
./start.sh   # or start.bat / start.ps1
```

Lint/type-check tools:

```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
ruff check app tests
mypy app --ignore-missing-imports
```

## Running the tests before you open a PR

```bash
cd backend
pytest tests/unit                       # fast, no server/DB/network needed
pytest tests/integration tests/security # needs the backend running
pytest tests/e2e                        # needs the backend + a local Ollama model
```

CI (`.github/workflows/ci.yml`) runs all of this automatically on every
push/PR, plus a full `docker compose up --build` of all four services --
but running it locally first saves a round trip. See
[docs/architecture.md](docs/architecture.md)'s Phase 11 section for what
each test category actually covers.

## How this project is built

Aurora was built incrementally across 12 phases (see
[docs/architecture.md](docs/architecture.md)), each implemented and
**verified live** before the next began -- real Postgres, real Redis, real
Ollama, real side effects, not mocks of the core behavior. Keep
contributing in that spirit:

- **No placeholders.** Don't add a function that pretends to work, a TODO
  where real logic should be, or a fabricated response. A smaller feature
  that actually works is better than a large one that only pretends to.
- **Test what you touch, live.** If you add or change a tool, an agent, or
  an API endpoint, exercise it against the real running stack (or add a
  test that does) before calling it done -- don't assume from reading the
  code that it works.
- **State limitations honestly.** If something can't be done because a
  credential, model, or platform capability isn't available, say so
  explicitly (see `docs/architecture.md`'s "Known limitations" notes) --
  don't paper over it.

## Adding a new tool

Every capability the AI can call is a `ToolDefinition` registered with the
central `ToolRegistry` (see the README's
[Plugin development](README.md#plugin-development) section for the exact
steps). In particular:

- Give it an honest `risk_level` and `permission_level` -- see
  [docs/security.md](docs/security.md) for how confirmation is enforced
  *centrally* by `ToolRouter`, not inside individual tool handlers. Don't
  re-implement your own confirmation gate inside a tool.
- Validate arguments with a pydantic model; never trust model-generated
  arguments directly.
- If your tool touches the filesystem, resolve paths through
  `app/security/validators.py::resolve_safe_path`. If it makes network
  requests, go through `app/tools/web/fetch.py::fetch_url`'s SSRF-guarded
  fetcher rather than a raw `httpx` call.

## Security-sensitive changes

Read [docs/security.md](docs/security.md) first. If your change touches
permissions, secret handling, path/network validation, or the sandbox,
add a test under `backend/tests/security/` that exercises it against the
real running backend, not just a unit test of the pure logic.

## Cross-platform correctness

This project ships a `docker compose` stack (Linux containers) in
addition to native Windows development. Two real bugs were found this way
and are documented in `docs/architecture.md`'s Phase 12 section as a
cautionary example:

- An eagerly-imported Windows/GUI-only library crashed the entire backend
  container on headless Linux. If you add a dependency that touches
  hardware/display/audio, defer its import to the point of actual use
  (see `app/tools/computer/control.py`'s `_pg()` for the pattern), not
  the module top level.
- A unit test hardcoded a Windows-only absolute path (`C:\Windows\...`)
  and only failed when pytest itself ran on Linux in CI -- Docker+HTTP
  testing of the Linux server hadn't caught it, because that's a
  different guarantee than unit-level code actually executing on Linux.
  Build test paths from `tmp_path`/`Path` operations, not hardcoded
  OS-specific syntax.

If you're touching anything OS-interacting, the full `docker compose up
--build` (not just `postgres`/`redis`) is worth running locally, and CI
will run it regardless.

## Commit messages and PRs

Explain *why*, not just *what* -- the diff already shows what changed.
Keep the same incremental, verify-before-you-move-on spirit: a PR that
adds a feature and confirms it actually works (with what you checked,
stated in the description) is much more useful than one that just
describes the intended behavior.
