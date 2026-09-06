# Security

This document reflects what's actually implemented as of Phase 10
(security hardening) and verified by the Phase 11 test suite. See
[docs/architecture.md](architecture.md) for the full phase-by-phase
implementation history.

## Threat model

Aurora is a **single-user desktop assistant**, not a multi-tenant service.
The threat it defends against is a language model doing something
unintended, destructive, or overreaching -- not a malicious external
attacker with shell access, and not an adversarial user deliberately trying
to break out of the sandbox. Controls are sized accordingly: real,
meaningful barriers against "the model went off the rails," not a
security boundary you'd trust for hostile multi-tenant code execution.

## Centralized permission engine

Every tool has a `risk_level` (safe/low/medium/high/critical) and a
`permission_level` (safe/user/confirm). `app/security/permissions.py::enforce()`
is the **single** place that decision is enforced, called from
`ToolRouter.execute()` before any tool handler runs -- individual tools
(`click`, `double_click`, `type_text`, `press_key`, `delete_file`) do not
each re-implement their own confirmation gate. A CONFIRM-level tool called
without `confirm=true` is refused with `PERMISSION_REQUIRED`, before it
ever touches the filesystem/OS.

Computer-control tools have a *second*, independent gate on top: the
`SECURITY_COMPUTER_CONTROL_ENABLED` flag (off by default) must also be true,
so even a confirmed click/type/key-press is refused unless the operator has
explicitly opted the whole capability in.

**Known limitation:** confirmation is stateless within a single
conversation turn (the agent passes `confirm=true` after the user approves
in chat), not a stored, expiring token as `SECURITY_CONFIRMATION_TIMEOUT_SECONDS`
implies. A real token-based confirmation flow would need a small
persistence layer plus a frontend dialog and is deferred rather than
half-built.

## Filesystem access

- Every file tool (`app/tools/files/`) resolves paths through
  `app/security/validators.py::resolve_safe_path`, which is fail-closed: if
  `SECURITY_ALLOWED_FILESYSTEM_PATHS` is empty, every file operation is
  refused. Paths are resolved (following symlinks, normalizing `..`) *before*
  the containment check, so traversal and symlink escapes are both caught.
- `delete_file` additionally requires `confirm=true`, enforced centrally
  (see above).
- Reads/writes are capped at `SECURITY_MAX_FILE_READ_BYTES`/`SECURITY_MAX_FILE_WRITE_BYTES`.

## Code execution sandbox (`app/tools/terminal/`)

- Only runs Python **source code the model provides**, in a subprocess --
  never a shell string, never arbitrary OS commands.
- A denylist blocks source containing `os.system`, `subprocess.*`,
  `shutil.rmtree`, `socket`, `ctypes`, or literal absolute-path opens under
  `/etc/`, `/dev/`, or a Windows drive root. This is a pattern check on the
  code text, not a runtime jail -- it stops the obvious cases, not a
  determined adversary.
- Runs with `python -I` (isolated mode: ignores the user's site-packages,
  environment variables, and `.pth`/`sitecustomize` files).
- Hard-killed on timeout (`SECURITY_SANDBOX_TIMEOUT_SECONDS`).
- Runs in the same directory as the file tools (the first allowed
  filesystem path) so a script the Coding Agent just wrote can actually be
  read back and executed. This does mean executed code can read/write
  anything under that directory (and, being a real Python process, anything
  the OS user themselves could reach via an absolute path) -- it is **not**
  a filesystem jail. Point `SECURITY_ALLOWED_FILESYSTEM_PATHS` at a
  directory you're comfortable with a generated script touching.

## Network access (web tools) -- SSRF guard

- `open_url`/`extract_page` only accept `http`/`https`.
- Before fetching (and again after following redirects), the target
  hostname is resolved and rejected if it's private/loopback/link-local/
  multicast/reserved -- blocks SSRF against `127.0.0.1`, RFC1918 ranges, the
  cloud metadata endpoint (`169.254.169.254`), etc.
- Responses are capped at `WEB_MAX_RESPONSE_BYTES` and a request timeout.

## Active prompt-injection detection

Beyond labeling tool output as untrusted in the system prompt (below),
`app/security/prompt_injection.py::scan()` actively pattern-matches
retrieved web/file content against known injection phrasing ("ignore
previous instructions", "reveal your system prompt", "you are now a...",
etc.). A match prepends a warning banner directly into the text the model
sees (`annotate()`) and sets a `prompt_injection_suspected` flag in the
tool's metadata -- applied to `open_url`, `extract_page`, and `read_file`.

## Trust boundary for tool/web output

Content returned by any tool (web pages, file contents, search results) is
explicitly labeled as untrusted data in the system prompt every agent
receives (`app/agents/base.py::build_core_system_prompt`) -- the model is
told to treat it as a quotation, never as instructions, and to flag
suspicious embedded instructions to the user rather than follow them.

## Secret redaction

`app/security/secrets.py::redact()`/`redact_value()` mask secrets wherever
they could otherwise leak:

- Every log line, via a structlog processor (`app/utils/logging.py`) --
  applies regardless of which subsystem produced the log record.
- Every tool result/error/metadata, via `ToolRouter.execute()` -- before it
  ever reaches the AI model or the frontend.

Two different mechanisms, deliberately: opaque high-entropy secrets (API
keys, tokens, `APP_SECRET_KEY`) are matched by a safe blind substring
replace; DB/Redis connection-string passwords are matched only via their
actual `://user:PASSWORD@` shape, **not** blind substring matching -- this
project's own dev DB password is literally `"aurora"`, the same string as
the project directory name, and an earlier blind-match implementation was
caught live mangling unrelated file paths as a result (see
`docs/architecture.md`'s Phase 10 section).

## Agent loop protection

- Every agent has `max_steps` and `max_execution_seconds`. The execution
  budget is enforced as a **hard deadline** wrapping each individual model
  call (`asyncio.wait_for`), not just checked between steps.
- Repeated-tool-call loop detection: if the last 4 tool-call signatures
  collapse to ≤2 distinct values, the run stops with `LOOP_DETECTED` rather
  than spinning.

## Rate limiting

A simple per-client-IP fixed-window limiter (`app/core/rate_limit.py`,
`RATE_LIMIT_REQUESTS_PER_MINUTE`, default 120/min) sits in front of every
HTTP endpoint. This is sized for "catch a runaway retry loop or accidental
hammering," not for defending a public multi-tenant deployment -- there is
only ever one real operator of this assistant.

## Audit logging

Every tool call made through an agent run is persisted as a `ToolExecution`
row: `tool_name`, `risk_level`, `success`, `error_code`, `duration_ms`,
`request_id` (the owning `AgentRun.id`), `user_id` (constant `"local"` --
no multi-user auth exists yet), `arguments_hash` (SHA-256 of the redacted,
sorted arguments -- hashed rather than stored raw so audit rows never carry
sensitive argument values), and `permission_status`
(`not_required`/`granted`/`denied`).

## Frontend

No use of `dangerouslySetInnerHTML`/`innerHTML` anywhere in the frontend --
all message and tool-result content renders as plain React text (auto-
escaped) or inside `<pre>{JSON.stringify(...)}}`, so there is no raw-HTML
injection point for XSS to begin with.

## Verified by the Phase 11 test suite

`backend/tests/security/` exercises every control above against the real
running backend: path traversal, permission bypass (including confirming
a JSON string `"true"` does **not** count as boolean `true`), the SSRF
guard, the sandbox denylist plus a real timeout kill, unauthorized/
malformed tool calls, and secret redaction through the real `ToolRouter`.
Run it with `pytest tests/security` (see the README's Testing section).
