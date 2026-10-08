#!/bin/sh
set -e

# The /content volume may be created by Docker as root on a fresh host.
# Fix ownership so appuser can write index.html, then drop privileges.
# -h changes symlinks themselves, never the files they point at
chown -R -h appuser:appgroup /content

exec su-exec appuser python generate.py
