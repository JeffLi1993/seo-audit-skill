# seo-audit — Reference Guide

This document provides detailed field definitions, audit scope, edge case guidance, and agent instructions for the `seo-audit` basic SEO audit skill.

---

## Positioning

`seo-audit` is the **default, lightweight entry point** for SEO auditing. It covers the most essential SEO signals that can be assessed quickly, without requiring source code access, crawl data, or performance tooling.

**Target audience:**
- Users doing a first-pass check on a page
- Clients who want a readable summary, not a technical report
- Scenarios where only the live URL is available

**Not suitable for:**
- Deep technical audits (use `seo-audit-full`)
- Multi-page site audits
- Audits requiring GSC data, crawl logs, or CWV metrics

---

## Script + LLM Division of Responsibility

The `check-page.py` script uses a **two-layer design** for H1 keyword analysis:

| Layer | Who | What |
|---|---|---|
| Layer 1 | Script | Mechanical checks: uniqueness, length, full/partial/no string match |
| Layer 2 | Agent (LLM) | Semantic judgment: does H1 cover the keyword's search intent? |

**When `h1.llm_review_required == true`:**
The script found a partial string match (e.g. keyword = "AI computer", H1 = "Best Personal AI").
It cannot determine if this qualifies as a valid natural variant — that requires language understanding.
The agent must read `h1.values[0]` + the keyword and judge:

- Does the H1 semantically cover the keyword's search intent?
- Would a user searching for this keyword consider this H1 relevant?
- Is this a natural variant (acceptable) or a keyword gap (needs fix)?

**`keyword_match` field values:**

| Value | Meaning | LLM action required |
|---|---|---|
| `"full"` | Keyword string found verbatim in H1 | None |
| `"partial"` | At least one keyword word (>3 chars) found | Yes — semantic judgment |
| `"none"` | No keyword words found | None — flag as missing |
| `"unverified"` | No `--keyword` passed | None — note as unverified |

---

## Audit Scope — What Basic Report Checks

### Site-Level Checks

| Check | What to Verify | Pass Condition |
|-------|---------------|----------------|
| `sitemap.xml` | Does `{domain}/sitemap.xml` return a valid XML sitemap? | HTTP 200, valid XML, at least one `<url>` entry |
| `robots.txt` | Does `{domain}/robots.txt` exist? Any obvious blocking rules? | HTTP 200, no `Disallow: /` for Googlebot |

**How to check:**
- Attempt to fetch `{url_origin}/sitemap.xml` and `{url_origin}/robots.txt`
- If the page URL is the only available input, note that site-level checks rely on public accessibility

**Edge cases:**
- Sitemap may be referenced in `robots.txt` under `Sitemap:` directive — check both
- Some sites use non-standard paths (e.g. `/sitemap_index.xml`) — note this as a finding if the default path fails
- If robots.txt is inaccessible (non-200), flag as a moderate issue

---

### Page-Level Checks

| Check | What to Verify | Pass Condition |
|-------|---------------|----------------|
| H1 uniqueness | Is there exactly one `<h1>` on the page? | Exactly 1 H1 tag present |
| H1 content | Does the H1 reflect the page's primary topic? | H1 is descriptive and keyword-relevant |
| Title tag | Is `<title>` present, non-empty, and within 50–60 characters? | Present, 50–60 chars recommended |
| Meta description | Is `<meta name="description">` present and within 120–160 characters? | Present, 120–160 chars recommended |
| Canonical tag | Is `<link rel="canonical">` present and pointing to the correct URL? | Present, self-referencing or correct canonical |

> **Basic audit scope note:** The above checks represent the current basic audit scope.
> Additional checks (structured data, Core Web Vitals, internal linking, image alt text, etc.) are out of scope for this skill — use `seo-audit-full`.

---

## Trigger Keywords

This skill should activate when the user says (among others):

- "audit this page"
- "check my SEO"
- "quick SEO check"
- "analyze this URL"
- "what SEO issues does this page have"
- "SEO report" (without specifying depth)
- "page audit"
- "check my meta tags"

---

## Agent Instructions

### Output quality rules

1. **Be specific.** Never say "the title tag could be improved." Say: "The title tag is 82 characters, exceeding the recommended 60-character limit. Truncation in SERPs may reduce click-through rates."
2. **Evidence first.** Always ground findings in observable evidence before stating impact.
3. **Mark assumptions clearly.** If you cannot verify a check due to missing data, write: `[ASSUMPTION]` or `[UNVERIFIED]` next to the finding.

### Handling missing data

If source HTML is unavailable:
> "On-page checks are based on rendered page content only. Results may differ if the page relies on JavaScript rendering or server-side logic not visible in the public response."

If site-level checks fail due to access restrictions:
> "Site-level checks (sitemap, robots.txt) could not be completed. The domain may restrict public access to these files, or a firewall/CDN may be blocking automated requests."

### Scope escalation — when to recommend seo-audit-full

Suggest upgrading to `seo-audit-full` when:

- More than 3 issues are found that require deeper investigation
- User mentions: performance, Core Web Vitals, structured data, competitor comparison, content strategy, crawl budget
- The page has unusual technical setup (SPA, heavy JavaScript rendering, paywalled content)
- User asks: "is that everything?" or "what else should I check?"

---

## Finding Format Reminder

Every important finding must be structured as:

```
**Finding: [Title]**
- **Evidence:** ...
- **Impact:** ...
- **Fix:** ...
```

If evidence is not available, write:
```
- **Evidence:** [UNVERIFIED] Unable to confirm — [reason]. Assumption: [what is assumed].
```

---

## Limitations Disclosure

Always include a limitations section in the final report. Use language like:

> This audit is based on publicly accessible page signals at the time of analysis. It does not include: source code review, JavaScript rendering audit, Core Web Vitals metrics, Google Search Console data, crawl log analysis, or competitive benchmarking. For a full audit, use `seo-audit-full`.
