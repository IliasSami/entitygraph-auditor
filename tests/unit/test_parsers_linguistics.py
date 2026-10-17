"""Unit tests for deterministic linguistic utilities and normalization.

These back the extraction-quality flags and text statistics, so their edge
cases (abbreviations, decimals, CJK terminators, language gating) are pinned
here rather than only through the end-to-end parser tests.
"""

from __future__ import annotations

from ega_parsers.linguistics import (
    count_syllables,
    detect_language,
    readability,
    split_sentences,
    stopwords_for,
    tokenize_words,
)
from ega_parsers.normalize import block_normalized, content_hash, normalize_text

# --------------------------------------------------------------------------------------
# tokenization
# --------------------------------------------------------------------------------------

def test_tokenize_words_is_unicode_aware():
    assert tokenize_words("hello world's well-known") == ["hello", "world's", "well-known"]
    assert tokenize_words("বাংলা ভাষা") == ["বাংলা", "ভাষা"]


def test_tokenize_words_excludes_punctuation_and_digits_split():
    assert tokenize_words("costs $12.50 total!") == ["costs", "12", "50", "total"]


# --------------------------------------------------------------------------------------
# sentence splitting
# --------------------------------------------------------------------------------------

def test_split_on_plain_terminators():
    assert split_sentences("One. Two! Three?") == ["One.", "Two!", "Three?"]


def test_abbreviations_do_not_split():
    text = "Use e.g. this option. Dr. Smith agreed. The U.S. market grew."
    assert len(split_sentences(text)) == 3


def test_decimal_numbers_do_not_split():
    text = "The value is 3.14 exactly. Next sentence begins here."
    assert len(split_sentences(text)) == 2


def test_cjk_terminators_split():
    assert len(split_sentences("这是第一句。这是第二句！")) == 2


def test_ellipsis_splits_only_on_final_terminator():
    assert split_sentences("Wait... Now go.") == ["Wait...", "Now go."]


# --------------------------------------------------------------------------------------
# syllables + readability
# --------------------------------------------------------------------------------------

def test_syllable_counts_english_and_french():
    assert count_syllables("time", "en") == 1
    assert count_syllables("table", "en") == 2
    # French: best-effort vowel-group count after diacritic stripping.
    assert count_syllables("étude", "fr") == 3
    assert count_syllables("cœur", "fr") == 1


def test_readability_english_returns_both_values():
    text = "The cat sat on the mat. The dog ran to the park."
    fre, fk, warning = readability(text, "en")
    assert fre is not None and fk is not None
    assert warning is None


def test_readability_french_gives_fre_but_no_grade():
    text = "Le service est simple et rapide. Nous vous aidons à démarrer."
    fre, fk, warning = readability(text, "fr")
    assert fre is not None
    assert fk is None
    assert warning


def test_readability_unsupported_language_withheld():
    text = "এটি একটি পরীক্ষামূলক বাক্য যা ভাষা সনাক্তকরণ যাচাই করে।"
    fre, fk, warning = readability(text, "bn")
    assert fre is None and fk is None
    assert warning


# --------------------------------------------------------------------------------------
# language detection
# --------------------------------------------------------------------------------------

def test_detect_bengali_script():
    lang, confidence = detect_language("এটি একটি পরীক্ষামূলক বাক্য যা ভাষা সনাক্তকরণ যাচাই করে।")
    assert lang == "bn"
    assert confidence > 0.5


def test_detect_french_markers_and_accents():
    text = "Le service est simple pour une petite équipe avec beaucoup de fonctionnalités."
    lang, confidence = detect_language(text)
    assert lang == "fr"


def test_detect_english_fallback_is_low_confidence():
    lang, confidence = detect_language("The and for with that this from are the words here.")
    assert lang == "en"
    assert confidence <= 0.5


def test_detect_language_empty_text():
    lang, confidence = detect_language("")
    assert lang == "en"
    assert confidence <= 0.2


def test_stopwords_only_for_known_languages():
    assert "the" in stopwords_for("en")
    assert "le" in stopwords_for("fr")
    assert stopwords_for("bn") == frozenset()


# --------------------------------------------------------------------------------------
# normalization
# --------------------------------------------------------------------------------------

def test_normalize_text_strips_invisible_and_collapses_newlines():
    raw = "a\u200bb\n\n\n\nb\nc   "
    out = normalize_text(raw)
    assert "\u200b" not in out
    assert "\n\n\n" not in out
    assert not any(line.endswith(" ") for line in out.splitlines())


def test_normalize_text_is_idempotent():
    raw = "ﬁne\u00ad ligature\r\n\r\n\r\n   spaced   "
    once = normalize_text(raw)
    assert normalize_text(once) == once


def test_normalize_text_nfkc_compat():
    assert "fi" in normalize_text("ﬁne ligature")


def test_content_hash_is_stable_and_prefixed():
    assert content_hash("abc") == content_hash("abc")
    assert content_hash("abc") != content_hash("abd")
    assert content_hash("abc").startswith("sha256:")


def test_block_normalized_collapses_inner_newlines():
    out = block_normalized("line one\n\n\nline two")
    assert "\n\n" not in out
