# AGENTS.md

Instructions for AI coding agents working in this repository.

## Project

Veritas AI Hackathon project. See `README.md` for the team and project name.

The stack, build commands, and test commands are not set up yet. Update this file once they are decided.

## Working Conventions

- Keep changes small and scoped to the request.
- Before coding a new feature, check whether an existing library already covers it.
- Never commit secrets (API keys, tokens, `.env` files). Use environment variables and add a `.env.example` if config is needed.
- Run the project's build and tests before reporting work as done. If none exist yet, say so.

## Git

- The team's git rules are in `CLAUDE.md` on `origin/main`. Follow them: work on `main`, do not create branches or pull requests unless asked, and start each commit message with the task ID (for example `T23: add dose-change rule`).
- Keep commits focused: one logical change per commit.

## Open Items

- [ ] Add the tech stack and how to run the app
- [ ] Add build, test, and lint commands
- [ ] Add the deployment target, if any
