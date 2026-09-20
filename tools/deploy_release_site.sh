#!/usr/bin/env bash
# Prepare a GitHub Pages worktree locally. Pushing is a separate guarded action.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
SITE_DIR="$ROOT/website"

usage() {
  cat <<'EOF'
Usage:
  bash tools/deploy_release_site.sh --prepare
  ICSTEX_RELEASE_SITE_WORKTREE=/absolute/path ICSTEX_RELEASE_SITE_PUSH=1 \
    bash tools/deploy_release_site.sh --push

--prepare creates or refreshes a local gh-pages worktree and commits only the
checked-in static website. It never contacts a remote. --push is intentionally
guarded because it changes the public GitHub Pages state.
EOF
}

prepare() {
  if ! git -C "$ROOT" diff --quiet || ! git -C "$ROOT" diff --cached --quiet; then
    echo "Refusing to prepare Pages from a dirty worktree. Commit or stash unrelated changes first." >&2
    exit 1
  fi
  python3 "$ROOT/tools/release_prepare.py" --check
  [[ -f "$SITE_DIR/index.html" && -f "$SITE_DIR/release.json" ]] || { echo "website source is incomplete" >&2; exit 1; }

  local stamp worktree
  stamp="$(date +%Y%m%dT%H%M%S)"
  worktree="${ICSTEX_RELEASE_SITE_WORKTREE:-${TMPDIR:-/tmp}/icstex-gh-pages-$stamp}"
  [[ ! -e "$worktree" ]] || { echo "worktree path already exists: $worktree" >&2; exit 1; }

  if git -C "$ROOT" show-ref --verify --quiet refs/heads/gh-pages; then
    git -C "$ROOT" worktree add "$worktree" gh-pages
    git -C "$worktree" rm -rf --ignore-unmatch .
  else
    git -C "$ROOT" worktree add --detach "$worktree" HEAD
    git -C "$worktree" checkout --orphan gh-pages
    git -C "$worktree" rm -rf --ignore-unmatch .
  fi

  find "$worktree" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
  cp -R "$SITE_DIR/." "$worktree/"
  git -C "$worktree" add --all
  if ! git -C "$worktree" diff --cached --quiet; then
    git -C "$worktree" commit -m "website: publish ICSTeX release site"
  fi

  printf 'Prepared local Pages worktree: %s\n' "$worktree"
  printf 'Review: git -C %q log -1 --stat\n' "$worktree"
  printf 'After explicit publication approval: ICSTEX_RELEASE_SITE_WORKTREE=%q ICSTEX_RELEASE_SITE_PUSH=1 bash tools/deploy_release_site.sh --push\n' "$worktree"
}

push_pages() {
  local worktree="${ICSTEX_RELEASE_SITE_WORKTREE:-}"
  [[ "${ICSTEX_RELEASE_SITE_PUSH:-}" == "1" ]] || {
    echo "Refusing remote push. Set ICSTEX_RELEASE_SITE_PUSH=1 only after explicit approval." >&2
    exit 1
  }
  [[ -n "$worktree" && -e "$worktree/.git" ]] || {
    echo "Set ICSTEX_RELEASE_SITE_WORKTREE to the prepared worktree path." >&2
    exit 1
  }
  [[ -z "$(git -C "$worktree" status --porcelain)" ]] || {
    echo "Refusing to push a dirty Pages worktree." >&2
    exit 1
  }
  git -C "$worktree" push origin gh-pages
}

case "${1:-}" in
  --prepare) prepare ;;
  --push) push_pages ;;
  *) usage; exit 2 ;;
esac
