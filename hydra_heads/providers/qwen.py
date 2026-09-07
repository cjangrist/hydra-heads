"""Qwen Code CLI provider — qwen --safe-mode -m qwen3.7-max --yolo -p PROMPT"""

PROVIDER = {
    "name": "qwen",
    "binary": "qwen",
    "args": ["--safe-mode", "-m", "qwen3.8-max", "--yolo"],
    "prompt_flag": "-p",
    "model_flag": "-m",
    "env": {"QWEN_CODE_SUPPRESS_YOLO_WARNING": "1"},
}
