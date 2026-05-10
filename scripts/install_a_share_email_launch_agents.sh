#!/bin/zsh
set -euo pipefail

PROJECT_ROOT="/Users/wuzehe/Documents/New project"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
USER_ID="$(id -u)"

mkdir -p "$LAUNCH_AGENTS_DIR"
mkdir -p "$PROJECT_ROOT/logs"

chmod +x "$PROJECT_ROOT/scripts/send_scheduled_a_share_report.sh"

for plist in \
  com.codex.ashare.premarket.email.plist \
  com.codex.ashare.aftermarket.email.plist
do
  src="$PROJECT_ROOT/launchd/$plist"
  dst="$LAUNCH_AGENTS_DIR/$plist"
  label="${plist%.plist}"

  plutil -lint "$src" >/dev/null
  cp "$src" "$dst"

  launchctl bootout "gui/$USER_ID" "$dst" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$USER_ID" "$dst"
  launchctl enable "gui/$USER_ID/$label"

  echo "Installed $label"
done

echo "Done. Premarket email runs on weekdays at 08:45; aftermarket email runs on weekdays at 16:45."
