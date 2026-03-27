"""OpenCode CLI provider — opencode run PROMPT"""

PROVIDER = {
    "name": "opencode",
    "binary": "opencode",
    "args": ["run"],
    "prompt_flag": None,
    "model_detect_command": """grep -o '"modelID": *"[^"]*"' ~/.local/state/opencode/model.json 2>/dev/null | head -1 | cut -d'"' -f4 | awk -F/ '{print $NF}'""",
    "env": {"OPENCODE_PERMISSION": '{"*":"allow"}'},
}
