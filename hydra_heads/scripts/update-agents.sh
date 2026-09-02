#!/usr/bin/env bash
# update-agents — Update all hydra-heads provider CLI binaries
# Source: https://github.com/cjangrist/hydra-heads/tree/main/hydra_heads/providers
#
# Provider → Binary mapping (from repo):
#   claude.py   → claude   (Claude Code)
#   codex.py    → codex    (Codex CLI)
#   gemini.py   → agy      (Antigravity CLI — Gemini 3.1 Pro; legacy gemini CLI retired 2026-06-18)
#   goose.py    → goose    (Goose)
#   grok.py     → grok     (Grok Build)
#   kilo.py     → kilo     (Kilo Code)
#   kimi.py     → kimi     (Kimi Code)
#   opencode.py → opencode (OpenCode)
#   pi.py       → pi       (Pi Coding Agent)
#   qwen.py     → qwen     (Qwen Code)
#
# Compatible with bash 3.2+ (macOS default).

set -eo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
# PROVIDER_DEFS describes how to UPDATE a binary that is already installed.
# Each line: "binary|method|package"
#   npm|@scope/pkg    → npm install -g @scope/pkg@latest
#   go|module@latest  → go install module@latest
#   pip|pkg           → pip install --upgrade pkg
#   cargo|pkg         → cargo install pkg --force
#   custom|command    → eval command
#
# Most providers ship their own self-update subcommand, so their method is
# "custom" and the package is that subcommand. A self-update subcommand cannot
# bootstrap a binary that does not exist yet, so first-install is a separate
# concern, handled by install_command_for() below.
#
# Edit these if your install sources differ.

PROVIDER_DEFS="\
agy|custom|agy update
claude|custom|claude update
codex|custom|codex update
goose|custom|goose update
grok|custom|grok update
kilo|custom|kilo upgrade
kimi|custom|kimi update
opencode|custom|opencode upgrade
pi|custom|pi update --all
qwen|npm|@qwen-code/qwen-code"

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
DIM='\033[2m'
BOLD='\033[1m'
RESET='\033[0m'

# ── State ─────────────────────────────────────────────────────────────────────
UPDATED=""
FAILED=""
SKIPPED=""
DRY_RUN=false
PARALLEL=false

# ── Usage ─────────────────────────────────────────────────────────────────────
usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] [provider ...]

Update all (or specified) hydra-heads provider CLI binaries.

Options:
  -n, --dry-run     Show what would be done without executing
  -p, --parallel    Run updates in parallel (faster, noisier output)
  -l, --list        List all configured providers and exit
  -c, --check       Check which providers are installed and their versions
  -h, --help        Show this help

Examples:
  $(basename "$0")                  # Update all providers
  $(basename "$0") claude codex     # Update only claude and codex
  $(basename "$0") -n               # Dry run — show commands only
  $(basename "$0") -c               # Check installed versions
EOF
    exit 0
}

# ── Helpers ───────────────────────────────────────────────────────────────────
log_info()  { printf "${CYAN}[INFO]${RESET}  %b\n" "$*"; }
log_ok()    { printf "${GREEN}[  OK]${RESET}  %b\n" "$*"; }
log_warn()  { printf "${YELLOW}[WARN]${RESET}  %b\n" "$*"; }
log_fail()  { printf "${RED}[FAIL]${RESET}  %b\n" "$*"; }
log_dim()   { printf "${DIM}       %b${RESET}\n" "$*"; }

get_version() {
    local bin="$1"
    local ver=""
    # Merge stderr (some tools like pi write version to stderr); filter node deprecation noise.
    # Only try --version / -v flags — never bare subcommand 'version' which can invoke an agent.
    for flag in --version -v; do
        ver=$("$bin" $flag 2>&1 | grep -v -E '^\(node:[0-9]+\)|^\(Use |DeprecationWarning' | head -1) && [ -n "$ver" ] && {
            echo "$ver"
            return 0
        }
    done
    # Fallback: check pip package metadata
    ver=$(pip show "$bin" 2>/dev/null | grep -i '^Version:' | awk '{print $2}')
    [ -n "$ver" ] && { echo "$ver"; return 0; }
    echo "unknown"
}

get_bin_path() {
    command -v "$1" 2>/dev/null || echo ""
}

# Lookup a provider definition by binary name. Prints "binary|method|package" or nothing.
lookup_provider() {
    local name="$1"
    echo "$PROVIDER_DEFS" | grep "^${name}|" | head -1
}

# Get sorted list of all provider binary names
all_provider_names() {
    echo "$PROVIDER_DEFS" | cut -d'|' -f1 | sort
}

# Official non-interactive first-install command for a "custom" provider, or empty
# if none is known. Only consulted when the binary is absent — an installed binary
# always updates through its own PROVIDER_DEFS entry.
#
# These are the vendors' documented one-liners. They live in a case statement rather
# than a fourth PROVIDER_DEFS field because most contain a pipe, which would collide
# with that table's '|' separator.
#
# Two host-verified quirks are baked in:
#   pi       — pi.dev's installer shows an interactive reinstall menu whenever a
#              controlling tty is present (it reads /dev/tty directly, so redirecting
#              stdin is not enough). setsid detaches the controlling terminal and
#              forces the installer's no-tty branch, which never prompts.
#   opencode — its installer hardcodes INSTALL_DIR=$HOME/.opencode/bin (it no longer
#              honours XDG_BIN_DIR) and then appends a PATH line to the user's shell
#              rc file, which does nothing for the current process. --no-modify-path
#              suppresses that edit and the symlink puts opencode on the same PATH
#              entry every other provider installs to.
install_command_for() {
    case "$1" in
        agy)      echo 'curl -fsSL https://antigravity.google/cli/install.sh | bash' ;;
        claude)   echo 'curl -fsSL https://claude.ai/install.sh | bash' ;;
        codex)    echo 'curl -fsSL https://chatgpt.com/codex/install.sh | sh' ;;
        goose)    echo 'curl -fsSL https://github.com/aaif-goose/goose/releases/download/stable/download_cli.sh | CONFIGURE=false bash' ;;
        grok)     echo 'curl -fsSL https://x.ai/cli/install.sh | bash' ;;
        kilo)     echo 'npm install -g @kilocode/cli' ;;
        kimi)     echo 'npm install -g @moonshot-ai/kimi-code' ;;
        opencode) echo 'curl -fsSL https://opencode.ai/install | bash -s -- --no-modify-path && mkdir -p "$HOME/.local/bin" && ln -sf "$HOME/.opencode/bin/opencode" "$HOME/.local/bin/opencode"' ;;
        pi)       echo 'curl -fsSL https://pi.dev/install.sh | setsid sh' ;;
        *)        echo "" ;;
    esac
}

# ── Core update logic ────────────────────────────────────────────────────────
update_provider() {
    local name="$1"
    local def
    def=$(lookup_provider "$name")

    if [ -z "$def" ]; then
        log_fail "unknown provider: $name"
        return 1
    fi

    local method package
    method=$(echo "$def" | cut -d'|' -f2)
    package=$(echo "$def" | cut -d'|' -f3-)

    local bin_path
    bin_path=$(get_bin_path "$name")

    local old_ver="not installed"
    if [ -n "$bin_path" ]; then
        old_ver=$(get_version "$name")
    fi

    # A missing binary cannot run its own self-update subcommand — that is what makes
    # `agy update` exit 127 on a host with no agy. Swap in the vendor's first-install
    # one-liner for that case. Methods that install from a package spec (npm/go/pip/
    # cargo) already bootstrap a missing binary correctly, so they are left alone.
    local action="update"
    if [ -z "$bin_path" ] && [ "$method" = "custom" ]; then
        local install_cmd
        install_cmd=$(install_command_for "$name")
        if [ -z "$install_cmd" ]; then
            echo ""
            log_info "${BOLD}${name}${RESET} ${DIM}(${method}: ${package})${RESET}"
            log_fail "$name is not installed and has no install command configured"
            log_dim "add one to install_command_for() in this script"
            FAILED="${FAILED} ${name}"
            return 1
        fi
        action="install"
        method="install"
        package="$install_cmd"
    fi

    echo ""
    log_info "${BOLD}${name}${RESET} ${DIM}(${method}: ${package})${RESET}"
    if [ -n "$bin_path" ]; then
        log_dim "path: $bin_path"
        log_dim "current: $old_ver"
    else
        log_warn "binary '$name' not found in PATH — installing"
    fi

    if $DRY_RUN; then
        case "$method" in
            npm)     log_dim "[dry-run] npm install -g ${package}@latest" ;;
            go)      log_dim "[dry-run] go install ${package}" ;;
            pip)     log_dim "[dry-run] pip install --upgrade --break-system-packages ${package}" ;;
            cargo)   log_dim "[dry-run] cargo install ${package} --force" ;;
            custom)  log_dim "[dry-run] ${package}" ;;
            install) log_dim "[dry-run] ${package}" ;;
            *)       log_fail "unknown method: $method" ;;
        esac
        SKIPPED="${SKIPPED} ${name}"
        return 0
    fi

    # stdin is closed on every path so an installer that probes it cannot stall a
    # non-interactive run. Installers that read /dev/tty directly instead of stdin
    # need their own guard — see the pi entry in install_command_for().
    local output=""
    local rc=0
    case "$method" in
        npm)     output=$(npm install -g "${package}@latest" 2>&1 </dev/null) || rc=$? ;;
        go)      output=$(go install "$package" 2>&1 </dev/null) || rc=$? ;;
        pip)     output=$(pip install --upgrade --break-system-packages "$package" 2>&1 </dev/null) || rc=$? ;;
        cargo)   output=$(cargo install "$package" --force 2>&1 </dev/null) || rc=$? ;;
        custom)  output=$(eval "$package" 2>&1 </dev/null) || rc=$? ;;
        install) output=$(eval "$package" 2>&1 </dev/null) || rc=$? ;;
        *)
            log_fail "unknown install method '$method' for $name"
            FAILED="${FAILED} ${name}"
            return 1
            ;;
    esac

    if [ "$rc" -ne 0 ]; then
        log_fail "$name $action failed (exit $rc)"
        echo "$output" | while IFS= read -r line; do log_dim "$line"; done
        FAILED="${FAILED} ${name}"
        return 1
    fi

    # A fresh install lands in a directory whose contents bash may have already
    # resolved, so drop the command hash table before looking the binary up again.
    hash -r 2>/dev/null || true
    bin_path=$(get_bin_path "$name")
    if [ -z "$bin_path" ]; then
        log_fail "$name $action reported success but '$name' is still not on PATH"
        log_dim "installer output follows:"
        echo "$output" | while IFS= read -r line; do log_dim "$line"; done
        FAILED="${FAILED} ${name}"
        return 1
    fi

    local new_ver
    new_ver=$(get_version "$name")
    if [ "$old_ver" != "$new_ver" ]; then
        log_ok "$name: ${old_ver} → ${GREEN}${new_ver}${RESET}"
    else
        log_ok "$name: ${new_ver} ${DIM}(unchanged)${RESET}"
    fi
    UPDATED="${UPDATED} ${name}"
}

# ── List / Check modes ───────────────────────────────────────────────────────
list_providers() {
    printf "\n${BOLD}Configured providers:${RESET}\n\n"
    printf "  ${DIM}%-12s %-8s %s${RESET}\n" "BINARY" "METHOD" "PACKAGE"
    echo "  ────────── ──────── ─────────────────────────────────"
    echo "$PROVIDER_DEFS" | sort | while IFS='|' read -r bin method pkg; do
        [ -z "$bin" ] && continue
        printf "  %-12s %-8s %s\n" "$bin" "$method" "$pkg"
    done
    echo ""
    exit 0
}

check_providers() {
    printf "\n${BOLD}Provider status:${RESET}\n\n"
    printf "  ${DIM}%-12s %-10s %-40s %s${RESET}\n" "BINARY" "STATUS" "PATH" "VERSION"
    echo "  ────────── ────────── ──────────────────────────────────────── ───────────────"
    echo "$PROVIDER_DEFS" | sort | while IFS='|' read -r bin method pkg; do
        [ -z "$bin" ] && continue
        local bin_path
        bin_path=$(get_bin_path "$bin")
        if [ -n "$bin_path" ]; then
            local ver
            ver=$(get_version "$bin")
            printf "  %-12s ${GREEN}%-10s${RESET} %-40s %s\n" "$bin" "installed" "$bin_path" "$ver"
        else
            printf "  %-12s ${RED}%-10s${RESET} %-40s %s\n" "$bin" "missing" "-" "-"
        fi
    done
    echo ""
    exit 0
}

# ── Parse args ────────────────────────────────────────────────────────────────
ONLY=""
while [ $# -gt 0 ]; do
    case "$1" in
        -n|--dry-run)  DRY_RUN=true; shift ;;
        -p|--parallel) PARALLEL=true; shift ;;
        -l|--list)     list_providers ;;
        -c|--check)    check_providers ;;
        -h|--help)     usage ;;
        -*)            echo "Unknown option: $1"; usage ;;
        *)             ONLY="${ONLY} $1"; shift ;;
    esac
done

# ── Main ──────────────────────────────────────────────────────────────────────
printf "\n${BOLD}🐍 hydra-heads provider updater${RESET}\n"
printf "${DIM}%s${RESET}\n" "$(date '+%Y-%m-%d %H:%M:%S')"
$DRY_RUN && printf "${YELLOW}(dry-run mode — no changes will be made)${RESET}\n"

# Build target list
targets=""
ONLY=$(echo "$ONLY" | xargs)  # trim
if [ -n "$ONLY" ]; then
    for name in $ONLY; do
        def=$(lookup_provider "$name")
        if [ -z "$def" ]; then
            log_fail "unknown provider: $name"
            log_dim "available: $(all_provider_names | tr '\n' ' ')"
            exit 1
        fi
        targets="${targets} ${name}"
    done
else
    targets=$(all_provider_names | tr '\n' ' ')
fi
targets=$(echo "$targets" | xargs)

count=$(echo "$targets" | wc -w | tr -d ' ')
printf "${DIM}Updating %s provider(s): %s${RESET}\n" "$count" "$targets"

if $PARALLEL; then
    log_info "Running updates in parallel..."
    pids=""
    for name in $targets; do
        update_provider "$name" &
        pids="${pids} $!"
    done
    for pid in $pids; do
        wait "$pid" || true
    done
else
    for name in $targets; do
        update_provider "$name" || true
    done
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
printf "${BOLD}━━━ Summary ━━━${RESET}\n"
UPDATED=$(echo "$UPDATED" | xargs)
SKIPPED=$(echo "$SKIPPED" | xargs)
FAILED=$(echo "$FAILED" | xargs)
[ -n "$UPDATED" ] && printf "  ${GREEN}✓ Updated:${RESET} %s\n" "$UPDATED"
[ -n "$SKIPPED" ] && printf "  ${YELLOW}○ Skipped:${RESET} %s\n" "$SKIPPED"
[ -n "$FAILED" ]  && printf "  ${RED}✗ Failed:${RESET}  %s\n" "$FAILED"
echo ""

# Exit non-zero if anything failed
[ -z "$FAILED" ]
