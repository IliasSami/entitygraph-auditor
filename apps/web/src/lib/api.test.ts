import { beforeAll, describe, expect, it } from "vitest";

/**
 * The mock client is the contract the whole UI renders against in demo mode.
 * These tests pin its shape so a refactor of the fixture cannot silently break
 * a screen.
 */
describe("mock api client shape", () => {
  let api: typeof import("@/lib/api").api;
  let MOCK_MODE: boolean;

  beforeAll(async () => {
    const mod = await import("@/lib/api");
    api = mod.api;
    MOCK_MODE = mod.MOCK_MODE;
  });

  it("runs in mock mode when NEXT_PUBLIC_MOCK=1", () => {
    expect(MOCK_MODE).toBe(true);
  });

  it("exposes projects with the fields the project screens read", async () => {
    const projects = await api.listProjects();
    expect(projects.length).toBeGreaterThan(0);
    const northwind = projects.find((p) => p.project_id === "proj-northwind");
    expect(northwind).toBeDefined();
    expect(northwind).toMatchObject({
      project_id: expect.any(String),
      name: expect.any(String),
    });
  });

  it("lists audits with the summary columns the history table needs", async () => {
    const audits = await api.listAudits();
    expect(audits.length).toBeGreaterThan(0);
    for (const row of audits) {
      expect(row).toEqual(
        expect.objectContaining({
          audit_id: expect.any(String),
          project_id: expect.any(String),
          status: expect.any(String),
          created_at: expect.any(String),
        }),
      );
    }
  });

  it("returns a report whose component scores cover the core rubric keys", async () => {
    const detail = await api.getAudit("aud-nw-main");
    expect(detail.report).toBeTruthy();
    for (const key of ["EOS", "ERS", "KGR", "FCS", "PRS", "CWS", "HRS"] as const) {
      expect(detail.report!.scores[key]).toBeDefined();
    }
    // AVR is the weighted composite, stored separately from the component scores.
    expect(detail.report!.composite_avr).toBeGreaterThan(0);
    expect(detail.report!.gate.status).toBe("pass_with_fixes");
  });

  it("compares two audits and returns score_delta, entity_changes and coverage_delta", async () => {
    const result = await api.compareAudits("aud-nw-baseline", "aud-nw-main");
    expect(result.score_delta.length).toBeGreaterThan(0);
    expect(result.score_delta[0]).toEqual(
      expect.objectContaining({ key: expect.any(String) }),
    );
    expect(result.entity_changes).toEqual(
      expect.objectContaining({
        added: expect.any(Array),
        removed: expect.any(Array),
        changed: expect.any(Array),
      }),
    );
    expect(result.coverage_delta).toEqual(
      expect.objectContaining({
        baseline_covered: expect.any(Number),
        candidate_covered: expect.any(Number),
        total: expect.any(Number),
      }),
    );
    expect(Array.isArray(result.warnings)).toBe(true);
  });

  it("lists providers and tests a connection deterministically", async () => {
    const { providers } = await api.listProviders();
    expect(providers.length).toBeGreaterThan(0);
    expect(providers.map((p) => p.type)).toContain("dummy");

    const connected = await api.testConnection({ provider_type: "dummy", model: "deterministic" });
    expect(connected.ok).toBe(true);

    const missingKey = await api.testConnection({ provider_type: "openai", model: "gpt-4o-mini" });
    expect(missingKey.ok).toBe(false);
  });

  it("treats an unimplemented MCP surface as an empty list", async () => {
    await expect(api.listMcpServers()).resolves.toEqual([]);
  });

  it("derives the Entity Hub registry from the mock audits", async () => {
    const registry = await api.listEntities("proj-northwind");
    expect(registry.project_id).toBe("proj-northwind");
    expect(registry.entities.length).toBeGreaterThan(0);
    expect(registry.entities[0]).toEqual(
      expect.objectContaining({
        entity_id: expect.any(String),
        name: expect.any(String),
        kind: expect.any(String),
        facts: expect.any(Array),
        sources: expect.any(Array),
      }),
    );
    expect(registry.disclaimer.length).toBeGreaterThan(0);
  });

  it("assembles a brief from the mock coverage queries", async () => {
    const brief = await api.generateBrief({ project_id: "proj-northwind" });
    expect(brief.sources.length).toBeGreaterThan(0);
    expect(brief.sections.length).toBeGreaterThan(0);
    expect(brief.sections[0]).toEqual(
      expect.objectContaining({ h2_number: 1, title: expect.any(String) }),
    );
    expect(brief.disclaimer.length).toBeGreaterThan(0);
  });

  it("analyses a draft deterministically for the optimizer inspector", async () => {
    const result = await api.analyzeContent({
      text: "# Is this a question?\n\nBody copy with guaranteed results.",
      target_entities: ["Northwind Roofing"],
      banned_terms: ["guaranteed results"],
      word_target: 200,
    });
    expect(result.dimensions).toHaveLength(5);
    expect(result.violations[0]?.term).toBe("guaranteed results");
    expect(result.entities[0]?.status).toBe("missing");
    expect(result.metrics.word_count).toBeGreaterThan(0);
    expect(result.overall_score).toBeGreaterThanOrEqual(0);
    expect(result.disclaimer.length).toBeGreaterThan(0);
  });

  it("builds a content brief without fabricating data sources", async () => {
    const brief = await api.generateContentBrief({
      target_query: "Bookkeeping for Creative Agencies",
      brand_name: "Fernhill Bookkeeping",
      location: "Austin, TX",
    });
    // The generator must never imply it consulted a source it did not.
    const fabricated = ["Google PAA", "Perplexity", "AI Citation Gap", "Entity Hub"];
    for (const source of brief.sources) {
      expect(fabricated).not.toContain(source.source);
    }
    expect(brief.sections.length).toBeGreaterThan(0);
    expect(brief.sections[0]).toEqual(
      expect.objectContaining({ h2Number: 1, directive: expect.any(String) }),
    );
    expect(brief.disclaimer?.length).toBeGreaterThan(0);
    expect(brief.recommended_word_count.length).toBeGreaterThan(0);
    expect(brief.lexicon.include.length).toBeGreaterThan(0);
    expect(typeof brief.grounded).toBe("boolean");
  });

  it("does not score a single banned-term hit as strong evidence", async () => {
    const result = await api.analyzeContent({
      text: "# A question heading?\n\nBody copy that contains one banned term.",
      banned_terms: ["banned term"],
      word_target: 200,
    });
    const evidence = result.dimensions.find((d) => d.key === "evidence");
    expect(evidence).toBeDefined();
    expect(evidence?.band).not.toBe("strong");
  });
});
