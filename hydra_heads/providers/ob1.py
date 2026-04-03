"""OB-1 CLI provider — ob1 --yolo -p PROMPT"""

PROVIDER = {
    "name": "ob1",
    "binary": "ob1",
    "args": ["--yolo"],
    "prompt_flag": "-p",
    "model_flag": "-m",
    "model_detect_command": "grep -o '\"key\": *\"[^\"]*\"' ~/.ob1/model-config.json 2>/dev/null | cut -d'\"' -f4",
    "env": {},
}
