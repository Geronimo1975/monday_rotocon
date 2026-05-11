# monday_rotocon

Typed monday.com client and dashboard-export CLI for ROTOCON Europe GmbH.
Implements sub-project A of the digital-transformation roadmap; spec at
`docs/superpowers/specs/2026-05-10-monday-core-skeleton-design.md`.

## Quickstart

```bash
# 1. Copy the env template and add your monday API token.
cp .env.example .env
# edit .env — set MONDAY_API_TOKEN

# 2. Install dependencies into a project-local venv.
uv sync --all-extras

# 3. Verify connectivity.
uv run monday ping
```

See the spec and `docs/superpowers/plans/` for design and implementation
detail.
