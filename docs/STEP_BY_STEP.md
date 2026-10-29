# Step-by-Step: Collecting the Data & Submitting

## Step 0 — Pick the website

Choose **one** of these:

- **Option A: your own site** (portfolio, project demo). Works with **Ahrefs Webmaster Tools**, which only analyses sites you verify. Downside: a new site may have very few backlinks.
- **Option B: a small/medium site in a niche you know** (a tech blog, local business, edtech startup). Use the **free Ahrefs Backlink Checker** + **Ubersuggest**, which work on any domain. This usually gives a richer analysis. Avoid giants like Amazon/Wikipedia: millions of links, and free tools only show a tiny slice.

Then edit `config.json`:

```json
"target_site": "thesite.com",
"brand_terms": ["the brand name", "thesite"],
"niche_keywords": ["5–12 words that describe the site's topic"]
```

## Step 1 — Ahrefs

**Webmaster Tools (own site):** sign up at ahrefs.com/webmaster-tools → *Add project* → verify (easiest: *Import from Google Search Console*, or HTML file / meta tag / DNS) → wait for the crawl → **Site Explorer → Backlinks** → **Export** (CSV). Also open **Referring domains** and **Anchors** and screenshot them.

**Free Backlink Checker (any site):** ahrefs.com/backlink-checker → enter the domain → shows DR, backlink + referring-domain counts and the top 100 backlinks. If there is no export button, copy the rows into `data/manual_template.csv`.

📸 Screenshot → `screenshots/ahrefs_overview.png`

## Step 2 — Ubersuggest

app.neilpatel.com → enter the domain → **Backlinks** (left menu). Free accounts get a few searches per day. Export CSV if available; otherwise copy the visible rows into the manual template.

📸 Screenshot → `screenshots/ubersuggest_backlinks.png`

> You can run the script on each export separately, or merge them into one CSV (same column names) — duplicates from the same URL are fine to remove first.

## Step 3 — Google Search (verification + prospects)

The old `link:` operator no longer works, so use Google to **verify** and **find opportunities**:

| Purpose | Query |
|---|---|
| Brand mentions on other sites | `"Brand Name" -site:thesite.com` |
| Pages mentioning the domain | `"thesite.com" -site:thesite.com` |
| Guest-post prospects | `"<niche keyword>" "write for us"` |
| Resource pages | `"<niche keyword>" inurl:resources` |

Open 5–10 of the flagged "risky" and "high quality" links to confirm they look right. Add anything new you find to `data/manual_template.csv`.

📸 Screenshot → `screenshots/google_search.png`

## Step 4 — Run the analysis

```bash
pip install -r requirements.txt
python backlink_analyzer.py --input data/ahrefs_export.csv
```

Open `reports/<site>_<date>/backlink_report.html` in Chrome → **Ctrl+P → Save as PDF** → save as `backlink_report.pdf` in the same folder.

## Step 5 — Finish the README

Fill the **Key Findings** table and **Top 3 insights** from report sections 1–2, and change `YOUR_REPORT_FOLDER` in the chart image paths to your real report folder name. Replace `<TARGET WEBSITE>`, `<your-username>` and `<your-profile>`.

## Step 6 — Push to GitHub

```bash
git init
git add .
git commit -m "Backlink analysis of thesite.com"
git branch -M main
git remote add origin https://github.com/<your-username>/backlink-analysis.git
git push -u origin main
```

Optionally delete `data/sample_backlinks_DEMO_ONLY.csv` before pushing so reviewers only see your real data.

## Step 7 — Submission form

| Field | What to give |
|---|---|
| GitHub Repo Link | `https://github.com/<you>/backlink-analysis` |
| GitHub Files Screenshot | Screenshot of the repo homepage showing the files + README |
| LinkedIn Project / Post Link | Your post URL (draft in `docs/LINKEDIN_POST.md`) |
| LinkedIn Post Screenshot | Screenshot of the published post |
| Task / Project Report | `backlink_report.pdf` (or zip the report folder; keep it under 5 MB) |
