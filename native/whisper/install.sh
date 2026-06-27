#!/usr/bin/env bash
# Install the native MLX-Whisper Wyoming server as a macOS LaunchAgent.
#
# Why not run straight from the repo? macOS TCC blocks launchd from executing
# files under ~/Desktop, ~/Documents, ~/Downloads ("Operation not permitted").
# So we deploy the runtime to ~/Library/Application Support (not protected) and
# point the LaunchAgent there. The repo stays the source of truth.
#
# Usage: native/whisper/install.sh [model] [uri]
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
APP="$HOME/Library/Application Support/jarvis-whisper"
PLIST="$HOME/Library/LaunchAgents/com.jarvis.whisper.plist"
MODEL="${1:-mlx-community/whisper-medium.en-mlx}"
URI="${2:-tcp://0.0.0.0:10301}"

echo "Deploying to: $APP"
mkdir -p "$APP"
cp "$SRC/wyoming_mlx_whisper.py" "$SRC/requirements.txt" "$APP/"

if [ ! -d "$APP/.venv" ]; then
  python3 -m venv "$APP/.venv"
fi
"$APP/.venv/bin/pip" install --quiet --upgrade pip
"$APP/.venv/bin/pip" install --quiet -r "$APP/requirements.txt"

echo "Writing LaunchAgent: $PLIST"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>com.jarvis.whisper</string>
    <key>ProgramArguments</key>
    <array>
      <string>$APP/.venv/bin/python</string>
      <string>$APP/wyoming_mlx_whisper.py</string>
      <string>--uri</string>
      <string>$URI</string>
      <string>--model</string>
      <string>$MODEL</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/jarvis-whisper.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/jarvis-whisper.log</string>
  </dict>
</plist>
EOF

# Modern launchctl: bootout any existing instance, then bootstrap (plain `load`
# silently no-ops on recent macOS).
launchctl bootout "gui/$(id -u)/com.jarvis.whisper" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

echo "Loaded. Model: $MODEL on $URI"
echo "Logs: /tmp/jarvis-whisper.log   (first start downloads the model)"
echo "Manage: launchctl unload/load -w $PLIST"
