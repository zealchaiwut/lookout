#!/bin/bash
# Install the lookout launchd jobs for the clone this script lives in.
#
# The plists under launchd/ are templates: they carry __REPO_ROOT__ and
# __PYTHON__ placeholders which are substituted here. Nothing is hardcoded to a
# particular user or machine, so this works from any clone on any Mac.
#
# Idempotent: safe to run repeatedly.
#
# Usage:
#   scripts/install.sh                 # nightly sweep only
#   scripts/install.sh --with-digest   # also the weekly Notion digest
#   scripts/install.sh --uninstall     # remove both jobs
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
AGENTS_DIR="$HOME/Library/LaunchAgents"

ALL_LABEL="com.zealchaiwut.lookout-all"
DIGEST_LABEL="com.zealchaiwut.lookout-digest"

WITH_DIGEST=0
UNINSTALL=0
for arg in "$@"; do
    case "$arg" in
        --with-digest) WITH_DIGEST=1 ;;
        --uninstall)   UNINSTALL=1 ;;
        *) echo "Unknown option: $arg" >&2; exit 2 ;;
    esac
done

unload_job() {
    launchctl bootout "gui/$(id -u)/$1" 2>/dev/null || true
}

if [ "$UNINSTALL" -eq 1 ]; then
    for label in "$ALL_LABEL" "$DIGEST_LABEL"; do
        unload_job "$label"
        rm -f "$AGENTS_DIR/$label.plist"
        echo "Removed: $label"
    done
    exit 0
fi

# Prefer the clone's own venv so the job does not depend on whatever python3
# happens to be first on launchd's minimal PATH.
if [ -x "$REPO_ROOT/venv/bin/python" ]; then
    PYTHON="$REPO_ROOT/venv/bin/python"
else
    PYTHON="$(command -v python3 || true)"
fi

if [ -z "$PYTHON" ]; then
    echo "ERROR: no python3 found on PATH and no venv at $REPO_ROOT/venv" >&2
    exit 1
fi

# Fail now rather than at 06:15 tomorrow.
if ! "$PYTHON" -c 'import yaml, requests' 2>/dev/null; then
    echo "ERROR: $PYTHON is missing required modules (pyyaml, requests)." >&2
    echo "       Install them, or create a venv at $REPO_ROOT/venv." >&2
    exit 1
fi

# launchd starts jobs with PATH=/usr/bin:/bin:/usr/sbin:/sbin. `git` survives
# that via the /usr/bin shim, but `gh` and `claude` typically live in
# /opt/homebrew/bin or ~/.local/bin. Without them a run collects no GitHub
# issues and silently skips every LLM call while still reporting success — so
# resolve them here and bake their directories into the job's PATH.
JOB_PATH_DIRS=()
for tool in gh git claude; do
    resolved="$(command -v "$tool" 2>/dev/null || true)"
    if [ -n "$resolved" ]; then
        JOB_PATH_DIRS+=("$(dirname "$resolved")")
    else
        echo "WARNING: '$tool' not found on PATH."
        case "$tool" in
            gh)     echo "         The job will collect no GitHub issues or PRs." ;;
            claude) echo "         LLM enrichment will fall back to deterministic output." ;;
            git)    echo "         The job cannot commit snapshots." ;;
        esac
    fi
done
JOB_PATH_DIRS+=("$(dirname "$PYTHON")" /usr/local/bin /opt/homebrew/bin /usr/bin /bin /usr/sbin /sbin)

# Deduplicate, preserving order.
JOB_PATH=""
for dir in "${JOB_PATH_DIRS[@]}"; do
    case ":$JOB_PATH:" in
        *":$dir:"*) ;;
        *) JOB_PATH="${JOB_PATH:+$JOB_PATH:}$dir" ;;
    esac
done

if [ ! -f "$REPO_ROOT/.env" ]; then
    echo "WARNING: $REPO_ROOT/.env not found."
    echo "         Create it with GITHUB_TOKEN / NOTION_TOKEN before the job runs."
    echo "         Add LOOKOUT_LLM=1 there to enable model-backed enrichment."
fi

mkdir -p "$REPO_ROOT/logs" "$AGENTS_DIR"

install_job() {
    local label="$1"
    local template="$REPO_ROOT/launchd/$label.plist.template"
    local dest="$AGENTS_DIR/$label.plist"

    if [ ! -f "$template" ]; then
        echo "ERROR: template not found: $template" >&2
        exit 1
    fi

    sed -e "s|__REPO_ROOT__|$REPO_ROOT|g" \
        -e "s|__PYTHON__|$PYTHON|g" \
        -e "s|__PATH__|$JOB_PATH|g" \
        "$template" > "$dest"

    if grep -q '__[A-Z_]*__' "$dest"; then
        echo "ERROR: unsubstituted placeholder left in $dest" >&2
        grep -o '__[A-Z_]*__' "$dest" | sort -u >&2
        rm -f "$dest"
        exit 1
    fi

    plutil -lint "$dest" >/dev/null

    unload_job "$label"
    launchctl bootstrap "gui/$(id -u)" "$dest"
    echo "Installed and loaded: $label"
}

install_job "$ALL_LABEL"
[ "$WITH_DIGEST" -eq 1 ] && install_job "$DIGEST_LABEL"

echo ""
echo "Repo root:   $REPO_ROOT"
echo "Interpreter: $PYTHON"
echo ""
echo "Verify:       launchctl list | grep lookout"
echo "Run now:      launchctl kickstart -k gui/$(id -u)/$ALL_LABEL"
echo "Manual run:   $REPO_ROOT/bin/lookout --all"
echo "Logs:         $REPO_ROOT/logs/lookout-all.log"
echo "Release lock: rmdir /tmp/lookout-all.lock"
echo "Uninstall:    scripts/install.sh --uninstall"
