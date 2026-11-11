#!/usr/bin/env sh
# Thin wrapper so the add-on works without remembering the interpreter.
set -eu
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 -u "$DIR/install.py" "$@"
