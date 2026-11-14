#!/usr/bin/env bash
# Paradev setup script. Runs once, in the new worktree's root, each time a
# workspace is created. It gives the new checkout the git-ignored things a
# fresh worktree is missing, so an agent can start work straight away.
set -euo pipefail

ROOT="${SUPERSET_ROOT_PATH:-}"
WT="${SUPERSET_WORKSPACE_PATH:-$PWD}"
cd "$WT"
echo "== Handover workspace setup: ${SUPERSET_WORKSPACE_NAME:-$(basename "$WT")}"

# 1. Keep local-only files out of git in every worktree, even before the
#    repo's .gitignore exists. info/exclude is shared by all worktrees and is
#    never committed. No trailing slash on synthea_raw, so the symlink made
#    below is excluded too (a symlink is a file to git, not a folder).
EXCLUDE="$(git rev-parse --git-common-dir)/info/exclude"
mkdir -p "$(dirname "$EXCLUDE")"
for p in .env pipeline/data/synthea_raw .venv app/node_modules app/.next; do
  grep -qxF "$p" "$EXCLUDE" 2>/dev/null || echo "$p" >> "$EXCLUDE"
done

if [ -n "$ROOT" ] && [ "$ROOT" != "$WT" ]; then
  # 2. Copy the API key file from the main checkout. Copied, not linked,
  #    so an agent editing it can't change the main one.
  if [ -f "$ROOT/.env" ] && [ ! -e .env ]; then
    cp "$ROOT/.env" .env && echo "-- copied .env from the main checkout"
  elif [ ! -f "$ROOT/.env" ]; then
    echo "-- no .env in the main checkout yet (fine until the pipeline calls the API)"
  fi

  # 3. Link the Synthea download (large, read-only, never committed) instead
  #    of copying it into every worktree.
  if [ -d "$ROOT/pipeline/data/synthea_raw" ] && [ ! -e pipeline/data/synthea_raw ]; then
    mkdir -p pipeline/data
    ln -s "$ROOT/pipeline/data/synthea_raw" pipeline/data/synthea_raw
    echo "-- linked pipeline/data/synthea_raw to the main checkout"
  fi
else
  echo "-- running in the main checkout, nothing to copy"
fi

# 4. Python: a separate .venv per worktree, so one agent adding a package
#    can't break another agent's environment. The pipeline needs Python 3.11+
#    (pandas 3 won't install on the Mac's built-in 3.9), so pick a new enough one.
if [ -f pipeline/requirements.txt ]; then
  echo "-- installing pipeline/requirements.txt into .venv"
  if command -v uv >/dev/null 2>&1; then
    [ -d .venv ] || uv venv -q --python ">=3.11" .venv
    uv pip install -q --python .venv/bin/python -r pipeline/requirements.txt
  else
    PY=""
    for c in python3.13 python3.12 python3.11 /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3.11 python3; do
      if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then PY="$c"; break; fi
    done
    if [ -z "$PY" ]; then
      echo "!! No Python 3.11 or newer found. Install it with: brew install python@3.12" >&2
      exit 1
    fi
    [ -d .venv ] || "$PY" -m venv .venv
    .venv/bin/pip install -q -r pipeline/requirements.txt
  fi
fi

# 5. Node: install the app's packages with whichever tool its lockfile uses,
#    so `npm run build` works before pushing (a push to main goes live).
if [ -f app/package.json ]; then
  echo "-- installing app/ packages"
  cd app
  if   [ -f pnpm-lock.yaml ];    then pnpm install --frozen-lockfile
  elif [ -f yarn.lock ];         then yarn install --frozen-lockfile
  elif [ -f bun.lockb ] || [ -f bun.lock ]; then bun install --frozen-lockfile
  elif [ -f package-lock.json ]; then npm ci
  # No lockfile yet: install without writing one, so the worktree stays clean.
  else npm install --no-save --package-lock=false
  fi
  cd "$WT"
fi

echo "== setup done"
