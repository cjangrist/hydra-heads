"""Kilo Code CLI provider — KILO_PERMISSION='{"*":"allow"}' kilo run --auto PROMPT"""

PROVIDER = {
    "name": "kilo",
    "binary": "kilo",
    "args": ["run", "--auto"],
    "prompt_flag": None,
    "model_detect_command": """grep -o '"modelID": *"[^"]*"' ~/.local/state/kilo/model.json 2>/dev/null | head -1 | cut -d'"' -f4 | awk -F/ '{print $NF}'""",
    "env": {"KILO_PERMISSION": '{"*":"allow"}'},
}
