#!/usr/bin/env bash
# Launcher script for Shroudbyte
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
exec python3 -m browser "$@"
