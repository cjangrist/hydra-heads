"""Grok Build provider — grok --always-approve -p PROMPT."""

PROVIDER = {
    "name": "grok",
    "binary": "grok",
    "args": ["--always-approve"],
    "prompt_flag": "-p",
    "model_flag": "-m",
    "model_detect_command": "grok models 2>/dev/null | awk -F': ' '/^Default model:/{print $2; exit}'",
    "env": {},
}
