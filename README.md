# IPL Pulse 2026 — Local Testing & GitHub Pages

This repository contains the automated podcast generator and a static Next.js dashboard optimized for GitHub Pages.

## Prerequisites

- Node 18+ with `pnpm` (via Corepack)
- Python 3.10+ with `pip`

## Dashboard (static export)

```bash
corepack enable
pnpm install
pnpm build
# static site is generated in ./out
```

Preview static output:

```bash
npx serve out
```

## Podcast generator (Python)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/generate_podcast.py
```

## GitHub Pages deployment

- Push to `main`.
- Workflow [`.github/workflows/deploy_pages.yml`](.github/workflows/deploy_pages.yml) builds and deploys `out/`.

## Environment

Copy `.env.example` to `.env` (local only; never commit secrets).

- `GOOGLE_API_KEY`: Gemini 3 Flash key (Google AI Studio) — primary model.
- `OPENROUTER_API_KEY`: fallback OpenRouter key (optional).
- `NEXT_PUBLIC_GITHUB_REPO`: `owner/repo` for the dashboard trigger link.
