"""Composite AI Visibility Readiness (AVR) and scorecard assembly (PRD §9.4).

``AVR = Σ(component_score_i × weight_i)`` over the profile's weight table,
which always sums to 1. The table itself comes from the page-type profile's
score preset (PRD §9.4's four columns: informational, listicle, commercial,
case study) so the weights are a single source of truth in
``auditor.rules.page_profiles``.

Two rules from PRD §9.4 drive everything here:

* *"If a component is not assessed, either block composite calculation or
  re-normalize explicitly and label the modified denominator."* — the engine
  re-normalizes automatically only in the narrow, always-expected case of a
  single missing FCS (fan-out runs are frequently omitted in offline mode);
  any other missing component blocks the composite unless the caller passes
  ``force_renormalize=True``, in which case the denominator is labelled.
* *"Never silently count N/A as zero."* — an unassessed component never
  contributes 0; it is excluded from both numerator and denominator.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from ega_schemas.enums import ScoreKey

from auditor.rules.page_profiles import WEIGHT_PRESETS, get_profile, weight_preset
from ega_scoring.components import (
    compute_cws,
    compute_eos,
    compute_ers,
    compute_fcs,
    compute_hrs,
    compute_kgr,
    compute_prs,
)
from ega_scoring.models import Scorecard, ScoreComponent, overall_confidence
from ega_scoring.optional import (
    compute_conversion,
    compute_intent,
    compute_internal_links,
    compute_local_fit,
    compute_paid_fit,
    compute_trust,
)
from ega_scoring.rubric import PROFILE_VERSION, clamp, heuristic_disclaimer
from ega_scoring.state import get_page_type, get_score_profile_override

#: The seven core components and the order they are reported in (PRD §9.2).
CORE_COMPONENT_ORDER: tuple[ScoreKey, ...] = (
    ScoreKey.EOS,
    ScoreKey.ERS,
    ScoreKey.KGR,
    ScoreKey.FCS,
    ScoreKey.PRS,
    ScoreKey.CWS,
    ScoreKey.HRS,
)

#: Optional components (PRD §9.3) — computed when the state carries the inputs
#: they need, otherwise reported as *not applicable* with no weight at all.
OPTIONAL_COMPONENT_ORDER: tuple[ScoreKey, ...] = (
    ScoreKey.INTENT,
    ScoreKey.LOCAL_FIT,
    ScoreKey.PAID_FIT,
    ScoreKey.CONVERSION,
    ScoreKey.TRUST,
    ScoreKey.LINKS,
)

#: Component label map (mirrors the schema ``ScoreKey`` vocabulary).
COMPONENT_LABELS: dict[ScoreKey, str] = {
    ScoreKey.AVR: "AI Visibility Readiness (composite)",
    ScoreKey.INTENT: "Intent Alignment",
    ScoreKey.LOCAL_FIT: "Local Fit",
    ScoreKey.PAID_FIT: "Paid Landing Page Fit",
    ScoreKey.CONVERSION: "Conversion Readiness",
    ScoreKey.TRUST: "Trust / E-E-A-T Coverage",
    ScoreKey.LINKS: "Internal-Link Readiness",
}

#: Components whose absence is expected enough that the composite re-normalizes
#: without blocking (PRD §9.4 "re-normalize explicitly and label the
#: modified denominator"). Anything else blocks the composite by default.
AUTO_RENORMALIZABLE: frozenset[ScoreKey] = frozenset({ScoreKey.FCS})

#: How many components may be missing before re-normalization stops being
#: automatic, even when they are all in ``AUTO_RENORMALIZABLE``.
MAX_AUTO_MISSING = 1

_CORE_COMPUTE = {
    ScoreKey.EOS: compute_eos,
    ScoreKey.ERS: compute_ers,
    ScoreKey.KGR: compute_kgr,
    ScoreKey.FCS: compute_fcs,
    ScoreKey.PRS: compute_prs,
    ScoreKey.CWS: compute_cws,
    ScoreKey.HRS: compute_hrs,
}

_OPTIONAL_COMPUTE = {
    ScoreKey.INTENT: compute_intent,
    ScoreKey.LOCAL_FIT: compute_local_fit,
    ScoreKey.PAID_FIT: compute_paid_fit,
    ScoreKey.CONVERSION: compute_conversion,
    ScoreKey.TRUST: compute_trust,
    ScoreKey.LINKS: compute_internal_links,
}


def resolve_preset(state: Any) -> str:
    """The AVR weight preset for ``state`` (PRD §9.4).

    A user-supplied ``score_profile`` override wins; otherwise the page type's
    profile preset is used. Unknown overrides raise ``ValueError``.
    """
    override = get_score_profile_override(state)
    profile = get_profile(get_page_type(state))
    preset = override or profile.score_preset
    if preset not in WEIGHT_PRESETS:
        raise ValueError(
            f"Unknown score preset {preset!r}; expected one of {sorted(WEIGHT_PRESETS)}"
        )
    return preset


def compute_components(
    state: Any,
    *,
    include_optional: bool = True,
) -> dict[ScoreKey, ScoreComponent]:
    """Compute every component (core + optional) from ``state``.

    Pure and deterministic: the same state always yields the same components.
    """
    components: dict[ScoreKey, ScoreComponent] = {}
    for key, fn in _CORE_COMPUTE.items():
        components[key] = fn(state)
    if include_optional:
        for key, fn in _OPTIONAL_COMPUTE.items():
            components[key] = fn(state)
    return components


def compute_avr(
    components: Mapping[ScoreKey, ScoreComponent],
    preset: str,
    *,
    force_renormalize: bool = False,
) -> ScoreComponent:
    """Build the composite AVR component for ``preset`` (PRD §9.4).

    Returns a component whose ``value`` is ``None`` (``not_assessed=True``) when
    the composite is blocked because unassessed components would silently
    distort the denominator — the reason names exactly which components blocked
    it. ``force_renormalize=True`` re-normalizes over the assessed components
    regardless of how many are missing, and labels the modified denominator.
    """
    weights = weight_preset(preset)
    label = COMPONENT_LABELS[ScoreKey.AVR]
    auto_ok_names = {key.value for key in AUTO_RENORMALIZABLE}

    assessed: dict[str, ScoreComponent] = {}
    for name in weights:
        component = components.get(ScoreKey(name))
        if component is not None and component.assessed:
            assessed[name] = component
    missing = [name for name in weights if name not in assessed]

    if not assessed:
        return ScoreComponent.unassessed(
            ScoreKey.AVR,
            label,
            "No core component could be assessed from the run state — the composite "
            "AVR cannot be computed (PRD §9.4).",
            observations=0,
        )

    if missing and not force_renormalize:
        auto_ok = len(missing) <= MAX_AUTO_MISSING and set(missing) <= auto_ok_names
        if not auto_ok:
            blocked = ", ".join(missing)
            total_blocked = sum(weights[name] for name in missing)
            return ScoreComponent.unassessed(
                ScoreKey.AVR,
                label,
                f"Composite blocked: {len(missing)} component(s) not assessed ({blocked}) "
                f"carrying {total_blocked:.2f} of the weight. PRD §9.4 forbids counting them "
                f"as zero, so the composite is withheld — re-run with fan-out/claim inputs, "
                f"or pass force_renormalize=True to compute it over a labelled reduced "
                f"denominator.",
                observations=len(assessed),
            )

    total_weight = sum(weights[name] for name in assessed)
    value = sum(float(assessed[name].value) * weights[name] for name in assessed) / total_weight
    renormalized = total_weight < 1.0 - 1e-9

    used = {name: weights[name] for name in assessed}
    notes: list[str] = []
    lost: list[str] = []
    if missing:
        excluded = ", ".join(f"{name} ({weights[name]:.2f})" for name in missing)
        notes.append(
            f"Modified denominator: excluded unassessed {excluded}; "
            f"remaining weights renormalized from {total_weight:.2f} to 1.00 (PRD §9.4)."
        )
        lost.append(
            f"Composite re-normalized because {', '.join(missing)} was not assessed — "
            f"this is a labelled reduced denominator, not a zero."
        )
    notes.append(
        f"Weights from the '{preset}' preset (profile version {PROFILE_VERSION}); "
        f"{heuristic_disclaimer()}"
    )

    return ScoreComponent(
        score_key=ScoreKey.AVR,
        label=label,
        value=clamp(value),
        sub_scores={name: float(assessed[name].value) for name in assessed},
        sub_weights=used,
        renormalized=renormalized,
        lost_points=lost,
        rationale=(
            f"AVR = Σ(component × weight) over {len(assessed)} assessed component(s) "
            f"using the '{preset}' weight preset."
        )
        + " "
        + " ".join(notes),
        confidence=overall_confidence(list(assessed.values())),
        observations=sum(key in components for key in weights),
    )


def build_scorecard(
    state: Any,
    components: Optional[Mapping[ScoreKey, ScoreComponent]] = None,
    *,
    include_optional: bool = True,
    force_renormalize: bool = False,
    gate: Any = None,
) -> Scorecard:
    """Assemble the full ``Scorecard``: components, weights, composite, gate.

    Core components receive their profile weight as a percentage (0–100); the
    six optional components of PRD §9.3 carry ``weight=None`` because they are
    reported beside the composite, never folded into it. Not-assessed
    components are kept in ``Scorecard.components`` with their reason but are
    omitted from ``Scorecard.scores`` (the schema contract requires a 0–10
    value there).
    """
    preset = resolve_preset(state)
    weights = weight_preset(preset)
    comps = dict(components) if components is not None else compute_components(
        state, include_optional=include_optional
    )

    for key in CORE_COMPONENT_ORDER:
        if key in comps:
            comps[key].weight = round(weights[key.value] * 100.0, 4)

    avr = compute_avr(comps, preset, force_renormalize=force_renormalize)

    rich = {key.value: comps[key] for key in comps if key is not ScoreKey.AVR}
    rich[ScoreKey.AVR.value] = avr

    schema_scores = {
        name: component.to_component_score()
        for name, component in rich.items()
        if component.assessed and component.to_component_score() is not None
    }

    from ega_scoring.gate import evaluate_gate

    if gate is None:
        gate = evaluate_gate(state)

    return Scorecard(
        scores=schema_scores,  # type: ignore[arg-type]
        components=rich,  # type: ignore[arg-type]
        gate=gate,
        avr=float(avr.value) if avr.assessed else None,
        composite=schema_scores.get(ScoreKey.AVR.value),
        profile=preset,
        profile_name=preset,
        profile_version=PROFILE_VERSION,
        confidence=overall_confidence(
            [comps[key] for key in CORE_COMPONENT_ORDER if key in comps]
        ),
        renormalized=avr.renormalized,
    )


def compute_all_scores(
    state: Any,
    *,
    include_optional: bool = True,
    force_renormalize: bool = False,
    gate: Any = None,
) -> Scorecard:
    """Run every deterministic component and return the assembled scorecard.

    This is the primary scoring entry point (PRD §9). It never calls an LLM,
    never touches the network, and is a pure function of ``state``.
    """
    return build_scorecard(
        state,
        include_optional=include_optional,
        force_renormalize=force_renormalize,
        gate=gate,
    )


def component_weights(state: Any) -> dict[str, float]:
    """Percentage weights (summing to 100) the composite uses for ``state``."""
    preset = resolve_preset(state)
    return {key: round(value * 100.0, 4) for key, value in weight_preset(preset).items()}


def missing_components(
    components: Mapping[ScoreKey, ScoreComponent], preset: str
) -> list[ScoreKey]:
    """Core components that carry weight in ``preset`` but were not assessed."""
    weights = weight_preset(preset)
    missing: list[ScoreKey] = []
    for name in weights:
        key = ScoreKey(name)
        component = components.get(key)
        if component is None or not component.assessed:
            missing.append(key)
    return missing


__all__ = [
    "AUTO_RENORMALIZABLE",
    "COMPONENT_LABELS",
    "CORE_COMPONENT_ORDER",
    "MAX_AUTO_MISSING",
    "OPTIONAL_COMPONENT_ORDER",
    "build_scorecard",
    "component_weights",
    "compute_all_scores",
    "compute_avr",
    "compute_components",
    "missing_components",
    "resolve_preset",
]
