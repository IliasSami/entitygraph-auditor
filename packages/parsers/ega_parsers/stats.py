"""Text statistics: counts, densities, repetition, boilerplate and duplicates.

The functions here operate on the *normalized* text plus the already-extracted
passages. They return a plain :class:`StatsData` value; assembling it into the
shared :class:`ega_schemas.content.TextStats` model happens once, in the
document assembly layer, so the math stays independent of schema churn.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from ega_parsers.linguistics import (
    detect_language,
    readability,
    split_sentences,
    stopwords_for,
    tokenize_words,
)

# A repeated line must be shorter than this (in words) to count as nav-like.
_NAV_LINE_MAX_WORDS = 5
_NAV_LINE_MIN_REPEATS = 3

_WHITESPACE_RUN = re.compile(r"\s+")


@dataclass(frozen=True)
class RepeatedPhrase:
    """A frequent 3- or 4-gram found across passages."""

    phrase: str
    count: int
    first_passage_id: str


@dataclass(frozen=True)
class StatsData:
    """Everything the shared ``TextStats`` model needs, in spec names."""

    char_count: int
    word_count: int
    sentence_count: int
    paragraph_count: int
    avg_sentence_words: float
    avg_paragraph_words: float
    long_sentence_ratio: float
    lexical_density: float
    language: str
    language_confidence: float
    flesch_reading_ease: float | None
    flesch_kincaid_grade: float | None
    readability_warning: str | None
    boilerplate_ratio: float
    duplicate_paragraph_ratio: float
    repeated_phrase_hits: list[RepeatedPhrase] = field(default_factory=list)


def count_words(text: str) -> int:
    """Number of Unicode word tokens in *text*."""
    return len(tokenize_words(text))


def paragraph_blocks(normalized_text: str) -> list[str]:
    """Non-empty paragraph blocks (split on blank lines)."""
    return [b.strip() for b in re.split(r"\n\s*\n", normalized_text) if b.strip()]


def long_sentence_ratio(normalized_text: str) -> tuple[float, int]:
    """``(ratio, sentence_count)`` for sentences longer than 30 words."""
    sentences = split_sentences(normalized_text)
    if not sentences:
        return 0.0, 0
    long_ones = sum(1 for s in sentences if len(tokenize_words(s)) > 30)
    return long_ones / len(sentences), len(sentences)


def lexical_density(normalized_text: str, language: str) -> float:
    """Ratio of non-stopword word tokens to all word tokens."""
    tokens = [t.lower() for t in tokenize_words(normalized_text)]
    if not tokens:
        return 0.0
    stops = stopwords_for(language)
    if stops:
        content = sum(1 for t in tokens if t not in stops)
    else:
        content = len(tokens)
    return round(content / len(tokens), 4)


def boilerplate_ratio(
    normalized_text: str, extra_lines: list[str] | None = None
) -> float:
    """Fraction of text made of repeated short nav-like lines.

    A line qualifies when it has fewer than 6 words and appears at least 3
    times in the pooled lines (visible text plus *extra_lines*, which carries
    the skipped nav/footer/aside blocks so template menus still contribute).
    """
    lines = [
        ln.strip()
        for ln in normalized_text.splitlines()
        if ln.strip()
    ]
    if extra_lines:
        lines.extend(ln.strip() for ln in extra_lines if ln.strip())
    if not lines:
        return 0.0
    counts = Counter(lines)
    repeated = {
        ln
        for ln, c in counts.items()
        if c >= _NAV_LINE_MIN_REPEATS and len(tokenize_words(ln)) < _NAV_LINE_MAX_WORDS
    }
    if not repeated:
        return 0.0
    total_chars = sum(len(ln) for ln in lines)
    if total_chars == 0:
        return 0.0
    repeated_chars = sum(len(ln) for ln in lines if ln in repeated)
    return round(repeated_chars / total_chars, 4)


def duplicate_paragraph_ratio(normalized_text: str) -> float:
    """Fraction of paragraphs whose normalized text appears more than once.

    All members of a duplicate group count, so two identical paragraphs out of
    four yield 0.5.
    """
    paragraphs = paragraph_blocks(normalized_text)
    if not paragraphs:
        return 0.0
    keys = [_WHITESPACE_RUN.sub(" ", p).strip().lower() for p in paragraphs]
    counts = Counter(keys)
    duplicates = sum(1 for k in keys if counts[k] > 1)
    return round(duplicates / len(paragraphs), 4)


def repeated_phrases(
    passage_texts: list[tuple[str, str]],
    language: str,
    min_repeats: int = 3,
    top: int = 10,
) -> list[RepeatedPhrase]:
    """Frequent 3-grams and 4-grams across passages.

    *passage_texts* is an ordered ``[(passage_id, text), ...]`` list. Tokens
    are lowercased and punctuation-stripped by tokenization; stopwords are
    removed for ``en``/``fr`` (no curated list exists for other languages, so
    no filtering happens there). Phrases appearing at least *min_repeats*
    times are returned, best count first, ties broken alphabetically for
    determinism.
    """
    stops = stopwords_for(language)
    counts: Counter[str] = Counter()
    first_seen: dict[str, str] = {}
    for passage_id, text in passage_texts:
        tokens = [t.lower() for t in tokenize_words(text)]
        if stops:
            tokens = [t for t in tokens if t not in stops]
        for n in (3, 4):
            for i in range(len(tokens) - n + 1):
                phrase = " ".join(tokens[i : i + n])
                counts[phrase] += 1
                first_seen.setdefault(phrase, passage_id)
    hits = [
        RepeatedPhrase(phrase=p, count=c, first_passage_id=first_seen[p])
        for p, c in counts.items()
        if c >= min_repeats
    ]
    hits.sort(key=lambda h: (-h.count, h.phrase))
    return hits[:top]


def compute_stats(
    normalized_text: str,
    passage_texts: list[tuple[str, str]],
    *,
    language_hint: str | None = None,
    boilerplate_extra_lines: list[str] | None = None,
) -> StatsData:
    """Compute every text statistic for a parsed document.

    *language_hint* overrides script-based detection only when it is one of
    the supported language codes (``en``/``fr``/``bn``); otherwise the
    detected language is used.
    """
    detected, confidence = detect_language(normalized_text)
    language = language_hint if language_hint in ("en", "fr", "bn") else detected

    word_count = count_words(normalized_text)
    char_count = len(normalized_text)
    paragraphs = paragraph_blocks(normalized_text)
    ratio_long, sentence_count = long_sentence_ratio(normalized_text)

    avg_sentence_words = round(word_count / sentence_count, 2) if sentence_count else 0.0
    avg_paragraph_words = round(word_count / len(paragraphs), 2) if paragraphs else 0.0

    fre, fk, warning = readability(normalized_text, language)

    return StatsData(
        char_count=char_count,
        word_count=word_count,
        sentence_count=sentence_count,
        paragraph_count=len(paragraphs),
        avg_sentence_words=avg_sentence_words,
        avg_paragraph_words=avg_paragraph_words,
        long_sentence_ratio=round(ratio_long, 4),
        lexical_density=lexical_density(normalized_text, language),
        language=language,
        language_confidence=round(confidence, 2),
        flesch_reading_ease=fre,
        flesch_kincaid_grade=fk,
        readability_warning=warning,
        boilerplate_ratio=boilerplate_ratio(normalized_text, boilerplate_extra_lines),
        duplicate_paragraph_ratio=duplicate_paragraph_ratio(normalized_text),
        repeated_phrase_hits=repeated_phrases(passage_texts, language),
    )
