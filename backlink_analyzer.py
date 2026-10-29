#!/usr/bin/env python3
"""
Backlink Analyzer
-----------------
Reads a backlink export from Ahrefs Webmaster Tools / Ahrefs Backlink Checker,
Ubersuggest, or a manually collected CSV (Google Search), then produces:

  1. Backlink report            -> BACKLINK_REPORT.md + backlink_report.html
  2. Link-quality classification -> backlinks_classified.csv (+ Excel sheet)
  3. Referring-domain analysis   -> referring_domains.csv (+ Excel sheet)
  4. Link-building recommendations (inside the report)
  + charts in charts/*.png

Usage:
  python backlink_analyzer.py --input data/your_export.csv --config config.json
"""
import argparse
import base64
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ---------------------------------------------------------------- constants
COLUMN_ALIASES = {
    "source_url": ["referring page url", "source url", "source page url", "url from",
                   "referring url", "from url", "linking page", "source"],
    "source_title": ["referring page title", "source page title", "page title", "title"],
    "target_url": ["target url", "url to", "destination url", "target"],
    "anchor": ["anchor", "anchor text", "link anchor"],
    "authority": ["domain rating", "dr", "domain authority", "da", "domain score", "authority"],
    "page_authority": ["ur", "url rating", "page authority", "pa"],
    "nofollow": ["nofollow", "is nofollow"],
    "link_type": ["link type", "follow type", "rel", "type"],
    "sponsored": ["sponsored"],
    "ugc": ["ugc"],
    "external_links": ["external links", "outbound links", "external links count"],
    "http_code": ["referring page http code", "http code", "status code"],
    "first_seen": ["first seen", "first found"],
    "last_seen": ["last seen", "last checked"],
    "lost": ["lost status", "lost"],
    "notes": ["notes", "note"],
}

MULTI_TLDS = {"co.in", "org.in", "net.in", "ac.in", "gov.in", "edu.in", "co.uk", "org.uk",
              "ac.uk", "com.au", "net.au", "co.jp", "com.br", "co.za", "com.sg", "com.my",
              "co.nz", "com.pk", "com.ng"}
SPAM_TLDS = {"xyz", "top", "click", "loan", "work", "gq", "tk", "ml", "cf", "ga", "icu",
             "buzz", "rest", "cam", "monster", "bid", "win", "review", "party", "date",
             "racing", "download", "stream", "kim", "men"}
SPAM_WORDS = re.compile(
    r"\b(casino|poker|betting|bet365|slots?|porn|xxx|sex|adult|escort|viagra|cialis|"
    r"pharma|payday|replica|crack|keygen|warez|torrent|essay-?writing|cheap-?seo|"
    r"buy-?backlinks?|free-?backlinks?|linkfarm|link-?farm)\b", re.I)
DIRECTORY_PATTERNS = ["directory", "submit-url", "submiturl", "add-url", "addurl", "linkdir",
                      "web-dir", "webdir", "bookmark", "links.htm", "link-exchange",
                      "linkexchange", "seo-stats", "site-info", "websiteoutlook", "whois"]
GENERIC_ANCHORS = {"click here", "here", "read more", "website", "this", "link", "visit",
                   "visit site", "more", "this site", "learn more", "source", "homepage",
                   "this article", "check it out", "view", "go"}

CATEGORY_ORDER = ["High Quality", "Relevant", "Neutral", "Low Quality", "Potentially Risky"]
CATEGORY_COLORS = {"High Quality": "#2e7d32", "Relevant": "#1565c0", "Neutral": "#9e9e9e",
                   "Low Quality": "#ef6c00", "Potentially Risky": "#c62828"}
CATEGORY_DEFINITIONS = {
    "High Quality": "Strong authority (≥ high threshold) and topically relevant, or very high "
                    "authority (≥ 70), with no risk signals.",
    "Relevant": "Topically related to the target site's niche (keyword match in referring "
                "page title, URL, domain or anchor) with no risk signals.",
    "Neutral": "Not risky, not topically relevant, average authority. Harmless but adds little.",
    "Low Quality": "Low authority (< low threshold), broken/redirecting source page, and not "
                   "relevant. Little to no SEO value.",
    "Potentially Risky": "Risk score at or above the flag threshold: spammy TLD, spam keywords, "
                         "link-farm/directory pattern, huge outbound-link count, money anchors, "
                         "or sitewide link patterns.",
}

# ------------------------------------------------------------------ helpers
def read_any(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(path)
    last_err = None
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            df = pd.read_csv(path, sep=None, engine="python", encoding=enc)
            if df.shape[1] > 1:
                return df
        except Exception as e:  # noqa: BLE001
            last_err = e
    raise SystemExit(f"Could not read {path}: {last_err}")


def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    lower = {c.strip().lower(): c for c in df.columns}
    out = pd.DataFrame(index=df.index)
    for canon, aliases in COLUMN_ALIASES.items():
        for a in aliases:
            if a in lower and lower[a] not in out.attrs.get("used", set()):
                out[canon] = df[lower[a]]
                out.attrs.setdefault("used", set()).add(lower[a])
                break
    if "source_url" not in out:
        raise SystemExit("No source/referring URL column found. Columns in file: "
                         + ", ".join(df.columns))
    return out


def to_bool(v) -> bool:
    if pd.isna(v):
        return False
    return str(v).strip().lower() in ("true", "yes", "1", "y", "nofollow", "x")


def host_of(url) -> str:
    s = str(url).strip()
    if not re.match(r"^[a-z]+://", s, re.I):
        s = "http://" + s
    h = urlparse(s).netloc.lower().split("@")[-1].split(":")[0]
    return h[4:] if h.startswith("www.") else h


def root_domain(host: str) -> str:
    parts = host.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in MULTI_TLDS:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def tld_of(root: str) -> str:
    parts = root.split(".")
    if len(parts) >= 2 and ".".join(parts[-2:]) in MULTI_TLDS:
        return "." + ".".join(parts[-2:])
    return "." + parts[-1]


def short(s, n=60) -> str:
    s = "" if pd.isna(s) else str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


def anchor_type(anchor, brand_terms, money_kw, site) -> str:
    a = "" if pd.isna(anchor) else str(anchor).strip().lower()
    if not a or a in ("nan", "[image]", "img", "image"):
        return "Empty / Image"
    if site.lower() in a or re.match(r"^(https?://|www\.)", a) or re.search(r"\.[a-z]{2,4}(/|$)", a):
        return "Naked URL"
    if any(b.lower() in a for b in brand_terms):
        return "Branded"
    if any(m.lower() in a for m in money_kw):
        return "Money / Commercial"
    if a in GENERIC_ANCHORS:
        return "Generic"
    return "Partial / Topical"


def authority_band(v) -> str:
    if pd.isna(v):
        return "Unknown"
    v = float(v)
    for lo, hi in ((0, 9), (10, 29), (30, 49), (50, 69), (70, 100)):
        if lo <= v <= hi:
            return f"{lo}-{hi}"
    return "70-100" if v > 100 else "0-9"


BAND_ORDER = ["0-9", "10-29", "30-49", "50-69", "70-100", "Unknown"]


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    rows = ["| " + " | ".join(map(str, cols)) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in df.iterrows():
        rows.append("| " + " | ".join(str(r[c]).replace("|", "\\|").replace("\n", " ")
                                      for c in cols) + " |")
    return "\n".join(rows)


# ----------------------------------------------------------------- analysis
def analyse(raw: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    th = cfg["thresholds"]
    df = normalise_columns(raw)
    df = df[df["source_url"].notna() & (df["source_url"].astype(str).str.strip() != "")].copy()

    df["host"] = df["source_url"].map(host_of)
    df["referring_domain"] = df["host"].map(root_domain)
    df["tld"] = df["referring_domain"].map(tld_of)
    df["authority"] = pd.to_numeric(df.get("authority"), errors="coerce") if "authority" in df else np.nan
    for c in ("source_title", "anchor", "target_url"):
        if c not in df:
            df[c] = ""

    # follow / nofollow
    if "nofollow" in df:
        nofollow = df["nofollow"].map(to_bool)
    elif "link_type" in df:
        nofollow = df["link_type"].astype(str).str.lower().str.contains("nofollow|ugc|sponsored")
    else:
        nofollow = pd.Series(False, index=df.index)
    for extra in ("sponsored", "ugc"):
        if extra in df:
            nofollow = nofollow | df[extra].map(to_bool)
    df["follow"] = np.where(nofollow, "nofollow", "dofollow")

    # relevance
    niche = [k.lower() for k in cfg.get("niche_keywords", [])]
    text = (df["source_title"].fillna("").astype(str) + " " + df["source_url"].astype(str) + " "
            + df["anchor"].fillna("").astype(str)).str.lower()
    # remove the target site / brand itself so "MyTechBrand" doesn't count as "tech" relevance
    strip_terms = sorted([cfg["target_site"].lower()] + [b.lower() for b in cfg.get("brand_terms", [])],
                         key=len, reverse=True)
    for term in strip_terms:
        text = text.str.replace(term, " ", regex=False)
    # short keywords (≤ 3 chars, e.g. "ai", "seo") need whole-word matches
    kw_patterns = [(k, re.compile(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])") if len(k) <= 3 else None)
                   for k in niche]
    df["matched_keywords"] = text.map(
        lambda t: ", ".join(k for k, pat in kw_patterns if (pat.search(t) if pat else k in t)))
    df["relevant"] = df["matched_keywords"] != ""

    # anchors
    brand = cfg.get("brand_terms", [])
    money = cfg.get("money_keywords", [])
    df["anchor_type"] = df["anchor"].map(lambda a: anchor_type(a, brand, money, cfg["target_site"]))

    # per-domain link counts (sitewide signal)
    per_domain = df.groupby("referring_domain")["source_url"].transform("count")

    # risk scoring
    scores, flags = [], []
    ext = pd.to_numeric(df["external_links"], errors="coerce") if "external_links" in df else None
    for i, r in df.iterrows():
        s, f = 0, []
        blob = f"{r['referring_domain']} {r['source_url']} {r['source_title']}".lower()
        tld = r["tld"].lstrip(".").split(".")[-1]
        if tld in SPAM_TLDS:
            s += 3; f.append(f"spam-prone TLD (.{tld})")
        if SPAM_WORDS.search(blob):
            s += 3; f.append("spam keywords on referring page/domain")
        if any(p in blob for p in DIRECTORY_PATTERNS):
            s += 2; f.append("directory / auto-generated SEO page pattern")
        if ext is not None and not pd.isna(ext[i]) and ext[i] > th["max_outbound_links"]:
            s += 2; f.append(f"page links out to {int(ext[i])} sites (link-farm signal)")
        if not pd.isna(r["authority"]) and r["authority"] < th["low_authority"]:
            s += 1; f.append(f"very low authority ({int(r['authority'])})")
        if r["anchor_type"] == "Money / Commercial":
            s += 1; f.append("commercial / money anchor text")
        if sum(ch.isdigit() for ch in r["referring_domain"]) > 4 or r["referring_domain"].count("-") >= 3:
            s += 1; f.append("machine-generated looking domain")
        if per_domain[i] > th["sitewide_links"]:
            s += 1; f.append(f"sitewide pattern ({per_domain[i]} links from one domain)")
        scores.append(s); flags.append("; ".join(f))
    df["risk_score"] = scores
    df["risk_flags"] = flags

    broken = pd.Series(False, index=df.index)
    if "http_code" in df:
        code = pd.to_numeric(df["http_code"], errors="coerce")
        broken = code.notna() & (code != 200)

    cats, reasons = [], []
    for i, r in df.iterrows():
        a, known = r["authority"], not pd.isna(r["authority"])
        if r["risk_score"] >= th["risk_score_flag"]:
            cats.append("Potentially Risky"); reasons.append(r["risk_flags"])
        elif known and ((a >= th["high_authority"] and r["relevant"]) or a >= 70):
            cats.append("High Quality")
            reasons.append(f"authority {int(a)}" + (f"; relevant ({r['matched_keywords']})" if r["relevant"] else ""))
        elif r["relevant"]:
            cats.append("Relevant"); reasons.append(f"topical match: {r['matched_keywords']}")
        elif (known and a < th["low_authority"]) or broken[i]:
            cats.append("Low Quality")
            reasons.append("source page not returning 200" if broken[i] else f"low authority ({int(a)}), not relevant")
        else:
            cats.append("Neutral"); reasons.append("not relevant, no risk signals")
    df["quality_category"] = cats
    df["classification_reason"] = reasons
    df["authority_band"] = df["authority"].map(authority_band)
    return df


def domain_table(df: pd.DataFrame) -> pd.DataFrame:
    rank = {c: i for i, c in enumerate(CATEGORY_ORDER)}

    def dom_cat(s):
        if (s == "Potentially Risky").any():
            return "Potentially Risky"
        return min(s, key=lambda c: rank[c])

    g = df.groupby("referring_domain").agg(
        backlinks=("source_url", "count"),
        authority=("authority", "max"),
        dofollow_links=("follow", lambda s: int((s == "dofollow").sum())),
        relevant_links=("relevant", "sum"),
        max_risk_score=("risk_score", "max"),
        tld=("tld", "first"),
        domain_category=("quality_category", dom_cat),
    ).reset_index()
    g["relevant_links"] = g["relevant_links"].astype(int)
    return g.sort_values(["authority", "backlinks"], ascending=[False, False], na_position="last")


# ------------------------------------------------------------------- charts
def make_charts(df, dom, outdir: Path) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    charts = {}

    def save(name):
        p = outdir / f"{name}.png"
        plt.tight_layout(); plt.savefig(p, dpi=150); plt.close()
        charts[name] = p

    counts = df["quality_category"].value_counts().reindex(CATEGORY_ORDER).fillna(0)
    counts = counts[counts > 0]
    plt.figure(figsize=(6.5, 4.5))
    plt.pie(counts, labels=counts.index, autopct="%1.0f%%", startangle=90,
            colors=[CATEGORY_COLORS[c] for c in counts.index], wedgeprops={"edgecolor": "white"})
    plt.title("Backlinks by quality category")
    save("quality_classification")

    bands = dom["authority"].map(authority_band).value_counts().reindex(BAND_ORDER).fillna(0)
    plt.figure(figsize=(7, 4))
    plt.bar(bands.index, bands.values, color="#1565c0")
    plt.title("Referring domains by authority band (DR / DA)")
    plt.xlabel("Authority band"); plt.ylabel("Referring domains")
    save("authority_distribution")

    fol = df["follow"].value_counts()
    plt.figure(figsize=(5, 4))
    plt.bar(fol.index, fol.values, color=["#2e7d32" if i == "dofollow" else "#9e9e9e" for i in fol.index])
    plt.title("Dofollow vs nofollow backlinks"); plt.ylabel("Backlinks")
    save("follow_split")

    tld = dom["tld"].value_counts().head(10)
    plt.figure(figsize=(7, 4))
    plt.barh(tld.index[::-1], tld.values[::-1], color="#6a1b9a")
    plt.title("Top TLDs of referring domains"); plt.xlabel("Referring domains")
    save("tld_distribution")

    anc = df["anchor_type"].value_counts()
    plt.figure(figsize=(7, 4))
    plt.barh(anc.index[::-1], anc.values[::-1], color="#00838f")
    plt.title("Anchor text profile"); plt.xlabel("Backlinks")
    save("anchor_profile")
    return charts


# ------------------------------------------------------- recommendations
def build_recommendations(df, dom, cfg) -> tuple[list, list]:
    n, nd = len(df), len(dom)
    pct = lambda x: 0 if n == 0 else 100 * x / n  # noqa: E731
    cat = df["quality_category"].value_counts()
    data_recs = []

    risky = cat.get("Potentially Risky", 0)
    if pct(risky) >= 10:
        data_recs.append(f"**Audit the {risky} potentially risky links ({pct(risky):.0f}%).** Open each one "
                         "manually. Google ignores most spam links automatically, so only use the Disavow "
                         "tool if these are links someone built on purpose (paid/link schemes) or the site "
                         "has a manual action in Search Console.")
    elif risky:
        data_recs.append(f"**{risky} link(s) flagged as potentially risky** — a small share. Review them, but "
                         "no disavow is needed unless there is a manual action.")
    hq = cat.get("High Quality", 0)
    if pct(hq) < 20:
        data_recs.append(f"**Only {pct(hq):.0f}% of links are high quality.** Prioritise earning links from "
                         "authoritative, niche-relevant sites (digital PR, expert quotes, guest articles).")
    rel = int(df["relevant"].sum())
    if pct(rel) < 40:
        data_recs.append(f"**Relevance is low ({pct(rel):.0f}% of links are on-topic).** Focus outreach on "
                         "sites about: " + ", ".join(cfg.get("niche_keywords", [])[:6]) + ".")
    dof = (df["follow"] == "dofollow").sum()
    if pct(dof) < 50:
        data_recs.append(f"**Dofollow share is {pct(dof):.0f}%.** Nofollow links are still natural and useful "
                         "for traffic, but add more editorial dofollow links from content placements.")
    elif pct(dof) > 95 and n > 20:
        data_recs.append("**Almost every link is dofollow**, which can look unnatural. A natural profile "
                         "usually has a mix — don't chase only dofollow links.")
    money = (df["anchor_type"] == "Money / Commercial").sum()
    if pct(money) > 10:
        data_recs.append(f"**Commercial anchors are {pct(money):.0f}% of links** — over-optimised. Shift new "
                         "links toward branded and naked-URL anchors.")
    branded = (df["anchor_type"] == "Branded").sum()
    if pct(branded) < 25:
        data_recs.append(f"**Branded anchors are only {pct(branded):.0f}%.** Build brand mentions (profiles, "
                         "PR, podcasts) which naturally use the brand name as anchor.")
    if nd and n / nd > 5:
        data_recs.append(f"**Links are concentrated** ({n / nd:.1f} links per referring domain). Getting one "
                         "link each from many new domains is worth more than many links from the same ones.")
    top = dom.head(5)["referring_domain"].tolist()
    if top:
        data_recs.append("**Protect your strongest links** from " + ", ".join(top) + ": keep the linked pages "
                         "live (no 404s) and build relationships with these sites for future mentions.")

    site = cfg["target_site"]
    brand = (cfg.get("brand_terms") or [site])[0]
    kw = (cfg.get("niche_keywords") or ["your niche"])[0]
    tactics = [
        ("Unlinked brand mentions", f'Google: `"{brand}" -site:{site}` → find pages that mention the brand '
                                     "without linking, and politely ask them to add a link."),
        ("Guest posting", f'Google: `"{kw}" "write for us"` or `"{kw}" intitle:"guest post"` → pitch '
                          "useful articles to relevant blogs."),
        ("Resource-page link building", f'Google: `"{kw}" inurl:resources` or `"{kw}" "useful links"` → '
                                        "suggest your best guide as an addition."),
        ("Broken link building", "Use Ahrefs (Broken backlinks / Best by links) on competitor or niche sites, "
                                 "find dead pages that still get links, and offer your content as the replacement."),
        ("Competitor gap", "Run 2–3 competitors through Ubersuggest/Ahrefs; domains linking to them but not to "
                           "you are your warmest outreach list."),
        ("Linkable assets", "Publish something people cite: original data/surveys, free tools, templates, "
                            "infographics or ultimate guides."),
        ("Digital PR / expert quotes", "Answer journalist requests on platforms like Qwoted or Featured, and "
                                       "share your expertise on podcasts and community events."),
        ("Profiles & communities (natural mix)", "Relevant GitHub, LinkedIn, Medium/Dev.to, Reddit/Quora answers "
                                                 "— mostly nofollow, but they build a natural profile and traffic."),
        ("What to avoid", "Buying links, PBNs, link exchanges at scale, directory blasts and exact-match "
                          "anchor stuffing — these violate Google's spam policies."),
    ]
    return data_recs, tactics


# ----------------------------------------------------------------- report
def build_report(df, dom, charts, cfg, src_name, outdir: Path):
    n, nd = len(df), len(dom)
    th = cfg["thresholds"]
    today = date.today().isoformat()
    cat_counts = df["quality_category"].value_counts().reindex(CATEGORY_ORDER).fillna(0).astype(int)
    known = df["authority"].dropna()
    dof = int((df["follow"] == "dofollow").sum())
    data_recs, tactics = build_recommendations(df, dom, cfg)

    overview = pd.DataFrame({
        "Metric": ["Target website", "Data source file", "Analysis date", "Total backlinks analysed",
                   "Referring domains", "Dofollow backlinks", "Nofollow backlinks",
                   "Avg. referring-domain authority", "Median referring-domain authority",
                   "Topically relevant backlinks"],
        "Value": [cfg["target_site"], src_name, today, n, nd,
                  f"{dof} ({100 * dof / max(n, 1):.0f}%)", f"{n - dof} ({100 * (n - dof) / max(n, 1):.0f}%)",
                  f"{dom['authority'].mean():.1f}" if dom["authority"].notna().any() else "n/a",
                  f"{dom['authority'].median():.0f}" if dom["authority"].notna().any() else "n/a",
                  f"{int(df['relevant'].sum())} ({100 * df['relevant'].sum() / max(n, 1):.0f}%)"],
    })
    cls = pd.DataFrame({"Category": cat_counts.index, "Backlinks": cat_counts.values,
                        "Share": [f"{100 * v / max(n, 1):.0f}%" for v in cat_counts.values],
                        "Definition": [CATEGORY_DEFINITIONS[c] for c in cat_counts.index]})

    def link_view(sub, k=10):
        sub = sub.sort_values("authority", ascending=False, na_position="last").head(k)
        return pd.DataFrame({
            "Referring domain": sub["referring_domain"],
            "Authority": sub["authority"].map(lambda v: "?" if pd.isna(v) else int(v)),
            "Anchor": sub["anchor"].map(lambda a: short(a, 30)),
            "Follow": sub["follow"],
            "Why": sub["classification_reason"].map(lambda a: short(a, 70)),
        })

    top_dom = dom.head(15).copy()
    top_dom_view = pd.DataFrame({
        "Referring domain": top_dom["referring_domain"],
        "Authority": top_dom["authority"].map(lambda v: "?" if pd.isna(v) else int(v)),
        "Backlinks": top_dom["backlinks"], "Dofollow": top_dom["dofollow_links"],
        "Relevant": top_dom["relevant_links"], "Category": top_dom["domain_category"],
    })
    dom_cat = dom["domain_category"].value_counts().reindex(CATEGORY_ORDER).fillna(0).astype(int)
    dom_cat_view = pd.DataFrame({"Domain category": dom_cat.index, "Referring domains": dom_cat.values,
                                 "Share": [f"{100 * v / max(nd, 1):.0f}%" for v in dom_cat.values]})
    bands = dom["authority"].map(authority_band).value_counts().reindex(BAND_ORDER).fillna(0).astype(int)
    band_view = pd.DataFrame({"Authority band": bands.index, "Referring domains": bands.values})
    anc = df["anchor_type"].value_counts()
    anc_view = pd.DataFrame({"Anchor type": anc.index, "Backlinks": anc.values,
                             "Share": [f"{100 * v / max(n, 1):.0f}%" for v in anc.values]})
    top_anchor = (df["anchor"].fillna("(empty)").astype(str).str.strip().replace("", "(empty)")
                  .value_counts().head(10))
    top_anchor_view = pd.DataFrame({"Anchor text": [short(a, 40) for a in top_anchor.index],
                                    "Backlinks": top_anchor.values})

    hq, rk = cat_counts["High Quality"], cat_counts["Potentially Risky"]
    summary = [
        f"{cfg['target_site']} has **{n} backlinks from {nd} referring domains** in this dataset.",
        f"**{hq} links ({100 * hq / max(n, 1):.0f}%) are high quality** and "
        f"**{rk} ({100 * rk / max(n, 1):.0f}%) are potentially risky**.",
        f"**{100 * df['relevant'].sum() / max(n, 1):.0f}%** of links come from pages related to the site's niche.",
        f"The link profile is **{100 * dof / max(n, 1):.0f}% dofollow**; the most common anchor type is "
        f"**{anc.index[0] if len(anc) else 'n/a'}**.",
    ]
    if len(known):
        summary.append(f"Strongest referring domain: **{dom.iloc[0]['referring_domain']}** "
                       f"(authority {int(dom.iloc[0]['authority']) if not pd.isna(dom.iloc[0]['authority']) else '?'}).")

    sections = [
        ("1. Overview", None, [overview], []),
        ("2. Executive summary", summary, [], []),
        ("3. Link-quality classification",
         [f"Thresholds used: high authority ≥ {th['high_authority']}, low authority < {th['low_authority']}, "
          f"risk flag at score ≥ {th['risk_score_flag']}. Relevance = niche keyword found in the referring "
          "page title, URL or anchor. Full per-link results: `backlinks_classified.csv`."],
         [cls], ["quality_classification"]),
        ("3.1 Top high-quality backlinks", None, [link_view(df[df.quality_category == "High Quality"])], []),
        ("3.2 Relevant backlinks (sample)", None, [link_view(df[df.quality_category == "Relevant"])], []),
        ("3.3 Low-quality backlinks (sample)", None, [link_view(df[df.quality_category == "Low Quality"])], []),
        ("3.4 Potentially risky backlinks", ["These need a manual check — a flag is a signal, not proof of spam."],
         [link_view(df[df.quality_category == "Potentially Risky"], 15)], []),
        ("4. Referring-domain analysis",
         [f"{nd} unique referring domains. Domain category = the riskiest/best category among its links. "
          "Full table: `referring_domains.csv`."],
         [top_dom_view, dom_cat_view, band_view], ["authority_distribution", "tld_distribution", "follow_split"]),
        ("5. Anchor text analysis", None, [anc_view, top_anchor_view], ["anchor_profile"]),
        ("6. Link-building recommendations", ["**Based on this profile:**"] + [f"- {r}" for r in data_recs]
         + ["", "**Tactics to grow high-quality, relevant links:**"]
         + [f"- **{t}** — {d}" for t, d in tactics], [], []),
        ("7. Methodology & limitations", [
            "- Data was exported from the tool(s) listed in the overview and processed with `backlink_analyzer.py`.",
            "- Free tool tiers show a sample of backlinks, not the full profile; DR/DA are third-party "
            "estimates, not Google metrics.",
            "- Relevance uses keyword matching, and risk uses heuristic signals, so borderline links were "
            "reviewed manually.",
            "- The `link:` Google operator is deprecated, so Google Search was used for brand-mention and "
            "prospecting queries instead of counting backlinks.",
        ], [], []),
    ]

    # ---- markdown
    md = [f"# Backlink Analysis Report — {cfg['target_site']}", f"*Generated {today}*", ""]
    for title, paras, tables, imgs in sections:
        md += [f"## {title}" if title[1] == "." and title[2] == " " else f"### {title}", ""]
        for p in paras or []:
            md.append(p)
            if not p.startswith("- "):
                md.append("")
        if paras and paras[-1].startswith("- "):
            md.append("")
        for t in tables:
            md += [md_table(t) if len(t) else "_None found._", ""]
        for im in imgs:
            md += [f"![{im}](charts/{im}.png)", ""]
    (outdir / "BACKLINK_REPORT.md").write_text("\n".join(md), encoding="utf-8")

    # ---- html (print to PDF from browser)
    def b64(p):
        return base64.b64encode(Path(p).read_bytes()).decode()

    def mdinline(s):
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        return re.sub(r"`(.+?)`", r"<code>\1</code>", s)

    h = [f"<!doctype html><html><head><meta charset='utf-8'><title>Backlink Report — {cfg['target_site']}</title>",
         "<style>body{font-family:Segoe UI,Arial,sans-serif;max-width:980px;margin:32px auto;padding:0 20px;"
         "color:#1a1a2e;line-height:1.5}h1{color:#1a237e}h2{color:#1a237e;border-bottom:2px solid #ef6c00;"
         "padding-bottom:4px;margin-top:36px}table{border-collapse:collapse;width:100%;margin:12px 0;font-size:13px}"
         "th{background:#1a237e;color:#fff;text-align:left}th,td{border:1px solid #ddd;padding:6px 8px;"
         "vertical-align:top}tr:nth-child(even){background:#f6f7fb}img{max-width:100%;margin:10px 0}"
         "code{background:#f1f1f1;padding:1px 4px;border-radius:3px}@media print{h2{page-break-before:auto}"
         "table,img{page-break-inside:avoid}}</style></head><body>",
         f"<h1>Backlink Analysis Report — {cfg['target_site']}</h1><p><em>Generated {today}</em></p>"]
    for title, paras, tables, imgs in sections:
        tag = "h2" if title[1] == "." and title[2] == " " else "h3"
        h.append(f"<{tag}>{title}</{tag}>")
        in_list = False
        for p in paras or []:
            if p.startswith("- "):
                if not in_list:
                    h.append("<ul>"); in_list = True
                h.append(f"<li>{mdinline(p[2:])}</li>")
            else:
                if in_list:
                    h.append("</ul>"); in_list = False
                if p:
                    h.append(f"<p>{mdinline(p)}</p>")
        if in_list:
            h.append("</ul>")
        for t in tables:
            h.append(t.to_html(index=False, escape=True) if len(t) else "<p><em>None found.</em></p>")
        for im in imgs:
            h.append(f"<img alt='{im}' src='data:image/png;base64,{b64(charts[im])}'>")
    h.append("</body></html>")
    (outdir / "backlink_report.html").write_text("\n".join(h), encoding="utf-8")


def write_excel(df, dom, outdir: Path):
    keep = ["referring_domain", "source_url", "source_title", "target_url", "anchor", "anchor_type",
            "authority", "authority_band", "follow", "relevant", "matched_keywords", "risk_score",
            "risk_flags", "quality_category", "classification_reason"]
    out = df[[c for c in keep if c in df]]
    out.to_csv(outdir / "backlinks_classified.csv", index=False)
    dom.to_csv(outdir / "referring_domains.csv", index=False)
    summary = df["quality_category"].value_counts().reindex(CATEGORY_ORDER).fillna(0).astype(int).reset_index()
    summary.columns = ["Category", "Backlinks"]
    with pd.ExcelWriter(outdir / "backlink_analysis.xlsx", engine="openpyxl") as xw:
        summary.to_excel(xw, sheet_name="Summary", index=False)
        out.to_excel(xw, sheet_name="Classified Backlinks", index=False)
        dom.to_excel(xw, sheet_name="Referring Domains", index=False)
        df["anchor_type"].value_counts().rename_axis("Anchor type").reset_index(name="Backlinks") \
            .to_excel(xw, sheet_name="Anchor Profile", index=False)
        for ws in xw.book.worksheets:
            ws.freeze_panes = "A2"
            for col in ws.columns:
                width = max(len(str(c.value or "")) for c in col[:200])
                ws.column_dimensions[col[0].column_letter].width = min(max(10, width + 2), 60)


# --------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Classify and report on a backlink export.")
    ap.add_argument("--input", "-i", required=True, help="CSV/XLSX export (Ahrefs, Ubersuggest or manual)")
    ap.add_argument("--config", "-c", default="config.json")
    ap.add_argument("--out", "-o", default="reports")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    cfg.setdefault("thresholds", {})
    for k, v in {"high_authority": 50, "low_authority": 15, "risk_score_flag": 3,
                 "max_outbound_links": 100, "sitewide_links": 50}.items():
        cfg["thresholds"].setdefault(k, v)

    src = Path(args.input)
    df = analyse(read_any(src), cfg)
    if df.empty:
        sys.exit("No backlinks found in the input file.")
    dom = domain_table(df)

    outdir = Path(args.out) / f"{cfg['target_site'].replace('.', '_')}_{date.today().isoformat()}"
    charts = make_charts(df, dom, outdir / "charts")
    write_excel(df, dom, outdir)
    build_report(df, dom, charts, cfg, src.name, outdir)

    print(f"\n✅ Analysed {len(df)} backlinks from {len(dom)} referring domains")
    print(df["quality_category"].value_counts().reindex(CATEGORY_ORDER).fillna(0).astype(int).to_string())
    print(f"\n📁 Output: {outdir.resolve()}")
    print("   BACKLINK_REPORT.md · backlink_report.html (open → Print → Save as PDF)")
    print("   backlink_analysis.xlsx · backlinks_classified.csv · referring_domains.csv · charts/")


if __name__ == "__main__":
    main()
