# hydra-heads

[![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

> **Cut off one head, two more shall take its place.**

hydra-heads sends the same prompt to every AI coding CLI you have installed — in parallel — and returns structured JSON with every response. Preflight pings auto-exclude dead providers, output keys tell you exactly whose opinion you're reading (`claude--opus`, `codex--gpt-5.4`, `kimi--kimi-for-coding`), and full logs are saved to disk.

```
$ hydra-heads "review this function for bugs" --quiet | jq 'keys'
[
  "claude--opus",
  "cline--MiniMax-M2.5-highspeed",
  "codex--gpt-5.4",
  "kilo--mimo-v2-pro",
  "kimi--kimi-for-coding",
  "opencode--glm-5"
]
```

---

## Why

One model has blind spots. Six models reviewing the same code surface things none of them would catch alone.

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

| Provider | Binary | Model detection |
|----------|--------|-----------------|
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | `claude` | `--model` flag in args |
| [Codex CLI](https://github.com/openai/codex) | `codex` | `-m` flag in args |
| [Gemini CLI](https://github.com/google-gemini/gemini-cli) | `gemini` | `-m` flag in args |
| [Kimi](https://github.com/kimiAI/kimi-cli) | `kimi` | `~/.kimi/config.toml` |
| [Kilo Code](https://kilocode.ai/) | `kilo` | `~/.local/state/kilo/model.json` |
| [OpenCode](https://opencode.ai/) | `opencode` | `~/.local/state/opencode/model.json` |
| [Cline](https://cline.bot/) | `cline` | `~/.cline/data/globalState.json` |

Don't have all of them? The preflight ping automatically excludes anything that isn't installed or responding.

**Add your own** via `~/.hydra/providers.yaml`:

```yaml
providers:
  - name: aider
    binary: aider
    args: ["--yes", "--no-git"]
    prompt_flag: "--message"
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
```

### Health check

```
$ hydra-heads --status

Provider     Binary           Status
------------ ---------------- ------------
claude       claude           HEALTHY
cline        cline            HEALTHY
codex        codex            HEALTHY
gemini       gemini           UNHEALTHY
kilo         kilo             HEALTHY
kimi         kimi             HEALTHY
opencode     opencode         HEALTHY
```

---

## Output

JSON to stdout. Keys are `provider--model` so you always know whose opinion you're reading:

```json
{
  "claude--opus": {
    "response": "pong",
    "exit_code": 0,
    "latency_seconds": 6.3,
    "status": "success",
    "logs": {
      "stdout": "~/.hydra/tasks/2026-03-27T.../claude--opus_stdout.log",
      "stderr": "~/.hydra/tasks/2026-03-27T.../claude--opus_stderr.log"
    },
    "attempts": [
      { "attempt": 1, "exit_code": 0, "status": "success", "latency_seconds": 6.3 }
    ]
  },
  "codex--gpt-5.4": { "..." },
  "kimi--kimi-for-coding": { "..." }
}
```

`--schema` prints the full JSON schema. Status codes: `success`, `failed`, `timeout`, `aborted`, `error`.

---

## How it works

```
hydra-heads "review this code"
        |
        v
  +-----------+
  | Preflight |  Ping all providers (20s timeout).
  | Ping      |  Drop the dead. (sorry gemini)
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
  | Collect   |  Read stdout logs, strip ANSI, build JSON.
  | & Return  |  Retry attempts tracked per-provider.
  +-----------+
        |
        v
      stdout -> JSON
```

**Process management** -- Each provider runs in its own session (`_new_session=True`). Timeout or Ctrl+C triggers SIGTERM -> 5s grace -> SIGKILL to the entire process group. Signal handler uses `os.write` (not logging) to avoid deadlocks, skips the lock to avoid blocking on worker threads, and does immediate SIGTERM+SIGKILL escalation for fast cleanup.

**Preflight** -- Before the real task, a quick "say pong" ping with a strict timeout filters out providers that aren't configured, aren't installed, or just aren't feeling it today. Temp directory cleaned up in `finally`. No more leaked `/tmp/hydra_ping_*` dirs.

**Retries** -- Exponential backoff with `abort_event.wait()` (not busy-wait). Launch exceptions are caught and retried, not propagated. Each attempt is tracked in the JSON output.

---

## Configuration

Every flag has an env var:

| Flag | Env var | Default |
|------|---------|---------|
| `--providers` | `HYDRA_PROVIDERS` | all registered |
| `--timeout` | `HYDRA_TIMEOUT` | `1800` (30 min) |
| `--retries` | `HYDRA_RETRIES` | `0` |
| `--ping-timeout` | `HYDRA_PING_TIMEOUT` | `20` |
| `--cwd` | `HYDRA_CWD` | -- |
| `--fail-fast` | `HYDRA_FAIL_FAST` | `false` |
| `--ignore-errors` | `HYDRA_IGNORE_ERRORS` | `false` |
| `--stream` | `HYDRA_STREAM` | `false` |
| `--no-preflight` | `HYDRA_NO_PREFLIGHT` | `false` |
| `--quiet` | `HYDRA_QUIET` | `false` |
| `--log-dir` | `HYDRA_LOG_DIR` | `~/.hydra/tasks` |

Provider configs: `~/.hydra/providers.yaml` (or `HYDRA_PROVIDERS_FILE`).

---

## Project structure

```
hydra_heads/
  core.py              # Engine: parallel launch, poll, timeout, retry, streaming, signals
  cli.py               # Arg parsing, --status, --schema, prompt resolution
  providers/
    __init__.py         # Auto-discovery + YAML override + type validation
    claude.py           # One config dict per provider
    codex.py
    gemini.py
    kimi.py
    kilo.py
    opencode.py
    cline.py
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
kimi--kimi-for-coding: success (55.2s)
kilo--mimo-v2-pro: success (61.8s)
opencode--glm-5: success (48.3s)
cline--MiniMax-M2.5-highspeed: success (44.9s)
```

Six models. Six opinions. One JSON.

Cut a head off, two more grow back.

---

## License

MIT
