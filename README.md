# seo-audit-skill

**English** · [中文](README.zh.md)

Reusable Agent Skills for single-page SEO auditing. Give it a URL — get a structured HTML report with actionable findings.

Built on a **Script + LLM two-layer architecture**: Python scripts handle deterministic checks (HTTP status, XML parsing, string matching), while the LLM handles semantic judgment (keyword intent, content quality, page type inference). Works with Claude Code, Cursor, and any agent runtime that supports SKILL.md.

---

## Report Output

Each audit produces a standalone HTML report saved to `reports/<hostname>-audit.html`.

| Section | What you get |
|---|---|
| **Audit Summary** | One-line verdict + critical / warnings / passing at a glance |
| **Site Checks** | Crawlability · URL Canonicalization · i18n · Schema · E-E-A-T |
| **Page Checks** | PageSpeed · TDK · H1 · Headings · Word Count · Internal Links |
| **Priority Actions** | Top 3 highest-impact fixes, ranked |
| **Insight Walkthrough** | Evidence → Impact → Fix for each major finding |

```
audit this page: https://openclaw.ai
→ ✅ Report saved → reports/openclaw-ai-audit.html
```

| Website | Audit Summary | Site Checks | Page Checks & insights |
|---|---|---|---|
| colaos.ai | <img src="assets/0-0.png" alt="Audit Summary" width="240" /> | <img src="assets/0-1.png" alt="Site Checks" width="240" /> | <img src="assets/0-2.png" alt="Page Checks and insights" width="240" /> |

---

## Skills

| Skill | Tier | When to use |
|---|---|---|
| `seo-audit` | Basic | Default — give it a URL, get a 20+ check structured report |
| `seo-audit-full` | Full | Deep: Core Web Vitals, content quality, GSC data, competitor gap |

---

## Audit Coverage

### Site-level

| Check | What it verifies | Basic | Full |
|---|---|:---:|:---:|
| robots.txt | RFC 9309 group parsing, Allow/Disallow logic, Googlebot status, Sitemap directives | ✅ | ✅ |
| sitemap.xml | Valid XML, URL count, follows Sitemap directive path from robots.txt | ✅ | ✅ |
| 404 Handling | True 404 vs soft 404 (200) vs redirect-to-homepage (301) | ✅ | ✅ |
| URL Canonicalization | HTTP→HTTPS redirect, www consistency, trailing slash, canonical tag match | ✅ | ✅ |
| i18n / hreflang | Reciprocal symmetry, BCP 47 codes, x-default, URL path structure | ✅ | ✅ |
| Schema (JSON-LD) | @type detection, required fields, @graph flattening, type conflict check | ✅ | ✅ |
| E-E-A-T Trust Pages | About / Contact / Privacy / Terms — exists (HTTP 200) + reachable from footer/nav | ✅ | ✅ |
| PageSpeed Insights | Performance / Accessibility / Best Practices / SEO — mobile + desktop | ✅ | ✅ |
| GSC Crawl Status | Index coverage, crawl errors, blocked resources | — | ✅ |
| Core Web Vitals | LCP, CLS, INP from CrUX field data | — | ✅ |

### Page-level

| Check | What it verifies | Basic | Full |
|---|---|:---:|:---:|
| URL Slug | Lowercase, hyphenated, keyword present, stop word & stuffing detection | ✅ | ✅ |
| Title Tag | 50–60 chars, keyword position, homepage vs inner page rules | ✅ | ✅ |
| Meta Description | 120–160 chars, keyword match, concrete value prop (not generic fluff) | ✅ | ✅ |
| H1 Tag | Single H1, keyword match (full / partial / none), semantic intent review | ✅ | ✅ |
| Canonical Tag | Self-referencing, matches final URL after redirects | ✅ | ✅ |
| Image Alt Text | Alt attribute check on all `<img>`, JS-render detection | ✅ | ✅ |
| Word Count | Body text ≥ 500 words, thin content flag | ✅ | ✅ |
| Keyword Placement | Primary keyword within first 100 body words | ✅ | ✅ |
| Heading Structure | H2 count (target 5–7), H3/H2 ratio, keyword distribution in H2s | ✅ | ✅ |
| Internal Links | Same-origin links (excl. nav/footer), equity distribution | ✅ | ✅ |
| OG / Social Tags | og:image, twitter:card, social preview completeness | — | ✅ |
| Content Quality | E-E-A-T depth, readability, specificity vs competitors | — | ✅ |
| Robots Meta | noindex, nofollow, max-snippet directives | — | ✅ |

---

## Structure

```
seo-audit-skill/
├── seo-audit/
│   ├── SKILL.md                       # Skill definition + agent workflow
│   ├── references/REFERENCE.md        # Field definitions, edge cases
│   ├── assets/report-template.html    # HTML output template
│   └── scripts/
│       ├── check-site.py              # robots.txt + sitemap → JSON
│       ├── check-page.py              # TDK + H1 + canonical + slug → JSON
│       ├── check-schema.py            # JSON-LD extraction + validation → JSON
│       ├── check-pagespeed.py         # PageSpeed Insights API → JSON
│       └── fetch-page.py              # Raw HTML fetcher, SSRF protection
└── seo-audit-full/
    ├── SKILL.md
    ├── references/REFERENCE.md
    └── assets/report-template.html
```

---

## Architecture: Script + LLM

```
URL
 │
 ▼
┌──────────────────────────────────────────────────┐
│  Layer 1 · Python Scripts                        │
│  Deterministic checks → structured JSON          │
│                                                  │
│  check-site.py      robots.txt, sitemap (RFC 9309)
│  check-page.py      H1 / title / meta / canonical│
│  check-schema.py    JSON-LD @type + field valid. │
│  check-pagespeed.py PSI API (mobile + desktop)   │
│  fetch-page.py      raw HTML + SSRF protection   │
└───────────────────────┬──────────────────────────┘
                        │ JSON + llm_review_required flag
                        ▼
┌──────────────────────────────────────────────────┐
│  Layer 2 · LLM Agent                             │
│  Semantic judgment on flagged fields only         │
│                                                  │
│  · Keyword intent alignment (H1 / title)         │
│  · Meta description quality & specificity        │
│  · Page type → expected Schema @type mapping     │
│  · E-E-A-T trust page reachability (footer/nav)  │
│  · Content analysis (word count, heading, links) │
└───────────────────────┬──────────────────────────┘
                        │
                        ▼
              report-template.html
              → reports/<hostname>-audit.html
```

**Why two layers?** Scripts handle the 80% of checks that are deterministic — does `robots.txt` exist? Is the title 55 characters? The LLM handles the 20% that require understanding — does this H1 semantically cover the intent of "AI workflow automation"? The `llm_review_required` flag ensures the LLM only intervenes when the script explicitly cannot make the call. No hallucination on factual checks, no blind spots on semantic ones.

---

## Installation

**Option 1: CLI (Recommended)**

```bash
npx skills add JeffLi1993/seo-audit-skill

# Or install a specific tier
npx skills add JeffLi1993/seo-audit-skill --skill seo-audit
npx skills add JeffLi1993/seo-audit-skill --skill seo-audit-full
```

**Option 2: Claude Code Plugin**

```bash
/plugin marketplace add JeffLi1993/seo-audit-skill
/plugin install seo-audit-skill
```

## Usage

```
audit this page: https://example.com
```
---

## Scripts

All scripts output structured JSON to stdout. Exit code `0` = pass/warn, `1` = any fail.

| Script | What it does |
|---|---|
| `check-site.py` | robots.txt + sitemap — RFC 9309 group parsing, Allow override, multi-Sitemap path |
| `check-page.py` | H1 / title / meta / canonical / URL slug — keyword match with stop-word-aware filter |
| `check-schema.py` | JSON-LD extraction, @graph flattening, @type + required field validation |
| `check-pagespeed.py` | PageSpeed Insights API scores — mobile + desktop, 4 categories |
| `fetch-page.py` | Raw HTML fetch — SSRF protection, redirect chain tracking, Googlebot UA option |

**Dependency:** `pip install requests`

---

## License

MIT
