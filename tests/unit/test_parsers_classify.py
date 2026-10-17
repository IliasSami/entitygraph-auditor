"""Unit tests for the deterministic page-type classifier.

Rules run in fixed priority order, so these tests pin both the winning label
and the fact that a higher-priority rule shadows a lower one. Confidence is a
bounded, transparent heuristic — we assert only its range and that the rationale
cites a concrete signal.
"""

from __future__ import annotations

import pytest
from ega_parsers import classify_page_type, parse_content
from ega_schemas.content import ContentSourceMeta
from ega_schemas.enums import PageType


def _classify(text: str, fmt: str = "markdown", **kwargs):
    doc = parse_content(text, content_format=fmt, source=ContentSourceMeta(), **kwargs)
    return classify_page_type(doc)


def _check(page_type, confidence, rationale):
    assert isinstance(page_type, PageType)
    assert 0.0 <= confidence <= 1.0
    assert isinstance(rationale, str) and rationale.strip()
    return page_type


def test_glossary_definition_pattern():
    text = """# What is a Workflow Engine?

A workflow engine is defined as a system that coordinates tasks across tools.
It routes work items and tracks their state until completion.
"""
    pt, conf, rationale = _classify(text)
    assert pt == PageType.GLOSSARY
    assert "definition" in rationale


def test_comparison_keyword_in_title_beats_other_signals():
    text = """# Acme vs Globex

Both tools do the same job, but one is cheaper. We compare features, pricing
and support so you can decide quickly which alternative fits your team.
"""
    pt, conf, rationale = _classify(text)
    assert pt == PageType.COMPARISON
    assert "vs" in rationale


def test_comparison_table_detection_without_vs_in_title():
    html = """<html><head><title>Plan Matrix</title></head><body>
    <h1>Plan Matrix</h1>
    <table>
    <tr><th>Feature</th><th>Free plan price</th><th>Pro plan price</th></tr>
    <tr><td>Seats</td><td>3</td><td>25</td></tr>
    <tr><td>Support</td><td>Community</td><td>Priority</td></tr>
    </table></body></html>"""
    pt, conf, rationale = _classify(html, fmt="html")
    assert pt == PageType.COMPARISON
    assert "table" in rationale


def test_listicle_needs_both_title_and_numbered_list():
    text = """# Top 5 CRMs for Small Teams

1. Acme CRM
2. Globex CRM
3. Northwind CRM
4. Initech CRM
5. Umbrella CRM
"""
    pt, conf, rationale = _classify(text)
    assert pt == PageType.LISTICLE
    assert "numbered list" in rationale


def test_listicle_without_numbered_list_does_not_fire():
    text = """# Top 5 CRMs for Small Teams

Acme is the best CRM because it is affordable and easy to use for teams.
Globex follows with a pricier but more capable platform. Northwind competes
on integrations while Initech targets enterprises with heavy compliance.
"""
    pt, conf, rationale = _classify(text)
    assert pt != PageType.LISTICLE


def test_case_study_with_before_after_narrative():
    text = """# How We Migrated Northwind

Before and after the migration, the team measured results. After the switch,
reduced latency increased throughput across every service in production.
"""
    pt, conf, rationale = _classify(text)
    assert pt == PageType.CASE_STUDY


def test_service_cta_with_service_noun():
    text = """# Call Us for Plumbing Repair

Emergency plumbing repair and drain cleaning for homes and businesses. We
offer same-day service and free estimates. Book now to schedule a licensed
technician today.
"""
    pt, conf, rationale = _classify(text)
    assert pt == PageType.SERVICE


def test_about_page_vocabulary():
    text = """# About Us

Our story began in a garage. Today our team builds tools for thousands of
customers. Who we are: engineers, designers and support staff who care.
"""
    pt, conf, rationale = _classify(text)
    assert pt == PageType.ABOUT


def test_docs_with_code_fence():
    text = """# API Reference

Install with the following command and authenticate before calling the API.

```bash
npm install acme-sdk
```

The endpoint returns a JSON object describing the resource.
"""
    pt, conf, rationale = _classify(text)
    assert pt == PageType.DOCS
    assert "code" in rationale


def test_trust_policy_vocabulary():
    text = """# Privacy Policy

We describe how we process personal data under GDPR. This cookie policy
explains retention. Our terms of service govern use of the platform.
"""
    pt, conf, rationale = _classify(text)
    assert pt == PageType.TRUST_POLICY


def test_local_service_place_pattern():
    text = """# Emergency Plumbing in Austin TX

We serve customers in Austin, in Round Rock and in Cedar Park. Call any time
for fast help. Our service areas cover the greater metro region.
"""
    pt, conf, rationale = _classify(text)
    assert pt == PageType.LOCAL_SERVICE


def test_article_long_form_with_byline():
    text = "by Jane Smith. " + (
        "This long article explains how modern teams plan, review and ship "
        "software. " * 90
    )
    pt, conf, rationale = _classify(text)
    assert pt == PageType.ARTICLE
    assert "Jane Smith" in rationale


def test_fallback_to_general_for_short_unmarked_page():
    text = """# Warehouse

We keep boxes in a building. Nothing here matches any specific page type.
"""
    pt, conf, rationale = _classify(text)
    assert pt == PageType.GENERAL
    assert conf == pytest.approx(0.3)


def test_priority_order_glossary_beats_comparison():
    # A definition in the first 100 words must win even with "vs" in an H2.
    text = """# What is SEO?

SEO is defined as the practice of improving organic search visibility.
It involves technical fixes, content and links.

## Email vs SMS Marketing

Both channels work, but they differ in reach and cost per message.
"""
    pt, conf, rationale = _classify(text)
    assert pt == PageType.GLOSSARY


def test_classification_is_deterministic():
    text = "# Acme vs Globex\n\nWe compare the two platforms side by side.\n"
    first = _classify(text)
    second = _classify(text)
    assert first == second
