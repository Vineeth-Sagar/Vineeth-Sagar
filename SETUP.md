# Profile README — Setup Guide

## 0. Final folder layout

```
Vineeth-Sagar/                 <- repo name MUST equal your username
├── README.md
├── assets/
│   └── hero.gif                <- your animated banner
└── .github/
    └── workflows/
        └── snake.yml
```

## 1. Create the special repo

1. GitHub → **New repository**
2. Repository name: **exactly your username** (e.g. `Vineeth-Sagar`)
3. Visibility: **Public** (required — the README won't render otherwise)
4. Tick **Add a README file**
5. Create.

GitHub shows a "✨ You found a secret!" note — that confirms it's the profile repo.

## 2. Push these files

```bash
git clone https://github.com/Vineeth-Sagar/Vineeth-Sagar.git
```

Copy `README.md`, `assets/`, and `.github/` into the clone, then:

```bash
git add . && git commit -m "feat: profile readme" && git push
```

## 3. The hero portrait

The banner is `assets/portrait.svg` — a dot-matrix rendering generated from a photo
by `scripts/dotify.py`. It has a transparent background, so one file serves both
GitHub themes.

To regenerate from a different photo:

```bash
python scripts/dotify.py assets/source.jpg -o assets/portrait --cols 92 --detail 0.30 --min-r 2.2 --equalize --color --crop 240,120,790,665
```

- `--crop L,T,R,B` — pixel box around the head and shoulders. Adjust per photo.
- `--min-r` — smallest dot drawn. Raise it to erase a pale background, lower it
  to keep the full-frame LED texture.
- `--cols` — grid resolution. Higher is finer but the SVG grows fast.
- Drop `--color` for a monochrome neon portrait (`--mono-color '#52FF78'`).

`assets/source.jpg` is **gitignored** — the raw photo stays on your machine and only
the derived SVG is published. Keep a copy locally if you want to re-run the script.

## 4. Enable Actions write permissions (required for the snake)

Repo → **Settings** → **Actions** → **General** → *Workflow permissions*
→ select **Read and write permissions** → **Save**.

Without this the `output` branch push fails with `403`.

## 5. First snake run

Repo → **Actions** tab → **Generate Contribution Snake** → **Run workflow**.

After ~40 s it creates an orphan branch `output` containing:

- `github-contribution-grid-snake.svg` (light)
- `github-contribution-grid-snake-dark.svg` (dark, neon `#52FF78` snake)
- `github-contribution-grid-snake.gif`

The README's `<picture>` block reads those raw URLs and auto-switches with the viewer's theme. It runs daily at 00:00 UTC from then on.

> If the images 404 for a few minutes, that's the `raw.githubusercontent.com` CDN cache — it clears on its own.

## 6. Links wired in

Everything is filled in — no placeholders remain in `README.md`.

| Item | Value |
|---|---|
| GitHub | `Vineeth-Sagar` |
| Email | `vineethsagarhl0@gmail.com` |
| LinkedIn | `linkedin.com/in/vineeth-sagar-h-l` |
| Portfolio | `www.vineethsagar.co.in` |
| LeetCode | `leetcode.com/vineethQuinz` |
| Discord | user ID `1489321223497191425` |

Codeforces and Docker Hub badges were removed — add them back if you create accounts.

## 7. Notes on the third-party widgets

All image hosts used in the README were checked and return HTTP 200. Three popular
ones are **currently down for everyone** and are deliberately NOT used:

| Host | Status | Used instead |
|---|---|---|
| `github-readme-stats.vercel.app` | 503 | `github-profile-summary-cards.vercel.app` |
| `github-readme-activity-graph.vercel.app` | 402 (Vercel over quota) | `ghchart.rshah.org` |
| `github-profile-trophy.vercel.app` | 402 | `github-trophies.vercel.app` (mirror) |
| `visitcount.itsvg.in` | 404 | `komarev.com` |

These are free community deployments, so any of them can go down again. The durable
fix for the stats cards is to self-host: fork
[anuraghazra/github-readme-stats](https://github.com/anuraghazra/github-readme-stats),
deploy it to your own Vercel account, and point the URLs at
`https://<your-app>.vercel.app/api?...`.

- **Private commits** only count if you also enable
  *Settings → Profile → Include private contributions on my profile*.
- Skill icons: full slug list at [skillicons.dev](https://skillicons.dev) — edit the
  `i=` parameter to add or remove icons.
