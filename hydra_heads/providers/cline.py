"""Cline CLI provider — cline -y PROMPT"""

PROVIDER = {
    "name": "cline",
    "binary": "cline",
    "args": ["-y"],
    "prompt_flag": None,
    "model_detect_command": """grep -oi 'modelId": "[^"]*"' ~/.cline/data/globalState.json 2>/dev/null | tail -1 | cut -d'"' -f3 | awk -F/ '{print $NF}'""",
    "env": {},
}
