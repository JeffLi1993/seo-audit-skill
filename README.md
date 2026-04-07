# seo-audit-skill

**English** · [中文](README.zh.md)

Reusable Agent Skills for single-page SEO auditing — Basic and Full tiers.  

Works with Claude, Cursor, and OpenClaw.

---

## Skills

| Skill | Tier | When to use |
|---|---|---|
| `seo-audit` | Basic | Quick first-pass check — give it a URL, get a structured report |
| `seo-audit-full` | Full | Deep audit: technical SEO, on-page, schema, E-E-A-T, performance |

### What's covered

| Check | Basic | Full |
|---|:---:|:---:|
| robots.txt | ✅ | ✅ |
| sitemap.xml | ✅ | ✅ |
| Canonical strategy | ✅ | ✅ |
| URL structure | ✅ | ✅ |
| TDK (title, description, H1) | ✅ | ✅ |
| H2/H3 heading hierarchy | ✅ | ✅ |
| URL keyword | ✅ | ✅ |
| Schema structured data | ✅ | ✅ |
| i18n / hreflang | ✅ | ✅ |
| E-E-A-T signals | ❌ | ✅ |
| GSC crawl status | ❌ | ✅ |
| Core Web Vitals | ❌ | ✅ |
| PageSpeed Insights | ❌ | ✅ |
| Page content — quantity | ❌ | ✅ |
| Page content — quality | ❌ | ✅ |

> ¹ Requires GSC Service Account
> ² Requires PageSpeed API Key

---

## Structure

```
seo-audit-skill/
├── seo-audit/
│   ├── SKILL.md
│   ├── references/REFERENCE.md
│   ├── assets/report-template.html
│   └── scripts/
│       ├── fetch-page.py
│       ├── check-site.py
│       └── check-page.py
└── seo-audit-full/
    ├── SKILL.md
    ├── references/REFERENCE.md
    └── assets/report-template.html
```

---

## Installation

**Option 1: CLI Install (Recommended)**

```bash
# Install all skills
npx skills add JeffLi1993/seo-audit-skill

# Install a specific skill
npx skills add JeffLi1993/seo-audit-skill --skill seo-audit
npx skills add JeffLi1993/seo-audit-skill --skill seo-audit-full

# List available skills
npx skills add JeffLi1993/seo-audit-skill --list
```

**Option 2: Claude Code Plugin**

```bash
# Add the marketplace
/plugin marketplace add JeffLi1993/seo-audit-skill

# Install
/plugin install seo-audit-skill
```

## Usage

Once installed, just say:

```
audit this page: https://example.com
```

```
deep audit: https://example.com
```

---

## Scripts (seo-audit)

| Script | What it does |
|---|---|
| `check-site.py` | Checks robots.txt + sitemap.xml, outputs JSON |
| `check-page.py` | Checks H1 / title / meta description / canonical, outputs JSON |
| `fetch-page.py` | Fetches raw page HTML with SSRF protection |

All scripts output structured JSON to stdout. Exit code `0` = pass/warn, `1` = any fail.

---

## License

MIT
