import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "seo-audit" / "scripts" / "seo-optimize.py"
SPEC = importlib.util.spec_from_file_location("seo_optimize", SCRIPT_PATH)
seo_optimize = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(seo_optimize)


SAMPLE_HTML = """
<!doctype html>
<html>
<head>
  <title>Old title</title>
</head>
<body>
  <h1>Old heading</h1>
  <h2>Overview</h2>
  <img src="/hero.png">
  <a href="/pricing">Pricing</a>
  <p>AI workflow automation helps teams reduce manual operations and ship repeatable processes faster.</p>
</body>
</html>
"""


class SeoOptimizeTests(unittest.TestCase):
    def test_extract_page_facts_counts_static_elements(self):
        facts = seo_optimize.extract_page_facts(SAMPLE_HTML, "https://example.com/")

        self.assertEqual(facts["title"], "Old title")
        self.assertEqual(facts["headings"]["h1"], ["Old heading"])
        self.assertEqual(len(facts["missing_alt_images"]), 1)
        self.assertEqual(len(facts["internal_links"]), 1)
        self.assertGreater(facts["word_count"], 5)

    def test_build_plan_generates_actionable_tags(self):
        facts = seo_optimize.extract_page_facts(SAMPLE_HTML, "https://example.com/")
        checks = {
            "page": seo_optimize.build_local_page_result(
                facts,
                "https://example.com/",
                "ai workflow automation",
            ),
            "site": {"status": "skipped", "detail": "Site checks skipped."},
            "schema": {"status": "fail", "detail": "No JSON-LD found."},
            "social": {"status": "fail", "detail": "OG tags missing."},
        }
        plan = seo_optimize.build_plan(
            source_url="https://example.com/",
            final_url="https://example.com/",
            html_file=None,
            facts=facts,
            checks=checks,
            keyword="ai workflow automation",
            brand="Example",
            audience="ops teams",
            business_goal="automate recurring workflows",
            page_type="homepage",
        )

        tags = plan["generated"]["tags"]
        self.assertIn("ai workflow automation", tags["meta_description"].lower())
        self.assertIn("<title>", plan["generated"]["tag_html"])
        self.assertTrue(any(action["auto_apply"] for action in plan["actions"]))
        self.assertIn("JSON-LD", seo_optimize.render_markdown(plan))

    def test_apply_basic_html_optimizations_replaces_and_inserts_tags(self):
        tags = {
            "title": "AI Workflow Automation | Example",
            "meta_description": "AI workflow automation from Example helps teams compare benefits and next steps.",
            "h1": "Example: AI Workflow Automation",
            "canonical": "https://example.com/",
        }

        updated = seo_optimize.apply_basic_html_optimizations(SAMPLE_HTML, tags)

        self.assertIn("<title>AI Workflow Automation | Example</title>", updated)
        self.assertIn('name="description"', updated)
        self.assertIn('rel="canonical"', updated)
        self.assertIn("<h1>Example: AI Workflow Automation</h1>", updated)
        self.assertNotIn("<h1>Old heading</h1>", updated)

    def test_audit_and_comparison_reports_have_local_urls(self):
        facts = seo_optimize.extract_page_facts(SAMPLE_HTML, "https://moshuopc.com/")
        checks = {
            "page": seo_optimize.build_local_page_result(
                facts,
                "https://moshuopc.com/",
                "ai workflow automation",
            ),
            "site": {"status": "skipped", "detail": "Site checks skipped."},
            "schema": {"status": "fail", "detail": "No JSON-LD found."},
            "social": {"status": "fail", "detail": "OG tags missing."},
        }
        plan = seo_optimize.build_plan(
            source_url="https://moshuopc.com/",
            final_url="https://moshuopc.com/",
            html_file=None,
            facts=facts,
            checks=checks,
            keyword="ai workflow automation",
            brand="Moshu OPC",
            audience="ops teams",
            business_goal="automate recurring workflows",
            page_type="homepage",
        )

        with self.subTest("report naming"):
            self.assertEqual(
                seo_optimize.report_file_name("https://moshuopc.com/", "audit"),
                "moshuopc-com-audit.html",
            )
            self.assertEqual(
                seo_optimize.report_local_url("moshuopc-com-audit.html", 8766),
                "http://127.0.0.1:8766/moshuopc-com-audit.html",
            )

        audit_html = seo_optimize.render_audit_report(plan, "Before SEO optimization")
        comparison_html = seo_optimize.render_comparison_report(plan, facts)

        self.assertIn("Before SEO optimization", audit_html)
        self.assertIn("Old title", audit_html)
        self.assertIn("report-badge", audit_html)
        self.assertIn("summary-verdict", audit_html)
        self.assertIn("Audit Summary", audit_html)
        self.assertIn("Site Checks", audit_html)
        self.assertIn("Page Checks", audit_html)
        self.assertIn("Priority Actions", audit_html)
        self.assertIn("Insight Walkthrough", audit_html)
        self.assertIn("upgrade-box", audit_html)
        self.assertIn("check-table", audit_html)
        self.assertIn("Before vs After", comparison_html)
        self.assertIn("AI Workflow Automation", comparison_html)
        self.assertIn("report-badge", comparison_html)
        self.assertIn("summary-verdict", comparison_html)
        self.assertIn("Audit Summary", comparison_html)
        self.assertIn("Site Checks", comparison_html)
        self.assertIn("Page Checks", comparison_html)
        self.assertIn("Priority Actions", comparison_html)
        self.assertIn("Insight Walkthrough", comparison_html)
        self.assertIn("upgrade-box", comparison_html)
        self.assertIn("check-table", comparison_html)
        self.assertIn("priority-list", comparison_html)
        self.assertIn("finding", comparison_html)
        self.assertIn("Original Audit Report", comparison_html)
        self.assertIn("SEO Optimized Audit Report", comparison_html)
        self.assertIn("comparison-audit-grid", comparison_html)
        self.assertIn("comparison-column-before", comparison_html)
        self.assertIn("comparison-column-after", comparison_html)
        self.assertLess(
            comparison_html.index("comparison-column-before"),
            comparison_html.index("comparison-column-after"),
        )
        self.assertIn("Original Audit Summary", comparison_html)
        self.assertIn("SEO Optimized Audit Summary", comparison_html)
        self.assertIn("Original Site Checks", comparison_html)
        self.assertIn("SEO Optimized Site Checks", comparison_html)
        self.assertIn("Original Page Checks", comparison_html)
        self.assertIn("SEO Optimized Page Checks", comparison_html)
        self.assertIn("Original Priority Actions", comparison_html)
        self.assertIn("SEO Optimized Priority Actions", comparison_html)
        self.assertIn("Original Insight Walkthrough", comparison_html)
        self.assertIn("SEO Optimized Insight Walkthrough", comparison_html)


if __name__ == "__main__":
    unittest.main()
