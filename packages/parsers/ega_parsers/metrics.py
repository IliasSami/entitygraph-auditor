"""Deterministic text metrics and readability heuristics."""

from __future__ import annotations

import re
from collections import Counter


def compute_reading_time_minutes(word_count: int, wpm: int = 200) -> float:
    """Estimated reading time at 200 words per minute."""
    if word_count <= 0:
        return 0.0
    return round(word_count / float(wpm), 2)


def extract_sentences(text: str) -> list[str]:
    """Split text into sentences using regex boundary detection."""
    if not text:
        return []
    # Match sentences ending with ., !, ?, considering quotes and brackets
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"\'\(\[])', text.strip())
    return [s.strip() for s in sentences if s.strip()]


def compute_lexical_diversity(words: list[str]) -> float:
    """Type-Token Ratio (TTR) for vocabulary richness."""
    if not words:
        return 0.0
    tokens = [w.lower() for w in words if w.isalnum()]
    if not tokens:
        return 0.0
    return round(len(set(tokens)) / float(len(tokens)), 3)


def detect_repeated_phrases(text: str, n_gram: int = 3, min_count: int = 3) -> list[tuple[str, int]]:
    """Detect potential keyword-stuffing patterns by analyzing repeated n-grams."""
    words = [w.lower() for w in re.findall(r'\b[a-zA-Z0-9_-]+\b', text)]
    if len(words) < n_gram:
        return []
    
    ngrams = [' '.join(words[i:i + n_gram]) for i in range(len(words) - n_gram + 1)]
    counts = Counter(ngrams)
    return [(phrase, count) for phrase, count in counts.most_common() if count >= min_count]


def compute_flesch_reading_ease(text: str) -> float:
    """Heuristic Flesch Reading Ease score (0 - 100)."""
    words = re.findall(r'\b[a-zA-Z]+\b', text)
    sentences = extract_sentences(text)
    
    total_words = len(words)
    total_sentences = max(1, len(sentences))
    
    if total_words == 0:
        return 0.0

    # Syllable approximation
    def count_syllables(word: str) -> int:
        word = word.lower()
        if len(word) <= 3:
            return 1
        word = re.sub(r'(?:[^laeiouy]|ed|es|e)$', '', word)
        word = re.sub(r'^y', '', word)
        syllables = len(re.findall(r'[aeiouy]{1,2}', word))
        return max(1, syllables)

    total_syllables = sum(count_syllables(w) for w in words)
    
    asl = total_words / float(total_sentences)  # Average Sentence Length
    asw = total_syllables / float(total_words)  # Average Syllables per Word
    
    score = 206.835 - (1.015 * asl) - (84.6 * asw)
    return round(max(0.0, min(100.0, score)), 1)
