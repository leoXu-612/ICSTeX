#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$ROOT_DIR/build/source-archive"
DIST_DIR="$ROOT_DIR/dist"
APP_VERSION="$(python3 -c 'from app import __version__; print(__version__)')"
ARCHIVE_NAME="ICSTeX-Source-$APP_VERSION"
STAGE_DIR="$BUILD_DIR/$ARCHIVE_NAME"
ARCHIVE_PATH="$DIST_DIR/$ARCHIVE_NAME.zip"

cd "$ROOT_DIR"
rm -rf "$BUILD_DIR"
mkdir -p "$STAGE_DIR" "$DIST_DIR"

for directory in app tests packaging tools website docs; do
  mkdir -p "$STAGE_DIR/$directory"
  rsync -a \
    --exclude '.DS_Store' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '.env' \
    --exclude '.env.*' \
    --exclude '*.pem' \
    --exclude '*.key' \
    --exclude 'credentials.json' \
    --exclude 'release.json' \
    "$ROOT_DIR/$directory/" \
    "$STAGE_DIR/$directory/"
done

# Human-readable release documents are useful to source-build users, but the
# generated manifest and website/release.json are excluded: putting a source
# ZIP's own SHA-256 inside that ZIP would make the artifact self-referential.
mkdir -p "$STAGE_DIR/release"
for file in release/*.md release/*-verification.txt; do
  [[ -f "$ROOT_DIR/$file" ]] && cp "$ROOT_DIR/$file" "$STAGE_DIR/$file"
done

for file in README.md CHANGELOG.md CLAUDE.md FORCODEX.md pyproject.toml requirements.txt requirements-packaging.txt; do
  cp "$ROOT_DIR/$file" "$STAGE_DIR/$file"
done

find "$STAGE_DIR" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$STAGE_DIR" -type f \( -name '*.pyc' -o -name '.DS_Store' \) -delete

if grep -RIlE '(/Users/[l]eo\.xu|C:\\Users\\[l]eo|file:///Users/[l]eo\.xu)' "$STAGE_DIR" >/dev/null; then
  echo "Source archive rejected: local absolute path found" >&2
  exit 1
fi

rm -f "$ARCHIVE_PATH"
(
  cd "$BUILD_DIR"
  /usr/bin/zip -qryX "$ARCHIVE_PATH" "$ARCHIVE_NAME"
)

/usr/bin/unzip -tq "$ARCHIVE_PATH" >/dev/null

echo "Built $ARCHIVE_PATH"
du -h "$ARCHIVE_PATH"
