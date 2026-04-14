"""Factory Droid CLI provider — droid exec -r high --skip-permissions-unsafe PROMPT"""

PROVIDER = {
    "name": "factory",
    "binary": "droid",
    "args": ["exec", "-r", "high", "--skip-permissions-unsafe"],
    "prompt_flag": None,  # Positional argument
    "model_flag": "-m",
"model_detect_command": "python3 -c \"import json,os;d=json.load(open(os.path.expanduser('~/.factory/settings.json')));m=d.get('sessionDefaultSettings',{}).get('model','');cm=d.get('customModels',[]);print(next((c.get('model',m) for c in cm if c.get('id')==m),m) if m.startswith('custom:') else m)\" 2>/dev/null",    "env": {},
}
