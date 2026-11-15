#!/usr/bin/env bash
# Regenerates every pack asset, publishes the pack to pack-dist and points
# packUrl() in tc/pack.tc at it.
set -euo pipefail
cd "$(dirname "$0")/.."
for g in pack/src/character.py pack/src/anim_clips.py pack/src/weapons.py pack/src/ui.py; do
    [ -f "$g" ] && (cd pack/src && python3 "$(basename "$g")")
done
url=$(python3 tools/build_pack.py --publish --push | tee /dev/stderr | sed -n 's/^url: //p')
[ -n "$url" ] || { echo "no url" >&2; exit 1; }
sed -i -E "s#return \"[^\"]*\";( // pack url)?#return \"$url\"; // pack url#" tc/pack.tc
echo "packUrl -> $url"
