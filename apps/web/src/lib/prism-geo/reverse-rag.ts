const STOP_WORDS = new Set([
  "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
  "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but",
  "by", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from",
  "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him",
  "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just",
  "me", "more", "most", "my", "myself", "no", "nor", "not", "now", "of", "off", "on", "once",
  "only", "or", "other", "our", "ours", "ourselves", "out", "over", "own", "same", "she",
  "should", "so", "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves",
  "then", "there", "these", "they", "this", "those", "through", "to", "too", "under", "until",
  "up", "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom",
  "why", "with", "would", "you", "your", "yours", "yourself", "yourselves"
]);

export class ReverseRagParser {
  /**
   * Tokenize text into normalized word stems, omitting common stop words.
   */
  public static tokenize(text: string): string[] {
    if (!text) return [];
    return text
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, " ")
      .split(/\s+/)
      .filter((w) => w.length > 2 && !STOP_WORDS.has(w));
  }

  /**
   * Compute Cosine TF-IDF vector similarity between query answer and passage chunk.
   */
  public static calculateCosineSimilarity(textA: string, textB: string): number {
    const tokensA = this.tokenize(textA);
    const tokensB = this.tokenize(textB);

    if (tokensA.length === 0 || tokensB.length === 0) return 0;

    const freqA: Record<string, number> = {};
    const freqB: Record<string, number> = {};

    for (const t of tokensA) freqA[t] = (freqA[t] || 0) + 1;
    for (const t of tokensB) freqB[t] = (freqB[t] || 0) + 1;

    let dotProduct = 0;
    let normA = 0;
    let normB = 0;

    for (const t in freqA) {
      normA += freqA[t] * freqA[t];
      if (freqB[t]) {
        dotProduct += freqA[t] * freqB[t];
      }
    }

    for (const t in freqB) {
      normB += freqB[t] * freqB[t];
    }

    const denom = Math.sqrt(normA) * Math.sqrt(normB);
    if (denom === 0) return 0;

    return Number(Math.min(1.0, dotProduct / denom).toFixed(3));
  }

  /**
   * Normalize URLs, unwrapping Google/Bing click redirect wrappers and stripping tracking tags.
   */
  public static normalizeUrl(rawUrl: string): { normalizedUrl: string; domain: string } {
    if (!rawUrl) return { normalizedUrl: "", domain: "unknown" };
    let clean = rawUrl.trim().replace(/[.,;:)\]>"']+$/, "");

    // Unwrap Google click redirect
    if (clean.includes("/url?q=")) {
      try {
        const u = new URL(clean);
        const target = u.searchParams.get("q");
        if (target) clean = target;
      } catch {
        // ignore
      }
    }

    try {
      const parsed = new URL(clean);
      const domain = parsed.hostname.toLowerCase().replace(/^www\./, "");
      return { normalizedUrl: clean, domain };
    } catch {
      return { normalizedUrl: clean, domain: "unknown" };
    }
  }
}
