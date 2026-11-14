#!/usr/bin/env bash
# Paradev Run button: starts the Next.js dev server for this workspace.
# If port 3000 is taken by another workspace, Next.js picks the next free
# port and prints it, so several workspaces can preview at once.
set -euo pipefail
if [ ! -f app/package.json ]; then
  echo "No app yet (app/package.json is missing). Theo scaffolds it in T09."
  exit 0
fi
cd app
if [ -f pnpm-lock.yaml ]; then exec pnpm dev
elif [ -f bun.lockb ] || [ -f bun.lock ]; then exec bun run dev
elif [ -f yarn.lock ]; then exec yarn dev
else exec npm run dev
fi
