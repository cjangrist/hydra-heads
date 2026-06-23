"""Kimi provider — kimi -p PROMPT (Kimi Code CLI).

The legacy kimi-cli was migrated to Kimi Code (`~/.kimi-code/`, host-migrated 2026-06-19).
Kimi Code dropped the old `--quiet` and `--thinking` flags — passing them now aborts the
run with `error: unknown option '--quiet'`, which is why this provider was failing preflight.

Kimi Code's prompt mode (`-p`) is the standalone non-interactive path: it cannot be combined
with `--yolo` or `--auto` (both error out), and it already auto-approves tool calls on its own
(host-verified: `kimi -p` writes files without prompting), so no permission flag is needed.
The clean answer goes to stdout; reasoning/session chatter goes to stderr, which the core
ignores unless stdout is empty. Output format defaults to text. Model defaults to
default_model in config.toml (detected below for the display name).
"""

PROVIDER = {
    "name": "kimi",
    "binary": "kimi",
    "args": [],
    "prompt_flag": "-p",
    "model_detect_command": "cat ~/.kimi-code/config.toml ~/.kimi/config.toml 2>/dev/null | grep '^default_model' | head -1 | cut -d'\"' -f2 | awk -F/ '{print $NF}'",
    "env": {},
}
