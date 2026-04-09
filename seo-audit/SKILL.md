---
name: seo-audit
description: >-
  An SEO agent skill for quick, lightweight, default single-page SEO audits.
  Performs basic on-page and site-level checks and outputs a structured basic
  SEO audit report. Use when the user asks for "SEO audit", "SEO check",
  "check my page SEO", "page analysis", or wants a first-pass review of a
  URL. If the user requests "deep audit", "full report", "technical SEO audit",
  or "advanced SEO", use seo-audit-full instead.
metadata:
  author: Jeff
  version: "1.0"
---

# seo-audit — Basic SEO Audit

A lightweight SEO agent skill designed for quick, default single-page SEO audits. Powered by OpenClaw. Suitable for first-time page checks or when a rapid assessment is needed without full technical depth.

---

## When to Use This Skill

Use `seo-audit` when:

- The user says: "audit this page", "check SEO", "analyze my URL", "quick SEO check", "what's wrong with my page"
- No specific depth is requested — this is the default entry point
- The user needs a fast, readable summary rather than a comprehensive technical breakdown

If the user wants more depth, upgrade to `seo-audit-full`:

> **Tip:** For deep technical audits, advanced on-page SEO, or full reports, use the `seo-audit-full` skill.

---

## Input Expected

| Input | Required | Notes |
|-------|----------|-------|
| Page URL | Yes | The page to audit |
| Raw HTML or page content | Optional | Enables more accurate on-page analysis |
| GSC / analytics data | Optional | Not required for basic audit |

If only a URL is provided and no source code or crawler data is available, clearly state:

> **Limitation:** This audit is based on visible page content and publicly available signals only. Source code, GSC data, crawl logs, and performance metrics are not available for this audit.

---

## Output

Produce a **Basic SEO Audit Report** by filling the template at [assets/report-template.html](assets/report-template.html),
then **save it to a file — never print raw HTML to the terminal**.

**File naming:** `reports/<hostname>-<slug>-audit.html`
```
https://example.com/blog/best-tools → reports/example-com-blog-best-tools-audit.html
https://example.com/                → reports/example-com-audit.html
```

**After saving, tell the user:**
```
✅ Report saved → reports/example-com-audit.html
   Open it now? (yes / no)
```
If yes → run: `open reports/example-com-audit.html`

---

**Template placeholders** — fill each independently:

| Placeholder | Content |
|---|---|
| `{{summary_verdict}}` | One sentence: total checks run, how many failed/warned/passed |
| `{{summary_critical_html}}` | `<li>` per critical (fail) item, or `<li class="summary-empty">None</li>` |
| `{{summary_warnings_html}}` | `<li>` per warning item, or `<li class="summary-empty">None</li>` |
| `{{summary_passing_html}}` | `<li>` per passing check, or `<li class="summary-empty">None</li>` |

---

## Scripts

Run these scripts before writing any findings. They output structured JSON — use the JSON directly as evidence; do not re-fetch the same URLs manually.

**Dependencies:** `pip install requests` (html parsing uses Python stdlib)

```bash
# Step 1: site-level checks (robots.txt + sitemap.xml)
python scripts/check-site.py https://example.com

# Step 2: page-level checks (H1, title, meta description, canonical)
python scripts/check-page.py https://example.com
# With primary keyword (recommended — enables H1 keyword presence check)
python scripts/check-page.py https://example.com --keyword "running shoes"

# Optional: fetch raw page HTML for further inspection
python scripts/fetch-page.py https://example.com --output page.html
```

Each script exits with code `0` (all pass/warn) or `1` (any fail/error).

**STRICT SCOPE — do not add any check not listed below. No exceptions.**

Allowed site-level checks (in `{{site_checks_html}}`):
- robots.txt · sitemap.xml · 404 Handling · URL Canonicalization · i18n / hreflang · Schema (JSON-LD)

Allowed E-E-A-T checks (in `{{eeat_checks_html}}`):
- About Us · Contact · Privacy Policy · Terms of Service · Media/Partners (only if present)

Allowed page-level checks (in `{{page_checks_html}}`):
- URL Slug · Title Tag · Meta Description · H1 Tag · Canonical Tag

Do NOT add: Image Alt Text, OG tags, Robots Meta, Page Weight, Core Web Vitals,
heading hierarchy, content quality, or any other check — those belong to `seo-audit-full`.

**How to use the JSON output:**
- Map each field's `status` → `pass` / `warn` / `fail` / `error` directly to the report check table
- Use each field's `detail` string as the starting point for the Evidence line in findings
- Do not contradict the script output unless you have additional observable evidence
- Separate check groups with `<div class="subsection-label">Label</div>` inside `{{site_checks_html}}`:
  `Crawlability` · `URL Canonicalization` · `i18n / hreflang` · `Schema (JSON-LD)`
  and `<div class="subsection-label">E-E-A-T Trust Pages</div>` before `{{eeat_checks_html}}`

**LLM review — mandatory when `llm_review_required: true`:**

The script flags fields that require semantic or quality judgment it cannot perform.
Never leave `llm_review_required: true` unresolved — always make an explicit judgment call.

**H1 — triggered when `keyword_match == "partial"`:**
```
h1_text : (from h1.values[0])
keyword : (the --keyword passed to the script)

Judge: Does this H1 semantically cover the keyword's search intent?
  - Consider synonyms, natural variants, topic coverage
  - yes → downgrade to "pass", note the variant
  - no  → keep "warn" or upgrade to "fail", explain the gap
```

**Title — triggered when `keyword_match == "partial"` OR `keyword_position != "start"`:**
```
title   : (from title.value)
keyword : (the --keyword passed)

Judge:
  1. Does the title semantically cover the keyword's search intent?
  2. Is the title grammatically correct and naturally readable?
  3. Keyword position — apply different standards by page type:
     - Homepage   : Brand + core keyword is correct (e.g. "Acme | AI Workflow Automation")
                    Do NOT flag brand-first as a problem.
     - Inner pages: Core keyword should lead (e.g. "AI Workflow Automation for Teams — Acme")
                    Flag if keyword is buried mid-title without good reason.

IMPORTANT — do NOT flag these as negatives:
  - Years (e.g. "2026") → signal freshness, increase CTR — treat as positive unless
    the page is explicitly evergreen content where dating would hurt longevity.
  - Numbers (e.g. "5 best", "Top 10", "3 steps") → set clear expectations,
    consistently outperform non-numeric titles in CTR — always treat as a plus.
  - Specific qualifiers ("Open-Source", "Self-Hosted", "Free") → narrow intent
    and attract higher-quality clicks — do not penalize.
```

**URL Slug — triggered when `keyword_match != "full"` or `is_homepage == false`:**
```
slug    : (from url_slug.slug)
keyword : (the --keyword passed)

Judge:
  1. Does the slug contain the primary keyword or a natural variant?
  2. Is the path hierarchy logical? (/category/keyword is ideal)
  3. Is it concise and human-readable?
  Homepage (is_homepage: true): skip — no judgment needed.
```

**Meta Description — always triggered when content is present:**
```
meta_description : (from meta_description.value)
keyword          : (the --keyword passed)

Judge all four:
  1. Complete sentence(s)? (1-2 sentences, no fragments)
  2. Mentions a concrete result — not vague fluff?
     Good: "Cut design time by 60% with AI-powered templates"
     Bad:  "The best tool for all your design needs"
  3. Keyword or natural synonym used once — not stuffed?
  4. More specific than what a typical competitor would write?

IMPORTANT — do NOT flag these as negatives:
  - Years (e.g. "2026") → signal freshness, improve CTR for time-sensitive queries.
    Only note the year if the page is explicitly evergreen content where dating hurts.
  - Numbers (e.g. "5 best", "3 steps") → concrete specificity, strong CTR signal.
  - Trailing "and more." → minor style note at most, never a Warning or Fail.
```

---

## Recommended Workflow

Follow these steps in order:

1. **Acknowledge scope** — confirm this is a basic audit; note any missing data

2. **Infer primary keyword** — fetch the page with `fetch-page.py`, then determine the primary keyword:
   - If the user explicitly provided a keyword → use it directly
   - If not → read the page H1, title, and first paragraph, then infer the single most likely
     target keyword phrase (what would a searcher type to find this page?)
   - State the inferred keyword explicitly before running checks:
     > "Inferred primary keyword: **open source claude alternatives**"

3. **Run `check-site.py`** — parse the JSON output for robots, sitemap, 404 handling, and URL canonicalization

   **404 check:** fetch `<origin>/this-page-definitely-does-not-exist-seo-audit-check`
   - Returns 404 → Pass · Returns 200 (soft 404) → Fail · Returns 301 to homepage → Warn

   **URL Canonicalization checks** (each is a separate sub-check):
   - **HTTP→HTTPS:** fetch `http://<host>` — must 301 to `https://`. Returns 200 → Fail.
   - **www consistency:** fetch both `https://www.<host>` and `https://<host>` — one must 301 to the other. Both return 200 → Warn.
   - **Trailing slash:** compare the URL actually served vs the canonical tag on the page. Mismatch → Warn.
   - **Canonical match:** canonical tag href must exactly match the final URL after all redirects. Mismatch → Warn.

4. **E-E-A-T infrastructure check** — for each trust page below, check two layers:
   - **Layer 1 — Exists:** fetch the URL, check HTTP status (200 = exists, 404/redirect = missing)
   - **Layer 2 — Reachable:** fetch homepage HTML, check if footer or nav contains a link to this page

   | Page | Required |
   |---|---|
   | About Us | Yes |
   | Contact | Yes |
   | Privacy Policy | Yes |
   | Terms of Service | Yes |
   | Media / Partners | No — include only if present |

   Status rules:
   - Page missing (non-200) → **Fail**
   - Page exists but not linked in footer/nav → **Warn**
   - Page exists and linked in footer/nav → **Pass**
   - Optional page missing → skip, do not include row

5. **Run `check-page.py --keyword "<inferred_keyword>"`** — parse the JSON output for H1, title,
   meta description, canonical, and URL slug

6. **i18n / hreflang check** — only run if the page contains hreflang tags or `<html lang>` suggests multi-language:
   - **Skip entirely (N/A)** if no hreflang tags found and site appears single-language
   - If hreflang tags present, check:
     - **Reciprocal symmetry**: every URL referenced must link back to all other variants — any broken link = Fail
     - **Language codes**: must be valid BCP 47 (e.g. `zh-CN` not `zh`, `en-US` not `en-us`) — wrong code = Warn
     - **x-default**: should be present for language-selector or fallback pages — missing = Warn
     - **html[lang] attribute**: must match the primary hreflang of the page — mismatch = Warn
     - **URL structure**: recommended pattern — default language (usually `en`) at root with no prefix,
       other languages under subpaths (`/zh/`, `/es/`).
       - `/page` (en) + `/zh/page` + `/es/page` → Pass
       - `/en/page` + `/zh/page` → Warn (en prefix is redundant, wastes crawl depth)
       - Only flag if the pattern is clearly inconsistent or en is unnecessarily prefixed

7. **Schema (JSON-LD) check** — inspect the page's `<script type="application/ld+json">` blocks:
   - Detect page type first (Homepage / Article / Product / FAQ / HowTo / LocalBusiness / Other)
   - Map page type → expected `@type` and required fields:

   | Page Type | Expected @type | Min. required fields |
   |---|---|---|
   | Homepage | WebSite + Organization | name, url, logo |
   | Blog / Article | Article or BlogPosting | headline, datePublished, author, image |
   | Product | Product | name, image, offers (price, priceCurrency) |
   | FAQ | FAQPage | mainEntity[].name, acceptedAnswer.text |
   | How-to | HowTo | name, step[].text |
   | Local business | LocalBusiness | name, address, telephone |
   | Generic landing | — | N/A — skip, no widely-supported type |

   - Pass: correct @type present, all required fields valid, no conflicts
   - Warn: @type present but missing recommended fields
   - Fail: expected @type missing entirely
   - N/A: generic landing page — do not penalize

7. **Summarize findings** — each finding must follow the Evidence / Impact / Fix format

7. **Priority actions** — list the top 3 highest-impact fixes

8. **Render report** — save to `reports/<hostname>-<slug>-audit.html`, then ask user to open

9. **Upgrade prompt** — if issues beyond basic scope are found, suggest `seo-audit-full`

---

## Report Detail Writing Rules

**The Detail cell in check tables must follow these rules — no exceptions:**

**Pass → one short phrase. No lists, no elaboration.**
```
Good: "Valid XML urlset · 104 URLs · referenced in robots.txt."
Bad:  "Valid XML urlset with 104 URLs. Correctly referenced in robots.txt.
       Blog posts are likely indexed through this sitemap."
```

**Warn → one `<div class="detail-issue">` with ≤2 bullet points. One `<div class="detail-fix">` with the fix.**
```
Good:
  <div class="detail-issue">· Title 48 chars — 2 below minimum. · Year "2026" will date the page.</div>
  <div class="detail-fix">Expand to 50–60 chars; remove year if evergreen.</div>

Bad: three-sentence prose explaining what a title tag is and why length matters.
```

**Fail → same as Warn. Lead with the exact failure. No background explanations.**

Do NOT explain what a check is, do NOT repeat information already visible in the status badge,
do NOT treat the reader as unfamiliar with SEO basics.

---

## Mandatory Finding Format

Every important finding **must** follow this structure:

```
**Finding: [Finding Title]**

- **Evidence:** [What was observed — direct quote, screenshot ref, or measurable data]
- **Impact:** [Why this matters for SEO or UX]
- **Fix:** [Specific, actionable recommendation]
```

Do not write vague conclusions. If evidence is insufficient, state assumptions explicitly.

---

## Upgrade Prompt

Include this at the end of every basic audit report:

> **Want a deeper analysis?**
> This was a basic SEO audit covering site-level signals and core on-page checks.
> For advanced technical SEO, content quality scoring, structured data analysis, and full crawl-based findings, use the `seo-audit-full` skill.

---

## Reference Files

- Detailed audit scope and field definitions: [references/REFERENCE.md](references/REFERENCE.md)
- Final HTML report template: [assets/report-template.html](assets/report-template.html)
- Site-level check script: [scripts/check-site.py](scripts/check-site.py)
- Page-level check script: [scripts/check-page.py](scripts/check-page.py)
- Raw page fetcher: [scripts/fetch-page.py](scripts/fetch-page.py)
