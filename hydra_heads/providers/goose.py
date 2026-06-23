"""Goose CLI provider — goose run --no-session -t PROMPT

Model detection reads ~/.config/goose/config.yaml. Goose's schema moved the model out of a
top-level GOOSE_MODEL key (legacy) into providers.<active_provider>.model — so we resolve the
active provider, then its model (host-verified 2026-06-23: active_provider=xai_oauth →
providers.xai_oauth.model=grok-4.3), falling back to the legacy GOOSE_MODEL key if present.
"""

PROVIDER = {
    "name": "goose",
    "binary": "goose",
    "args": ["run", "--no-session"],
    "prompt_flag": "-t",
    "model_flag": "--model",
    "model_detect_command": "python3 -c \"import yaml,os; d=yaml.safe_load(open(os.path.expanduser('~/.config/goose/config.yaml'))) or {}; ap=d.get('active_provider'); p=(d.get('providers') or {}).get(ap) or {}; print(p.get('model') or d.get('GOOSE_MODEL') or '')\" 2>/dev/null",
    "env": {"GOOSE_MODE": "auto", "GOOSE_DISABLE_SESSION_NAMING": "true"},
}
