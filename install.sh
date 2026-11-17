#!/usr/bin/env sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if command -v python3 >/dev/null 2>&1; then
  python_cmd=python3
elif command -v python >/dev/null 2>&1; then
  python_cmd=python
else
  echo 'Python 3.10+ is required. Install Python and retry.' >&2
  exit 1
fi

# Preserve ./install.sh <skill> while also accepting the shared CLI options.
case "${1:-}" in
  ''|-*) ;;
  *) skill=$1; shift; set -- --skill "$skill" "$@" ;;
esac
exec "$python_cmd" "$repo_root/scripts/install.py" "$@"
