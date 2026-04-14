"""ForgeCode CLI provider — forge -p PROMPT"""

PROVIDER = {
    "name": "forge",
    "binary": "forge",
    "args": [],
    "prompt_flag": "-p",
    "model_detect_command": "forge config get model --porcelain 2>/dev/null",
    "env": {},
}
