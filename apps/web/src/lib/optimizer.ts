/**
 * Content Optimizer Engine for Entity SEO & Machine Retrieval
 * (Pure deterministic functions for real-time editor feedback)
 */

export interface HeadingItem {
  level: number;
  text: string;
  isQuestion: boolean;
  containsKeyword: boolean;
}

export interface EntityMatch {
  name: string;
  count: number;
  recommendedMin: number;
  recommendedMax: number;
  status: "missing" | "optimal" | "excessive" | "low";
  isPrimary?: boolean;
}

export interface BannedTermViolation {
  term: string;
  count: number;
  reason?: string;
  suggestedReplacement?: string;
}

export interface OptimizerMetrics {
  wordCount: number;
  charCount: number;
  readingTimeMinutes: number;
  sentenceCount: number;
  paragraphCount: number;
  fleschReadingEase: number;
  fleschKincaidGrade: number;
  readingLevel: string;
  headings: HeadingItem[];
  h1Count: number;
  h2Count: number;
  h3Count: number;
  entities: EntityMatch[];
  bannedViolations: BannedTermViolation[];
  overallScore: number; // 0-100
  categories: {
    entitySalience: { score: number; max: 25; label: string };
    headingHierarchy: { score: number; max: 20; label: string };
    contentDepth: { score: number; max: 20; label: string };
    readability: { score: number; max: 15; label: string };
    answerReadiness: { score: number; max: 10; label: string };
    brandSafety: { score: number; max: 10; label: string };
  };
  recommendations: Array<{
    priority: "high" | "medium" | "low";
    title: string;
    description: string;
    category: string;
  }>;
}

// Common English stop words
const STOP_WORDS = new Set([
  "a", "an", "the", "and", "or", "but", "if", "because", "as", "what",
  "which", "this", "that", "these", "those", "then", "just", "so", "than",
  "such", "both", "through", "about", "for", "is", "of", "while", "during",
  "to", "from", "in", "out", "on", "off", "again", "further", "then", "once",
  "here", "there", "when", "where", "why", "how", "all", "any", "both", "each",
  "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only",
  "own", "same", "so", "than", "too", "very", "s", "t", "can", "will", "don",
  "should", "now", "are", "was", "were", "been", "being", "have", "has", "had",
  "do", "does", "did", "with", "at", "by", "into", "its", "it", "they", "we"
]);

function countSyllables(word: string): number {
  const w = word.toLowerCase().replace(/[^a-z]/g, "");
  if (w.length <= 3) return 1;
  const cleaned = w.replace(/(?:[^laeiouy]|ed|es|e)$/, "").replace(/^y/, "");
  const syllables = cleaned.match(/[aeiouy]{1,2}/g);
  return syllables ? Math.max(1, syllables.length) : 1;
}

export function analyzeContent(
  text: string,
  primaryKeyword = "",
  bannedTerms: string[] = ["100% unhackable", "unhackable", "guarantee", "miracle", "foolproof"],
  targetWordCount = 800
): OptimizerMetrics {
  const clean = text.trim();
  if (!clean) {
    return getEmptyMetrics();
  }

  // 1. Basic Counts
  const words = clean.split(/\s+/).filter(Boolean);
  const wordCount = words.length;
  const charCount = clean.length;
  const readingTimeMinutes = Math.max(1, Math.round(wordCount / 200));

  // Paragraphs
  const paragraphs = clean.split(/\n\s*\n/).filter((p) => p.trim().length > 0);
  const paragraphCount = paragraphs.length;

  // Sentences
  const sentences = clean
    .split(/(?<=[.?!])\s+/)
    .map((s) => s.trim())
    .filter((s) => s.length > 2);
  const sentenceCount = Math.max(1, sentences.length);

  // 2. Readability (Flesch-Kincaid)
  const totalSyllables = words.reduce((sum, w) => sum + countSyllables(w), 0);
  const wordsPerSentence = wordCount / sentenceCount;
  const syllablesPerWord = totalSyllables / Math.max(1, wordCount);

  // Flesch Reading Ease = 206.835 - 1.015*(words/sentences) - 84.6*(syllables/words)
  let fleschReadingEase = Math.round(
    206.835 - 1.015 * wordsPerSentence - 84.6 * syllablesPerWord
  );
  fleschReadingEase = Math.max(0, Math.min(100, fleschReadingEase));

  // Flesch-Kincaid Grade Level = 0.39*(words/sentences) + 11.8*(syllables/words) - 15.59
  let fleschKincaidGrade = Math.round(
    0.39 * wordsPerSentence + 11.8 * syllablesPerWord - 15.59
  );
  fleschKincaidGrade = Math.max(1, Math.min(18, fleschKincaidGrade));

  let readingLevel = "Standard (High School)";
  if (fleschReadingEase >= 80) readingLevel = "Easy (Conversational)";
  else if (fleschReadingEase >= 60) readingLevel = "Standard (Plain English)";
  else if (fleschReadingEase >= 50) readingLevel = "Fairly Difficult (Professional)";
  else readingLevel = "Difficult (Technical / Academic)";

  // 3. Headings extraction
  const headings: HeadingItem[] = [];
  const lines = clean.split("\n");
  for (const line of lines) {
    const trimmed = line.trim();
    const mdMatch = trimmed.match(/^(#{1,6})\s+(.+)$/);
    if (mdMatch) {
      const level = mdMatch[1].length;
      const hText = mdMatch[2].trim();
      const isQuestion = /[?]$/i.test(hText) || /^(what|how|why|when|where|who|which|can|is|are|does)/i.test(hText);
      const containsKeyword = Boolean(
        primaryKeyword && hText.toLowerCase().includes(primaryKeyword.toLowerCase())
      );
      headings.push({ level, text: hText, isQuestion, containsKeyword });
    }
  }

  const h1Count = headings.filter((h) => h.level === 1).length;
  const h2Count = headings.filter((h) => h.level === 2).length;
  const h3Count = headings.filter((h) => h.level === 3).length;

  // 4. Entity & Keyword Extraction
  const entities: EntityMatch[] = [];
  const lowerText = clean.toLowerCase();

  // Primary keyword
  if (primaryKeyword) {
    const kwRegex = new RegExp(`\\b${escapeRegExp(primaryKeyword.toLowerCase())}\\b`, "gi");
    const count = (lowerText.match(kwRegex) || []).length;
    const targetMin = Math.max(2, Math.round(wordCount * 0.005));
    const targetMax = Math.max(4, Math.round(wordCount * 0.02));

    let status: EntityMatch["status"] = "optimal";
    if (count === 0) status = "missing";
    else if (count < targetMin) status = "low";
    else if (count > targetMax) status = "excessive";

    entities.push({
      name: primaryKeyword,
      count,
      recommendedMin: targetMin,
      recommendedMax: targetMax,
      status,
      isPrimary: true,
    });
  }

  // Auto-extract candidate entities (Capitalized noun phrases or frequent multi-word tokens)
  const candidateMap = new Map<string, number>();
  const nounPhraseRegex = /\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b/g;
  let match;
  while ((match = nounPhraseRegex.exec(clean)) !== null) {
    const phrase = match[1].trim();
    if (phrase.length > 3 && phrase.toLowerCase() !== primaryKeyword.toLowerCase()) {
      candidateMap.set(phrase, (candidateMap.get(phrase) || 0) + 1);
    }
  }

  // Also single capitalized technical terms
  const singleCapRegex = /\b([A-Z][a-z]{3,})\b/g;
  while ((match = singleCapRegex.exec(clean)) !== null) {
    const term = match[1].trim();
    if (!STOP_WORDS.has(term.toLowerCase()) && term.toLowerCase() !== primaryKeyword.toLowerCase()) {
      if (!candidateMap.has(term)) {
        candidateMap.set(term, (candidateMap.get(term) || 0) + 1);
      }
    }
  }

  // Sort and take top entities
  const sortedCandidates = Array.from(candidateMap.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10);

  for (const [name, count] of sortedCandidates) {
    const recommendedMin = Math.max(1, Math.round(wordCount * 0.003));
    const recommendedMax = Math.max(3, Math.round(wordCount * 0.015));
    let status: EntityMatch["status"] = "optimal";
    if (count < recommendedMin) status = "low";
    else if (count > recommendedMax) status = "excessive";

    entities.push({
      name,
      count,
      recommendedMin,
      recommendedMax,
      status,
    });
  }

  // 5. Banned Terms & Brand Safety
  const bannedViolations: BannedTermViolation[] = [];
  for (const term of bannedTerms) {
    if (!term) continue;
    const regex = new RegExp(`\\b${escapeRegExp(term)}\\b`, "gi");
    const matches = lowerText.match(regex);
    if (matches && matches.length > 0) {
      bannedViolations.push({
        term,
        count: matches.length,
        reason: "Prohibited absolute or non-compliant marketing claim",
      });
    }
  }

  // 6. Category Scores & Overall Score
  // A. Entity Salience (0-25)
  let entityScore = 0;
  if (primaryKeyword) {
    const prim = entities.find((e) => e.isPrimary);
    if (prim) {
      if (prim.count >= prim.recommendedMin && prim.count <= prim.recommendedMax) entityScore += 15;
      else if (prim.count > 0) entityScore += 8;
    }
    // Check first 100 words
    const first100 = words.slice(0, 100).join(" ").toLowerCase();
    if (first100.includes(primaryKeyword.toLowerCase())) {
      entityScore += 5;
    }
    // Secondary entity coverage
    const secOptimal = entities.filter((e) => !e.isPrimary && e.count >= 1).length;
    entityScore += Math.min(5, secOptimal);
  } else {
    entityScore = 18; // Default when no target keyword given
  }

  // B. Heading Hierarchy (0-20)
  let headingScore = 0;
  if (h1Count === 1) headingScore += 8;
  else if (h1Count > 1) headingScore += 3;
  if (h2Count >= 2) headingScore += 7;
  else if (h2Count === 1) headingScore += 4;
  if (headings.some((h) => h.isQuestion)) headingScore += 3;
  if (headings.some((h) => h.containsKeyword)) headingScore += 2;

  // C. Content Depth & Length (0-20)
  let depthScore = 0;
  const lengthRatio = wordCount / targetWordCount;
  if (lengthRatio >= 0.8 && lengthRatio <= 1.5) depthScore += 12;
  else if (lengthRatio >= 0.5) depthScore += 8;
  else depthScore += 4;

  if (paragraphCount >= 4) depthScore += 4;
  else if (paragraphCount >= 2) depthScore += 2;
  if (clean.includes("- ") || clean.includes("* ") || clean.includes("1. ")) depthScore += 4; // Lists / structured data

  // D. Readability (0-15)
  let readabilityScore = 0;
  if (fleschReadingEase >= 55 && fleschReadingEase <= 75) readabilityScore = 15;
  else if (fleschReadingEase >= 40) readabilityScore = 11;
  else readabilityScore = 7;

  // E. Answer Readiness & Passage Salience (0-10)
  let answerScore = 0;
  // Answer-first check: first paragraph is concise (30-60 words) and direct
  if (paragraphs[0]) {
    const p1Words = paragraphs[0].split(/\s+/).length;
    if (p1Words >= 20 && p1Words <= 75) answerScore += 5;
    else answerScore += 2;
  }
  if (headings.some((h) => h.level === 2 && h.isQuestion)) answerScore += 5;
  else if (h2Count >= 1) answerScore += 3;

  // F. Brand Safety (0-10)
  let brandScore = 10;
  if (bannedViolations.length > 0) {
    brandScore = Math.max(0, 10 - bannedViolations.length * 4);
  }

  const overallScore = Math.min(
    100,
    entityScore + headingScore + depthScore + readabilityScore + answerScore + brandScore
  );

  // 7. Actionable Recommendations
  const recommendations: OptimizerMetrics["recommendations"] = [];

  if (primaryKeyword) {
    const prim = entities.find((e) => e.isPrimary);
    if (!prim || prim.count === 0) {
      recommendations.push({
        priority: "high",
        category: "Entity SEO",
        title: `Include primary entity "${primaryKeyword}"`,
        description: `Your draft currently does not mention the primary entity "${primaryKeyword}". Mention it in the title, first paragraph, and at least one H2.`,
      });
    } else if (prim.count < prim.recommendedMin) {
      recommendations.push({
        priority: "medium",
        category: "Entity SEO",
        title: `Increase mentions of "${primaryKeyword}"`,
        description: `Found ${prim.count} mention(s). Recommended target is ${prim.recommendedMin}-${prim.recommendedMax} mentions for natural entity salience.`,
      });
    }
  }

  if (h1Count === 0) {
    recommendations.push({
      priority: "high",
      category: "Structure",
      title: "Add a single H1 Title heading",
      description: "Start the article with a clear, descriptive H1 heading containing your target topic.",
    });
  } else if (h1Count > 1) {
    recommendations.push({
      priority: "medium",
      category: "Structure",
      title: "Multiple H1 headings detected",
      description: `Found ${h1Count} H1 tags. Best practice for search engines and screen readers is exactly one H1 per page. Use H2 for sub-topics.`,
    });
  }

  if (h2Count < 2) {
    recommendations.push({
      priority: "high",
      category: "Structure",
      title: "Add more H2 subheadings",
      description: "Structure your content with at least two or three H2 headings to divide the article into clear thematic sections.",
    });
  }

  if (!headings.some((h) => h.isQuestion)) {
    recommendations.push({
      priority: "medium",
      category: "AEO / AI Search",
      title: "Add an FAQ or question-based H2 heading",
      description: "Headings formatted as direct questions (e.g., 'How Does...', 'What Is...') align with generative engine query fan-out.",
    });
  }

  if (bannedViolations.length > 0) {
    recommendations.push({
      priority: "high",
      category: "Compliance",
      title: `Remove ${bannedViolations.length} prohibited term(s)`,
      description: `Flagged: ${bannedViolations.map((v) => `"${v.term}" (${v.count}x)`).join(", ")}. Replace with objective, verifiable statements.`,
    });
  }

  if (wordCount < targetWordCount * 0.7) {
    recommendations.push({
      priority: "medium",
      category: "Depth",
      title: `Expand content length (currently ${wordCount} words)`,
      description: `Target benchmark is ~${targetWordCount} words. Add practical examples, architecture details, or step-by-step guidance.`,
    });
  }

  if (fleschReadingEase < 50) {
    recommendations.push({
      priority: "low",
      category: "Readability",
      title: "Simplify complex sentences",
      description: `Reading ease is ${fleschReadingEase}/100. Break up long compound sentences into concise, punchy statements.`,
    });
  }

  return {
    wordCount,
    charCount,
    readingTimeMinutes,
    sentenceCount,
    paragraphCount,
    fleschReadingEase,
    fleschKincaidGrade,
    readingLevel,
    headings,
    h1Count,
    h2Count,
    h3Count,
    entities,
    bannedViolations,
    overallScore,
    categories: {
      entitySalience: { score: entityScore, max: 25, label: "Entity Salience" },
      headingHierarchy: { score: headingScore, max: 20, label: "Heading Hierarchy" },
      contentDepth: { score: depthScore, max: 20, label: "Content Depth" },
      readability: { score: readabilityScore, max: 15, label: "Readability" },
      answerReadiness: { score: answerScore, max: 10, label: "Answer Readiness" },
      brandSafety: { score: brandScore, max: 10, label: "Brand Safety" },
    },
    recommendations,
  };
}

function getEmptyMetrics(): OptimizerMetrics {
  return {
    wordCount: 0,
    charCount: 0,
    readingTimeMinutes: 0,
    sentenceCount: 0,
    paragraphCount: 0,
    fleschReadingEase: 0,
    fleschKincaidGrade: 0,
    readingLevel: "—",
    headings: [],
    h1Count: 0,
    h2Count: 0,
    h3Count: 0,
    entities: [],
    bannedViolations: [],
    overallScore: 0,
    categories: {
      entitySalience: { score: 0, max: 25, label: "Entity Salience" },
      headingHierarchy: { score: 0, max: 20, label: "Heading Hierarchy" },
      contentDepth: { score: 0, max: 20, label: "Content Depth" },
      readability: { score: 0, max: 15, label: "Readability" },
      answerReadiness: { score: 0, max: 10, label: "Answer Readiness" },
      brandSafety: { score: 10, max: 10, label: "Brand Safety" },
    },
    recommendations: [
      {
        priority: "high",
        category: "Content",
        title: "Start writing or paste an article draft",
        description: "Paste your markdown or draft in the editor to get real-time entity scoring, readability diagnostics, and search crawler readiness.",
      },
    ],
  };
}

function escapeRegExp(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
