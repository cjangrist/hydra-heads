"""Aider CLI provider — aider --yes-always --no-git --message PROMPT"""

PROVIDER = {
    "name": "aider",
    "binary": "aider",
    "args": [
        "--yes-always",
        "--no-git",
        "--no-auto-commits",
        "--no-dirty-commits",
        "--no-check-update",
        "--no-show-release-notes",
        "--no-pretty",
        "--no-stream",
        "--no-fancy-input",
        "--no-analytics",
        "--no-detect-urls",
        "--no-suggest-shell-commands",
        "--disable-playwright",
        "--map-tokens", "0",
        "--no-auto-lint",
    ],
    "prompt_flag": "--message",
    "model_flag": "--model",
    "model_detect_command": "awk -F': *' '/^model:/{print $2; exit}' ~/.aider.conf.yml 2>/dev/null",
    "env": {},
}
