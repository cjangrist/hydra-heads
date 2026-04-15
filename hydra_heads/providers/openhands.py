"""OpenHands CLI provider — openhands --headless --yolo -t PROMPT"""

PROVIDER = {
    "name": "openhands",
    "binary": "openhands",
    "args": ["--headless", "--yolo"],
    "prompt_flag": "-t",
    "model_detect_command": "python3 -c \"import json; print(json.load(open(__import__('os').path.expanduser('~/.openhands/agent_settings.json')))['llm']['model'].split('/')[-1])\" 2>/dev/null",
    "env": {"OPENHANDS_SUPPRESS_BANNER": "1"},
}
