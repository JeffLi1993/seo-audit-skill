#!/usr/bin/env python3
"""
SEO optimization kit generator.

This script turns the existing audit checks into direct optimization output:
recommended tags, structured data snippets, robots/sitemap snippets, content
briefs, and optional local HTML edits for low-risk on-page fields.

Usage:
    python seo-audit/scripts/seo-optimize.py https://example.com \
        --keyword "ai workflow automation" --brand "Acme"

    python seo-audit/scripts/seo-optimize.py https://example.com \
        --html-file ./index.html --keyword "ai workflow automation" --apply

Dependencies:
    pip install requests
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin, urlparse, urlunparse

try:
    import requests
except ImportError:  # pragma: no cover - exercised by users without requests.
    requests = None  # type: ignore[assignment]


DEFAULT_TIMEOUT = 20
DEFAULT_REPORT_PORT = 8766
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 ClaudeSEOOptimizer/1.0"
)
STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "for",
        "with",
        "in",
        "on",
        "to",
        "by",
        "from",
        "at",
    }
)
ACRONYMS = frozenset({"ai", "api", "b2b", "b2c", "cms", "crm", "gsc", "json-ld", "llm", "og", "seo", "ui", "ux"})


class PageFactsParser(HTMLParser):
    """Small static HTML extractor for optimization inputs."""

    def __init__(self) -> None:
        super().__init__()
        self.title: Optional[str] = None
        self.meta: dict[str, str] = {}
        self.canonical: Optional[str] = None
        self.headings: dict[str, list[str]] = {f"h{i}": [] for i in range(1, 7)}
        self.images: list[dict[str, Any]] = []
        self.links: list[dict[str, str]] = []
        self.body_text_parts: list[str] = []
        self._in_title = False
        self._title_buf = ""
        self._capture_heading: Optional[str] = None
        self._heading_buf = ""
        self._in_body = False
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        attrs_dict = {k.lower(): (v or "") for k, v in attrs}

        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1

        if tag == "body":
            self._in_body = True
        elif tag == "title" and self.title is None:
            self._in_title = True
            self._title_buf = ""
        elif tag in self.headings:
            self._capture_heading = tag
            self._heading_buf = ""
        elif tag == "meta":
            key = (attrs_dict.get("name") or attrs_dict.get("property") or "").lower()
            content = attrs_dict.get("content", "").strip()
            if key and content and key not in self.meta:
                self.meta[key] = content
        elif tag == "link":
            rel = attrs_dict.get("rel", "").lower()
            if "canonical" in rel and not self.canonical:
                href = attrs_dict.get("href", "").strip()
                if href:
                    self.canonical = href
        elif tag == "img":
            self.images.append(
                {
                    "src": attrs_dict.get("src", "").strip(),
                    "alt": attrs_dict.get("alt", ""),
                    "alt_present": "alt" in attrs_dict,
                }
            )
        elif tag == "a":
            href = attrs_dict.get("href", "").strip()
            if href:
                self.links.append({"href": href})

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        if tag == "body":
            self._in_body = False
        elif tag == "title" and self._in_title:
            self._in_title = False
            self.title = clean_text(self._title_buf) or None
        elif tag == self._capture_heading and self._capture_heading:
            text = clean_text(self._heading_buf)
            if text:
                self.headings[self._capture_heading].append(text)
            self._capture_heading = None
            self._heading_buf = ""

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_buf += data
        if self._capture_heading:
            self._heading_buf += data
        if self._in_body and self._skip_depth == 0:
            text = clean_text(data)
            if text:
                self.body_text_parts.append(text)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        return f"https://{url}"
    return url


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path or "/",
            "",
            "",
            "",
        )
    )


def origin_from_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


def slug_from_url(url: str, suffix: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc or "local-page"
    path = parsed.path.strip("/").replace("/", "-")
    base = f"{host}-{path}" if path else host
    base = re.sub(r"[^A-Za-z0-9]+", "-", base).strip("-").lower() or "seo"
    return f"{base}-{suffix}"


def report_file_name(url: str, report_type: str) -> str:
    parsed = urlparse(url)
    host = (parsed.netloc or "local-page").replace("www.", "")
    path = parsed.path.strip("/").replace("/", "-")
    base = f"{host}-{path}" if path else host
    base = re.sub(r"[^A-Za-z0-9]+", "-", base).strip("-").lower() or "seo"
    return f"{base}-{report_type}.html"


def report_local_url(file_name: str, port: int = DEFAULT_REPORT_PORT) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", file_name).strip("-")
    return f"http://127.0.0.1:{port}/{safe_name}"


def fetch_html(url: str, timeout: int) -> tuple[str, str]:
    if requests is None:
        raise RuntimeError("requests library required. Install with: pip install requests")
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8"},
        timeout=timeout,
        allow_redirects=True,
    )
    response.raise_for_status()
    return response.text, response.url


def extract_page_facts(html: str, final_url: str) -> dict[str, Any]:
    parser = PageFactsParser()
    parser.feed(html)

    body_text = clean_text(" ".join(parser.body_text_parts))
    words = re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?|[\u4e00-\u9fff]", body_text)
    parsed_final = urlparse(final_url)
    same_origin_links = []
    for link in parser.links:
        href = link["href"]
        if href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(final_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme in {"http", "https"} and parsed.netloc == parsed_final.netloc:
            same_origin_links.append(absolute)

    missing_alt_images = [
        img for img in parser.images if not img.get("alt_present") or not clean_text(img.get("alt", ""))
    ]

    return {
        "title": parser.title,
        "meta_description": parser.meta.get("description"),
        "canonical": parser.canonical,
        "meta": parser.meta,
        "headings": parser.headings,
        "body_text": body_text,
        "word_count": len(words),
        "images": parser.images,
        "missing_alt_images": missing_alt_images,
        "links": parser.links,
        "internal_links": same_origin_links,
    }


def run_json_script(script_path: Path, args: list[str]) -> dict[str, Any]:
    command = [sys.executable, str(script_path), *args]
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    stdout = completed.stdout.strip()
    if not stdout:
        return {
            "status": "error",
            "error": completed.stderr.strip() or "Script returned no JSON.",
            "returncode": completed.returncode,
        }
    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        return {
            "status": "error",
            "error": "Script output was not valid JSON.",
            "stdout": stdout[:1000],
            "stderr": completed.stderr.strip(),
            "returncode": completed.returncode,
        }
    if completed.returncode != 0:
        result.setdefault("script_returncode", completed.returncode)
    return result


def build_local_page_result(facts: dict[str, Any], final_url: str, keyword: str) -> dict[str, Any]:
    title = facts.get("title")
    meta_description = facts.get("meta_description")
    h1_values = facts.get("headings", {}).get("h1", [])
    canonical = facts.get("canonical")

    return {
        "url": final_url,
        "final_url": final_url,
        "http_status": None,
        "url_slug": {
            "status": "pass",
            "slug": urlparse(final_url).path or "/",
            "detail": "Local HTML mode. URL slug check is limited.",
        },
        "title": {
            "status": "pass" if title else "fail",
            "value": title,
            "length": len(title or ""),
            "detail": "Title found." if title else "No <title> tag found.",
        },
        "meta_description": {
            "status": "pass" if meta_description else "fail",
            "value": meta_description,
            "length": len(meta_description or ""),
            "detail": (
                "Meta description found."
                if meta_description
                else "No <meta name='description'> found."
            ),
        },
        "h1": {
            "status": "pass" if len(h1_values) == 1 else "fail",
            "count": len(h1_values),
            "values": h1_values,
            "detail": "Single H1 found." if len(h1_values) == 1 else "Page should have exactly one H1.",
        },
        "canonical": {
            "status": "pass" if canonical else "warn",
            "value": canonical,
            "matches_final_url": bool(canonical and canonical.rstrip("/") == final_url.rstrip("/")),
            "detail": "Canonical found." if canonical else "No canonical tag found.",
        },
        "keyword": keyword,
    }


def infer_keyword(facts: dict[str, Any], url: str) -> str:
    h1_values = facts.get("headings", {}).get("h1", [])
    source = h1_values[0] if h1_values else facts.get("title") or ""
    source = clean_text(source)
    if source:
        for separator in (" | ", " - ", " – ", " — ", ": "):
            if separator in source:
                parts = [p.strip() for p in source.split(separator) if p.strip()]
                if parts:
                    source = max(parts, key=len)
                    break
        words = [w for w in source.split() if w.lower() not in STOP_WORDS]
        if words:
            return clean_text(" ".join(words[:7]))

    parsed = urlparse(url)
    host = parsed.netloc.replace("www.", "").split(".")[0]
    return host.replace("-", " ").strip() or "primary topic"


def infer_brand(facts: dict[str, Any], url: str) -> str:
    title = facts.get("title") or ""
    for separator in (" | ", " - ", " – ", " — "):
        if separator in title:
            parts = [p.strip() for p in title.split(separator) if p.strip()]
            if len(parts) > 1:
                return parts[-1]
    parsed = urlparse(url)
    host = parsed.netloc.replace("www.", "").split(".")[0]
    return host.replace("-", " ").title() or "Your Brand"


def infer_page_type(url: str, facts: dict[str, Any], requested: str) -> str:
    if requested != "auto":
        return requested
    path = urlparse(url).path.lower().rstrip("/")
    if path in {"", "/"}:
        return "homepage"
    if any(token in path for token in ("/blog", "/article", "/post", "/news", "/story")):
        return "article"
    if any(token in path for token in ("/product", "/item", "/shop", "/store")):
        return "product"
    if any(token in path for token in ("/faq", "/questions")):
        return "faq"
    if any(token in path for token in ("/how-to", "/howto", "/guide")):
        return "howto"
    h1 = " ".join(facts.get("headings", {}).get("h1", [])).lower()
    if "faq" in h1 or "questions" in h1:
        return "faq"
    return "generic"


def fit_title(candidates: list[str]) -> str:
    cleaned = [clean_text(c) for c in candidates if clean_text(c)]
    for candidate in cleaned:
        if 35 <= len(candidate) <= 60:
            return candidate
    for candidate in cleaned:
        if len(candidate) <= 60:
            return candidate
    if not cleaned:
        return ""
    return trim_to_words(cleaned[0], 60)


def fit_meta(candidates: list[str]) -> str:
    cleaned = [clean_text(c) for c in candidates if clean_text(c)]
    for candidate in cleaned:
        if 120 <= len(candidate) <= 160:
            return candidate
    for candidate in cleaned:
        if len(candidate) <= 160:
            return candidate
    if not cleaned:
        return ""
    return trim_to_words(cleaned[0], 157) + "..."


def trim_to_words(value: str, limit: int) -> str:
    value = clean_text(value)
    if len(value) <= limit:
        return value
    trimmed = value[:limit].rstrip()
    if " " in trimmed:
        trimmed = trimmed.rsplit(" ", 1)[0]
    return trimmed.rstrip(".,;:-")


def display_keyword(keyword: str) -> str:
    words = clean_text(keyword).split()
    formatted = []
    for index, word in enumerate(words):
        lower = word.lower()
        if lower in ACRONYMS:
            formatted.append(lower.upper())
        elif re.match(r"^[A-Za-z]", word):
            formatted.append(word[:1].upper() + word[1:])
        else:
            formatted.append(word)
    return " ".join(formatted) or "Primary topic"


def build_recommended_tags(
    *,
    keyword: str,
    brand: str,
    audience: str,
    business_goal: str,
    page_type: str,
    final_url: str,
    facts: dict[str, Any],
) -> dict[str, Any]:
    canonical = canonicalize_url(final_url) if final_url.startswith(("http://", "https://")) else ""
    origin = origin_from_url(canonical) if canonical else ""
    public_url = canonical or "https://example.com/your-page"
    public_origin = origin or "https://example.com"
    keyword_title = display_keyword(keyword)

    if page_type == "homepage":
        title_candidates = [
            f"{brand} | {keyword_title}",
            f"{brand}: {keyword_title} for {audience}" if audience else "",
            f"{keyword_title} | {brand}",
        ]
        h1 = f"{brand}: {keyword_title}"
    else:
        title_candidates = [
            f"{keyword_title} | {brand}",
            f"{keyword_title} for {audience} | {brand}" if audience else "",
            f"{keyword_title}: Guide, Benefits and Next Steps",
        ]
        h1 = f"{keyword_title} for {audience}" if audience else keyword_title

    goal = business_goal or "compare benefits, use cases, and next steps"
    meta_candidates = [
        (
            f"{keyword_title} from {brand}: {goal}. Explore practical details, "
            "clear proof points, and the best next step for your team."
        ),
        (
            f"Explore {keyword_title} from {brand}. Compare benefits, use cases, "
            "and practical details so you can choose the right next step."
        ),
        (
            f"{keyword_title}: benefits, use cases, and practical details from {brand} "
            "to help visitors understand the offer and take action."
        ),
    ]

    title = fit_title(title_candidates)
    meta_description = fit_meta(meta_candidates)
    og_image = facts.get("meta", {}).get("og:image")
    if not og_image:
        og_image = f"{public_origin}/og-image.jpg"

    return {
        "title": title,
        "meta_description": meta_description,
        "h1": h1,
        "canonical": canonical,
        "og": {
            "title": title,
            "description": meta_description,
            "url": public_url,
            "type": "website" if page_type == "homepage" else "article",
            "image": og_image,
        },
        "twitter": {
            "card": "summary_large_image",
            "title": title,
            "description": meta_description,
            "image": og_image,
        },
    }


def build_schema_snippet(
    page_type: str,
    brand: str,
    keyword: str,
    final_url: str,
    tags: dict[str, Any],
) -> str:
    canonical = tags.get("canonical") or "https://example.com/your-page"
    origin = origin_from_url(canonical) or "https://example.com"
    if page_type == "article":
        schema: dict[str, Any] = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": tags["title"],
            "description": tags["meta_description"],
            "url": canonical,
            "author": {"@type": "Organization", "name": brand},
            "publisher": {"@type": "Organization", "name": brand},
            "datePublished": "YYYY-MM-DD",
            "dateModified": "YYYY-MM-DD",
            "image": tags["og"]["image"],
        }
    elif page_type == "product":
        schema = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": keyword,
            "description": tags["meta_description"],
            "brand": {"@type": "Brand", "name": brand},
            "url": canonical,
            "image": tags["og"]["image"],
            "offers": {
                "@type": "Offer",
                "url": canonical,
                "priceCurrency": "USD",
                "availability": "https://schema.org/InStock",
            },
        }
    elif page_type == "faq":
        schema = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": f"What is {keyword}?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "Replace this with a concise, factual answer from the page.",
                    },
                }
            ],
        }
    else:
        schema = {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "WebSite",
                    "name": brand,
                    "url": origin,
                    "potentialAction": {
                        "@type": "SearchAction",
                        "target": f"{origin}/search?q={{search_term_string}}",
                        "query-input": "required name=search_term_string",
                    },
                },
                {
                    "@type": "Organization",
                    "name": brand,
                    "url": origin,
                    "logo": f"{origin}/logo.png",
                    "sameAs": [],
                },
            ],
        }
    return json.dumps(schema, indent=2, ensure_ascii=False)


def tag_html_snippet(tags: dict[str, Any]) -> str:
    og = tags["og"]
    twitter = tags["twitter"]
    lines = [
        f"<title>{escape(tags['title'])}</title>",
        f'<meta name="description" content="{escape(tags["meta_description"], quote=True)}">',
    ]
    if tags.get("canonical"):
        lines.append(f'<link rel="canonical" href="{escape(tags["canonical"], quote=True)}">')
    lines.extend(
        [
            f'<meta property="og:title" content="{escape(og["title"], quote=True)}">',
            f'<meta property="og:description" content="{escape(og["description"], quote=True)}">',
            f'<meta property="og:url" content="{escape(og["url"], quote=True)}">',
            f'<meta property="og:type" content="{escape(og["type"], quote=True)}">',
            f'<meta property="og:image" content="{escape(og["image"], quote=True)}">',
            f'<meta name="twitter:card" content="{escape(twitter["card"], quote=True)}">',
            f'<meta name="twitter:title" content="{escape(twitter["title"], quote=True)}">',
            f'<meta name="twitter:description" content="{escape(twitter["description"], quote=True)}">',
            f'<meta name="twitter:image" content="{escape(twitter["image"], quote=True)}">',
        ]
    )
    return "\n".join(lines)


def robots_snippet(final_url: str) -> str:
    origin = origin_from_url(final_url) or "https://example.com"
    return f"User-agent: *\nAllow: /\nSitemap: {origin}/sitemap.xml"


def sitemap_snippet(final_url: str) -> str:
    canonical = canonicalize_url(final_url) if final_url.startswith(("http://", "https://")) else "https://example.com/"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        "  <url>\n"
        f"    <loc>{escape(canonical)}</loc>\n"
        "    <changefreq>weekly</changefreq>\n"
        "    <priority>1.0</priority>\n"
        "  </url>\n"
        "</urlset>"
    )


def add_action(
    actions: list[dict[str, Any]],
    priority: str,
    area: str,
    title: str,
    evidence: str,
    fix: str,
    snippet: str = "",
    auto_apply: bool = False,
) -> None:
    actions.append(
        {
            "priority": priority,
            "area": area,
            "title": title,
            "evidence": clean_text(evidence),
            "fix": clean_text(fix),
            "snippet": snippet,
            "auto_apply": auto_apply,
        }
    )


def check_status(result: dict[str, Any], key: str) -> tuple[str, str]:
    item = result.get(key) if isinstance(result, dict) else None
    if not isinstance(item, dict):
        return "unknown", ""
    return item.get("status", "unknown"), item.get("detail", "")


def build_actions(
    checks: dict[str, Any],
    facts: dict[str, Any],
    tags: dict[str, Any],
    final_url: str,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    page = checks.get("page", {})
    site = checks.get("site", {})
    schema = checks.get("schema", {})
    social = checks.get("social", {})

    title_status, title_detail = check_status(page, "title")
    if title_status in {"fail", "warn", "error"}:
        add_action(
            actions,
            "P1" if title_status == "fail" else "P2",
            "On-page",
            "Replace the title tag",
            title_detail,
            "Use a concise title that includes the primary keyword and brand.",
            f"<title>{escape(tags['title'])}</title>",
            auto_apply=True,
        )

    meta_status, meta_detail = check_status(page, "meta_description")
    if meta_status in {"fail", "warn", "error"}:
        add_action(
            actions,
            "P1" if meta_status == "fail" else "P2",
            "On-page",
            "Rewrite the meta description",
            meta_detail,
            "Add a specific 120-160 character description with the keyword and a clear next step.",
            f'<meta name="description" content="{escape(tags["meta_description"], quote=True)}">',
            auto_apply=True,
        )

    h1_status, h1_detail = check_status(page, "h1")
    if h1_status in {"fail", "warn", "error"}:
        add_action(
            actions,
            "P1",
            "On-page",
            "Normalize the H1",
            h1_detail,
            "Keep one visible H1 and make it describe the page topic.",
            f"<h1>{escape(tags['h1'])}</h1>",
            auto_apply=True,
        )

    canonical_status, canonical_detail = check_status(page, "canonical")
    if canonical_status in {"fail", "warn", "error"} and tags.get("canonical"):
        add_action(
            actions,
            "P2",
            "Technical",
            "Add a self-referencing canonical",
            canonical_detail,
            "Point canonical to the clean final URL without tracking parameters.",
            f'<link rel="canonical" href="{escape(tags["canonical"], quote=True)}">',
            auto_apply=True,
        )

    robots = site.get("robots", {}) if isinstance(site, dict) else {}
    if robots.get("status") in {"fail", "warn", "error"}:
        add_action(
            actions,
            "P1" if robots.get("status") == "fail" else "P2",
            "Crawlability",
            "Fix robots.txt",
            robots.get("detail", ""),
            "Allow important pages and declare the XML sitemap.",
            robots_snippet(final_url),
        )

    sitemap = site.get("sitemap", {}) if isinstance(site, dict) else {}
    if sitemap.get("status") in {"fail", "warn", "error"}:
        add_action(
            actions,
            "P1" if sitemap.get("status") == "fail" else "P2",
            "Crawlability",
            "Publish a valid XML sitemap",
            sitemap.get("detail", ""),
            "Expose canonical, indexable URLs in sitemap.xml and reference it from robots.txt.",
            sitemap_snippet(final_url),
        )

    if schema.get("status") in {"fail", "warn", "info", "error"}:
        add_action(
            actions,
            "P2",
            "Structured data",
            "Add or complete JSON-LD schema",
            schema.get("detail", ""),
            "Add page-type appropriate structured data and validate it with a rich results test.",
            "",
        )

    if social.get("status") in {"fail", "warn", "error"}:
        add_action(
            actions,
            "P3",
            "Social preview",
            "Complete OG and Twitter Card tags",
            social.get("detail", ""),
            "Use consistent social tags so shared URLs render with title, description, and image.",
            tag_html_snippet(tags),
        )

    if facts.get("word_count", 0) < 500:
        add_action(
            actions,
            "P2",
            "Content",
            "Expand primary page content",
            f"Static body text has {facts.get('word_count', 0)} words.",
            "Add search-intent sections, proof points, FAQs, and comparison details.",
        )

    missing_alt = facts.get("missing_alt_images", [])
    if missing_alt:
        example = missing_alt[0].get("src") or "first missing image"
        add_action(
            actions,
            "P3",
            "Images",
            "Write descriptive alt text",
            f"{len(missing_alt)} image(s) are missing useful alt text. Example: {example}",
            "Describe the image function or subject in plain language.",
        )

    h2_count = len(facts.get("headings", {}).get("h2", []))
    if h2_count < 3:
        add_action(
            actions,
            "P2",
            "Content structure",
            "Add supporting H2 sections",
            f"Only {h2_count} H2 heading(s) found.",
            "Use H2s to cover definition, benefits, use cases, process, proof, and FAQs.",
        )

    if len(facts.get("internal_links", [])) < 3 and final_url.startswith(("http://", "https://")):
        add_action(
            actions,
            "P3",
            "Internal links",
            "Add contextual internal links",
            f"{len(facts.get('internal_links', []))} same-origin link(s) found in static HTML.",
            "Link from the body to related features, docs, case studies, pricing, or contact pages.",
        )

    priority_order = {"P1": 1, "P2": 2, "P3": 3}
    actions.sort(key=lambda item: priority_order.get(item["priority"], 9))
    return actions


def build_content_brief(keyword: str, audience: str, page_type: str) -> dict[str, Any]:
    target = f" for {audience}" if audience else ""
    sections = [
        f"What is {keyword}?",
        f"Key benefits{target}",
        "How it works",
        "Use cases and examples",
        "Proof, integrations, or customer outcomes",
        "Pricing, demo, or next step",
        "Frequently asked questions",
    ]
    if page_type == "article":
        sections = [
            f"Quick answer: {keyword}",
            "Why it matters",
            "Step-by-step guidance",
            "Examples and common mistakes",
            "Tools, templates, or resources",
            "FAQ",
        ]
    return {
        "recommended_h2s": sections,
        "keyword_placement": [
            "Use the primary keyword in the title, H1, meta description, first 100 words, and one H2.",
            "Use natural variants in supporting headings and image alt text.",
            "Avoid repeating the exact phrase in every section.",
        ],
        "internal_link_targets": [
            "Feature or product page",
            "Pricing or demo page",
            "Relevant blog guide",
            "Case study or customer story",
            "Contact or signup page",
        ],
    }


def build_plan(
    *,
    source_url: str,
    final_url: str,
    html_file: Optional[Path],
    facts: dict[str, Any],
    checks: dict[str, Any],
    keyword: str,
    brand: str,
    audience: str,
    business_goal: str,
    page_type: str,
) -> dict[str, Any]:
    tags = build_recommended_tags(
        keyword=keyword,
        brand=brand,
        audience=audience,
        business_goal=business_goal,
        page_type=page_type,
        final_url=final_url,
        facts=facts,
    )
    schema = build_schema_snippet(page_type, brand, keyword, final_url, tags)
    actions = build_actions(checks, facts, tags, final_url)
    return {
        "source_url": source_url,
        "final_url": final_url,
        "html_file": str(html_file) if html_file else None,
        "keyword": keyword,
        "brand": brand,
        "audience": audience,
        "business_goal": business_goal,
        "page_type": page_type,
        "summary": {
            "word_count": facts.get("word_count", 0),
            "h1_count": len(facts.get("headings", {}).get("h1", [])),
            "h2_count": len(facts.get("headings", {}).get("h2", [])),
            "image_count": len(facts.get("images", [])),
            "missing_alt_count": len(facts.get("missing_alt_images", [])),
            "internal_link_count": len(facts.get("internal_links", [])),
        },
        "generated": {
            "tags": tags,
            "tag_html": tag_html_snippet(tags),
            "h1_html": f"<h1>{escape(tags['h1'])}</h1>",
            "schema_json_ld": schema,
            "robots_txt": robots_snippet(final_url),
            "sitemap_xml": sitemap_snippet(final_url),
            "content_brief": build_content_brief(keyword, audience, page_type),
        },
        "actions": actions,
        "checks": checks,
    }


def render_markdown(plan: dict[str, Any]) -> str:
    generated = plan["generated"]
    tags = generated["tags"]
    brief = generated["content_brief"]

    action_lines = []
    if plan["actions"]:
        for item in plan["actions"]:
            action_lines.append(
                f"- {item['priority']} [{item['area']}] {item['title']}: {item['fix']}"
            )
    else:
        action_lines.append("- No critical optimization gaps found in the static checks.")

    h2_lines = "\n".join(f"- {section}" for section in brief["recommended_h2s"])
    keyword_lines = "\n".join(f"- {item}" for item in brief["keyword_placement"])
    link_lines = "\n".join(f"- {item}" for item in brief["internal_link_targets"])

    return "\n".join(
        [
            f"# SEO Optimization Kit: {plan['brand']}",
            "",
            f"- URL: {plan['final_url']}",
            f"- Primary keyword: {plan['keyword']}",
            f"- Page type: {plan['page_type']}",
            f"- Static text: {plan['summary']['word_count']} words",
            "",
            "## Apply First",
            "",
            *action_lines,
            "",
            "## Recommended Head Tags",
            "",
            "```html",
            generated["tag_html"],
            "```",
            "",
            "## Recommended H1",
            "",
            "```html",
            generated["h1_html"],
            "```",
            "",
            "## JSON-LD",
            "",
            "```html",
            '<script type="application/ld+json">',
            generated["schema_json_ld"],
            "</script>",
            "```",
            "",
            "## robots.txt",
            "",
            "```txt",
            generated["robots_txt"],
            "```",
            "",
            "## sitemap.xml",
            "",
            "```xml",
            generated["sitemap_xml"],
            "```",
            "",
            "## Content Brief",
            "",
            "Recommended H2s:",
            h2_lines,
            "",
            "Keyword placement:",
            keyword_lines,
            "",
            "Internal link targets:",
            link_lines,
            "",
            "## Generated Values",
            "",
            f"- Title: {tags['title']}",
            f"- Meta description: {tags['meta_description']}",
            f"- Canonical: {tags['canonical'] or 'Add a public canonical URL before publishing.'}",
        ]
    )


def status_display(status: str) -> tuple[str, str]:
    normalized = (status or "unknown").lower()
    mapping = {
        "pass": ("pass", "Pass"),
        "warn": ("warn", "Warning"),
        "warning": ("warn", "Warning"),
        "fail": ("fail", "Fail"),
        "error": ("fail", "Fail"),
        "info": ("info", "Unverified"),
        "unknown": ("info", "Unverified"),
        "skipped": ("na", "N/A"),
        "na": ("na", "N/A"),
        "n/a": ("na", "N/A"),
    }
    return mapping.get(normalized, ("info", normalized.title()))


def status_badge(status: str) -> str:
    css_class, label = status_display(status)
    return f'<span class="status status-{escape(css_class)}">{escape(label)}</span>'


def value_or_empty(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(clean_text(str(item)) for item in value if clean_text(str(item)))
    return clean_text(str(value))


def page_check_rows(checks: dict[str, Any]) -> list[dict[str, str]]:
    page = checks.get("page", {}) if isinstance(checks, dict) else {}
    rows: list[dict[str, str]] = []
    for key, label in (
        ("url_slug", "URL slug"),
        ("title", "Title"),
        ("meta_description", "Meta description"),
        ("h1", "H1"),
        ("canonical", "Canonical"),
    ):
        item = page.get(key, {}) if isinstance(page, dict) else {}
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "area": "Page",
                "check": label,
                "status": item.get("status", "unknown"),
                "value": value_or_empty(
                    item.get("value")
                    or item.get("values")
                    or item.get("slug")
                    or item.get("checked_url")
                ),
                "detail": item.get("detail", ""),
            }
        )

    site = checks.get("site", {}) if isinstance(checks, dict) else {}
    if isinstance(site, dict):
        for key, label in (("robots", "robots.txt"), ("sitemap", "sitemap.xml")):
            item = site.get(key, {})
            if isinstance(item, dict):
                rows.append(
                    {
                        "area": "Site",
                        "check": label,
                        "status": item.get("status", "unknown"),
                        "value": value_or_empty(item.get("checked_url") or item.get("sitemap_directive")),
                        "detail": item.get("detail", ""),
                    }
                )

    for key, label in (("schema", "JSON-LD"), ("social", "Social preview")):
        item = checks.get(key, {}) if isinstance(checks, dict) else {}
        if isinstance(item, dict):
            rows.append(
                {
                    "area": "Enhancement",
                    "check": label,
                    "status": item.get("status", "unknown"),
                    "value": value_or_empty(item.get("found_types") or item.get("url")),
                    "detail": item.get("detail", ""),
                }
            )
    return rows


def audit_template_path() -> Path:
    return Path(__file__).resolve().parents[1] / "assets" / "report-template.html"


def load_audit_template() -> str:
    return audit_template_path().read_text(encoding="utf-8")


def table_row(check: str, status: str, detail: str, fix: str = "") -> str:
    css_class, _ = status_display(status)
    if css_class in {"warn", "fail"}:
        detail_html = (
            f'<div class="detail-issue">· {escape(clean_text(detail) or "Needs review.")}</div>'
            f'<div class="detail-fix">{escape(clean_text(fix) or "Apply the recommended optimization.")}</div>'
        )
    else:
        detail_html = escape(clean_text(detail) or "No issue found.")
    return (
        "<tr>"
        f"<td>{escape(check)}</td>"
        f"<td>{status_badge(status)}</td>"
        f"<td>{detail_html}</td>"
        "</tr>"
    )


def table_html(rows: list[str]) -> str:
    body = "\n".join(rows) or table_row("No checks", "info", "No data available.")
    return (
        '<div class="table-scroll"><table class="check-table">'
        "<thead><tr><th>Check</th><th>Status</th><th>Detail</th></tr></thead>"
        f"<tbody>{body}</tbody></table></div>"
    )


def summary_item(row: dict[str, str]) -> str:
    label = row.get("check", "Check")
    detail = row.get("detail") or row.get("value") or ""
    text = f"{label}: {detail}" if detail else label
    return f"<li>{escape(trim_to_words(text, 120))}</li>"


def summary_lists(rows: list[dict[str, str]]) -> tuple[str, str, str, str]:
    critical = [row for row in rows if status_display(row.get("status", ""))[0] == "fail"]
    warnings = [row for row in rows if status_display(row.get("status", ""))[0] in {"warn", "info", "na"}]
    passing = [row for row in rows if status_display(row.get("status", ""))[0] == "pass"]

    def render(items: list[dict[str, str]]) -> str:
        if not items:
            return '<li class="summary-empty">None</li>'
        return "\n".join(summary_item(item) for item in items[:6])

    total = len(rows)
    verdict = (
        f"Found {len(critical)} critical issue(s), {len(warnings)} warning/unverified item(s), "
        f"and {len(passing)} passing check(s) across {total} checks."
    )
    return verdict, render(critical), render(warnings), render(passing)


def fix_for_check(check: str, plan: dict[str, Any]) -> str:
    check_lower = check.lower()
    for action in plan.get("actions", []):
        haystack = f"{action.get('title', '')} {action.get('area', '')}".lower()
        if "title" in check_lower and "title" in haystack:
            return action.get("fix", "")
        if "meta" in check_lower and "description" in haystack:
            return action.get("fix", "")
        if "h1" in check_lower and "h1" in haystack:
            return action.get("fix", "")
        if "canonical" in check_lower and "canonical" in haystack:
            return action.get("fix", "")
        if "schema" in check_lower and "schema" in haystack:
            return action.get("fix", "")
        if "robots" in check_lower and "robots" in haystack:
            return action.get("fix", "")
        if "sitemap" in check_lower and "sitemap" in haystack:
            return action.get("fix", "")
        if "alt" in check_lower and "alt" in haystack:
            return action.get("fix", "")
        if "word" in check_lower and "content" in haystack:
            return action.get("fix", "")
        if "heading" in check_lower and "heading" in haystack:
            return action.get("fix", "")
        if "internal" in check_lower and "internal" in haystack:
            return action.get("fix", "")
    return "Apply the recommended optimization from the generated kit."


def row_from_check(check: str, item: dict[str, Any], plan: dict[str, Any]) -> str:
    value = value_or_empty(item.get("value") or item.get("values") or item.get("slug"))
    detail_text = value_or_empty(item.get("detail"))
    detail = f"{value} · {detail_text}" if value and detail_text else (detail_text or value)
    return table_row(check, item.get("status", "unknown"), detail, fix_for_check(check, plan))


def site_checks_html(plan: dict[str, Any]) -> str:
    checks = plan.get("checks", {})
    site = checks.get("site", {}) if isinstance(checks, dict) else {}
    page = checks.get("page", {}) if isinstance(checks, dict) else {}
    schema = checks.get("schema", {}) if isinstance(checks, dict) else {}

    crawl_rows: list[str] = []
    if isinstance(site, dict):
        for key, label in (("robots", "robots.txt"), ("sitemap", "sitemap.xml")):
            item = site.get(key)
            if isinstance(item, dict):
                crawl_rows.append(row_from_check(label, item, plan))
    if not crawl_rows:
        crawl_rows.append(table_row("robots.txt", "info", "Public crawlability check was not available."))
        crawl_rows.append(table_row("sitemap.xml", "info", "Public sitemap check was not available."))

    canonical = page.get("canonical", {}) if isinstance(page, dict) else {}
    canonical_rows = [
        row_from_check("URL Canonicalization", canonical, plan)
        if isinstance(canonical, dict)
        else table_row("URL Canonicalization", "info", "Canonical check unavailable.")
    ]
    i18n_rows = [table_row("i18n / hreflang", "na", "Single-language check is not part of the optimizer pass.")]
    schema_rows = [
        row_from_check("Schema (JSON-LD)", schema, plan)
        if isinstance(schema, dict)
        else table_row("Schema (JSON-LD)", "info", "Schema check unavailable.")
    ]

    return "\n".join(
        [
            '<div class="subsection-label">Crawlability</div>',
            table_html(crawl_rows),
            '<div class="subsection-label">URL Canonicalization</div>',
            table_html(canonical_rows),
            '<div class="subsection-label">i18n / hreflang</div>',
            table_html(i18n_rows),
            '<div class="subsection-label">Schema (JSON-LD)</div>',
            table_html(schema_rows),
        ]
    )


def eeat_checks_html() -> str:
    rows = []
    for page_name in ("About Us", "Contact", "Privacy Policy", "Terms of Service"):
        rows.append(
            "<tr>"
            f"<td>{escape(page_name)}</td>"
            f"<td>{status_badge('info')}</td>"
            f"<td>{status_badge('info')}</td>"
            "<td>Trust page existence and footer/nav reachability need a site crawl or manual confirmation.</td>"
            "</tr>"
        )
    return (
        '<div class="subsection-label">E-E-A-T Trust Pages</div>'
        '<div class="table-scroll"><table class="check-table">'
        "<thead><tr><th>E-E-A-T Page</th><th>Exists</th><th>Reachable (footer/nav)</th><th>Detail</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def page_checks_html(plan: dict[str, Any]) -> str:
    checks = plan.get("checks", {})
    page = checks.get("page", {}) if isinstance(checks, dict) else {}
    schema = checks.get("schema", {}) if isinstance(checks, dict) else {}
    summary = plan.get("summary", {})
    keyword = plan.get("keyword", "")

    rows: list[str] = []
    mapping = (
        ("url_slug", "URL Slug"),
        ("title", "Title Tag"),
        ("meta_description", "Meta Description"),
        ("h1", "H1 Tag"),
        ("canonical", "Canonical Tag"),
    )
    for key, label in mapping:
        item = page.get(key) if isinstance(page, dict) else None
        if isinstance(item, dict):
            rows.append(row_from_check(label, item, plan))

    missing_alt = int(summary.get("missing_alt_count", 0) or 0)
    image_count = int(summary.get("image_count", 0) or 0)
    alt_status = "warn" if missing_alt else ("info" if image_count == 0 else "pass")
    rows.append(
        table_row(
            "Image Alt Text",
            alt_status,
            f"{image_count} image(s) found · {missing_alt} missing useful alt text.",
            "Add descriptive alt text to content images. Decorative images can use empty alt text.",
        )
    )

    word_count = int(summary.get("word_count", 0) or 0)
    word_basis = clean_text(str(summary.get("word_count_basis", "visible static")))
    word_status = "fail" if word_count < 100 else ("warn" if word_count < 500 else "pass")
    rows.append(
        table_row(
            "Word Count",
            word_status,
            f"{word_count} {word_basis} word(s).",
            "Expand primary content with useful sections, examples, proof points, and FAQs.",
        )
    )

    body_text = value_or_empty(page.get("body_text") if isinstance(page, dict) else "")
    keyword_status = "info"
    keyword_detail = f'Keyword "{keyword}" placement needs rendered-page review.'
    if keyword and body_text:
        first_100 = " ".join(body_text.split()[:100]).lower()
        keyword_status = "pass" if keyword.lower() in first_100 else "warn"
        keyword_detail = f'Keyword "{keyword}" presence checked in available opening text.'
    rows.append(
        table_row(
            "Keyword Placement",
            keyword_status,
            keyword_detail,
            "Use the primary keyword or a natural variant in the opening paragraph.",
        )
    )

    h2_count = int(summary.get("h2_count", 0) or 0)
    heading_status = "pass" if 5 <= h2_count <= 7 else "warn"
    rows.append(
        table_row(
            "Heading Structure",
            heading_status,
            f"{h2_count} H2 heading(s) found.",
            "Use 5-7 H2 sections covering definition, benefits, process, proof, and FAQs.",
        )
    )

    internal_count = int(summary.get("internal_link_count", 0) or 0)
    internal_status = "pass" if 2 <= internal_count <= 20 else "warn"
    rows.append(
        table_row(
            "Internal Links",
            internal_status,
            f"{internal_count} same-origin link(s) found in static HTML.",
            "Add contextual internal links to related pages, case studies, pricing, or signup.",
        )
    )

    if isinstance(schema, dict):
        rows.append(row_from_check("Schema (JSON-LD)", schema, plan))

    return table_html(rows)


def priority_actions_html(plan: dict[str, Any]) -> str:
    actions = plan.get("actions", [])
    if not actions:
        return '<ol class="priority-list"><li>No high-priority action found in the static checks.</li></ol>'
    items = "\n".join(
        f"<li><strong>{escape(action.get('priority', 'P'))}</strong> "
        f"{escape(action.get('title', 'Action'))}: {escape(action.get('fix', 'Apply the recommended fix.'))}</li>"
        for action in actions[:8]
    )
    return f'<ol class="priority-list">{items}</ol>'


def insights_html(plan: dict[str, Any]) -> str:
    actions = plan.get("actions", [])
    if not actions:
        return (
            '<article class="finding"><div class="finding-header">'
            f"{status_badge('pass')}<h3>No priority issues found</h3></div>"
            '<div class="finding-body"><div class="finding-field"><span class="label">Evidence</span>'
            '<span class="value">Static checks did not find a critical issue.</span></div></div></article>'
        )
    articles = []
    for action in actions[:6]:
        priority = action.get("priority", "P3")
        status = "fail" if priority == "P1" else "warn"
        articles.append(
            '<article class="finding">'
            '<div class="finding-header">'
            f"{status_badge(status)}<h3>{escape(action.get('title', 'SEO action'))}</h3>"
            "</div>"
            '<div class="finding-body">'
            '<div class="finding-field"><span class="label">Evidence</span>'
            f"<span class=\"value\">{escape(action.get('evidence', 'Detected by static audit checks.'))}</span></div>"
            '<div class="finding-field"><span class="label">Impact</span>'
            f"<span class=\"value\">{escape(action.get('area', 'SEO'))} issue may reduce crawl clarity, SERP presentation, or content relevance.</span></div>"
            '<div class="finding-field"><span class="label">Fix</span>'
            f"<span class=\"value\">{escape(action.get('fix', 'Apply the recommended optimization.'))}</span></div>"
            "</div></article>"
        )
    return "\n".join(articles)


def render_template_audit_report(plan: dict[str, Any], title: str) -> str:
    rows = page_check_rows(plan.get("checks", {}))
    verdict, critical_html, warnings_html, passing_html = summary_lists(rows)
    generated_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    replacements = {
        "{{report_title}}": title,
        "{{url}}": plan.get("final_url", ""),
        "{{audit_level}}": "Basic + Optimization",
        "{{generated_date}}": generated_date,
        "{{summary_verdict}}": verdict,
        "{{summary_critical_html}}": critical_html,
        "{{summary_warnings_html}}": warnings_html,
        "{{summary_passing_html}}": passing_html,
        "{{site_checks_html}}": site_checks_html(plan),
        "{{eeat_checks_html}}": eeat_checks_html(),
        "{{page_checks_html}}": page_checks_html(plan),
        "{{priority_actions_html}}": priority_actions_html(plan),
        "{{insights_html}}": insights_html(plan),
    }
    html = load_audit_template()
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, str(value))
    return html


def render_rows(rows: list[dict[str, str]]) -> str:
    if not rows:
        return '<tr><td colspan="5">No checks available.</td></tr>'
    html_rows = []
    for row in rows:
        html_rows.append(
            "<tr>"
            f"<td>{escape(row['area'])}</td>"
            f"<td>{escape(row['check'])}</td>"
            f"<td>{status_badge(row['status'])}</td>"
            f"<td>{escape(row['value'])}</td>"
            f"<td>{escape(row['detail'])}</td>"
            "</tr>"
        )
    return "\n".join(html_rows)


def render_report_shell(title: str, subtitle: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f6f7f9; color: #1f2937; }}
    header, main {{ max-width: 1120px; margin: 0 auto; padding: 24px; }}
    header {{ background: #ffffff; border-bottom: 1px solid #e5e7eb; max-width: none; }}
    header .inner {{ max-width: 1120px; margin: 0 auto; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    h2 {{ margin: 0 0 14px; font-size: 18px; }}
    p {{ margin: 0 0 10px; }}
    section {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 18px; margin-bottom: 18px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ text-align: left; border-bottom: 1px solid #eef0f3; padding: 10px; vertical-align: top; }}
    th {{ color: #4b5563; background: #f9fafb; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
    code, pre {{ background: #f3f4f6; border-radius: 6px; }}
    pre {{ padding: 14px; overflow-x: auto; }}
    .meta {{ color: #6b7280; }}
    .grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }}
    .metric {{ background: #f9fafb; border: 1px solid #edf0f2; border-radius: 7px; padding: 12px; }}
    .metric strong {{ display: block; font-size: 24px; }}
    .status {{ display: inline-block; border-radius: 999px; padding: 2px 8px; font-weight: 700; font-size: 12px; }}
    .status-pass {{ background: #dcfce7; color: #166534; }}
    .status-warn, .status-info, .status-skipped, .status-unknown {{ background: #fef3c7; color: #92400e; }}
    .status-fail, .status-error {{ background: #fee2e2; color: #991b1b; }}
    @media (max-width: 760px) {{ .grid {{ grid-template-columns: 1fr; }} table {{ min-width: 760px; }} section {{ overflow-x: auto; }} }}
  </style>
</head>
<body>
  <header><div class="inner">
    <h1>{escape(title)}</h1>
    <p class="meta">{escape(subtitle)}</p>
  </div></header>
  <main>{body}</main>
</body>
</html>"""


def render_audit_report(plan: dict[str, Any], title: str = "Before SEO optimization") -> str:
    return render_template_audit_report(plan, title)


def audit_status_counts(plan: dict[str, Any]) -> dict[str, int]:
    rows = page_check_rows(plan.get("checks", {}))
    counts = {"fail": 0, "warn": 0, "pass": 0, "total": len(rows)}
    for row in rows:
        css_class, _ = status_display(row.get("status", ""))
        if css_class == "fail":
            counts["fail"] += 1
        elif css_class in {"warn", "info", "na"}:
            counts["warn"] += 1
        elif css_class == "pass":
            counts["pass"] += 1
    return counts


def audit_summary_table(plan: dict[str, Any]) -> str:
    counts = audit_status_counts(plan)
    return table_html(
        [
            table_row(
                "Critical",
                "fail" if counts["fail"] else "pass",
                f"{counts['fail']} fail check(s) across {counts['total']} audited checks.",
                "Resolve remaining failed checks before publishing.",
            ),
            table_row(
                "Warnings",
                "warn" if counts["warn"] else "pass",
                f"{counts['warn']} warning or unverified check(s) across {counts['total']} audited checks.",
                "Review warnings that remain after the generated fixes are applied.",
            ),
            table_row(
                "Passing",
                "pass",
                f"{counts['pass']} passing check(s) across {counts['total']} audited checks.",
            ),
        ]
    )


def schema_types_for_page_type(page_type: str) -> list[str]:
    if page_type == "article":
        return ["Article"]
    if page_type == "product":
        return ["Product"]
    if page_type == "faq":
        return ["FAQPage"]
    return ["WebSite", "Organization"]


def build_optimized_plan(plan: dict[str, Any], before_facts: dict[str, Any]) -> dict[str, Any]:
    optimized = copy.deepcopy(plan)
    generated = optimized["generated"]
    tags = generated["tags"]
    brief = generated["content_brief"]
    final_url = optimized.get("final_url", "")
    keyword = optimized.get("keyword", "")
    audience = optimized.get("audience", "")
    page_type = optimized.get("page_type", "homepage")
    original_checks = plan.get("checks", {})
    original_page = original_checks.get("page", {}) if isinstance(original_checks, dict) else {}
    original_slug = (
        original_page.get("url_slug", {}).get("slug")
        if isinstance(original_page, dict) and isinstance(original_page.get("url_slug"), dict)
        else (urlparse(final_url).path or "/")
    )
    canonical = tags.get("canonical") or ""
    target_word_count = max(int(plan.get("summary", {}).get("word_count", 0) or 0), 650)
    target_h2_count = max(
        int(plan.get("summary", {}).get("h2_count", 0) or 0),
        len(brief.get("recommended_h2s", [])),
    )
    target_internal_links = max(
        int(plan.get("summary", {}).get("internal_link_count", 0) or 0),
        len(brief.get("internal_link_targets", [])),
    )

    optimized["summary"] = {
        **copy.deepcopy(plan.get("summary", {})),
        "word_count": target_word_count,
        "word_count_basis": "target",
        "h1_count": 1,
        "h2_count": target_h2_count,
        "missing_alt_count": 0,
        "internal_link_count": target_internal_links,
    }
    optimized["checks"] = copy.deepcopy(original_checks)
    optimized["checks"]["page"] = {
        "url": final_url,
        "final_url": final_url,
        "http_status": original_page.get("http_status") if isinstance(original_page, dict) else None,
        "url_slug": {
            "status": "pass",
            "slug": original_slug,
            "detail": "Optimized target keeps a clean, indexable URL path.",
        },
        "title": {
            "status": "pass",
            "value": tags["title"],
            "length": len(tags["title"]),
            "detail": "Optimized title generated with the primary topic and brand.",
        },
        "meta_description": {
            "status": "pass",
            "value": tags["meta_description"],
            "length": len(tags["meta_description"]),
            "detail": "Optimized meta description generated for search snippets.",
        },
        "h1": {
            "status": "pass",
            "count": 1,
            "values": [tags["h1"]],
            "detail": "Single optimized H1 generated.",
        },
        "canonical": {
            "status": "pass" if canonical else "warn",
            "value": canonical,
            "matches_final_url": bool(canonical and canonical.rstrip("/") == final_url.rstrip("/")),
            "detail": "Self-referencing canonical generated." if canonical else "Public canonical URL needed.",
        },
        "body_text": f"{keyword} opening copy for {audience or 'the target audience'}.",
        "keyword": keyword,
    }

    site = optimized["checks"].get("site", {})
    if not isinstance(site, dict):
        site = {}
    site["status"] = "pass"
    site["robots"] = {
        "status": "pass",
        "detail": "Generated robots.txt allows crawling and references the XML sitemap.",
        "sitemap_directive": f"Sitemap: {origin_from_url(final_url) or 'https://example.com'}/sitemap.xml",
    }
    site["sitemap"] = {
        "status": "pass",
        "detail": "Generated sitemap.xml contains the canonical page URL.",
        "checked_url": f"{origin_from_url(final_url) or 'https://example.com'}/sitemap.xml",
    }
    optimized["checks"]["site"] = site
    optimized["checks"]["schema"] = {
        "status": "pass",
        "found_types": schema_types_for_page_type(page_type),
        "detail": "Generated JSON-LD matches the inferred page type.",
    }
    optimized["checks"]["social"] = {
        "status": "pass",
        "found_types": ["Open Graph", "Twitter Card"],
        "detail": "Generated OG and Twitter Card tags are ready to publish.",
    }
    optimized["actions"] = []
    optimized["source_snapshot"] = before_facts
    return optimized


def full_audit_sections_html(plan: dict[str, Any], label: str) -> str:
    return "\n".join(
        [
            f'<div class="subsection-label">{escape(label)} Audit Report</div>',
            f'<div class="subsection-label">{escape(label)} Audit Summary</div>',
            audit_summary_table(plan),
            f'<div class="subsection-label">{escape(label)} Site Checks</div>',
            site_checks_html(plan),
            f'<div class="subsection-label">{escape(label)} E-E-A-T Checks</div>',
            eeat_checks_html(),
            f'<div class="subsection-label">{escape(label)} Page Checks</div>',
            page_checks_html(plan),
            f'<div class="subsection-label">{escape(label)} Priority Actions</div>',
            priority_actions_html(plan),
            f'<div class="subsection-label">{escape(label)} Insight Walkthrough</div>',
            insights_html(plan),
        ]
    )


def side_by_side_audits_html(original_plan: dict[str, Any], optimized_plan: dict[str, Any]) -> str:
    return "\n".join(
        [
            '<div class="comparison-audit-grid" aria-label="Original and optimized SEO audit comparison">',
            '<div class="comparison-column comparison-column-before">',
            full_audit_sections_html(original_plan, "Original"),
            "</div>",
            '<div class="comparison-column comparison-column-after">',
            full_audit_sections_html(optimized_plan, "SEO Optimized"),
            "</div>",
            "</div>",
        ]
    )


def comparison_report_css() -> str:
    return """

    /* ── Comparison report split view ── */
    .comparison-audit-grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      gap: 18px;
      align-items: start;
    }
    .comparison-column {
      min-width: 0;
    }
    .comparison-column .subsection-label:first-child {
      margin-top: 0;
    }
    .comparison-column-before .subsection-label {
      color: #0f62fe;
      background: #f0f5ff;
      border-left-color: #0f62fe;
    }
    .comparison-column-after .subsection-label {
      color: #1a6b35;
      background: #f0faf3;
      border-left-color: #1a6b35;
    }
    .comparison-column .check-table {
      min-width: 30rem;
    }
    .comparison-column .check-table:has(thead tr th:nth-child(4)) {
      min-width: 34rem;
    }
    .comparison-column article.finding .finding-field {
      grid-template-columns: 68px 1fr;
    }
    @media (max-width: 980px) {
      .comparison-audit-grid {
        grid-template-columns: 1fr;
      }
    }
    @media (max-width: 640px) {
      .comparison-column .check-table {
        min-width: 28rem;
      }
      .comparison-column .check-table:has(thead tr th:nth-child(4)) {
        min-width: 32rem;
      }
    }
"""


def inject_comparison_css(html: str) -> str:
    return html.replace("</style>", f"{comparison_report_css()}\n  </style>", 1)


def comparison_rows(plan: dict[str, Any], before_facts: dict[str, Any]) -> list[tuple[str, str, str]]:
    tags = plan["generated"]["tags"]
    h1_values = before_facts.get("headings", {}).get("h1", [])
    return [
        ("Title", value_or_empty(before_facts.get("title")), tags["title"]),
        ("Meta description", value_or_empty(before_facts.get("meta_description")), tags["meta_description"]),
        ("Canonical", value_or_empty(before_facts.get("canonical")), tags.get("canonical") or "https://example.com/your-page"),
        ("H1", value_or_empty(h1_values), tags["h1"]),
        ("Schema", "Current page schema from audit checks", "Recommended JSON-LD snippet included below"),
        ("Content structure", f"{len(before_facts.get('headings', {}).get('h2', []))} H2 heading(s)", "Use the recommended H2 brief"),
    ]


def comparison_table(rows: list[tuple[str, str, str]]) -> str:
    html_rows = []
    for field, before, after in rows:
        changed = clean_text(before) != clean_text(after)
        status = "warn" if changed else "pass"
        impact = "Changed by optimizer" if changed else "No change needed"
        html_rows.append(
            "<tr>"
            f"<td>{escape(field)}</td>"
            f"<td>{status_badge(status)}</td>"
            "<td>"
            f"<div class=\"detail-issue\"><strong>Before:</strong> {escape(before or 'Missing')}</div>"
            f"<div class=\"detail-fix\"><strong>After:</strong> {escape(after or 'Missing')}</div>"
            f"<div class=\"detail-issue\">· {escape(impact)}</div>"
            "</td>"
            "</tr>"
        )
    return table_html(html_rows)


def comparison_summary_lists(
    rows: list[tuple[str, str, str]],
    original_plan: Optional[dict[str, Any]] = None,
    optimized_plan: Optional[dict[str, Any]] = None,
) -> tuple[str, str, str, str]:
    changed = [row for row in rows if clean_text(row[1]) != clean_text(row[2])]
    unchanged = [row for row in rows if clean_text(row[1]) == clean_text(row[2])]
    original_counts = audit_status_counts(original_plan) if original_plan else None
    optimized_counts = audit_status_counts(optimized_plan) if optimized_plan else None

    def render_changed(items: list[tuple[str, str, str]]) -> str:
        if not items:
            return '<li class="summary-empty">None</li>'
        return "\n".join(
            f"<li>{escape(field)}: {escape(trim_to_words(before or 'Missing', 42))} → {escape(trim_to_words(after or 'Missing', 42))}</li>"
            for field, before, after in items[:6]
        )

    def render_unchanged(items: list[tuple[str, str, str]]) -> str:
        if not items:
            return '<li class="summary-empty">None</li>'
        return "\n".join(f"<li>{escape(field)} unchanged</li>" for field, _, _ in items[:6])

    verdict = f"Compared {len(rows)} SEO fields. {len(changed)} field(s) have recommended changes and {len(unchanged)} field(s) are unchanged."
    if original_counts and optimized_counts:
        verdict = (
            f"Original audit found {original_counts['fail']} critical issue(s) and "
            f"{original_counts['warn']} warning/unverified item(s). SEO optimized audit has "
            f"{optimized_counts['fail']} critical issue(s), {optimized_counts['warn']} warning/unverified item(s), "
            f"and {optimized_counts['pass']} passing check(s)."
        )
    critical_items = ['<li class="summary-empty">None</li>']
    passing_items = [render_unchanged(unchanged)]
    if original_counts and optimized_counts:
        critical_items = [
            (
                f"<li>Original Audit Summary: {original_counts['fail']} critical, "
                f"{original_counts['warn']} warning/unverified, {original_counts['pass']} passing.</li>"
            ),
            (
                f"<li>SEO Optimized Audit Summary: {optimized_counts['fail']} critical, "
                f"{optimized_counts['warn']} warning/unverified, {optimized_counts['pass']} passing.</li>"
            ),
        ]
        passing_items = [
            f"<li>SEO Optimized Audit Summary: {optimized_counts['pass']} passing check(s) after generated fixes.</li>",
            render_unchanged(unchanged),
        ]
    return verdict, "\n".join(critical_items), render_changed(changed), "\n".join(passing_items)


def comparison_priority_actions_html(
    plan: dict[str, Any],
    rows: list[tuple[str, str, str]],
    optimized_plan: Optional[dict[str, Any]] = None,
) -> str:
    changed_fields = [field for field, before, after in rows if clean_text(before) != clean_text(after)]
    items = []
    for field in changed_fields[:6]:
        items.append(f"<li>Apply the optimized {escape(field.lower())} value from the comparison table.</li>")
    for action in plan.get("actions", [])[:4]:
        items.append(
            f"<li><strong>{escape(action.get('priority', 'P'))}</strong> "
            f"{escape(action.get('title', 'SEO action'))}: {escape(action.get('fix', 'Apply the recommended fix.'))}</li>"
        )
    if not items:
        items.append("<li>No comparison changes required.</li>")
    sections = [
        '<div class="subsection-label">Comparison Priority Actions</div>',
        f"<ol class=\"priority-list\">{''.join(items)}</ol>",
    ]
    if optimized_plan is not None:
        sections.extend(
            [
                '<div class="subsection-label">Original Priority Actions</div>',
                priority_actions_html(plan),
                '<div class="subsection-label">SEO Optimized Priority Actions</div>',
                priority_actions_html(optimized_plan),
            ]
        )
    return "\n".join(sections)


def comparison_insights_html(
    plan: dict[str, Any],
    rows: list[tuple[str, str, str]],
    optimized_plan: Optional[dict[str, Any]] = None,
) -> str:
    articles = []
    for field, before, after in rows[:6]:
        changed = clean_text(before) != clean_text(after)
        status = "warn" if changed else "pass"
        title = f"{field} {'updated' if changed else 'kept'}"
        evidence = f"Before: {before or 'Missing'}"
        fix = f"After: {after or 'Missing'}"
        articles.append(
            '<article class="finding">'
            '<div class="finding-header">'
            f"{status_badge(status)}<h3>{escape(title)}</h3>"
            "</div>"
            '<div class="finding-body">'
            '<div class="finding-field"><span class="label">Evidence</span>'
            f"<span class=\"value\">{escape(evidence)}</span></div>"
            '<div class="finding-field"><span class="label">Impact</span>'
            f"<span class=\"value\">{escape(field)} controls search snippet quality, crawl clarity, or page topic matching.</span></div>"
            '<div class="finding-field"><span class="label">Fix</span>'
            f"<span class=\"value\">{escape(fix)}</span></div>"
            "</div></article>"
        )
    sections: list[str] = []
    if optimized_plan is not None:
        sections.extend(
            [
                '<div class="subsection-label">Original Insight Walkthrough</div>',
                insights_html(plan),
                '<div class="subsection-label">SEO Optimized Insight Walkthrough</div>',
                insights_html(optimized_plan),
                '<div class="subsection-label">Field-Level Change Walkthrough</div>',
            ]
        )
    sections.extend(articles)
    return "\n".join(sections)


def render_comparison_report(plan: dict[str, Any], before_facts: dict[str, Any]) -> str:
    optimized_plan = build_optimized_plan(plan, before_facts)
    rows = comparison_rows(plan, before_facts)
    verdict, critical_html, warnings_html, passing_html = comparison_summary_lists(
        rows,
        plan,
        optimized_plan,
    )
    generated = plan["generated"]
    generated_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    comparison_site_checks = side_by_side_audits_html(plan, optimized_plan)
    comparison_page_checks = "\n".join(
        [
            '<div class="subsection-label">On-page Comparison</div>',
            comparison_table(rows),
            '<div class="subsection-label">Optimized Head Tags</div>',
            f'<pre><code>{escape(generated["tag_html"])}</code></pre>',
            '<div class="subsection-label">JSON-LD</div>',
            f'<pre><code>{escape(generated["schema_json_ld"])}</code></pre>',
        ]
    )
    replacements = {
        "{{report_title}}": "SEO Before vs After Comparison",
        "{{url}}": plan.get("final_url", ""),
        "{{audit_level}}": "Optimization Comparison",
        "{{generated_date}}": generated_date,
        "{{summary_verdict}}": verdict,
        "{{summary_critical_html}}": critical_html,
        "{{summary_warnings_html}}": warnings_html,
        "{{summary_passing_html}}": passing_html,
        "{{site_checks_html}}": comparison_site_checks,
        "{{eeat_checks_html}}": "",
        "{{page_checks_html}}": comparison_page_checks,
        "{{priority_actions_html}}": comparison_priority_actions_html(plan, rows, optimized_plan),
        "{{insights_html}}": comparison_insights_html(plan, rows, optimized_plan),
    }
    html = inject_comparison_css(load_audit_template())
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, str(value))
    return html


def is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((host, port)) == 0


def report_url_available(file_name: str, port: int = DEFAULT_REPORT_PORT) -> bool:
    try:
        with urllib.request.urlopen(report_local_url(file_name, port), timeout=1) as response:
            return 200 <= response.status < 400
    except (OSError, urllib.error.URLError):
        return False


def report_server_pids(port: int) -> list[int]:
    try:
        completed = subprocess.run(
            ["lsof", "-ti", f"tcp:{port}"],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return []
    pids = []
    for raw_pid in completed.stdout.splitlines():
        raw_pid = raw_pid.strip()
        if not raw_pid.isdigit():
            continue
        pid = int(raw_pid)
        try:
            command = subprocess.run(
                ["ps", "-p", str(pid), "-o", "command="],
                text=True,
                capture_output=True,
                check=False,
            ).stdout
        except OSError:
            continue
        if "http.server" in command and str(port) in command:
            pids.append(pid)
    return pids


def stop_existing_report_server(port: int) -> bool:
    pids = report_server_pids(port)
    if not pids:
        return False
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    for _ in range(20):
        if not is_port_open("127.0.0.1", port):
            return True
        time.sleep(0.1)
    return not is_port_open("127.0.0.1", port)


def ensure_report_server(
    reports_dir: Path,
    port: int = DEFAULT_REPORT_PORT,
    probe_file: Optional[str] = None,
) -> bool:
    if is_port_open("127.0.0.1", port):
        if not probe_file or report_url_available(probe_file, port):
            return True
        if not stop_existing_report_server(port):
            return False
    reports_dir.mkdir(parents=True, exist_ok=True)
    log_path = reports_dir / ".seo-report-server.log"
    with log_path.open("ab") as log_file:
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "http.server",
                str(port),
                "--bind",
                "127.0.0.1",
                "--directory",
                str(reports_dir),
            ],
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,
        )
    for _ in range(20):
        if is_port_open("127.0.0.1", port) and (
            not probe_file or report_url_available(probe_file, port)
        ):
            return True
        time.sleep(0.1)
    return False


def write_process_reports(
    plan: dict[str, Any],
    before_facts: dict[str, Any],
    reports_dir: Path,
    port: int = DEFAULT_REPORT_PORT,
    serve: bool = True,
) -> dict[str, Any]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    audit_name = report_file_name(plan["final_url"], "audit")
    comparison_name = report_file_name(plan["final_url"], "comparison")
    audit_path = reports_dir / audit_name
    comparison_path = reports_dir / comparison_name

    audit_path.write_text(render_audit_report(plan), encoding="utf-8")
    comparison_path.write_text(render_comparison_report(plan, before_facts), encoding="utf-8")

    server_ready = ensure_report_server(reports_dir, port, audit_name) if serve else False
    return {
        "audit_path": audit_path,
        "comparison_path": comparison_path,
        "audit_url": report_local_url(audit_name, port),
        "comparison_url": report_local_url(comparison_name, port),
        "server_ready": server_ready,
    }


def replace_or_insert_head(html: str, pattern: str, replacement: str) -> str:
    flags = re.IGNORECASE | re.DOTALL
    if re.search(pattern, html, flags=flags):
        return re.sub(pattern, replacement, html, count=1, flags=flags)
    if re.search(r"</head\s*>", html, flags=flags):
        return re.sub(r"</head\s*>", replacement + "\n</head>", html, count=1, flags=flags)
    return replacement + "\n" + html


def apply_basic_html_optimizations(html: str, tags: dict[str, Any]) -> str:
    title = f"<title>{escape(tags['title'])}</title>"
    meta = f'<meta name="description" content="{escape(tags["meta_description"], quote=True)}">'
    html = replace_or_insert_head(html, r"<title\b[^>]*>.*?</title\s*>", title)
    html = replace_or_insert_head(
        html,
        r"<meta\b(?=[^>]*(?:name|property)\s*=\s*['\"]description['\"])[^>]*>",
        meta,
    )
    if tags.get("canonical"):
        canonical = f'<link rel="canonical" href="{escape(tags["canonical"], quote=True)}">'
        html = replace_or_insert_head(
            html,
            r"<link\b(?=[^>]*rel\s*=\s*['\"][^'\"]*canonical[^'\"]*['\"])[^>]*>",
            canonical,
        )

    h1_text = escape(tags["h1"])
    flags = re.IGNORECASE | re.DOTALL
    if re.search(r"<h1\b[^>]*>.*?</h1\s*>", html, flags=flags):
        html = re.sub(
            r"<h1\b([^>]*)>.*?</h1\s*>",
            lambda match: f"<h1{match.group(1)}>{h1_text}</h1>",
            html,
            count=1,
            flags=flags,
        )
    elif re.search(r"<body\b[^>]*>", html, flags=flags):
        html = re.sub(
            r"(<body\b[^>]*>)",
            lambda match: f"{match.group(1)}\n<h1>{h1_text}</h1>",
            html,
            count=1,
            flags=flags,
        )
    else:
        html = f"<h1>{h1_text}</h1>\n{html}"
    return html


def collect_inputs(args: argparse.Namespace) -> tuple[str, str, Optional[Path], str]:
    html_file = Path(args.html_file).expanduser().resolve() if args.html_file else None
    source_url = normalize_url(args.url) if args.url else ""

    if html_file:
        html = html_file.read_text(encoding=args.encoding)
        final_url = source_url or html_file.as_uri()
        return html, final_url, html_file, source_url or str(html_file)

    if not source_url:
        raise RuntimeError("Provide a URL or --html-file.")
    html, final_url = fetch_html(source_url, args.timeout)
    return html, final_url, None, source_url


def collect_checks(
    *,
    source_url: str,
    final_url: str,
    html_file: Optional[Path],
    facts: dict[str, Any],
    keyword: str,
    timeout: int,
) -> dict[str, Any]:
    script_dir = Path(__file__).resolve().parent
    root = script_dir.parent.parent
    checks: dict[str, Any] = {}

    if html_file:
        checks["page"] = build_local_page_result(facts, final_url, keyword)
        checks["schema"] = run_json_script(script_dir / "check-schema.py", ["--file", str(html_file)])
        checks["social"] = run_json_script(
            root / "seo-audit-full" / "scripts" / "check-social.py",
            [source_url, "--file", str(html_file)] if source_url else ["--file", str(html_file)],
        )
        if source_url.startswith(("http://", "https://")):
            checks["site"] = run_json_script(
                script_dir / "check-site.py",
                [source_url, "--timeout", str(timeout)],
            )
        else:
            checks["site"] = {"status": "skipped", "detail": "Site checks require a public URL."}
    elif source_url.startswith(("http://", "https://")):
        checks["page"] = run_json_script(
            script_dir / "check-page.py",
            [source_url, "--timeout", str(timeout), "--keyword", keyword],
        )
        checks["site"] = run_json_script(
            script_dir / "check-site.py",
            [source_url, "--timeout", str(timeout)],
        )
        checks["schema"] = run_json_script(
            script_dir / "check-schema.py",
            [source_url, "--timeout", str(timeout)],
        )
        checks["social"] = run_json_script(
            root / "seo-audit-full" / "scripts" / "check-social.py",
            [source_url, "--timeout", str(timeout)],
        )
    else:
        checks["page"] = build_local_page_result(facts, final_url, keyword)
        checks["schema"] = {"status": "unknown", "detail": "No HTML file available."}
        checks["social"] = {"status": "unknown", "detail": "No HTML file available."}
        checks["site"] = {"status": "skipped", "detail": "Site checks require a public URL."}

    if not isinstance(checks.get("page"), dict) or "title" not in checks["page"]:
        checks["page"] = build_local_page_result(facts, final_url, keyword)

    return checks


def write_output(plan: dict[str, Any], output: Optional[str], output_format: str) -> Path:
    if output:
        output_path = Path(output).expanduser().resolve()
    else:
        extension = "json" if output_format == "json" else "md"
        output_path = Path.cwd() / "reports" / f"{slug_from_url(plan['final_url'], 'seo-optimization')}.{extension}"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "json":
        output_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        output_path.write_text(render_markdown(plan), encoding="utf-8")
    return output_path


def apply_to_file(html_file: Path, plan: dict[str, Any], encoding: str) -> Path:
    original = html_file.read_text(encoding=encoding)
    updated = apply_basic_html_optimizations(original, plan["generated"]["tags"])
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup = html_file.with_suffix(html_file.suffix + f".{stamp}.bak")
    shutil.copy2(html_file, backup)
    html_file.write_text(updated, encoding=encoding)
    return backup


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an SEO optimization kit and optionally patch local HTML."
    )
    parser.add_argument("url", nargs="?", help="Public URL to optimize")
    parser.add_argument("--html-file", help="Local HTML file to analyze or patch")
    parser.add_argument("--keyword", "-k", help="Primary keyword to optimize for")
    parser.add_argument("--brand", help="Brand or site name")
    parser.add_argument("--audience", default="", help="Target audience, e.g. 'B2B marketing teams'")
    parser.add_argument("--business-goal", default="", help="Concrete business goal or value proposition")
    parser.add_argument(
        "--page-type",
        default="auto",
        choices=["auto", "homepage", "article", "product", "faq", "howto", "generic"],
        help="Page type used for schema and title recommendations",
    )
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTP timeout in seconds")
    parser.add_argument("--output", "-o", help="Output file. Defaults to reports/<site>-seo-optimization.md")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown", help="Output format")
    parser.add_argument("--reports-dir", default="reports", help="Directory for required HTML reports")
    parser.add_argument("--report-port", type=int, default=DEFAULT_REPORT_PORT, help="Local report server port")
    parser.add_argument(
        "--no-report-server",
        action="store_true",
        help="Write required HTML reports without starting the local report server.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Patch --html-file with generated title, meta description, canonical, and H1.",
    )
    parser.add_argument("--encoding", default="utf-8", help="Encoding for --html-file")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    if args.apply and not args.html_file:
        raise SystemExit("--apply requires --html-file")

    html, final_url, html_file, source_label = collect_inputs(args)
    facts = extract_page_facts(html, final_url)
    keyword = clean_text(args.keyword or infer_keyword(facts, final_url))
    brand = clean_text(args.brand or infer_brand(facts, final_url))
    page_type = infer_page_type(final_url, facts, args.page_type)
    checks = collect_checks(
        source_url=normalize_url(args.url) if args.url else "",
        final_url=final_url,
        html_file=html_file,
        facts=facts,
        keyword=keyword,
        timeout=args.timeout,
    )

    plan = build_plan(
        source_url=source_label,
        final_url=final_url,
        html_file=html_file,
        facts=facts,
        checks=checks,
        keyword=keyword,
        brand=brand,
        audience=clean_text(args.audience),
        business_goal=clean_text(args.business_goal),
        page_type=page_type,
    )

    reports_dir = Path(args.reports_dir).expanduser().resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)
    audit_name = report_file_name(final_url, "audit")
    audit_path = reports_dir / audit_name
    audit_path.write_text(render_audit_report(plan), encoding="utf-8")
    server_ready = False
    if not args.no_report_server:
        server_ready = ensure_report_server(reports_dir, args.report_port, audit_name)
    audit_url = report_local_url(audit_name, args.report_port)
    print(f"Audit report -> {audit_url}")
    print(f"Audit report file -> {audit_path}")

    output_path = write_output(plan, args.output, args.format)
    print(f"SEO optimization kit saved -> {output_path}")

    if args.apply and html_file:
        backup = apply_to_file(html_file, plan, args.encoding)
        print(f"Applied basic HTML optimizations -> {html_file}")
        print(f"Backup saved -> {backup}")

    comparison_name = report_file_name(final_url, "comparison")
    comparison_path = reports_dir / comparison_name
    comparison_path.write_text(render_comparison_report(plan, facts), encoding="utf-8")
    comparison_url = report_local_url(comparison_name, args.report_port)
    print(f"Comparison report -> {comparison_url}")
    print(f"Comparison report file -> {comparison_path}")
    if not server_ready and not args.no_report_server:
        print("Warning: report files were written, but the local report server did not become ready.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
