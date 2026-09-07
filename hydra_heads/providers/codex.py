"""Codex CLI provider — GPT-5.6 Sol with Fast mode, extra-high reasoning, and no approvals."""

PROVIDER = {
    "name": "codex",
    "binary": "codex",
    "args": [
        "exec",
        "-m", "gpt-6-astra",
        "-c", "service_tier=\"fast\"",
        "-c", "features.fast_mode=true",
        "-c", "model_reasoning_effort=\"xhigh\"",
        "--yolo",
    ],
    "prompt_flag": None,
    "model_flag": "-m",
    "env": {},
}
