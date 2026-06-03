# Dawnwalker Guide

A fast, SEO-first **Astro** site covering *The Blood of Dawnwalker* (releases **2026-09-03**). Static output, hosted free on Cloudflare Pages, monetized with Google AdSense.

Full strategy lives in the plan file: `~/.claude/plans/adsense-1-2-google-inherited-trinket.md`.

## Run locally

```bash
npm install
npm run dev      # http://localhost:4321
npm run build    # outputs static site to ./dist
npm run preview  # preview the production build
```

## Project map

| Path | What it is |
| --- | --- |
| `src/consts.ts` | **Edit this first.** Domain URL, site name, AdSense ID, nav. |
| `src/content/news/` | News posts (one `.md` per day). |
| `src/content/guides/` | Guides & walkthroughs (`.md`/`.mdx`). |
| `src/content.config.ts` | Frontmatter schema for the above. |
| `src/pages/` | Routes (home, news, guides, about, legal, rss, robots). |
| `src/components/` | SEO, JSON-LD, breadcrumbs, ad slot, cards, header/footer. |
| `src/lib/` | `schema.ts` (structured data) + `utils.ts` (content helpers). |
| `public/` | `ads.txt`, `favicon.svg`, `_headers`. Add `og-default.png` (1200×630). |

## Add a daily news post

Create `src/content/news/your-slug.md`. The filename becomes the URL: `/news/your-slug/`.

```markdown
---
title: "Headline goes here"
description: "One-sentence summary used for SEO + social cards."
publishDate: 2026-06-04
author: "Dawnwalker Guide Team"
tags: ["news", "trailer"]
sources:
  - label: "Source name"
    url: "https://example.com/article"
---

Body in Markdown. **Rewrite and add original analysis** — never paste source
text. Always cite sources in the frontmatter above.
```

Set `draft: true` in the frontmatter to keep a post out of the production build while you work on it.

## Add a guide

Same as above but in `src/content/guides/`. Extra fields:

- `category`: one of `overview | walkthrough | boss | build | quest | endings | beginner | system | preview`
- `pillar: true` to feature it in "Start Here" / "Essential Guides"
- `faq`: list of `{ question, answer }` — renders an accordion **and** FAQ rich-result schema

## Going live (one-time)

1. Buy a domain (Cloudflare Registrar, ~$10/yr) and set it in `src/consts.ts` (`SITE.url`).
2. Push this repo to GitHub.
3. Cloudflare Pages → connect the repo. Build command `npm run build`, output dir `dist`.
4. Add the domain in Pages and point DNS.
5. Google Search Console → add property → submit `https://yourdomain/sitemap-index.xml`.
6. Turn on Cloudflare Web Analytics (free, no cookie banner needed).

## Turning on AdSense (after ~20–30 quality pages)

1. Apply at adsense.google.com with the live domain.
2. Once approved: paste your publisher line into `public/ads.txt`, set `ADSENSE.publisherId` and `ADSENSE.enabled = true` in `src/consts.ts`, then redeploy.
3. In AdSense → **Privacy & messaging**, enable the GDPR consent message (Funding Choices). **Required** for EU/UK traffic.
