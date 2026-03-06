#!/bin/sh
set -e

# The /content volume may be created by Docker as root on a fresh host.
# Fix ownership so appuser can write index.html, then drop privileges.
chown -R appuser:appgroup /content

exec su-exec appuser python generate.py
