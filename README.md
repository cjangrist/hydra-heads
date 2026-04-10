# hydra-heads

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

> **Cut off one head, two more shall take its place.**

hydra-heads sends the same prompt to every AI coding CLI you have installed — in parallel — and returns structured JSON with every response. Preflight pings auto-exclude dead providers, each agent gets an isolated sandbox directory, output keys tell you exactly whose opinion you're reading (`claude--opus`, `codex--gpt-5.4`, `kimi--kimi-for-coding`), and full logs with token counts are saved to disk.

```
$ hydra-heads "review this function for bugs" --quiet | jq 'keys'
[
  "claude--opus",
  "cline--MiniMax-M2.5-highspeed",
  "codex--gpt-5.4",
  "factory--claude-sonnet-4",
  "kilo--mimo-v2-pro",
  "kimi--kimi-for-coding",
  "ob1--o3-pro",
  "opencode--glm-5"
]
```

---

## Why

One model has blind spots. Eight models reviewing the same code surface things none of them would catch alone.

We built hydra-heads to run parallel code reviews across every AI CLI we had installed and cross-reference the findings by consensus. Then we pointed it at its own source code.

| Round | Bugs found | Bugs fixed | What happened next |
|-------|-----------|------------|---------------------|
| 1 | 25 | 25 | Felt great |
| 2 | 13 | 13 | Reviewers found deeper concurrency issues |
| 3 | 18 | 18 | Reviewers found edge cases in the fixes |
| 4 | 9 | 9 | One reviewer caught a name-mismatch bug the other five missed |
| 5 | Still finding things | - | Cut one head off, two more grow back |

The name isn't ironic — it's prophetic. Every round of fixes creates new surface area for the next round to chew on:

| Category | R2 | R4 | R5 | Trend |
|----------|-----|-----|-----|-------|
| Correctness | 6.0 | 6.5 | 6.3 | Reviewers find new edge cases as fast as we fix old ones |
| Concurrency | 4.0 | 5.0 | 5.5 | Steady climb |
| Robustness | 5.0 | 5.5 | 6.0 | Steady climb |
| Architecture | 6.0 | 7.3 | 7.3 | Big jump, held |
| Performance | 8.0 | 7.3 | 7.3 | Traded speed for correctness |

65+ bugs across 5 rounds. The tool that finds the bugs is the tool with the bugs. It's hydras all the way down.

---

## Providers

Works with any AI coding CLI that takes a prompt argument. These ship built-in:

| Provider | Binary | Default model | Prompt flag |
|----------|--------|---------------|-------------|
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | `claude` | opus | `-p` |
| [Codex CLI](https://github.com/openai/codex) | `codex` | gpt-5.4 | stdin |
| [Gemini CLI](https://github.com/google-gemini/gemini-cli) | `gemini` | gemini-3.1-pro-preview | `-p` |
| [Kimi](https://github.com/kimiAI/kimi-cli) | `kimi` | auto-detected | `-p` |
| [Kilo Code](https://kilocode.ai/) | `kilo` | auto-detected | stdin |
| [OpenCode](https://opencode.ai/) | `opencode` | auto-detected | stdin |
| [Cline](https://cline.bot/) | `cline` | auto-detected | stdin |
| [Factory Droid](https://factory.ai/) | `droid` | auto-detected | stdin |
| [OB-1](https://ob1.ai/) | `ob1` | auto-detected | `-p` |

Don't have all of them? The preflight ping automatically excludes anything that isn't installed or responding.

**Add your own** via `~/.hydra/providers.yaml`:

```yaml
providers:
  - name: aider
    binary: aider
    args: ["--yes", "--no-git"]
    prompt_flag: "--message"
    model_flag: "--model"       # optional: flag to override model
    env: {}                     # optional: environment variables
```

---

## Install

```bash
pip install hydra-heads
```

Or from source:

```bash
git clone https://github.com/cjangrist/hydra-heads.git
cd hydra-heads
pip install -e .
```

---

## Quick start

```bash
# Send a prompt to all healthy providers
hydra-heads "explain what this repo does" --cwd /path/to/repo

# Pipe a prompt from a file
hydra-heads --prompt-file review_prompt.txt

# Check which providers are alive
hydra-heads --status

# Stream live output panels (Rich TUI)
hydra-heads "say hello" --stream

# Override models per-provider
hydra-heads "say hi" --model claude:sonnet --model codex:gpt-4o

# Quiet mode for scripting (JSON to stdout, nothing to stderr)
hydra-heads "say pong" --quiet | jq '.[] | .status'

# Print the full JSON output schema
hydra-heads --schema
```

### Health check

```
$ hydra-heads --status

Provider     Binary           Status
------------ ---------------- ------------
claude       claude           HEALTHY
cline        cline            HEALTHY
codex        codex            HEALTHY
factory      droid            HEALTHY
gemini       gemini           UNHEALTHY
kilo         kilo             HEALTHY
kimi         kimi             HEALTHY
ob1          ob1              HEALTHY
opencode     opencode         HEALTHY
```

---

## Output

JSON to stdout. Keys are `provider--model` so you always know whose opinion you're reading.

Each provider result includes the response, sandbox path, a sorted file listing, and a gist with token counts and content previews for every file the agent created:

```json
{
  "codex--gpt-5.4": {
    "response": "4",
    "exit_code": 0,
    "latency_seconds": 17.73,
    "status": "success",
    "logs": {
      "stdout": {
        "path": "/home/user/project/tmp/2026-04-10-11-16-47_0eaf9d0_answer-two-plus-two/codex--gpt-5.4/logs/stdout.log",
        "size_bytes": 2,
        "token_count": 2
      },
      "stderr": {
        "path": "/home/user/project/tmp/2026-04-10-11-16-47_0eaf9d0_answer-two-plus-two/codex--gpt-5.4/logs/stderr.log",
        "size_bytes": 5207,
        "token_count": 1819
      }
    },
    "attempts": [
      {
        "attempt": 1,
        "exit_code": 0,
        "status": "success",
        "latency_seconds": 17.73,
        "logs": {
          "stdout": "/home/user/.hydra/tasks/2026-04-10-11-16-47_0eaf9d0_answer-two-plus-two/codex--gpt-5.4_stdout.log",
          "stderr": "/home/user/.hydra/tasks/2026-04-10-11-16-47_0eaf9d0_answer-two-plus-two/codex--gpt-5.4_stderr.log"
        }
      }
    ],
    "sandbox_path": "/home/user/project/tmp/2026-04-10-11-16-47_0eaf9d0_answer-two-plus-two/codex--gpt-5.4",
    "sandbox_files": [
      "/home/user/project/tmp/.../codex--gpt-5.4/logs/stderr.log",
      "/home/user/project/tmp/.../codex--gpt-5.4/logs/stdout.log",
      "/home/user/project/tmp/.../codex--gpt-5.4/response.md",
      "/home/user/project/tmp/.../codex--gpt-5.4/task_exit_code__0.txt",
      "/home/user/project/tmp/.../codex--gpt-5.4/task_finished_at__2026-04-10T11-17-05.txt",
      "/home/user/project/tmp/.../codex--gpt-5.4/task_started_at__2026-04-10T11-16-47.txt"
    ],
    "gist": [
      {
        "path": "/home/user/project/tmp/.../codex--gpt-5.4/logs/stderr.log",
        "size_bytes": 5207,
        "line_count": 91,
        "token_count": 1819,
        "first_25_lines": "Reading additional input from stdin...\nOpenAI Codex v0.118.0...",
        "tail_25_lines": "tokens used\n12,725\n"
      },
      {
        "path": "/home/user/project/tmp/.../codex--gpt-5.4/response.md",
        "size_bytes": 2,
        "line_count": 2,
        "token_count": 2,
        "first_25_lines": "4\n"
      },
      {
        "path": "/home/user/project/tmp/.../codex--gpt-5.4/task_exit_code__0.txt",
        "size_bytes": 0
      }
    ]
  }
}
```

Notes on the gist:
- Zero-byte files (like marker files) only include `path` and `size_bytes` — no line counts or content
- `tail_25_lines` is omitted when the file has 50 or fewer lines (redundant with `first_25_lines`)
- All paths are fully qualified absolute paths

`--schema` prints the full JSON schema. Status codes: `success`, `failed`, `timeout`, `aborted`, `collection_timeout`, `error`.

### Stderr log output

```
2026-04-10 11:16:40 hydra_heads INFO Providers: codex
2026-04-10 11:16:40 hydra_heads INFO Prompt: what is 2+2? just answer with the number
2026-04-10 11:16:40 hydra_heads INFO Timeout: 60s per provider
2026-04-10 11:16:40 hydra_heads INFO Preflight ping: testing 1 providers (timeout=20s)
2026-04-10 11:16:43 hydra_heads INFO Preflight OK: codex (2.81s)
2026-04-10 11:16:43 hydra_heads INFO Title generation order (by latency): codex
2026-04-10 11:16:47 hydra_heads INFO Generated prompt title: answer-two-plus-two-with-number-only
2026-04-10 11:16:47 hydra_heads INFO Display names: codex--gpt-5.4
2026-04-10 11:16:47 hydra_heads INFO ================================================================
2026-04-10 11:16:47 hydra_heads INFO TASK START — LOG DIR: ~/.hydra/tasks/2026-04-10-..._0eaf9d0_answer-two-plus-two-with-number-only
2026-04-10 11:16:47 hydra_heads INFO ================================================================
2026-04-10 11:16:47 hydra_heads INFO Agent sandbox [codex--gpt-5.4]: ./tmp/2026-04-10-..._answer-two-plus-two.../codex--gpt-5.4
2026-04-10 11:17:05 hydra_heads INFO codex success (exit_code=0) in 17.73s
2026-04-10 11:17:05 hydra_heads INFO ================================================================
2026-04-10 11:17:05 hydra_heads INFO TASK END
2026-04-10 11:17:05 hydra_heads INFO ================================================================
2026-04-10 11:17:05 hydra_heads INFO --- codex: ./tmp/.../codex--gpt-5.4 ---
2026-04-10 11:17:05 hydra_heads INFO   .../codex--gpt-5.4/logs/stderr.log
2026-04-10 11:17:05 hydra_heads INFO   .../codex--gpt-5.4/logs/stdout.log
2026-04-10 11:17:05 hydra_heads INFO   .../codex--gpt-5.4/response.md
2026-04-10 11:17:05 hydra_heads INFO   .../codex--gpt-5.4/task_exit_code__0.txt
2026-04-10 11:17:05 hydra_heads INFO   .../codex--gpt-5.4/task_finished_at__...txt
2026-04-10 11:17:05 hydra_heads INFO   .../codex--gpt-5.4/task_started_at__...txt
2026-04-10 11:17:05 hydra_heads INFO ================================================================
2026-04-10 11:17:05 hydra_heads INFO All providers completed
```

---

## How it works

```
hydra-heads "review this code"
        |
        v
  +-----------+
  | Preflight |  Ping all providers (20s timeout).
  | Ping      |  Drop the dead. Track latency per provider.
  +-----------+
        |
        v
  +-----------+
  | Title     |  Fastest healthy provider generates a 4-10 word
  | Generation|  dash-separated title for the task directory.
  +-----------+
        |
        v
  +-----------+
  | Sandbox   |  Create per-agent sandbox dirs under <cwd>/tmp/.
  | Setup     |  Inject sandboxing rules into each agent's prompt.
  +-----------+
        |
        v
  +-----------+
  | Parallel  |  ThreadPoolExecutor fans out to all healthy
  | Launch    |  providers. Each runs in its own process group.
  +-----------+
        |
        v
  +-----------+
  | Poll/Wait |  0.5s poll loop: completion, timeout, abort.
  |           |  Streaming mode: 150ms log-file polling for
  |           |  live Rich TUI panels.
  +-----------+
        |
        v
  +-----------+
  | Collect   |  Copy logs to sandbox, write marker files,
  | & Return  |  generate file gist with token counts, build JSON.
  +-----------+
        |
        v
      stdout -> JSON
```

### Task directory naming

Each task gets a deterministic, human-readable directory:

```
YYYY-MM-DD-HH-MM-SS_<md5>_<title>/
```

- **Timestamp**: UTC, second precision
- **MD5**: 7-character hash of the prompt (same length as a git short hash), deterministic
- **Title**: 4-10 word dash-separated summary, generated by the fastest healthy provider. Falls back to word extraction from the prompt if all providers fail.

Example: `2026-04-10-11-16-47_0eaf9d0_answer-two-plus-two-with-number-only/`

### Sandbox isolation

Each agent runs in its own sandbox directory:

```
<cwd>/tmp/<task-folder>/
  ├── claude--opus/
  │   ├── response.md          # Agent's final response
  │   ├── 01-analysis.py       # Numbered working files
  │   ├── logs/
  │   │   ├── stdout.log
  │   │   └── stderr.log
  │   ├── task_started_at__2026-04-10T11-16-47.txt
  │   ├── task_finished_at__2026-04-10T11-17-05.txt
  │   └── task_exit_code__0.txt
  ├── codex--gpt-5.4/
  │   └── ...
  └── kimi--kimi-for-coding/
      └── ...
```

Rules are silently injected into every agent's prompt:
1. All file writes confined to the agent's sandbox directory
2. Final response must go to `response.md`
3. No modifying the original codebase
4. No inline code execution — write to file first, then execute
5. No `rm` — move to `trash/` subdirectory instead
6. No piping through `head`/`tail` — capture full output
7. Number files (`01-foo.py`, `02-bar.sh`) and copy before editing
8. Use `~/anaconda3/bin/python` and `~/anaconda3/bin/pip` for Python
9. Add shebangs to executable files

Backup copies of all logs also go to `~/.hydra/tasks/<task-folder>/`.

### Marker files

Empty marker files track task lifecycle in each sandbox:

| File | Created when |
|------|-------------|
| `task_started_at__<YYYY-MM-DDTHH-MM-SS>.txt` | Sandbox is initialized |
| `task_finished_at__<YYYY-MM-DDTHH-MM-SS>.txt` | Provider finishes |
| `task_exit_code__<code>.txt` | Provider finishes |

### Token counting

All file references include token counts computed with `tiktoken` (cl100k_base encoding):
- Log files (`stdout.log`, `stderr.log`) in the `logs` object
- Every file in the `gist` array

### Process management

Each provider runs in its own session (`_new_session=True`). Timeout or Ctrl+C triggers SIGTERM -> 5s grace -> SIGKILL to the entire process group. Signal handler uses `os.write` (not logging) to avoid deadlocks, skips the lock to avoid blocking on worker threads, and does immediate SIGTERM+SIGKILL escalation for fast cleanup.

### Preflight

Before the real task, a quick "respond with just the word pong" ping with a strict timeout filters out providers that aren't configured, aren't installed, or just aren't feeling it today. Latency from the ping is used to rank providers for title generation. Temp directory cleaned up in `finally`.

### Retries

Exponential backoff with `abort_event.wait()` (not busy-wait). Launch exceptions are caught and retried, not propagated. Backoff: `min(2^(attempt-1), 30)` seconds. Each attempt is tracked in the `attempts` array in the JSON output.

---

## Configuration

Every flag has an env var:

| Flag | Env var | Default | Description |
|------|---------|---------|-------------|
| `--providers` | `HYDRA_PROVIDERS` | all registered | Comma-separated provider names |
| `--timeout` | `HYDRA_TIMEOUT` | `1800` (30 min) | Max seconds per provider |
| `--retries` | `HYDRA_RETRIES` | `0` | Retry count per provider |
| `--ping-timeout` | `HYDRA_PING_TIMEOUT` | `20` | Preflight timeout (seconds) |
| `--cwd` | `HYDRA_CWD` | current dir | Working directory for execution |
| `--fail-fast` | `HYDRA_FAIL_FAST` | `false` | Abort all on first failure |
| `--ignore-errors` | `HYDRA_IGNORE_ERRORS` | `false` | Suppress failure warnings |
| `--stream` | `HYDRA_STREAM` | `false` | Show live Rich TUI panels |
| `--no-preflight` | `HYDRA_NO_PREFLIGHT` | `false` | Skip preflight ping |
| `--quiet` / `-q` | `HYDRA_QUIET` | `false` | Suppress all stderr log output |
| `--verbose` / `-v` | — | `false` | Enable debug logging |
| `--log-dir` | `HYDRA_LOG_DIR` | `~/.hydra/tasks` | Base directory for task logs |
| `--model` | — | — | Override model per provider (repeatable, `PROVIDER:MODEL`) |
| `--schema` | — | — | Print JSON output schema and exit |
| `--status` | — | — | Check provider health and exit |
| `--prompt-file` | — | — | Read prompt from file (use `-` for stdin) |

Provider configs: `~/.hydra/providers.yaml` (or `HYDRA_PROVIDERS_FILE`).

---

## JSON schema

`hydra-heads --schema` prints the full output schema. Here it is for reference:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "hydra-heads output",
  "type": "object",
  "description": "Top-level keys are provider names. Each value contains the provider's result.",
  "additionalProperties": {
    "type": "object",
    "required": ["response", "exit_code", "latency_seconds", "status", "logs"],
    "properties": {
      "response": {
        "type": "string",
        "description": "Full text output from the provider"
      },
      "exit_code": {
        "type": "integer",
        "description": "Process exit code (0=success, -1=timeout, -2=aborted, -3=collection_timeout, -4=error)"
      },
      "latency_seconds": {
        "type": "number",
        "description": "Wall-clock seconds from launch to completion"
      },
      "status": {
        "type": "string",
        "enum": ["success", "failed", "timeout", "aborted", "collection_timeout", "error"]
      },
      "logs": {
        "type": "object",
        "properties": {
          "stdout": {
            "type": "object",
            "properties": {
              "path": { "type": "string", "description": "Absolute path to stdout log" },
              "size_bytes": { "type": "integer" },
              "token_count": { "type": "integer" }
            }
          },
          "stderr": {
            "type": "object",
            "properties": {
              "path": { "type": "string", "description": "Absolute path to stderr log" },
              "size_bytes": { "type": "integer" },
              "token_count": { "type": "integer" }
            }
          }
        }
      },
      "attempts": {
        "type": "array",
        "description": "Per-attempt details when retries are enabled",
        "items": {
          "type": "object",
          "properties": {
            "attempt": { "type": "integer" },
            "exit_code": { "type": "integer" },
            "status": { "type": "string" },
            "latency_seconds": { "type": "number" },
            "logs": { "type": "object" }
          }
        }
      },
      "sandbox_path": {
        "type": "string",
        "description": "Absolute path to the agent's sandbox directory"
      },
      "sandbox_files": {
        "type": "array",
        "description": "Sorted list of absolute paths to all files in the agent sandbox",
        "items": { "type": "string" }
      },
      "gist": {
        "type": "array",
        "description": "File listing from the agent sandbox with sizes, token counts, and head/tail previews",
        "items": {
          "type": "object",
          "properties": {
            "path": { "type": "string" },
            "size_bytes": { "type": "integer" },
            "line_count": { "type": "integer" },
            "token_count": { "type": "integer" },
            "first_25_lines": { "type": "string" },
            "tail_25_lines": { "type": "string" }
          }
        }
      }
    }
  }
}
```

---

## Project structure

```
hydra_heads/
  core.py              # Engine: sandbox, parallel launch, poll, timeout, retry, streaming, signals
  cli.py               # Arg parsing, --status, --schema, prompt resolution
  providers/
    __init__.py         # Auto-discovery + YAML override + type validation
    claude.py           # One config dict per provider
    cline.py
    codex.py
    factory.py
    gemini.py
    kilo.py
    kimi.py
    ob1.py
    opencode.py
```

---

## Eating our own dogfood

This entire codebase was hardened by pointing hydra-heads at itself. Send the source to all providers as a code review prompt, score findings by severity and consensus, fix top-down, repeat. Five rounds produced 65+ fixes across concurrency, signal handling, process management, and error handling.

The meta-beauty: the tool that finds the bugs *is* the tool with the bugs. Every fix changes the code that gets reviewed next round, and the reviewers dutifully find new edge cases in those fixes. Correctness stubbornly hovers at 6.3/10 because they keep finding things as fast as we fix them.

```
$ hydra-heads --prompt-file review.txt --timeout 600 --quiet \
  | jq -r 'to_entries[] | "\(.key): \(.value.status) (\(.value.latency_seconds)s)"'

claude--opus: success (42.1s)
codex--gpt-5.4: success (38.7s)
factory--claude-sonnet-4: success (51.3s)
kimi--kimi-for-coding: success (55.2s)
kilo--mimo-v2-pro: success (61.8s)
ob1--o3-pro: success (47.6s)
opencode--glm-5: success (48.3s)
cline--MiniMax-M2.5-highspeed: success (44.9s)
```

Eight models. Eight opinions. One JSON.

Cut a head off, two more grow back.

---

## License

MIT
