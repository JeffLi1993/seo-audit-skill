# seo-audit-skill

**English** · [中文](README.zh.md) · [SEO Audit Agent Skill](https://nanoskill.ai/skills/seo-audit)

Reusable Agent Skills for single-page SEO auditing and optimization. Give it a URL to get a structured HTML report, or run the optimizer CLI to generate ready-to-use title tags, meta descriptions, H1, canonical tags, JSON-LD, robots.txt, sitemap.xml, and a content brief.

Built on a **Script + LLM two-layer architecture**: Python scripts handle deterministic checks (HTTP status, XML parsing, string matching), while the LLM handles semantic judgment (keyword intent, content quality, page type inference). Works with Claude Code, Cursor, and any agent runtime that supports SKILL.md.

## Best practices

1. Run `npx skills add JeffLi1993/seo-audit-skill`, then audit your page (for example: `audit this page: https://example.com`). Open the report at `reports/<hostname>-audit.html` and review it yourself: keep what matters for your goals, skip what does not.
2. Run the optimizer when you want direct implementation guidance:

```bash
python seo-audit/scripts/seo-optimize.py https://example.com \
  --keyword "ai workflow automation" \
  --brand "Acme"
```

3. If you have a local HTML file, let the optimizer apply low-risk changes directly:

```bash
python seo-audit/scripts/seo-optimize.py https://example.com \
  --html-file ./index.html \
  --keyword "ai workflow automation" \
  --brand "Acme" \
  --apply
```

The `--apply` mode updates `<title>`, `<meta name="description">`, canonical, and the first H1, then saves a timestamped backup.

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

## Direct SEO Optimization

`seo-audit/scripts/seo-optimize.py` turns audit findings into an optimization kit saved to `reports/<site>-seo-optimization.md`.

Detailed skill docs: [seo-optimize README](seo-optimize/README.md) · [中文](seo-optimize/README.zh.md)

Every optimizer run also writes a required HTML audit report first and serves it from the local report server:

```text
Audit report -> http://127.0.0.1:8766/moshuopc-com-audit.html
Comparison report -> http://127.0.0.1:8766/moshuopc-com-comparison.html
```

Flow: generate the before-audit report, generate/apply optimization output, then generate a before-vs-after comparison report.
The comparison report keeps the original audit-report styling and shows the complete original audit on the left and the SEO-optimized target audit on the right on desktop screens.

![SEO optimization comparison report](assets/seo-optimize-comparison-split.png)

| Output | What it contains |
|---|---|
| Recommended head tags | Optimized title, meta description, canonical, OG, and Twitter Card tags |
| H1 | One page-topic H1 tuned to the primary keyword |
| JSON-LD | Page-type schema snippet for homepage, article, product, FAQ, or generic pages |
| robots.txt / sitemap.xml | Crawlability snippets based on the target URL |
| Content brief | Recommended H2 sections, keyword placement, and internal link targets |
| Priority actions | P1/P2/P3 fixes mapped from the audit results |

Options:

```bash
# Markdown report
python seo-audit/scripts/seo-optimize.py https://example.com -k "primary keyword" --brand "Brand"

# JSON output for pipelines
python seo-audit/scripts/seo-optimize.py https://example.com -k "primary keyword" --format json

# Patch a local HTML file
python seo-audit/scripts/seo-optimize.py https://example.com --html-file ./index.html -k "primary keyword" --apply
```

`--keyword` and `--brand` are recommended. If omitted, the tool infers them from the title, H1, and host.

Report options:

```bash
python seo-audit/scripts/seo-optimize.py https://example.com \
  -k "primary keyword" \
  --reports-dir reports \
  --report-port 8766
```

Use `--no-report-server` only when you want files without starting the local server.

---

## Skills

| Skill | Tier | When to use |
|---|---|---|
| `seo-audit` | Basic | Default — give it a URL, get a 20+ check structured report |
| `seo-optimize` | Optimization | Generate tags, schema, robots/sitemap snippets, content brief, and optional local HTML edits |
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
│       ├── fetch-page.py              # Raw HTML fetcher, SSRF protection
│       └── seo-optimize.py            # Optimization kit generator + local HTML patcher
├── seo-audit-full/
│   ├── SKILL.md
│   ├── references/REFERENCE.md
│   ├── assets/report-template.html
│   └── scripts/
│       └── check-social.py            # OG + Twitter Card validation → JSON
└── seo-optimize/
    ├── SKILL.md                       # Direct optimization workflow
    ├── README.md                      # Detailed English optimizer docs
    └── README.zh.md                   # Detailed Chinese optimizer docs
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
npx skills add JeffLi1993/seo-audit-skill --skill seo-optimize
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
| `fetch-page.py` | Raw HTML fetch — SSRF protection, redirect chain tracking, Googlebot UA option |
| `seo-optimize.py` | Generates optimized tags, schema, robots/sitemap snippets, content brief, and optional local HTML edits |

`seo-optimize.py` always writes `*-audit.html` and `*-comparison.html` HTML reports. By default they are served at `http://127.0.0.1:8766/`.

**Dependency:** `pip install requests`

---

## License

MIT
