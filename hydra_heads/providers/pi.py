"""Pi Coding Agent CLI provider — pi -p --no-session PROMPT"""

PROVIDER = {
    "name": "pi",
    "binary": "pi",
    "args": ["-p", "--no-session"],
    "prompt_flag": None,
    "model_flag": "--model",
    "model_detect_command": "jq -r '.defaultProvider + \"/\" + .defaultModel' ~/.pi/agent/settings.json 2>/dev/null",
    "env": {},
}
