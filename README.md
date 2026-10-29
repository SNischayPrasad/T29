# 🔗 Basic Backlink Analysis — Off-Page SEO Project

> **Digital Marketing Track · Task: Perform a Basic Backlink Analysis**
> Analyzing the backlink profile of **`<TARGET WEBSITE>`** to identify high-quality, low-quality, relevant and potentially risky links, and turning the findings into a link-building plan.

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)
![SEO](https://img.shields.io/badge/SEO-Off--Page-orange)
![Tools](https://img.shields.io/badge/Tools-Ahrefs%20%7C%20Ubersuggest%20%7C%20Google-blue)

---

## 📌 Objective

Understand the basics of **off-page SEO** and **link building** by auditing a real website's backlink profile, i.e. *who links to the site, how strong and relevant those links are, and which ones could be harmful*.

## 🧰 Tools Used

| Tool | What I used it for |
|---|---|
| **Ahrefs Webmaster Tools** / Ahrefs Free Backlink Checker | Backlink list, Domain Rating (DR), referring domains, dofollow/nofollow, anchors |
| **Ubersuggest** | Second data source: Domain Authority, backlink sample, cross-checking counts |
| **Google Search** | Manual verification of linking pages, unlinked brand mentions, link-building prospects |
| **Python** (pandas, matplotlib, openpyxl) | Cleaning the exports, classifying links, charts and the final report |

## 📦 Deliverables

| Deliverable | Where to find it |
|---|---|
| ✅ Backlink report | `reports/<site>_<date>/BACKLINK_REPORT.md` · `backlink_report.pdf` |
| ✅ Link-quality classification | `reports/<site>_<date>/backlinks_classified.csv` + *Classified Backlinks* sheet in `backlink_analysis.xlsx` |
| ✅ Referring-domain analysis | `reports/<site>_<date>/referring_domains.csv` + *Referring Domains* sheet + charts |
| ✅ Link-building recommendations | Section 6 of the backlink report |

---

## 📊 Key Findings

> *Fill in from your generated report (sections 1–2).*

| Metric | Value |
|---|---|
| Backlinks analysed | `__` |
| Referring domains | `__` |
| Dofollow / Nofollow | `__% / __%` |
| Avg. referring-domain authority | `__` |
| High-quality links | `__ (__%)` |
| Relevant links | `__ (__%)` |
| Low-quality links | `__ (__%)` |
| Potentially risky links | `__ (__%)` |

**Top 3 insights**
1. `…`
2. `…`
3. `…`

<p align="center">
  <img src="reports/YOUR_REPORT_FOLDER/charts/quality_classification.png" width="45%">
  <img src="reports/YOUR_REPORT_FOLDER/charts/authority_distribution.png" width="45%">
</p>

---

## 🧪 How Links Were Classified

Every backlink gets a **relevance check** and a **risk score**, then one category:

| Category | Rule |
|---|---|
| 🟢 **High Quality** | Authority (DR/DA) ≥ 50 **and** niche-relevant, or authority ≥ 70, with no risk signals |
| 🔵 **Relevant** | Niche keyword found in the linking page's title / URL / anchor, no risk signals |
| ⚪ **Neutral** | Not risky, not relevant, average authority — harmless but low value |
| 🟠 **Low Quality** | Authority < 15 or broken source page, and not relevant |
| 🔴 **Potentially Risky** | Risk score ≥ 3 |

**Risk signals (points):** spam-prone TLD such as `.xyz` `.top` `.click` (+3) · spam keywords like casino/pharma/"free backlinks" (+3) · web-directory / auto-generated "site value" pages (+2) · page linking out to 100+ sites (+2) · authority < 15 (+1) · commercial/money anchor (+1) · machine-generated-looking domain (+1) · sitewide pattern, 50+ links from one domain (+1).

**Anchor types:** Branded · Naked URL · Partial/Topical · Generic ("click here") · Money/Commercial · Empty/Image.

> A "risky" flag is a signal for manual review, not proof of spam. Google ignores most spammy links on its own; disavowing is only for deliberate link schemes or a manual action.

All thresholds and keywords are editable in [`config.json`](config.json).

---

## 🚀 Run It Yourself

```bash
git clone https://github.com/<your-username>/backlink-analysis.git
cd backlink-analysis
pip install -r requirements.txt

# 1. Edit config.json → target_site, brand_terms, niche_keywords
# 2. Put your export in data/  (Ahrefs CSV, Ubersuggest CSV, or data/manual_template.csv)
python backlink_analyzer.py --input data/your_export.csv --config config.json
```

Try it instantly with the demo data (fictional domains, for testing only):

```bash
python backlink_analyzer.py --input data/sample_backlinks_DEMO_ONLY.csv
```

The script auto-detects Ahrefs (UTF-16, tab-separated) and Ubersuggest/manual CSV column names, and also reads `.xlsx`.

**Output** (`reports/<site>_<date>/`):

```
BACKLINK_REPORT.md        → full report (renders on GitHub)
backlink_report.html      → same report with charts; open → Print → Save as PDF
backlink_analysis.xlsx    → Summary · Classified Backlinks · Referring Domains · Anchor Profile
backlinks_classified.csv  → every link with category, risk score and reason
referring_domains.csv     → one row per referring domain
charts/                   → quality, authority, dofollow, TLD, anchor charts
```

## 📁 Repository Structure

```
backlink-analysis/
├── backlink_analyzer.py        # classification + report generator
├── config.json                 # target site, keywords, thresholds
├── requirements.txt
├── data/
│   ├── <your exports>.csv
│   ├── manual_template.csv     # for links collected via Google Search
│   └── sample_backlinks_DEMO_ONLY.csv
├── reports/<site>_<date>/      # generated deliverables
├── screenshots/                # Ahrefs / Ubersuggest / Google evidence
└── docs/
    └── STEP_BY_STEP.md         # how the data was collected
```

## 🖼️ Tool Screenshots

| Ahrefs | Ubersuggest | Google Search |
|---|---|---|
| ![Ahrefs](screenshots/ahrefs_overview.png) | ![Ubersuggest](screenshots/ubersuggest_backlinks.png) | ![Google](screenshots/google_search.png) |

## 💡 What I Learned

- **Quality beats quantity:** a few relevant links from trusted sites outweigh hundreds of directory links.
- **Referring domains matter more than total backlinks:** 50 links from one site ≠ 50 sites vouching for you.
- **Anchor text should look natural:** branded and URL anchors dominate healthy profiles; too many keyword anchors is a red flag.
- **Dofollow vs nofollow:** nofollow links still bring traffic and make a profile look natural.
- **Not every bad link is dangerous:** audit first; disavow only when necessary.

## ⚠️ Limitations

Free tool tiers show only a sample of backlinks; DR/DA are third-party estimates, not Google metrics; relevance is keyword-based and risk is heuristic, so borderline links were checked manually.

---

**Author:** Sadhanala Nischay Prasad · [LinkedIn](https://www.linkedin.com/in/<your-profile>) · Digital Marketing Track
