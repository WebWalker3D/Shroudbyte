#!/usr/bin/env bash
# Extract translatable strings into locale/shroudbyte.pot
#
# Requires: xgettext (part of gettext).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOCALE_DIR="$PROJECT_DIR/locale"
POT="$LOCALE_DIR/shroudbyte.pot"

if ! command -v xgettext >/dev/null 2>&1; then
    echo "ERROR: xgettext not found. Install the 'gettext' package." >&2
    exit 1
fi

mkdir -p "$LOCALE_DIR"

cd "$PROJECT_DIR"
find browser -name '*.py' -print0 \
  | xargs -0 xgettext \
        --language=Python \
        --keyword=_ \
        --keyword=gettext_ \
        --from-code=UTF-8 \
        --package-name=Shroudbyte \
        --copyright-holder="WebWalker3D" \
        --msgid-bugs-address="" \
        --output="$POT"

echo "Wrote $POT"
echo ""
echo "To start a new translation (e.g. French):"
echo "  msginit --input=$POT --locale=fr --output=$LOCALE_DIR/fr/LC_MESSAGES/shroudbyte.po"
echo ""
echo "To compile a .po file into a .mo:"
echo "  msgfmt $LOCALE_DIR/fr/LC_MESSAGES/shroudbyte.po -o $LOCALE_DIR/fr/LC_MESSAGES/shroudbyte.mo"
