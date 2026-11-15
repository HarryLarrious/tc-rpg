#!/usr/bin/env bash
# Drives the Minecraft client for testing.
#   tools/mc.sh say "@cmd args"     type a chat command
#   tools/mc.sh hold KEY SECONDS    hold a key
#   tools/mc.sh log [N] [PATTERN]   last N chat lines (matching PATTERN)
#   tools/mc.sh shot FILE           screenshot of the game monitor
set -euo pipefail
LOG="$HOME/.var/app/org.prismlauncher.PrismLauncher/data/PrismLauncher/instances/26.3/minecraft/logs/latest.log"
win() { xdotool search --name "Minecraft" | head -1; }
focus() { xdotool windowactivate --sync "$(win)" 2>/dev/null || true; sleep 0.15; }
case "$1" in
  say) focus; xdotool key t; sleep 0.25; xdotool type --delay 8 "$2"; sleep 0.1; xdotool key Return ;;
  hold) focus; xdotool keydown "$2"; sleep "$3"; xdotool keyup "$2" ;;
  key) focus; xdotool key "$2" ;;
  shot) python3 -c "
import mss, mss.tools, sys
with mss.mss() as m:
    x, y, w, h = [int(v) for v in sys.argv[2].split(',')]
    img = m.grab({'left': x, 'top': y, 'width': w, 'height': h})
    mss.tools.to_png(img.rgb, img.size, output=sys.argv[1])
" "$2" "${3:-0,0,2560,1440}" ;;
  log) grep -a "CHAT" "$LOG" | grep -a -- "${3:-.}" | tail -"${2:-10}" | cut -c1-400 ;;
  *) echo "usage"; exit 1 ;;
esac
