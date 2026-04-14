"""OpenHands CLI provider — openhands (TUI only, no headless mode)"""

PROVIDER = {
    "name": "openhands",
    "binary": "openhands",
    "args": [],
    "prompt_flag": None,
    "model_detect_command": "python3 -c \"import json; print(json.load(open(__import__('os').path.expanduser('~/.openhands/agent_settings.json')))['llm']['model'].split('/')[-1])\" 2>/dev/null",
    "env": {},
}
