---
name: seo-optimize
description: >-
  Generate and optionally apply direct SEO optimizations for a website page.
  Use when the user asks to "optimize this site for SEO", "fix SEO tags",
  "improve rankings", "write title/meta/schema", "apply SEO fixes", or wants
  implementation-ready SEO changes rather than an audit report only.
metadata:
  author: Jeff
  version: "1.0"
---

# seo-optimize

Use this skill when the user wants direct SEO optimization output for a website page.
The goal is to produce implementation-ready changes, not only findings.

## Inputs

| Input | Required | Notes |
|---|---:|---|
| URL | Yes | Public page URL to optimize |
| Primary keyword | Recommended | Enables stronger title, H1, meta, slug, and content suggestions |
| Brand | Recommended | Used in title, schema, and social tags |
| Local HTML file | Optional | Enables `--apply` mode for basic on-page edits |
| Audience / business goal | Optional | Improves meta description and content brief specificity |

If the keyword or brand is missing, infer them from the page title, H1, and host, then state that they were inferred.

## Workflow

1. Run the optimizer CLI from the repository root:

```bash
python seo-audit/scripts/seo-optimize.py https://example.com \
  --keyword "primary keyword" \
  --brand "Brand"
```

2. For JSON output, use:

```bash
python seo-audit/scripts/seo-optimize.py https://example.com \
  --keyword "primary keyword" \
  --brand "Brand" \
  --format json
```

3. To update a local HTML file with low-risk fields:

```bash
python seo-audit/scripts/seo-optimize.py https://example.com \
  --html-file ./index.html \
  --keyword "primary keyword" \
  --brand "Brand" \
  --apply
```

`--apply` updates:

- `<title>`
- `<meta name="description">`
- `<link rel="canonical">`
- the first `<h1>`

It also saves a timestamped backup before writing.

## Output

The optimizer saves a kit to `reports/<site>-seo-optimization.md` by default.
Every run must also produce a local HTML audit report before optimization and
a comparison report after optimization.

Required local report URLs:

```text
Audit report -> http://127.0.0.1:8766/<site>-audit.html
Comparison report -> http://127.0.0.1:8766/<site>-comparison.html
```

Execution order:

1. Generate the before-audit HTML report.
2. Generate optimization output and optionally apply local HTML edits.
3. Generate the before-vs-after comparison HTML report.

The kit includes:

- priority fixes ranked P1/P2/P3
- optimized head tags
- recommended H1
- JSON-LD schema snippet
- robots.txt snippet
- sitemap.xml snippet
- content brief with H2s, keyword placement, and internal link targets

## Quality Rules

- Use audit script JSON as evidence for priorities.
- Keep generated title tags within 60 characters when possible.
- Keep generated meta descriptions within 160 characters when possible.
- Do not invent factual claims about customers, pricing, certifications, awards, or metrics.
- Treat local `--apply` as a basic first pass. More complex framework edits need normal code inspection.
