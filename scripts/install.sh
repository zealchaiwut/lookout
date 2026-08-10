#!/bin/bash
# Install the lookout --all launchd job on zeal-server.
# Idempotent: safe to run multiple times.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PLIST_SRC="$REPO_ROOT/launchd/com.zealchaiwut.lookout-all.plist"
PLIST_LABEL="com.zealchaiwut.lookout-all"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_LABEL.plist"
LOG_DIR="$HOME/dev/lookout/logs"

# Ensure .env exists (tokens must be set before the job runs)
ENV_FILE="$HOME/dev/lookout/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "WARNING: $ENV_FILE not found. Create it with GITHUB_TOKEN and NOTION_TOKEN before the job runs."
fi

# Create log directory if needed
mkdir -p "$LOG_DIR"

# Copy plist into LaunchAgents
cp "$PLIST_SRC" "$PLIST_DEST"
echo "Installed plist: $PLIST_DEST"

# Bootout any existing job (idempotent — ignore error if not loaded)
launchctl bootout "gui/$(id -u)/$PLIST_LABEL" 2>/dev/null || true

# Bootstrap (load) the job
launchctl bootstrap "gui/$(id -u)" "$PLIST_DEST"
echo "Loaded: $PLIST_LABEL"
echo ""
echo "Verify with: launchctl list | grep lookout"
echo "Manual run:  $REPO_ROOT/bin/lookout --all"
echo "Release lock: rmdir /tmp/lookout-all.lock"
