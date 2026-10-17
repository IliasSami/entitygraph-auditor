# Evaluation & Calibration Framework

This document outlines the evaluation methodology for **EntityGraph Auditor (EGA)** to ensure repeatability, scoring calibration, and protection against hallucination.

## 1. Principles of Evaluation

1. **Deterministic Reproducibility**: Given the exact same structured inputs (entities, EAVs, triples, passages, claims), the scoring engine must yield bit-identical score breakdowns.
2. **Heuristic Calibration**: Scores must match human editorial intuition across standard grades:
   - Weak/shallow content: 2.0 - 4.5
   - Adequate standard content: 6.0 - 7.5
   - High-authority, well-structured, evidence-backed content: 8.0 - 9.2
   - Flawless/exceptional content: >9.5 (used sparingly)
3. **Gate Rigor**: Content containing high-risk unsubstantiated medical/financial/legal claims or explicit brand rule violations must trigger `GateStatus.FAIL` regardless of high keyword density or prose fluency.

## 2. Golden Dataset Matrix

The evaluation suite tests against four distinct archetypes:

1. **Golden Case 1: Informational Tech Guide (`case_info_tech`)**
   - *Archetype*: In-depth technical tutorial with code, clear entities, explicit attribute values, definitions.
   - *Expected Outcome*: High EOS, high PRS, Gate PASS.
2. **Golden Case 2: Local Emergency Plumber (`case_local_service`)**
   - *Archetype*: Location service page with explicit address, hours, licensed technicians, local entities.
   - *Expected Outcome*: High Local Fit, explicit EAV, Gate PASS.
3. **Golden Case 3: Keyword-Stuffed Thin Affiliate (`case_thin_stuffed`)**
   - *Archetype*: Excessive entity repetition, vague attributes ("best", "fastest"), no sources, generic AI phrasing.
   - *Expected Outcome*: Low EOS (penalized for stuffing), low CWS, low PRS, clear gap findings.
4. **Golden Case 4: High-Risk Unsubstantiated Health Claim (`case_health_hazard`)**
   - *Archetype*: Medical advice promising a "100% cure for arthritis without surgery", lacking clinical evidence.
   - *Expected Outcome*: High-stakes claim trigger, `GateStatus.FAIL`, severity CRITICAL.

## 3. Automated Benchmark Execution

Run the evaluation suite via:
```bash
pytest tests/evaluations/ -v
```
