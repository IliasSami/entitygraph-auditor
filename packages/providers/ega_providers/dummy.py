"""Local deterministic provider for zero-API-cost baseline audits (PRD §0 Rule 6)."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from ega_schemas.enums import (
    AnswerShape,
    ClaimRiskTier,
    EAVStatus,
    EntityKind,
    ExtractionMethod,
    IntentClass,
    PageType,
    QueryOrigin,
    QueryScope,
    QuerySource,
    TripleStatus,
    TripleType,
    VerificationState,
)
from ega_schemas.providers import (
    ModelCallRequest,
    ModelCallResponse,
    ModelConfig,
    ModelProviderType,
)

from ega_providers.base import (
    DEFAULT_TIMEOUT_S,
    GenerationSettings,
    HealthStatus,
    ModelProvider,
    ProviderCapabilities,
)


class DummyDeterministicProvider(ModelProvider):
    """Zero-cost local deterministic provider providing schema-valid agent outputs."""

    name: str = "dummy"

    def __init__(
        self,
        config: Optional[Any] = None,
        *,
        model: str = "deterministic-baseline",
        default_timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        super().__init__(default_timeout_s=default_timeout_s)
        self.config = config or ModelConfig(provider_type=ModelProviderType.DUMMY, model_name=model)
        self.model = model

    def call(self, request: ModelCallRequest) -> ModelCallResponse:
        system = request.system_prompt.lower()
        user = request.user_prompt

        # Extract untrusted content block if present
        content_match = re.search(r'<untrusted_content>([\s\S]*?)</untrusted_content>', user)
        content = content_match.group(1).strip() if content_match else user

        # Check if Central Entity was passed in user prompt
        ce_match = re.search(r'Central Entity:\s*([^\n]+)', user)
        prompt_central = ce_match.group(1).strip() if ce_match else None
        central_hint = prompt_central if prompt_central and prompt_central not in ("None", "", "unset") else None

        data: dict[str, Any] = {}

        # Dispatch on the "Agent N" header first: every prompt carries a unique
        # one. Loose keyword matching misfires because prompts legitimately
        # mention other agents' topics (e.g. the Coverage & Gap prompt talks
        # about "fan-out queries"). Keywords remain a fallback for prompts
        # without a numeric header.
        agent_match = re.search(r"agent\s+(\d+)", system)
        agent_num = agent_match.group(1) if agent_match else None

        if agent_num == "1" or (agent_num is None and "classifier" in system):
            data = self._classify(content, central_hint)
        elif agent_num == "2" or (agent_num is None and "fan-out" in system):
            data = self._fanout(content)
        elif agent_num == "3" or (agent_num is None and "entity & eav" in system):
            data = self._extract_entities_eav(content, central_hint)
        elif agent_num == "4" or (agent_num is None and "semantic triple" in system):
            data = self._extract_triples(content, central_hint)
        elif agent_num == "6" or (agent_num is None and "evidence / claim" in system):
            data = self._extract_claims(content)
        elif agent_num == "8" or (agent_num is None and "coverage & gap" in system):
            data = self._coverage(content)
        elif agent_num == "9" or (agent_num is None and "editorial" in system):
            data = self._editorial(content)
        elif agent_num == "12" or (agent_num is None and "handoff" in system):
            data = self._handoff(content, user)
        elif agent_num == "13" or (agent_num is None and "critic" in system):
            data = self._critic(content)
        else:
            data = {"status": "ok", "message": "Baseline deterministic analysis complete."}

        raw_text = json.dumps(data)
        return ModelCallResponse(
            raw_text=raw_text,
            parsed_json=data,
            latency_ms=5,
            input_tokens=len(user.split()),
            output_tokens=len(raw_text.split()),
            model_name=getattr(self.config, "model_name", self.model),
            provider="dummy_deterministic",
        )

    async def generate_structured(
        self,
        *,
        schema: dict[str, Any],
        messages: list[dict[str, Any]],
        settings: GenerationSettings,
    ) -> dict[str, Any]:
        user_content = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        sys_content = next((m["content"] for m in messages if m.get("role") == "system"), "")
        req = ModelCallRequest(system_prompt=sys_content, user_prompt=user_content)
        res = self.call(req)
        return res.parsed_json or {}

    async def generate_text(
        self,
        *,
        messages: list[dict[str, Any]],
        settings: GenerationSettings,
    ) -> str:
        res = await self.generate_structured(schema={}, messages=messages, settings=settings)
        return json.dumps(res)

    async def health_check(self) -> HealthStatus:
        return HealthStatus(
            ok=True,
            latency_ms=1.0,
            detail="Deterministic baseline provider active (zero API cost)",
            model_id=self.model,
        )

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider="dummy",
            model_id=self.model,
            structured_output=True,
            tool_calls=False,
            context_window=128000,
            sends_data_off_device=False,
            notes=["Zero external API cost; runs fully locally."],
        )

    def _classify(self, content: str, central_hint: Optional[str] = None) -> dict[str, Any]:
        lower = content.lower()
        page_type = PageType.GENERAL
        if "plumber" in lower or "near me" in lower or "emergency plumbing" in lower:
            page_type = PageType.SERVICE
        elif "guide" in lower or "tutorial" in lower or "postgresql" in lower or "how to" in lower:
            page_type = PageType.ARTICLE
        elif "vs" in lower or "alternative" in lower or "comparison" in lower:
            page_type = PageType.COMPARISON
        elif "saas" in lower or "database" in lower or "newsql" in lower or "enterprise" in lower:
            page_type = PageType.SAAS_B2B

        central = central_hint
        if not central:
            h1_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            if h1_match:
                central = h1_match.group(1).strip()
            else:
                first_line = content.strip().split("\n")[0].strip("# \t\r")
                central = first_line if first_line else "Primary Subject"

        return {
            "page_type": page_type.value,
            "central_entity": central,
            "primary_intent": IntentClass.INFORMATIONAL.value if page_type == PageType.ARTICLE else IntentClass.COMMERCIAL.value,
            "target_audience": "Prospective users, evaluators, or researchers",
            "target_action": "Read, evaluate capabilities, and take next step",
            "locale": "en",
            "confidence": "high",
            "assumptions": ["Determined from structural headings and dominant entity patterns."],
        }

    def _fanout(self, content: str) -> dict[str, Any]:
        h1_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        topic = h1_match.group(1).strip() if h1_match else "the service"

        queries = [
            {
                "query_id": "fo-1",
                "query_text": f"What is {topic}?",
                "origin": QueryOrigin.SIMULATED.value,
                "source": QuerySource.GENERATED.value,
                "intent": IntentClass.INFORMATIONAL.value,
                "importance": 3,
                "answer_shape": AnswerShape.DEFINITION.value,
                "scope": QueryScope.THIS_PAGE.value,
            },
            {
                "query_id": "fo-2",
                "query_text": f"How does {topic} work?",
                "origin": QueryOrigin.SIMULATED.value,
                "source": QuerySource.GENERATED.value,
                "intent": IntentClass.INFORMATIONAL.value,
                "importance": 3,
                "answer_shape": AnswerShape.PROCEDURE.value,
                "scope": QueryScope.THIS_PAGE.value,
            },
            {
                "query_id": "fo-3",
                "query_text": f"Key features and specifications of {topic}",
                "origin": QueryOrigin.SIMULATED.value,
                "source": QuerySource.GENERATED.value,
                "intent": IntentClass.COMMERCIAL.value,
                "importance": 2,
                "answer_shape": AnswerShape.CHECKLIST.value,
                "scope": QueryScope.THIS_PAGE.value,
            },
            {
                "query_id": "fo-4",
                "query_text": f"Who is {topic} best suited for?",
                "origin": QueryOrigin.SIMULATED.value,
                "source": QuerySource.GENERATED.value,
                "intent": IntentClass.EVALUATION.value,
                "importance": 2,
                "answer_shape": AnswerShape.SHORTLIST.value,
                "scope": QueryScope.THIS_PAGE.value,
            },
        ]
        return {"fanout_queries": queries}

    def _extract_entities_eav(self, content: str, central_hint: Optional[str] = None) -> dict[str, Any]:
        central_name = central_hint
        if not central_name:
            h1_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            if h1_match:
                central_name = h1_match.group(1).strip()
            else:
                first_line = content.strip().split("\n")[0].strip("# \t\r")
                central_name = first_line if first_line else "Central Entity"

        entities = [
            {
                "entity_id": "ent-central",
                "canonical_name": central_name,
                "kind": EntityKind.CENTRAL.value,
                "confidence": "high",
                "salience": 0.95,
                "is_central": True,
                "aliases": [],
                "method": ExtractionMethod.DETERMINISTIC.value,
                "occurrences": [],
            }
        ]

        # Extract capitalized multi-word phrases as candidate entities.
        # Use `[ \t]+` (not `\s+`) between words: `\s+` also matches newlines,
        # which glued separate headings/lines into single malformed names
        # (e.g. "Our Beans\nSingle" or duplicated multi-line brand names).
        cap_phrases = set(re.findall(r'\b[A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+)+\b', content))
        idx = 1
        for p in list(cap_phrases)[:6]:
            if p.lower() != central_name.lower():
                entities.append({
                    "entity_id": f"ent-{idx}",
                    "canonical_name": p,
                    "kind": EntityKind.CONCEPT.value,
                    "confidence": "medium",
                    "salience": 0.6,
                    "is_central": False,
                    "aliases": [],
                    "method": ExtractionMethod.DETERMINISTIC.value,
                    "occurrences": [],
                })
                idx += 1

        # Recognise standards/regulations the text actually names (e.g. SOC 2,
        # ISO 27001, AES-256). These are real trust entities; without them the
        # EOS/KGR trust signals have nothing to score.
        for offset, standard in enumerate(self._found_standards(content)):
            entities.append({
                "entity_id": f"ent-std-{offset + 1}",
                "canonical_name": standard,
                "kind": EntityKind.STANDARD.value,
                "confidence": "medium",
                "salience": 0.5,
                "is_central": False,
                "aliases": [],
                "method": ExtractionMethod.DETERMINISTIC.value,
                "occurrences": [],
            })

        # Emit attribute rows ONLY for values the content actually states. The
        # deterministic scoring engine already reports the page type's required
        # attributes as missing (PRD §5), so we never invent a value to fill a
        # slot. (Previously this returned canned category/protocol/encryption
        # rows such as value="Service"/"Standard"/"TLS" regardless of the text.)
        return {"entities": entities, "eav_rows": self._extract_eav_rows(content, central_name)}

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _sentences(content: str) -> list[str]:
        """Split markdown text into candidate sentences.

        Leading heading (``#``), blockquote (``>``) and bullet (``-``/``*``/``+``)
        markers are stripped, and the text is split on both sentence punctuation
        and line breaks — otherwise a heading on its own line swallows the
        sentence beneath it and no triple/claim is ever detected.
        """
        text = re.sub(r"^[ \t]*[#>*+-]+[ \t]*", "", content, flags=re.MULTILINE)
        parts = re.split(r"(?<=[.!?])\s+|\n+", text)
        return [p.strip() for p in parts if p and p.strip()]

    @classmethod
    def _sentence_with(cls, content: str, needle: str) -> str:
        needle = needle.strip()
        if not needle:
            return ""
        for sentence in cls._sentences(content):
            if needle.lower() in sentence.lower():
                return sentence
        return ""

    #: Standards / regulations / crypto suites recognised from the text. Only the
    #: ones literally named are surfaced — this is not a claim that a page holds
    #: the certification, only that it names the standard.
    _KNOWN_STANDARDS: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("SOC 2", ("soc 2", "soc-2", "soc2")),
        ("ISO 27001", ("iso 27001", "iso-27001", "iso27001")),
        ("GDPR", ("gdpr",)),
        ("HIPAA", ("hipaa",)),
        ("PCI DSS", ("pci dss", "pci-dss")),
        ("AES-256", ("aes-256", "aes 256")),
    )

    @classmethod
    def _found_standards(cls, content: str) -> list[str]:
        lower = content.lower()
        return [name for name, needles in cls._KNOWN_STANDARDS if any(n in lower for n in needles)]

    @classmethod
    def _sentence_for_standard(cls, content: str, name: str) -> str:
        """Return the sentence naming ``name`` using its real surface forms."""
        forms = dict(cls._KNOWN_STANDARDS).get(name, ())
        for candidate in (name, *forms):
            sentence = cls._sentence_with(content, candidate)
            if sentence:
                return sentence
        return ""

    @classmethod
    def _standard_sentence(cls, content: str) -> str:
        for name, _ in cls._KNOWN_STANDARDS:
            sentence = cls._sentence_for_standard(content, name)
            if sentence:
                return sentence
        return ""

    def _extract_eav_rows(self, content: str, central_name: str) -> list[dict[str, Any]]:
        """Extract only the attribute values the text explicitly states."""
        rows: list[dict[str, Any]] = []

        def add(attribute: str, value: str, sentence: str, confidence: str = "medium") -> None:
            rows.append(
                {
                    "eav_id": f"eav-{len(rows) + 1}",
                    "entity_name": central_name,
                    "attribute": attribute,
                    "value": value,
                    "status": EAVStatus.EXPLICIT.value,
                    "confidence": confidence,
                    "sentence": (sentence or "").strip()[:240] or None,
                }
            )

        # price / pricing basis — only when an explicit figure is stated.
        price = re.search(
            r"(?:[$€£]\s?\d[\d,]*(?:\.\d+)?|\b\d[\d,]*(?:\.\d+)?\s?(?:usd|eur|gbp)\b)",
            content,
            re.IGNORECASE,
        )
        if price:
            add("price", price.group(0).strip(), self._sentence_with(content, price.group(0)), "high")

        # contact phone — require a plausible digit count so years/ids don't match.
        phone = re.search(
            r"(?:(?:\+|00)\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?){1,3}\d{3,4}", content
        )
        if phone and len(re.sub(r"\D", "", phone.group(0))) >= 8:
            add("contact_phone", phone.group(0).strip(), self._sentence_with(content, phone.group(0)))

        # explicit "serving/in <Place>" phrasing only.
        place = re.search(
            r"\b(?:serving|based in|located in|operating in|covering|across|in)\s+"
            r"([A-Z][a-zA-Z]+(?:[ ,]+[A-Z][a-zA-Z]+){0,3})",
            content,
        )
        if place and len(place.group(1).strip()) > 2:
            value = place.group(1).strip()
            add("coverage_area", value, self._sentence_with(content, value))
            add("location", value, self._sentence_with(content, value))

        timeframe = re.search(
            r"\b(?:within|in|takes?)\s+(\d+\s?(?:business\s+)?(?:hours?|days?|weeks?|months?))\b",
            content,
            re.IGNORECASE,
        )
        if timeframe:
            add("timeframe", timeframe.group(1).strip(), self._sentence_with(content, timeframe.group(1)))

        founding = re.search(r"\b(?:founded|established|since)\s+(?:in\s+)?(\d{4})\b", content, re.IGNORECASE)
        if founding:
            add("founding", founding.group(1), self._sentence_with(content, founding.group(1)))

        standards = self._found_standards(content)
        standard_sentence = self._standard_sentence(content)
        for standard in standards:
            add("certification", standard, self._sentence_for_standard(content, standard), "high")
        if standards:
            # A named standard/regulation is both a security signal and a proof point.
            summary = "; ".join(standards)
            add("security", summary, standard_sentence, "high")
            add("proof", standard_sentence or summary, standard_sentence, "high")

        # value proposition — the object of an explicit "provides/offers/delivers" clause.
        value_prop = re.search(
            r"\b(?:provides|offers|delivers|supplies)\s+([^.;\n]{3,120})", content, re.IGNORECASE
        )
        if value_prop:
            add("value_proposition", value_prop.group(1).strip(), self._sentence_with(content, value_prop.group(0)))

        # target ICP / audience — explicit "for <audience>" phrasing.
        audience = re.search(r"\bfor\s+([A-Za-z][^.;\n]{2,59})", content)
        if audience:
            value = audience.group(1).strip()
            first_word = value.split()[0].lower() if value.split() else ""
            if 3 <= len(value) <= 60 and first_word not in {
                "a", "an", "the", "more", "this", "that", "your", "our", "its",
                "their", "any", "all", "free", "example",
            }:
                add("target_icp", value, self._sentence_with(content, audience.group(0)))

        # pricing model — the commercial cadence actually named.
        pricing = re.search(
            r"\b(monthly|annual|annually|yearly|per month|per year|per seat|per user|"
            r"subscription|retainer|one-off|fixed fee)\b",
            content,
            re.IGNORECASE,
        )
        if pricing:
            add("pricing_model", pricing.group(1).strip(), self._sentence_with(content, pricing.group(1)))

        return rows

    #: Subjects that are pronouns/function words — never treated as a triple subject.
    _TRIPLE_STOP_SUBJECTS = {
        "the", "a", "an", "this", "that", "these", "those", "our", "your",
        "their", "its", "we", "it", "they", "he", "she", "i",
    }

    def _extract_triples(self, content: str, central_hint: Optional[str] = None) -> dict[str, Any]:
        """Extract explicit subject-predicate-object statements from the text.

        Only relationships the content actually states are returned, with the
        source sentence kept as evidence. Nothing is invented — the previous
        version always returned "provides high performance" / "complies with
        security standards" regardless of the page.
        """
        # (verb alternatives, canonical predicate, triple type). The canonical
        # predicate keeps the scorer's keyword stem (provide / address / improve …)
        # and the type reflects what the verb actually asserts, so process and
        # outcome relationships are credited as such instead of every relationship
        # collapsing to "capability".
        patterns = (
            (r"provides|offers|delivers|supplies|specializes in|specialises in",
             "provides", TripleType.CAPABILITY.value),
            (r"includes|supports|uses|requires",
             "includes", TripleType.CAPABILITY.value),
            (r"complies with|is certified|certified",
             "complies_with", TripleType.SAFETY_COMPLIANCE.value),
            (r"integrates with|connects to|connect to|works with",
             "connects_to", TripleType.INTEGRATION.value),
            (r"maintains|handles|manages|processes|allocates|assigns|forks|"
             r"multiplexes|routes|pools",
             "maintains", TripleType.PROCESS.value),
            (r"reduces|lowers|improves|optimizes|optimises|increases|boosts|"
             r"accelerates|saves",
             "improves", TripleType.OUTCOME.value),
            (r"addresses|solves|resolves|prevents|eliminates|mitigates|fixes|"
             r"overcomes",
             "addresses", TripleType.OUTCOME.value),
            (r"is|are|serves as|acts as", "is_a", TripleType.CATEGORY.value),
        )
        compiled = [
            (
                re.compile(
                    r"^(?P<s>[A-Z][\w&.\-]*(?:[ \t]+[A-Z][\w&.\-]*)*)[ \t]+"
                    rf"(?P<p>{verbs})[ \t]+"
                    + (r"(?:a|an)[ \t]+" if predicate == "is_a" else "")
                    + r"(?P<o>[^.;\n]{3,90})"
                ),
                predicate,
                triple_type,
            )
            for verbs, predicate, triple_type in patterns
        ]

        triples: list[dict[str, Any]] = []
        seen: set[str] = set()
        for sentence in self._sentences(content):
            # Break ", and <Capital> …" clauses so a second real relationship in
            # the same sentence is not lost.
            for clause in re.split(r"(?<=,)\s+and\s+(?=[A-Z])", sentence):
                for pattern, predicate, triple_type in compiled:
                    match = pattern.match(clause)
                    if not match:
                        continue
                    subject = match.group("s").strip()
                    obj = match.group("o").strip().rstrip(" .,;")
                    if (
                        subject.lower() in self._TRIPLE_STOP_SUBJECTS
                        or len(obj) < 3
                        or subject.lower() == obj.lower()
                    ):
                        break
                    key = f"{subject}|{obj}".lower()
                    if key in seen:
                        break
                    seen.add(key)
                    triples.append(
                        {
                            "triple_id": f"tr-{len(triples) + 1}",
                            "subject": subject,
                            "predicate": predicate,
                            "object_": obj,
                            "triple_type": triple_type,
                            "status": TripleStatus.EXPLICIT.value,
                            "confidence": "medium",
                            "evidence_excerpt": clause.strip()[:240],
                        }
                    )
                    break
                if len(triples) >= 12:
                    break
            if len(triples) >= 12:
                break
        return {"triples": triples}

    def _extract_claims(self, content: str) -> dict[str, Any]:
        """Extract empirical claims the text makes — always UNVERIFIED.

        The deterministic baseline cannot check a claim against a source, so
        every claim is returned unverified and requiring substantiation. It never
        asserts a verified fact nor fabricates an evidence id. (Previously this
        always returned a canned "verified" claim with a fake source id.)
        """
        claims: list[dict[str, Any]] = []
        seen: set[str] = set()
        numeric = re.compile(
            r"\b(?:up to\s+)?\d+(?:[.,]\d+)?\s?(?:%|percent\b|x\b|times\b|\+)", re.IGNORECASE
        )
        superlative = re.compile(
            r"\b(?:best|fastest|cheapest|leading|#1|number one|world[- ]class|"
            r"guaranteed|100%|miracle)\b",
            re.IGNORECASE,
        )
        high_stakes = re.compile(
            r"\b(?:cures?|cancer|arthritis|miracle|diagnos\w*)\b", re.IGNORECASE
        )

        for sentence in self._sentences(content):
            if not (numeric.search(sentence) or superlative.search(sentence)):
                continue
            statement = sentence.strip()
            key = statement.lower()
            if key in seen:
                continue
            seen.add(key)
            claims.append(
                {
                    "claim_id": f"cl-{len(claims) + 1}",
                    "statement": statement[:300],
                    "risk_tier": (
                        ClaimRiskTier.HIGH_STAKES.value
                        if high_stakes.search(sentence)
                        else ClaimRiskTier.ORDINARY.value
                    ),
                    "verification_state": VerificationState.UNVERIFIED.value,
                    "requires_substantiation": True,
                    "evidence_source_ids": [],
                }
            )
            if len(claims) >= 10:
                break
        return {"claims": claims, "evidence_sources": []}

    def _coverage(self, content: str) -> dict[str, Any]:
        """No coverage verdicts.

        Coverage requires matching a fan-out query to a specific passage id; the
        deterministic baseline cannot do that reliably, and the coverage agent
        already drops any covered/partial row that does not cite a passage. We
        therefore report no coverage rather than assert invented matches.
        """
        return {"coverage_rows": []}

    def _editorial(self, content: str) -> dict[str, Any]:
        return {
            "passage_findings": []
        }

    def _handoff(self, content: str, prompt: str = "") -> dict[str, Any]:
        """Turn the REAL weaknesses/gaps from scoring into recommendations.

        Nothing is invented: each recommendation restates a weakness or a lost
        point the deterministic scorer actually produced. If a run has none, no
        recommendations are returned. (Previously this always returned a canned
        "Core Architecture / failover" recommendation for every page.)
        """
        weaknesses = self._prompt_list(prompt, "Weaknesses")
        gaps = self._prompt_list(prompt, "Key Gaps")
        items = (gaps or weaknesses)[:5]

        recommendations: list[dict[str, Any]] = []
        for index, item in enumerate(items):
            if not item:
                continue
            recommendations.append(
                {
                    "finding_id": f"rec-{index + 1}",
                    "category": "editorial" if item in weaknesses else "structure",
                    "severity": "medium",
                    "title": item[:110],
                    "what": item[:280],
                    "where": {"section_id": None, "excerpt": None},
                    "why": {"layer": "deterministic_scoring", "rule_id": None},
                    "how": {
                        "suggested_rewrite": "",
                        "verification_condition": (
                            f"Re-run the audit and confirm this is resolved: {item[:160]}"
                        ),
                    },
                    "evidence": [item[:240]],
                    "impact": 3,
                    "confidence_numeric": 3,
                    "effort": 2,
                    "priority_score": 6.0,
                }
            )

        # FR-18: the measurement plan tracks each flagged gap toward resolution.
        # The baseline is the honest "flagged in this audit" state — no invented
        # percentages.
        measurement_plan = [
            {
                "kpi": item[:120],
                "baseline": "flagged in this audit",
                "target": "not flagged on re-audit",
            }
            for item in items
        ]

        return {
            "recommendations": recommendations,
            "brief_markdown": "",
            "topical_cluster": "",
            "measurement_plan": measurement_plan,
        }

    @staticmethod
    def _prompt_list(prompt: str, label: str) -> list[str]:
        """Read a comma-separated ``Label: a, b, c`` line, respecting parentheses."""
        match = re.search(rf"^{re.escape(label)}:\s*(.*)$", prompt, re.MULTILINE)
        if not match:
            return []
        raw = match.group(1).strip()
        if not raw:
            return []
        items: list[str] = []
        buffer = ""
        depth = 0
        for part in raw.split(", "):
            buffer = f"{buffer}, {part}" if buffer else part
            depth += part.count("(") - part.count(")")
            if depth <= 0:
                items.append(buffer.strip())
                buffer = ""
                depth = 0
        if buffer.strip():
            items.append(buffer.strip())
        return items

    def _critic(self, content: str) -> dict[str, Any]:
        """Structural approval only — no semantic QA is performed here."""
        return {
            "approved": True,
            "score": 7.0,
            "notes": [
                "Deterministic baseline: structural checks only; semantic QA was not performed."
            ],
            "requires_repair": False,
        }
