"""Unit tests for ega_parsers."""

from ega_parsers import (
    DocumentParser,
    compute_flesch_reading_ease,
    compute_lexical_diversity,
    detect_repeated_phrases,
    extract_sentences,
)


def test_markdown_parsing():
    content = """# Main Entity Guide
This is the opening introduction for Acme System.

## Features
Acme System provides high-speed automated caching.
It also includes distributed data synchronization.

[Official Documentation](https://example.com/docs)
"""
    doc = DocumentParser.parse(content, default_title="Fallback Title")
    assert doc.title == "Main Entity Guide"
    assert len(doc.headings) == 2
    assert doc.headings[0].text == "Main Entity Guide"
    assert doc.headings[0].level == 1
    assert doc.headings[1].text == "Features"
    assert doc.headings[1].level == 2
    assert len(doc.passages) >= 2
    assert len(doc.links) == 1
    assert doc.links[0].url == "https://example.com/docs"
    assert doc.links[0].anchor_text == "Official Documentation"
    assert doc.word_count > 10


def test_html_parsing():
    html = """<!DOCTYPE html>
<html>
<head><title>Service Landing Page</title></head>
<body>
  <h1>Emergency Plumbing NYC</h1>
  <p>Acme Plumbing provides 24/7 licensed drain cleaning in Brooklyn.</p>
  <p>We are the fastest plumbers in the city.</p>
  <a href="/pricing">View Pricing</a>
</body>
</html>
"""
    doc = DocumentParser.parse(html)
    assert doc.title == "Service Landing Page"
    assert len(doc.headings) == 1
    assert doc.headings[0].text == "Emergency Plumbing NYC"
    assert len(doc.passages) == 2
    assert doc.passages[0].named_subject is True
    assert doc.passages[1].named_subject is False  # Starts with "We "
    assert len(doc.links) == 1
    assert doc.links[0].is_internal is True


def test_text_metrics():
    text = "The quick brown fox jumps over the lazy dog. A lazy dog sleeps under the warm sun."
    sentences = extract_sentences(text)
    assert len(sentences) == 2
    
    ttr = compute_lexical_diversity(text.split())
    assert 0.0 < ttr <= 1.0

    ease = compute_flesch_reading_ease(text)
    assert ease > 50.0  # Simple English text


def test_detect_repeated_phrases():
    stuffed_text = "best plumber new york. call the best plumber new york today. our best plumber new york team is ready."
    repeated = detect_repeated_phrases(stuffed_text, n_gram=3, min_count=2)
    assert len(repeated) > 0
    phrase, count = repeated[0]
    assert "best plumber new" in phrase
    assert count >= 3
