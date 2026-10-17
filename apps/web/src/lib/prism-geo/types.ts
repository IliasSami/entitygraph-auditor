export type SentimentType = "positive" | "neutral" | "negative";

export type StanceType =
  | "recommended_primary"
  | "recommended_alternative"
  | "neutral"
  | "warning_caution"
  | "omitted";

export type EngineType =
  | "perplexity"
  | "chatgpt"
  | "claude"
  | "gemini"
  | "google_aio"
  | "copilot";

export interface StanceMetrics {
  primaryCount: number;
  alternativeCount: number;
  neutralCount: number;
  warningCount: number;
  omittedCount: number;
  netStanceScore: number; // -1.0 to +1.0
}

export interface ProbabilisticMetric {
  citationProbability: number;
  wilsonInterval: [number, number]; // [lower, upper] 95% CI
  mentionRate: number;
  prominenceScore: number;
  effectiveVisibilityIndex: number; // EVI = P(Mention) * Prominence
  ndcpScore: number;
  conditionalNdcpScore: number;
  volatilityStdDev: number;
  sampleCount: number;
  sentimentDistribution: Record<SentimentType, number>;
  stanceDistribution: StanceMetrics;
}

export interface CSoVEntityShare {
  name: string;
  citations: number;
  marketSharePercentage: number;
  competitiveCSoVPercentage: number;
  smoothedCompetitiveCSoVPercentage: number;
  prominenceWeightedCSoVPercentage: number;
  topDomains?: string[];
  netStanceScore?: number;
}

export interface CSoVAnalysisResult {
  targetBrand: string;
  totalMarketCitations: number;
  totalCompetitiveCitations: number;
  editorialCitations: number;
  editorialDilutionRate: number;
  brandMarketShare: number;
  brandCompetitiveCSoV: number;
  smoothedBrandCompetitiveCSoV: number;
  brandProminenceWeightedCSoV: number;
  credenceWeight: number;
  entities: CSoVEntityShare[];
}

export interface ReverseRagAlignment {
  url: string;
  domain: string;
  matchedText: string;
  similarityScore: number; // Cosine TF-IDF (0.0 to 1.0)
  passageIndex: number;
  headingContext?: string;
}

export interface BrandRecord {
  id: string;
  slug: string;
  name: string;
  domain: string;
  description?: string;
  aliases: string[];
  valueProps: string[];
}

export interface CompetitorRecord {
  id: string;
  brandId: string;
  name: string;
  domain: string;
  aliases: string[];
  active: boolean;
}

export interface PromptRecord {
  id: string;
  brandId: string;
  queryText: string;
  intentType: string;
  personaDimension: string;
  active: boolean;
}

export interface PromptRunRecord {
  id: string;
  brandId: string;
  promptId: string;
  engine: string;
  runIndex: number;
  responseText: string;
  subQueries: string[];
  promptTokens?: number;
  executionMs: number;
  createdAt: string;
}

export interface CitationRecord {
  id: string;
  brandId: string;
  runId: string;
  domain: string;
  url: string;
  title?: string;
  snippet?: string;
  citationRank?: number;
  isBrandDomain?: boolean;
  isCompetitorDomain?: boolean;
}

export interface ReverseRagChunkRecord {
  id: string;
  citationId: string;
  chunkText: string;
  headingContext?: string;
  similarityScore: number;
}
