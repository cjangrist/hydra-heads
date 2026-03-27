"""Kimi CLI provider — kimi --quiet --thinking -p PROMPT"""

PROVIDER = {
    "name": "kimi",
    "binary": "kimi",
    "args": ["--quiet", "--thinking"],
    "prompt_flag": "-p",
    "model_detect_command": "grep '^default_model' ~/.kimi/config.toml 2>/dev/null | cut -d'\"' -f2 | awk -F/ '{print $NF}'",
    "env": {},
}
