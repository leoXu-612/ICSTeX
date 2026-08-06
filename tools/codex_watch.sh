#!/usr/bin/env bash
# Codex collaboration watcher.
# Run repeatedly (Claude drives it via /loop). Each run compares the current
# tree against the last snapshot and reports what changed:
#   - source (.py under app/ tests/) changed -> run compileall + unittest
#   - handoff docs changed -> Codex likely left a new message, flag it
# Content-hash based, so a plain `touch` or our own save echo is ignored.
# ponytail: shasum snapshot, swap to git if this ever becomes a real repo.
set -uo pipefail
cd "$(dirname "$0")/.."
STATE=".codex_watch_state"

# macOS does not provide the C.UTF-8 locale inherited by some agent shells.
# Perl-backed shasum fails under that locale, so normalize it before hashing.
unset LC_ALL LC_CTYPE
export LANG=en_US.UTF-8

src_hash() {
  find app tests -type f -name '*.py' -not -path '*/__pycache__/*' 2>/dev/null \
    | sort | xargs shasum 2>/dev/null | shasum | awk '{print $1}'
}
doc_hash() {
  shasum FORCODEX.md MEMORY.md DEARCLAUDE.md FORCLAUDE.md CHANGELOG.md 2>/dev/null \
    | shasum | awk '{print $1}'
}

cur_src=$(src_hash); cur_doc=$(doc_hash)
prev_src=""; prev_doc=""
[ -f "$STATE" ] && read -r prev_src prev_doc < "$STATE"
echo "$cur_src $cur_doc" > "$STATE"

if [ -z "$prev_src" ]; then
  echo "WATCH: baseline snapshot taken, no comparison yet."
  exit 0
fi

changed=0
if [ "$cur_doc" != "$prev_doc" ]; then
  echo "WATCH: handoff docs changed -> Codex may have left a new message. Re-read FORCODEX.md / MEMORY.md."
  changed=1
fi
if [ "$cur_src" != "$prev_src" ]; then
  echo "WATCH: source changed -> running checks..."
  if python3 -m compileall -q app tests && python3 -m unittest discover -s tests 2>&1 | tail -4; then
    echo "WATCH: checks PASSED."
  else
    echo "WATCH: checks FAILED -- see output above."
  fi
  changed=1
fi
[ "$changed" -eq 0 ] && echo "WATCH: no source/handoff change."
exit 0
