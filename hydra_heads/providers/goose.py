"""Goose CLI provider — goose run -t PROMPT"""

PROVIDER = {
    "name": "goose",
    "binary": "goose",
    "args": ["run", "--no-session"],
    "prompt_flag": "-t",
    "model_flag": "--model",
    "model_detect_command": "grep '^GOOSE_MODEL=' ~/.config/goose/config.yaml 2>/dev/null | cut -d'=' -f2 || echo ${GOOSE_MODEL:-unknown}",
    "env": {"GOOSE_MODE": "auto"},
}
