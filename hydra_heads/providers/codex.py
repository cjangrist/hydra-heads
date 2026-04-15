"""Codex CLI provider — codex exec -m gpt-5.4 -c model_reasoning_effort=high --yolo PROMPT"""

PROVIDER = {
    "name": "codex",
    "binary": "codex",
    "args": ["exec", "-m", "gpt-5.4", "-c", "model_reasoning_effort=xhigh", "--yolo"],
    "prompt_flag": None,
    "model_flag": "-m",
    "env": {},
}
