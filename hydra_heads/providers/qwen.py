"""Qwen Code CLI provider — qwen -m qwen3-max-preview --yolo -p PROMPT"""

PROVIDER = {
    "name": "qwen",
    "binary": "qwen",
    "args": ["-m", "qwen3-max-preview", "--yolo"],
    "prompt_flag": "-p",
    "model_flag": "-m",
    "env": {},
}
