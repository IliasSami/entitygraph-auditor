"""Golden benchmark dataset and test fixtures for EntityGraph Auditor (PRD §17, EVALUATION.md).

Defines the four core archetypes used for automated calibration and regression testing:
1. Informational Technical Guide (High-quality SaaS / engineering guide)
2. Local Emergency Service (Austin 24/7 emergency plumber)
3. Keyword-stuffed thin affiliate page (Shallow, repetitive content)
4. High-risk unsubstantiated medical claims (Critical compliance / safety gate failure)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ega_schemas.enums import GateStatus, PageType


@dataclass
class GoldenTestCase:
    id: str
    name: str
    description: str
    content: str
    expected_page_type: PageType
    expected_gate_publishable: bool
    expected_gate_statuses: list[GateStatus]
    min_composite_avr: float
    max_composite_avr: float
    min_eos: float | None = None
    max_eos: float | None = None
    expected_central_entity: str = ""
    critical_issues_expected: bool = False
    context_packs: list[dict[str, Any]] = field(default_factory=list)


# --------------------------------------------------------------------------
# 1. Informational Technical Guide
# --------------------------------------------------------------------------
TECH_GUIDE_CONTENT = """# PostgreSQL Connection Pooling with PgBouncer
PgBouncer is a lightweight, high-performance connection pooler for PostgreSQL engineered to reduce server connection overhead and optimize query throughput.

## Architecture and Process Flow
PostgreSQL handles client connections by forking a dedicated backend worker process per connection, which consumes approximately 2 MB to 10 MB of RAM per process. Under heavy concurrency (exceeding 200 concurrent clients), context-switching latency increases significantly.

PgBouncer addresses this bottleneck by acting as an intermediary proxy. Clients connect to PgBouncer via TCP port 6432, and PgBouncer maintains a compact pool of persistent connections directly to the PostgreSQL server on port 5432.

### Pool Modes Comparison
- **Session Pooling**: Allocates a server connection to a client for the entire lifecycle of its connection. Released when client disconnects.
- **Transaction Pooling**: The server connection is assigned only during an active transaction block. As soon as `COMMIT` or `ROLLBACK` executes, the connection returns to the pool. This is the optimal mode for high-throughput REST APIs.
- **Statement Pooling**: Allocates connections per individual SQL statement. Multi-statement transactions and prepared statements are prohibited in this mode.

## Production Configuration Specifications
Key configuration directives in `pgbouncer.ini`:
- `max_client_conn = 5000`: Maximum simultaneous client connections accepted by PgBouncer.
- `default_pool_size = 25`: Dedicated connections per database/user pair maintained to PostgreSQL.
- `reserve_pool_size = 5`: Emergency connections opened when the default pool is exhausted.
- `pool_mode = transaction`: Optimal transaction-level multiplexing.

## Performance Benchmark Results
In benchmarking using `pgbench` with 1,000 concurrent clients running read-write transactions:
- Direct PostgreSQL connections: 1,420 transactions per second (TPS) with 85ms P99 latency.
- With PgBouncer transaction pooling: 8,950 transactions per second (TPS) with 12ms P99 latency.
- CPU utilization on the database host decreased by 48%.
"""

CASE_INFO_TECH = GoldenTestCase(
    id="case_info_tech",
    name="PostgreSQL Connection Pooling Guide",
    description="High-quality technical architecture guide with benchmarks and explicit EAV specifications.",
    content=TECH_GUIDE_CONTENT,
    expected_page_type=PageType.ARTICLE,
    expected_gate_publishable=True,
    expected_gate_statuses=[GateStatus.PASS, GateStatus.PASS_WITH_FIXES, GateStatus.NOT_CONFIGURED],
    min_composite_avr=5.0,
    max_composite_avr=9.8,
    min_eos=6.5,
    expected_central_entity="PostgreSQL Connection Pooling with PgBouncer",
    critical_issues_expected=False,
)




# --------------------------------------------------------------------------
# 2. Local Emergency Service (Plumber)
# --------------------------------------------------------------------------
LOCAL_SERVICE_CONTENT = """# Austin Emergency Plumbing 24/7
Austin Emergency Plumbing provides rapid 24-hour residential and commercial emergency plumbing repairs across the Greater Austin metropolitan area.

## Certified Local Technicians
Every service technician is a licensed journeyman or master plumber certified under Texas State Board of Plumbing Examiners License #M-38491. We maintain comprehensive liability insurance of $2,000,000 and full workers' compensation coverage.

## Service Area and Rapid Response
Our fleet operates dispatch hubs across Central Texas:
- Travis County: Austin, Pflugerville, Lakeway, Bee Cave
- Williamson County: Round Rock, Cedar Park, Georgetown
- Average on-site arrival time: Under 45 minutes for emergency dispatches.

## Dispatch Location & Contact Information
- Physical Address: 1204 Congress Ave, Austin, TX 78701
- 24/7 Hotline: (512) 555-0199
- Dispatch Hours: Open 24 Hours, 365 Days a Year including holidays.

## Transparent Emergency Rates
- Standard diagnostic fee: $49 (waived when repair work is authorized).
- Burst pipe mitigation: Starting at $280.
- Sewer line camera inspection: $150 flat rate.
- Emergency water heater replacement: Starting at $1,250 with same-day installation warranty.
"""

CASE_LOCAL_SERVICE = GoldenTestCase(
    id="case_local_service",
    name="Austin Emergency Plumbing",
    description="Local service page with explicit address, license numbers, phone, hours, and transparent pricing.",
    content=LOCAL_SERVICE_CONTENT,
    expected_page_type=PageType.SERVICE,
    expected_gate_publishable=True,
    expected_gate_statuses=[GateStatus.PASS, GateStatus.PASS_WITH_FIXES, GateStatus.NOT_CONFIGURED],
    min_composite_avr=6.0,
    max_composite_avr=9.5,
    expected_central_entity="Austin Emergency Plumbing 24/7",
    critical_issues_expected=False,
)


# --------------------------------------------------------------------------
# 3. Keyword-Stuffed Thin Affiliate Page
# --------------------------------------------------------------------------
THIN_STUFFED_CONTENT = """# Best VPN 2026 - Best Cheap Fast VPN Service Provider
If you want the best vpn, you need the best vpn provider for the best fast vpn speeds. The best cheap vpn is the best vpn service for all your best vpn needs.

## Why Choose The Best VPN?
Our best vpn is the best vpn because it is the fastest best vpn and the cheapest best vpn online. When you buy our best vpn, you get the best vpn experience with the best vpn features. Everyone loves the best vpn.

### Best Fast VPN Features
- Best vpn connection speeds
- Best vpn unlimited servers
- Best vpn encryption protocols
- Best cheap vpn discount pricing
- Best vpn customer satisfaction guarantee

## Best Cheap VPN Online
Get the best vpn today. The best vpn offers the best vpn performance. Do not wait to get the best vpn. Buy the best cheap vpn now for the best vpn protection. The best vpn provider is simply the best vpn in 2026.
"""

CASE_THIN_STUFFED = GoldenTestCase(
    id="case_thin_stuffed",
    name="Thin Keyword-Stuffed VPN Affiliate",
    description="Thin affiliate page stuffed with repeated keywords, generic claims, and zero concrete technical details.",
    content=THIN_STUFFED_CONTENT,
    expected_page_type=PageType.GENERAL,
    expected_gate_publishable=True,  # May pass with fixes or have lower score
    expected_gate_statuses=[GateStatus.PASS_WITH_FIXES, GateStatus.PASS, GateStatus.NOT_CONFIGURED],
    min_composite_avr=2.0,
    max_composite_avr=6.5,
    max_eos=5.5,  # Penalized for keyword stuffing
    critical_issues_expected=False,
)


# --------------------------------------------------------------------------
# 4. High-Risk Unsubstantiated Health Claim (Gate Blocker)
# --------------------------------------------------------------------------
HEALTH_HAZARD_CONTENT = """# Miracle Joint Reversal - 100% Guaranteed Arthritis Cure Without Surgery
Discover the top-secret herbal breakthrough that permanently cures rheumatoid arthritis, osteoarthritis, and joint degeneration in 7 days flat with zero drugs, exercise, or surgical intervention.

## 100% Guaranteed Cure Rate
Clinical researchers have proven this secret formula provides a 100% permanent cure rate for all joint diseases. Unlike expensive dangerous prescription medications pushed by doctors, our miracle drops instantly rebuild all lost cartilage overnight.

## Why Doctors Hide This Miracle
The medical establishment wants to keep you sick. Stop taking your medications and throw away your prescriptions today. Taking just three drops per morning guarantees you will walk pain-free forever without any side effects.
"""

CASE_HEALTH_HAZARD = GoldenTestCase(
    id="case_health_hazard",
    name="Unsubstantiated Miracle Cure",
    description="Dangerous medical promises claiming 100% guaranteed cure without clinical evidence, triggering critical gate failure.",
    content=HEALTH_HAZARD_CONTENT,
    expected_page_type=PageType.GENERAL,
    expected_gate_publishable=False,
    expected_gate_statuses=[GateStatus.FAIL],
    min_composite_avr=0.0,
    max_composite_avr=7.0,
    critical_issues_expected=True,
)


GOLDEN_CASES: list[GoldenTestCase] = [
    CASE_INFO_TECH,
    CASE_LOCAL_SERVICE,
    CASE_THIN_STUFFED,
    CASE_HEALTH_HAZARD,
]


def get_golden_case(case_id: str) -> GoldenTestCase | None:
    for c in GOLDEN_CASES:
        if c.id == case_id:
            return c
    return None
