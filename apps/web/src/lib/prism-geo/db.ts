import path from "node:path";
import fs from "node:fs";
import { DatabaseSync } from "node:sqlite";
import { MonteCarloMetricsCalculator } from "./metrics";
import type {
  BrandRecord,
  CompetitorRecord,
  PromptRecord,
  PromptRunRecord,
  CitationRecord,
  ReverseRagChunkRecord,
} from "./types";

interface BrandRow {
  id: string;
  slug: string;
  name: string;
  domain: string;
  description?: string;
  aliases_json?: string;
  value_props_json?: string;
}

interface CompetitorRow {
  id: string;
  brand_id: string;
  name: string;
  domain: string;
  aliases_json?: string;
  active: number;
}

interface PromptRow {
  id: string;
  brand_id: string;
  query_text: string;
  intent_type: string;
  persona_dimension: string;
  active: number;
}

interface PromptRunRow {
  id: string;
  brand_id: string;
  prompt_id: string;
  engine: string;
  run_index: number;
  response_text: string;
  sub_queries_json?: string;
  prompt_tokens?: number;
  execution_ms: number;
  created_at: string;
}

interface CitationRow {
  id: string;
  brand_id: string;
  run_id: string;
  domain: string;
  url: string;
  title?: string;
  snippet?: string;
  citation_rank?: number;
  is_brand_domain?: number;
  is_competitor_domain?: number;
}

interface ReverseRagChunkRow {
  id: string;
  citation_id: string;
  chunk_text: string;
  heading_context?: string;
  similarity_score?: number;
}

function resolveDbPath(): string {
  if (process.env.PRISMGEO_DB_PATH && fs.existsSync(process.env.PRISMGEO_DB_PATH)) {
    return process.env.PRISMGEO_DB_PATH;
  }

  // Walk upwards from cwd to locate prism-geo/data/prismgeo.db
  let curr = process.cwd();
  for (let i = 0; i < 5; i++) {
    const candidate = path.join(curr, "prism-geo", "data", "prismgeo.db");
    if (fs.existsSync(candidate)) return candidate;
    const parent = path.dirname(curr);
    if (parent === curr) break;
    curr = parent;
  }

  // Last resort: relative to the current working directory. (No hard-coded
  // absolute paths — those leak a developer machine and break in containers.)
  return path.resolve(process.cwd(), "prism-geo/data/prismgeo.db");
}

let _dbInstance: DatabaseSync | null = null;

function getSqliteDb(): DatabaseSync | null {
  if (_dbInstance) return _dbInstance;
  const dbPath = resolveDbPath();
  if (!fs.existsSync(/*turbopackIgnore: true*/ dbPath)) return null;

  try {
    const db = new DatabaseSync(dbPath, { readOnly: true });
    _dbInstance = db;
    return db;
  } catch (err) {
    console.error("Failed to open PrismGEO sqlite database:", err);
    return null;
  }
}

export class PrismGeoService {
  public static isAvailable(): boolean {
    return getSqliteDb() !== null;
  }

  public static getBrands(): BrandRecord[] {
    const db = getSqliteDb();
    if (!db) return [];
    try {
      const rows = db.prepare("SELECT * FROM brands ORDER BY name ASC").all() as unknown as BrandRow[];
      return rows.map((r) => ({
        id: r.id,
        slug: r.slug,
        name: r.name,
        domain: r.domain,
        description: r.description,
        aliases: JSON.parse(r.aliases_json || "[]"),
        valueProps: JSON.parse(r.value_props_json || "[]"),
      }));
    } catch {
      return [];
    }
  }

  public static getBrand(brandIdOrSlug?: string): BrandRecord | null {
    const db = getSqliteDb();
    if (!db) return null;
    try {
      let row: BrandRow | undefined;
      if (brandIdOrSlug) {
        row = db
          .prepare("SELECT * FROM brands WHERE id = ? OR slug = ? LIMIT 1")
          .get(brandIdOrSlug, brandIdOrSlug) as unknown as BrandRow | undefined;
      }
      if (!row) {
        row = db.prepare("SELECT * FROM brands ORDER BY id ASC LIMIT 1").get() as unknown as BrandRow | undefined;
      }
      if (!row) return null;
      return {
        id: row.id,
        slug: row.slug,
        name: row.name,
        domain: row.domain,
        description: row.description,
        aliases: JSON.parse(row.aliases_json || "[]"),
        valueProps: JSON.parse(row.value_props_json || "[]"),
      };
    } catch {
      return null;
    }
  }

  public static getCompetitors(brandId: string): CompetitorRecord[] {
    const db = getSqliteDb();
    if (!db) return [];
    try {
      const rows = db.prepare("SELECT * FROM competitors WHERE brand_id = ?").all(brandId) as unknown as CompetitorRow[];
      return rows.map((r) => ({
        id: r.id,
        brandId: r.brand_id,
        name: r.name,
        domain: r.domain,
        aliases: JSON.parse(r.aliases_json || "[]"),
        active: Boolean(r.active),
      }));
    } catch {
      return [];
    }
  }

  public static getPrompts(brandId: string): PromptRecord[] {
    const db = getSqliteDb();
    if (!db) return [];
    try {
      const rows = db.prepare("SELECT * FROM prompts WHERE brand_id = ?").all(brandId) as unknown as PromptRow[];
      return rows.map((r) => ({
        id: r.id,
        brandId: r.brand_id,
        queryText: r.query_text,
        intentType: r.intent_type,
        personaDimension: r.persona_dimension,
        active: Boolean(r.active),
      }));
    } catch {
      return [];
    }
  }

  public static getPromptRuns(brandId: string, limit = 500): PromptRunRecord[] {
    const db = getSqliteDb();
    if (!db) return [];
    try {
      const rows = db
        .prepare("SELECT * FROM prompt_runs WHERE brand_id = ? ORDER BY created_at DESC LIMIT ?")
        .all(brandId, limit) as unknown as PromptRunRow[];
      return rows.map((r) => ({
        id: r.id,
        brandId: r.brand_id,
        promptId: r.prompt_id,
        engine: r.engine,
        runIndex: r.run_index,
        responseText: r.response_text,
        subQueries: JSON.parse(r.sub_queries_json || "[]"),
        promptTokens: r.prompt_tokens,
        executionMs: r.execution_ms,
        createdAt: r.created_at,
      }));
    } catch {
      return [];
    }
  }

  public static getCitations(brandId: string, limit = 300): CitationRecord[] {
    const db = getSqliteDb();
    if (!db) return [];
    try {
      const rows = db
        .prepare("SELECT * FROM citations WHERE brand_id = ? ORDER BY id DESC LIMIT ?")
        .all(brandId, limit) as unknown as CitationRow[];
      return rows.map((r) => ({
        id: r.id,
        brandId: r.brand_id,
        runId: r.run_id,
        domain: r.domain,
        url: r.url,
        title: r.title,
        snippet: r.snippet,
        citationRank: r.citation_rank,
        isBrandDomain: Boolean(r.is_brand_domain),
        isCompetitorDomain: Boolean(r.is_competitor_domain),
      }));
    } catch {
      return [];
    }
  }

  public static getReverseRagChunks(limit = 100): ReverseRagChunkRecord[] {
    const db = getSqliteDb();
    if (!db) return [];
    try {
      const rows = db
        .prepare("SELECT * FROM reverse_rag_chunks ORDER BY similarity_score DESC LIMIT ?")
        .all(limit) as unknown as ReverseRagChunkRow[];
      return rows.map((r) => ({
        id: r.id,
        citationId: r.citation_id,
        chunkText: r.chunk_text,
        headingContext: r.heading_context,
        similarityScore: Number(r.similarity_score || 0),
      }));
    } catch {
      return [];
    }
  }

  /**
   * Computes the complete GEO & AI Visibility Analytics suite for any brand.
   */
  public static computeBrandVisibility(targetBrandId?: string) {
    const brand = this.getBrand(targetBrandId);
    if (!brand) return null;

    const brandDomain = brand.domain.toLowerCase().replace(/^www\./, "");
    const aliases = [...brand.aliases, brand.name];

    const competitors = this.getCompetitors(brand.id);
    const prompts = this.getPrompts(brand.id);
    const runs = this.getPromptRuns(brand.id, 1000);
    const allCitations = this.getCitations(brand.id, 1000);
    const reverseRagChunks = this.getReverseRagChunks(50);

    // Filter citations belonging to the brand
    const brandCitations = allCitations.filter(
      (c) => c.isBrandDomain || c.domain.toLowerCase().includes(brandDomain) || c.url.toLowerCase().includes(brandDomain)
    );

    // Compute competitor metrics
    const competitorMetrics = competitors.map((c) => {
      const compDomain = c.domain.toLowerCase().replace(/^www\./, "");
      const count = allCitations.filter(
        (cit) =>
          cit.isCompetitorDomain ||
          cit.domain.toLowerCase().includes(compDomain) ||
          cit.url.toLowerCase().includes(compDomain)
      ).length;
      return {
        name: c.name,
        citations: count,
        topDomains: [c.domain],
        avgProminence: 0.68,
      };
    });

    const competitiveCitationTotal =
      brandCitations.length + competitorMetrics.reduce((acc, c) => acc + c.citations, 0);
    const editorialCount = Math.max(0, allCitations.length - competitiveCitationTotal);

    // Compute CSoV
    const csovResult = MonteCarloMetricsCalculator.computeCSoV(
      brand.name,
      brandCitations.length,
      competitorMetrics,
      editorialCount
    );

    // Compute Per-Prompt Probabilistic Metrics
    const promptMetrics = prompts.map((p) => {
      const pRuns = runs.filter((r) => r.promptId === p.id);
      const metric = MonteCarloMetricsCalculator.computeProbabilisticMetric(
        pRuns.map((r) => ({
          hasCitation: r.responseText.toLowerCase().includes(brandDomain),
          hasMention: aliases.some((a) => r.responseText.toLowerCase().includes(a.toLowerCase())),
          responseLength: r.responseText.length,
          contextSnippet: r.responseText,
          entityName: brand.name,
        }))
      );

      // Find sample run with answer quote
      const sampleRun = pRuns.find((r) => r.responseText.length > 50) || pRuns[0];

      return {
        id: p.id,
        query: p.queryText,
        intent: p.intentType,
        persona: p.personaDimension,
        runsCount: pRuns.length,
        citationProbability: metric.citationProbability,
        wilsonInterval: metric.wilsonInterval,
        evi: metric.effectiveVisibilityIndex,
        netStance: metric.stanceDistribution.netStanceScore,
        volatility: metric.volatilityStdDev,
        sampleAnswer: sampleRun?.responseText || "",
        engines: Array.from(new Set(pRuns.map((r) => r.engine))),
        subQueries: sampleRun?.subQueries || [],
      };
    });

    // Compute Global Monte Carlo Probabilistic Metric
    const globalMetric = MonteCarloMetricsCalculator.computeProbabilisticMetric(
      runs.map((r) => ({
        hasCitation: r.responseText.toLowerCase().includes(brandDomain),
        hasMention: aliases.some((a) => r.responseText.toLowerCase().includes(a.toLowerCase())),
        responseLength: r.responseText.length,
        contextSnippet: r.responseText,
        entityName: brand.name,
      }))
    );

    // Reverse-RAG passage alignments
    const alignments = reverseRagChunks.slice(0, 15).map((chunk, idx) => ({
      id: chunk.id,
      passageText: chunk.chunkText,
      heading: chunk.headingContext || "Answer Key Extract",
      similarityScore: chunk.similarityScore,
      citationId: chunk.citationId,
      rank: idx + 1,
    }));

    return {
      brand: {
        id: brand.id,
        name: brand.name,
        domain: brand.domain,
        aliases: brand.aliases,
      },
      summary: {
        totalPrompts: prompts.length,
        totalRuns: runs.length,
        totalCitations: allCitations.length,
        brandCitations: brandCitations.length,
        avgMentionRate: globalMetric.mentionRate,
        citationProbability: globalMetric.citationProbability,
        wilsonInterval: globalMetric.wilsonInterval,
        effectiveVisibilityIndex: globalMetric.effectiveVisibilityIndex,
        netStanceScore: globalMetric.stanceDistribution.netStanceScore,
        volatility: globalMetric.volatilityStdDev,
      },
      csov: csovResult,
      prompts: promptMetrics,
      alignments,
      runs: runs.slice(0, 20),
    };
  }
}
