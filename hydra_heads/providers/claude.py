"""Claude Code CLI provider — claude --print --output-format text --model opus --dangerously-skip-permissions -p PROMPT"""

PROVIDER = {
    "name": "claude",
    "binary": "claude",
    "args": ["--print", "--output-format", "text", "--model", "opus", "--effort", "max", "--dangerously-skip-permissions"],
    "prompt_flag": "-p",
    "model_flag": "--model",
    "env": {},
}
