#!/bin/sh
# Installs (or reinstalls) the launchd job that writes the weekly reading report every Monday at 8:00,
# to ~/Documents/marrydavid-analytics/, opens it, and shows a notification. Run once from the repo root:
#     sh analytics/install-weekly.sh
# Remove with:  launchctl bootout gui/$(id -u)/com.marrydavid.analytics-weekly
set -e
REPO="$(cd "$(dirname "$0")/.." && pwd)"
LABEL=com.marrydavid.analytics-weekly
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
OUT="$HOME/Documents/marrydavid-analytics"
PY="$(command -v python3)"
GCLOUD_BIN="$(dirname "$(command -v gcloud)")"
mkdir -p "$OUT" "$HOME/Library/Logs"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY</string>
    <string>$REPO/analytics/weekly.py</string>
    <string>--out</string>
    <string>$OUT</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>8</integer><key>Minute</key><integer>0</integer></dict>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>$GCLOUD_BIN:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string></dict>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/$LABEL.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/$LABEL.log</string>
</dict>
</plist>
EOF
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "installed $LABEL: Mondays 08:00 -> $OUT (log: ~/Library/Logs/$LABEL.log)"
