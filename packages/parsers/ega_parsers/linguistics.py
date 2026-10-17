"""Deterministic linguistic utilities: tokenization, sentence splitting,
syllable counting, language detection and readability formulas.

Everything here is pure functions over strings so results are reproducible
across runs. English formulas are never applied to non-English text; the
caller receives an explicit warning instead (see :func:`readability`).
"""

from __future__ import annotations

import re
import unicodedata

# --------------------------------------------------------------------------------------
# Tokenization
# --------------------------------------------------------------------------------------

# A "word" is a run of letters/digits (Unicode-aware) optionally joined with
# internal apostrophes/hyphens. The Bengali block is added explicitly because
# its vowel signs and marks are combining characters (category Mc/Mn) that are
# not ``\w``; without them Bengali text would tokenize into single consonants.
_WORD_CHAR = r"[^\W_]|[\u0980-\u09FF]"
WORD_RE = re.compile(rf"(?:{_WORD_CHAR})+(?:['’\-](?:{_WORD_CHAR})+)*", re.UNICODE)

# Sentence terminators: Latin, fullwidth and CJK.
_TERMINATORS = ".!?…。！？!?；;"

_ABBREVIATIONS = (
    frozenset(
        {
            # English
            "e.g", "i.e", "etc", "vs", "dr", "mr", "mrs", "ms", "prof", "st", "no",
            "fig", "cf", "approx", "jr", "sr", "inc", "ltd", "co", "dept", "est",
            "min", "max", "vol", "pp", "al", "ca", "ed", "eds", "resp",
            "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct",
            "nov", "dec", "mon", "tues", "wed", "thur", "fri", "sat", "sun",
            "u.s", "u.k", "a.m", "p.m", "ph.d", "b.a", "m.a", "m.sc", "b.sc",
            "govt", "intl", "misc", "obj", "subj", "ex", "incl", "desc", "spec",
        }
    )
    # French
    | frozenset(
        {
            "m", "mme", "mlle", "mgr", "me", "env", "jur",
            "tel", "bd", "av", "pl", "c.-à-d", "janv", "févr", "avr",
            "juil", "déc",
        }
    )
)

# Words that are lowercase single letters used as sentence words, protect them
# from abbreviation false-positives by requiring a following capital in some
# contexts is too clever; we keep the list conservative instead.

_ABBREV_RE = re.compile(r"([A-Za-zÀ-ÖØ-öø-ÿ]\.)(?:[A-Za-zÀ-ÖØ-öø-ÿ]\.)+")


def tokenize_words(text: str) -> list[str]:
    """Return Unicode word tokens (punctuation excluded by construction)."""
    return WORD_RE.findall(text)


def _is_abbreviation(text: str, dot_index: int) -> bool:
    """True if the ``.`` at *dot_index* terminates a known abbreviation."""
    # Walk back to the start of the token (letters, dots, apostrophes).
    start = dot_index
    while start > 0 and (text[start - 1].isalpha() or text[start - 1] in ".-'’"):
        start -= 1
    token = text[start : dot_index + 1]
    if not token:
        return False
    core = token.rstrip(".").lower()
    if core in _ABBREVIATIONS:
        return True
    # Multi-dot initials like "U.S." / "Ph.D." — the last dot ends the token.
    if "." in core and all(len(p) <= 1 for p in core.split(".")):
        return True
    return False


def split_sentences(text: str) -> list[str]:
    """Split *text* into sentences.

    Handles:

    * abbreviations (``e.g.``, ``i.e.``, ``Dr.``, ``Mr.``, ``vs.``, ``U.S.``,
      French ``M.``/``Mme.``) — no split after them;
    * decimal numbers (``3.14``) — no split inside;
    * CJK/fullwidth terminators (``。！？``);
    * closing quotes/brackets immediately after a terminator;
    * em-dash/parens after the terminator are *not* treated as continuation
      signals, so ``... (see below). Next`` still splits.
    """
    sentences: list[str] = []
    n = len(text)
    if not text.strip():
        return sentences

    i = 0
    sent_start = 0
    while i < n:
        ch = text[i]
        if ch in _TERMINATORS:
            # Decimal number: digit . digit
            if ch == "." and i > 0 and i + 1 < n and text[i - 1].isdigit() and text[i + 1].isdigit():
                i += 1
                continue
            if ch == "." and _is_abbreviation(text, i):
                i += 1
                continue
            # Skip ellipsis runs: only split on the final terminator.
            if ch in ".…" and i + 1 < n and text[i + 1] in ".…":
                i += 1
                continue
            # CJK terminators split unconditionally; Latin ones require a
            # following space/end (guards against "3.14" and stray dots).
            j = i + 1
            # Swallow closing quotes/brackets that hug the terminator.
            while j < n and text[j] in "\"'”’»）)]}":
                j += 1
            at_end = j >= n
            after = text[j] if j < n else ""
            if ch in "。！？！？;；":
                splits = True
            elif at_end:
                splits = True
            elif after in " \t\n":
                # Require that what follows looks like a new sentence start:
                # a letter/digit/CJK char (not another terminator-only run).
                k = j
                while k < n and text[k] in " \t\n\"'“‘([{":
                    k += 1
                splits = k < n and (text[k].isalnum() or text[k] in "\"'“‘([{$€£¥")
            else:
                splits = False
            if splits:
                candidate = text[sent_start:j].strip()
                if candidate:
                    sentences.append(candidate)
                sent_start = j
            i = j if j > i else i + 1
            continue
        i += 1

    tail = text[sent_start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


# --------------------------------------------------------------------------------------
# Syllables
# --------------------------------------------------------------------------------------

def _strip_diacritics(word: str) -> str:
    decomposed = unicodedata.normalize("NFD", word)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def count_syllables(word: str, language: str = "en") -> int:
    """Count syllables as contiguous vowel groups.

    * English: subtract one silent trailing ``e`` (``time`` → 1) unless the
      word ends in ``-le`` after a consonant (``table`` → 2).
    * French: pure vowel-group count after diacritic stripping, so ``cœur`` → 1
      and ``étude`` → 3 (a best-effort vowel-group count, not a phonetic one —
      French mute ``e`` still counts as a group).
    * Other languages: vowel-group count (best effort; callers avoid English
      readability formulas for these languages anyway).
    """
    lower = unicodedata.normalize("NFC", word).lower()
    if not lower:
        return 0
    if language == "fr":
        probe = _strip_diacritics(lower).replace("œ", "oe").replace("æ", "ae")
    else:
        probe = lower.replace("œ", "oe").replace("æ", "ae")
    groups = re.findall(r"[aeiouy]+", probe)
    count = len(groups)
    if count == 0:
        # Borrowed words / acronyms: treat each alphabetic char block as 1.
        return 1 if any(ch.isalpha() for ch in lower) else 0
    if language == "en" and count > 1 and probe.endswith("e") and not probe.endswith(
        ("le", "ee", "ye", "ie", "oe", "ue")
    ):
        count -= 1
    return max(count, 1)


def total_syllables(words: list[str], language: str) -> int:
    """Sum of per-word syllable counts."""
    return sum(count_syllables(w, language) for w in words)


# --------------------------------------------------------------------------------------
# Stopwords
# --------------------------------------------------------------------------------------

STOPWORDS_EN = frozenset(
    """
    a about above after again against all am an and any are as at be because
    been before being below between both but by can cannot could did do does
    doing down during each few for from further had has have having he her here
    hers herself him himself his how i if in into is it its itself just me more
    most my myself no nor not of off on once only or other ought our ours
    ourselves out over own same she should so some such than that the their
    theirs them themselves then there these they this those through to too under
    until up very was we were what when where which while who whom why with would
    you your yours yourself yourselves s t don ll re ve
    """.split()
)

STOPWORDS_FR = frozenset(
    """
    au aux avec ce ces dans de des du elle en et eux il ils je la le les leur
    lui ma mais me meme mes moi mon ne ni nos notre nous on ou par pas pour qu
    que qui sa se ses son sur ta te tes toi ton tu un une vos votre vous c d j l
    a m est sont etait etre avait fait faire plus tres cette cet maintenant
    alors aussi bien encore jamais toujours tout tous toute toutes autre autres
    entre chez sans sous depuis jusqu pourquoi comment
    """.split()
)

_STOPWORD_MAP = {"en": STOPWORDS_EN, "fr": STOPWORDS_FR}


def stopwords_for(language: str) -> frozenset[str]:
    """Stopword list for *language*; empty when no curated list exists."""
    return _STOPWORD_MAP.get(language, frozenset())


# --------------------------------------------------------------------------------------
# Language detection
# --------------------------------------------------------------------------------------

_BENGALI_RANGE = (0x0980, 0x09FF)

# High-frequency French function words and accent markers.
_FRENCH_MARKERS = frozenset(
    {"le", "la", "les", "des", "une", "est", "pour", "avec", "dans", "que",
     "qui", "pas", "sur", "son", "ses", "mais", "tout", "nous", "vous"}
)
_FRENCH_ACCENTS = set("àâçéèêëîïôùûüÿœ")


def detect_language(text: str) -> tuple[str, float]:
    """Script/keyword based language detection.

    Returns ``(language, confidence)`` where language is one of ``"bn"``,
    ``"fr"``, ``"en"``.

    * Bengali script dominance → ``bn`` (high confidence).
    * French function words + accented characters → ``fr``.
    * Otherwise ``en`` with *low* confidence — the caller must treat this as a
      fallback guess, not an assertion.
    """
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return "en", 0.2
    total = len(letters)
    bengali = sum(1 for ch in letters if _BENGALI_RANGE[0] <= ord(ch) <= _BENGALI_RANGE[1])
    if bengali / total >= 0.20:
        return "bn", min(0.5 + bengali / total, 0.99)

    words = [w.lower() for w in WORD_RE.findall(text)]
    marker_hits = sum(1 for w in words if w in _FRENCH_MARKERS)
    accent_count = sum(1 for ch in text.lower() if ch in _FRENCH_ACCENTS)
    french_score = marker_hits + min(accent_count, 20) * 0.5
    if marker_hits >= 3 and (accent_count >= 1 or marker_hits >= 5):
        confidence = min(0.55 + french_score / 60, 0.95)
        return "fr", confidence
    if accent_count >= 3 and marker_hits >= 2:
        return "fr", min(0.5 + french_score / 60, 0.9)

    # Fallback: English assumed, explicitly low confidence.
    english_markers = {"the", "and", "for", "with", "that", "this", "from"}
    hits = sum(1 for w in words if w in english_markers)
    confidence = 0.4 if hits >= 3 else 0.3
    return "en", confidence


# --------------------------------------------------------------------------------------
# Readability
# --------------------------------------------------------------------------------------

_READABILITY_NOT_VALIDATED = (
    "Readability formula not validated for this language; qualitative rubric used instead."
)
_FRENCH_WARNING = "French-adapted formula; approximate."


def readability(
    text: str, language: str
) -> tuple[float | None, float | None, str | None]:
    """Return ``(flesch_reading_ease, flesch_kincaid_grade, warning)``.

    * ``en``: standard Flesch Reading Ease and Flesch–Kincaid Grade Level.
    * ``fr``: standard French adaptation
      ``207 − 1.015·(words/sentences) − 73/(syllables/words)``; both returned
      values use the French formula and the French warning is set.
    * anything else: both values ``None`` and the "not validated" warning —
      English formulas are **never** applied silently to other languages.
    """
    words = tokenize_words(text)
    sentences = split_sentences(text)
    if not words or not sentences:
        if language == "fr":
            return None, None, _FRENCH_WARNING
        if language == "en":
            return None, None, None
        return None, None, _READABILITY_NOT_VALIDATED

    avg_sentence_words = len(words) / len(sentences)
    syllables = total_syllables(words, language)
    avg_syllables_per_word = syllables / len(words)

    if language == "en":
        if avg_syllables_per_word <= 0:
            return None, None, None
        fre = 206.835 - 1.015 * avg_sentence_words - 84.6 * avg_syllables_per_word
        fk = 0.39 * avg_sentence_words + 11.8 * avg_syllables_per_word - 15.59
        return round(fre, 2), round(fk, 2), None
    if language == "fr":
        if avg_syllables_per_word <= 0:
            return None, None, _FRENCH_WARNING
        # Standard French adaptation of Flesch Reading Ease. The
        # Flesch–Kincaid grade level has no validated French equivalent, so it
        # is deliberately left as None rather than silently using the English
        # formula.
        fre = 207 - 1.015 * avg_sentence_words - 73 / avg_syllables_per_word
        return round(fre, 2), None, _FRENCH_WARNING
    return None, None, _READABILITY_NOT_VALIDATED
