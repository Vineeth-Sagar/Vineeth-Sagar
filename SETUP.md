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

## 3. The hero GIF

- Put the banner at `assets/hero.gif`. Keep it **under ~5 MB** — GitHub proxies images through Camo and large GIFs get slow or dropped.
- Recommended: ~1200×300 px, transparent or `#0D1117` background so it blends with dark mode.
- The `<img src="assets/hero.gif">` relative path works because the README lives in the same repo. If you'd rather host it elsewhere, swap in the full `https://raw.githubusercontent.com/Vineeth-Sagar/Vineeth-Sagar/main/assets/hero.gif` URL.

Making one: export a short loop from Figma/After Effects, or run a photo through a halftone/dither filter (`ImageMagick -ordered-dither`, or ezgif.com's effects) and loop it.

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

## 6. Swap checklist

| Placeholder | Replace with | Status |
|---|---|---|
| `Vineeth-Sagar` | your GitHub username | ✅ done |
| LinkedIn | `linkedin.com/in/vineeth-sagar-h-l` | ✅ done |
| Portfolio | `https://vineethsgar.co.in` | ✅ done (domain not resolving yet) |
| Pinned repos | `prompt-security-framework`, `RAG-Ai-bot` | ✅ done |
| `YOUR_EMAIL` | public email | ⬜ 3 places |
| `YOUR_LEETCODE` | LeetCode handle, or delete the badge | ⬜ 1 |
| `YOUR_CODEFORCES` | Codeforces handle, or delete the badge | ⬜ 1 |
| `YOUR_DISCORD_ID` | Discord numeric user ID, or delete | ⬜ 1 |
| `YOUR_DOCKERHUB` | Docker Hub username, or delete | ⬜ 1 |

Fill the email in one shot:

```bash
sed -i 's/YOUR_EMAIL/you@example.com/g' README.md
```

## 7. Notes on the third-party widgets

- **`github-readme-stats`** is on a shared Vercel instance and rate-limits during peak hours (card shows "Maximum retries exceeded"). Fix: fork [anuraghazra/github-readme-stats](https://github.com/anuraghazra/github-readme-stats), deploy to your own Vercel, and point the URLs at `https://<your-app>.vercel.app/api?...`.
- **Private commits** only count if you also enable *Settings → Profile → Include private contributions on my profile*.
- **`streak-stats.demolab.com`** and **`github-readme-activity-graph.vercel.app`** are likewise community-hosted; both can be self-deployed the same way.
- Skill icons: full icon list at [skillicons.dev](https://skillicons.dev) — add/remove slugs in the `i=` parameter.
