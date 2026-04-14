"""Thin wrapper to exec bin/update-agents from the installed package."""

import os
import sys


def main():
    script = os.path.join(os.path.dirname(__file__), "scripts", "update-agents.sh")
    if not os.path.isfile(script):
        print(f"ERROR: update-agents script not found at {script}", file=sys.stderr)
        sys.exit(1)
    os.execvp("bash", ["bash", script] + sys.argv[1:])
