"""Gemini provider — driven via the Antigravity CLI (agy), NOT the deprecated gemini CLI.

The standalone gemini CLI was retired for consumer Google accounts (it now returns
IneligibleTierError — Google migrated individuals to the Antigravity suite), so the
"gemini" head now runs `agy --print` pinned to a Gemini model. The provider name stays
"gemini" so existing clients, title-gen priority, and display names keep working unchanged.

Three agy quirks drive this config:
  1. `agy --print` gates stdout on isatty() — piped/redirected stdout yields zero bytes.
     The generic core redirects stdout to a log file, so this provider sets "tty": true,
     which makes the core allocate a pseudo-terminal (sh _tty_out=True). Host-verified:
     under a PTY agy writes its clean answer to the log file; stderr stays empty (no need
     for agy's --log-file glog diversion). Without the PTY, agy emits nothing.
  2. agy authenticates ONLY via the host's logged-in Google account OAuth (Google AI
     Pro/Ultra subscription) under ~/.gemini/antigravity-cli/ — there is no API-key path,
     so no env vars are needed.
  3. agy's own --print-timeout defaults to 5m and would prematurely abort long reviews.
     We set it very high (24h) so hydra-heads' external sh _timeout / SIGTERM remains the
     single authoritative timeout guard, exactly as for every other provider.

The prompt is supplied as the value of `--print` (the core appends `--print <prompt>` last);
agy treats it as the flag's value, not a bare positional, so the leading flags are honored.
"""

PROVIDER = {
    "name": "gemini",
    "binary": "agy",
    "args": ["--dangerously-skip-permissions", "--print-timeout", "86400s", "--model", "Gemini 3.1 Pro (High)"],
    "prompt_flag": "--print",
    "model_flag": "--model",
    "tty": True,
    "env": {},
}
