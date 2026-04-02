"""Gemini CLI provider — gemini -m gemini-3.1-pro-preview --yolo -p PROMPT"""

PROVIDER = {
    "name": "gemini",
    "binary": "gemini",
    "args": ["-m", "gemini-3-pro-preview", "--yolo"],
    "prompt_flag": "-p",
    "model_flag": "-m",
    "env": {},
}
