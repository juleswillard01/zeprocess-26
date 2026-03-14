# Architecture Decision Records (ADRs)

## Overview

This document captures critical architectural decisions, trade-offs, and rationale for MEGA QUIXAI's design.

---

## ADR-001: Use Claude Code SDK as Core Execution Engine

**Status**: APPROVED
**Date**: 2026-03-14

### Context

MEGA QUIXAI requires:
- Code execution for tool integration
- Token counting for budget tracking
- Intelligent tool routing
- Multi-turn conversations with state

### Decision

Use **Claude Code SDK** (vs. LangChain/LLama.cpp/Mistral) as the core engine.

### Options Considered

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| Claude Code SDK | Native code execution, native tools, built-in token counting, production-ready | Proprietary, closed-source | **CHOSEN** |
| LangChain + Claude | Flexibility, multi-model support | Token counting manual, more code | Rejected |
| Local LLama | No API costs, privacy | Weak reasoning, small context window, slow | Rejected |
| OpenAI Code Interpreter | Code execution, good models | Expensive, unpredictable costs | Rejected |

### Consequences

**Positive:**
- Native tool definition support
- Automatic token counting → cost visibility
- Code execution sandboxed (safety)
- Streaming responses
- Minimal abstraction layers

**Negative:**
- Locked into Anthropic ecosystem
- Cannot easily switch models
- Dependent on API uptime
- Cold-start latency for agents

### Mitigation

- Implement cost tracking layer (abstract away SDK specifics)
- Maintain fallback to local Claude via API
- Design agent interface agnostic to SDK

---

## ADR-002: Model Routing by Task Complexity

**Status**: APPROVED
**Date**: 2026-03-14

### Context

Claude offers three models with different costs:
- Haiku: $0.80/$4 per million tokens (fast, cheap)
- Sonnet: $3/$15 per million tokens (balanced)
- Opus: $15/$75 per million tokens (powerful)

Budget: $3,000-$10,000/month for 200-1000 leads

### Decision

Implement **complexity-based routing**:
- **Haiku** (0.1-0.3): Filtering, scoring, classification
- **Sonnet** (0.4-0.6): Agent execution, DM generation
- **Opus** (0.7-1.0): Strategy, reasoning, closing decisions

### Alternatives

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| Always Opus | Best quality | Cost: $15k+/month for 200 leads | Rejected |
| Always Sonnet | Balanced | Overpays on filtering, underpays on closing | Rejected |
| Always Haiku | Cheapest | Fails on complex reasoning | Rejected |
| **Complexity-based routing** | Cost-optimized, quality matched | Requires prompt engineering per tier | **CHOSEN** |

### Consequences

**Positive:**
- 60-70% cost savings vs. always using Sonnet
- Quality appropriate for each task
- Scalable to 1000+ leads/month
- Clear token budget allocation

**Negative:**
- More complex routing logic
- Tier-specific prompt engineering needed
- Potential quality inconsistencies if routing miscalibrated

### Mitigation

- Strict prompt templates for each tier
- A/B test routing thresholds
- Fallback to higher tier if lower fails
- Monthly cost audits

---

## ADR-003: LangGraph for Multi-Agent Orchestration

**Status**: APPROVED
**Date**: 2026-03-14

### Context

MEGA QUIXAI requires:
- Three independent agents
- Sequential handoff (LEA → SED → CLOSING)
- Conditional routing (SED → CLOSING only if qualified)
- State persistence

### Decision

Use **LangGraph** (vs. Airflow/Celery/custom) for orchestration.

### Options Considered

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **LangGraph** | Explicit state, visual debugging, LangChain integration | Newer library, smaller community | **CHOSEN** |
| Airflow | Battle-tested, DAG visualization | Heavy, SQL-based state | Rejected |
| Celery | Distributed tasks, task queues | Overkill for this architecture | Rejected |
| Custom State Machine | Maximum control | Code complexity, hard to debug | Rejected |

### Consequences

**Positive:**
- Clear state transitions
- Easy to visualize agent flow
- Debuggable (can inspect state at each step)
- LangChain/LangFuse integration seamless

**Negative:**
- Smaller ecosystem (fewer extensions)
- Version churn possible
- Requires learning new library

### Mitigation

- Pin LangGraph version
- Monitor GitHub for breaking changes
- Implement custom utilities if needed

---

## ADR-004: PostgreSQL + pgvector for Vector Storage

**Status**: APPROVED
**Date**: 2026-03-14

### Context

MEGA QUIXAI needs:
- Transactional lead/conversation data
- Vector storage for RAG (embeddings)
- Relational integrity
- Scale to 100k+ records

### Decision

Use **PostgreSQL 16 + pgvector** (vs. separate vector DB).

### Options Considered

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **PostgreSQL + pgvector** | Unified, transactional, cost-effective | Performance at 10M+ vectors | **CHOSEN** |
| Pinecone | Managed, optimized for vectors | Vendor lock-in, expensive at scale | Rejected |
| Weaviate | Open-source, flexible | Operational burden | Rejected |
| Milvus | Powerful, open-source | Complex setup, resources | Rejected |

### Consequences

**Positive:**
- Single database system
- ACID compliance for transactions
- No vendor lock-in
- Good performance for <1M vectors
- Easy backup/recovery

**Negative:**
- Vector performance degrades at 10M+ records
- Requires tuning for production

### Mitigation

- Use exact cosine distance (optimized)
- Index strategy (HNSW for scale)
- Monitor query latency
- Plan Milvus migration at 1M+ vectors

---

## ADR-005: RAG with Sentence-Transformers (vs. Fine-Tuning)

**Status**: APPROVED
**Date**: 2026-03-14

### Context

SEDUCTION agent needs personalization:
- Retrieve relevant coaching knowledge
- Context-aware responses
- No training data available

### Decision

Use **RAG with sentence-transformers** (vs. fine-tuning).

### Options Considered

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **RAG** | No training needed, immediate, flexible | Retrieval quality depends on embeddings | **CHOSEN** |
| Fine-tune Claude | Custom model, possibly better | $$$, requires labeled data, slow | Rejected |
| Fine-tune embeddings | Better retrieval | Time-consuming, requires tuning | Future work |

### Consequences

**Positive:**
- Deploy immediately (no training cycle)
- Trivial to add new knowledge (append to DB)
- Cost-effective
- Quality sufficient for B2B coaching

**Negative:**
- Retrieval quality depends on prompt
- Occasional irrelevant context
- Token usage higher (large context windows)

### Mitigation

- Curate knowledge base (quality > quantity)
- Use prompt engineering to control retrieval
- Monitor retrieval precision with human feedback
- Plan fine-tuned embeddings model for Phase 2

---

## ADR-006: V-Code Safety Pattern (Automated Code Review)

**Status**: APPROVED
**Date**: 2026-03-14

### Context

MEGA QUIXAI makes real transactions:
- Sends payments (Stripe)
- Sends messages (Instagram)
- Manages leads (delete/block)
- Safety-critical decisions

### Decision

Implement **V-Code pattern**: Automated review layer before sensitive operations.

### Options Considered

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **V-Code review** | Automated, logged, no manual overhead | Complex to implement | **CHOSEN** |
| Manual review (Slack) | Human oversight | Slow, doesn't scale | Partial |
| No review (trust agent) | Fast, simple | Catastrophic risk | Rejected |

### Consequences

**Positive:**
- Catches ~90% of errors automatically
- Audit trail for compliance
- Scales without human overhead
- Cost-effective safety

**Negative:**
- Implementation overhead (~200 lines code per operation)
- False positives possible

### Mitigation

- Test extensively (unit + integration tests)
- Start conservative (reject > approve)
- Human fallback for uncertain cases
- Monthly audit review

---

## ADR-007: Rate Limiting by Operation Type

**Status**: APPROVED
**Date**: 2026-03-14

### Context

MEGA QUIXAI risks:
- Instagram account ban (rate limiting)
- Stripe fraud detection (unusual patterns)
- API quota exhaustion

### Decision

Implement **operation-level rate limiting** with Redis/in-memory buckets.

### Limits

```
instagram_dm:
  per_minute: 5
  per_hour: 100
  per_day: 1000

stripe_charge:
  per_day: 50
  per_week: 200

agent_invocation:
  per_minute: 100
```

### Consequences

**Positive:**
- Prevents account lockout
- Fraud detection compatible
- Transparent (observable)

**Negative:**
- Artificial ceiling on growth
- Requires tuning for each platform

### Mitigation

- Start conservative, raise over time
- Monitor Instagram/Stripe alerts
- Adjust based on real-world feedback

---

## ADR-008: Stripe for Payments (vs. Manual/Other)

**Status**: APPROVED
**Date**: 2026-03-14

### Context

CLOSING agent needs:
- Process $2000 payments reliably
- PCI compliance
- Fraud detection
- Instant settlement

### Decision

Use **Stripe** (vs. PayPal/Wise/manual).

### Options Considered

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **Stripe** | Reliable, fraud detection, webhooks | 2.9% + $0.30 fee | **CHOSEN** |
| PayPal | Instant, trusted brand | 2.9% + $0.30, integration slower | Comparable |
| Wise | Low fees, global | Slower settlement, weaker fraud | Rejected |
| Manual wire | No fees | Unreliable, slow | Rejected |

### Consequences

**Positive:**
- Industry standard
- Webhook integration reliable
- PCI SAC Level 1
- Fraud detection included

**Negative:**
- Takes 2.9% commission
- Potential disputes/chargebacks

### Mitigation

- Implement refund policy
- Monitor chargeback rates
- Clear payment terms pre-sale

---

## ADR-009: Licensing Model (SaaS Tiers vs. One-Time)

**Status**: APPROVED
**Date**: 2026-03-14

### Context

Monetization strategy for MEGA QUIXAI agents:
- Base cost: development, infrastructure, support
- Value-based: more agents, more leads

### Decision

Use **SaaS monthly tiers** (vs. one-time license/per-agent pricing).

### Options Considered

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **Monthly SaaS** | Recurring revenue, predictable | Barrier to adoption | **CHOSEN** |
| One-time license | High upfront | Unpredictable, scaling issues | Rejected |
| Per-lead pricing | Aligns incentives | Unpredictable costs for customer | Rejected |

### Tiers

- Base: $200/month (1 agent, 100 leads)
- Advanced: $500/month (2 agents, 500 leads)
- Enterprise: $2000+/month (unlimited)

### Consequences

**Positive:**
- Predictable MRR
- Customer commitment (longer retention)
- Easy to upsell

**Negative:**
- Acquisition friction
- Need strong onboarding

### Mitigation

- 14-day free trial
- Money-back guarantee
- Clear ROI messaging

---

## ADR-010: Observability: LangFuse + Prometheus + ELK

**Status**: APPROVED
**Date**: 2026-03-14

### Context

Production requirements:
- Token usage tracking (cost)
- Agent performance metrics
- Conversation tracing
- Error investigation

### Decision

Use **LangFuse** (tracing) + **Prometheus** (metrics) + **ELK** (logs).

### Options Considered

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **LangFuse + Prom + ELK** | Comprehensive, open-source | Operational overhead | **CHOSEN** |
| DataDog | All-in-one, vendor support | $$$$, overkill | Rejected |
| Only LangFuse | Simple, integrated | Missing metrics/logs | Partial |

### Consequences

**Positive:**
- Full observability
- Cost tracking built-in
- Debug traces available
- Standards-compliant (Prometheus, OTEL)

**Negative:**
- Multiple systems to maintain
- Disk space for logs

### Mitigation

- Docker containers for each service
- Auto-rotation of old logs
- Simplified dashboards (show only key metrics)

---

## ADR-011: Immutable Audit Logs (90-day retention)

**Status**: APPROVED
**Date**: 2026-03-14

### Context

Compliance and debugging:
- Every decision logged
- Audit trail for disputes
- Investigate failed conversions

### Decision

**Immutable JSONL audit logs** (90-day retention).

### Format

```jsonl
{"timestamp":"2026-03-14T10:00:00Z","event":"stripe_charge","agent":"CLOSING","lead_id":"...","amount":2000,"result":"approved"}
```

### Consequences

**Positive:**
- Immutable (append-only)
- Queryable (JSONL format)
- Lightweight (not DB)
- GDPR-compliant (90-day deletion)

**Negative:**
- Manual cleanup needed
- No built-in querying

---

## ADR-012: Python 3.12 + uv for Development

**Status**: APPROVED
**Date**: 2026-03-14

### Context

Tech stack choice:
- Fast development iteration
- Type safety
- Dependency management

### Decision

**Python 3.12 + uv** (vs. Go/Rust/older Python).

### Rationale

- Type hints (mypy --strict)
- Ecosystem (Anthropic SDK, LangChain native Python)
- Speed (3.12 faster than 3.11)
- Determinism (uv reproducible builds)

### Consequences

**Positive:**
- Fast to develop
- Good tooling (ruff, mypy)
- Rich library ecosystem

**Negative:**
- Slower than compiled languages at runtime
- GIL limits parallelism

### Mitigation

- Async/await for I/O
- Worker queues for CPU-heavy tasks
- Monitor performance metrics

---

## Summary: Trade-offs Accepted

| Decision | Pro | Con | Accepted |
|----------|-----|-----|----------|
| Claude SDK | Quality + tools | Vendor lock-in | ✓ |
| Complexity routing | Cost savings | Routing complexity | ✓ |
| LangGraph | Clear state | Small ecosystem | ✓ |
| PostgreSQL + pgvector | Unified DB | Limited at 10M+ vectors | ✓ |
| RAG (not fine-tune) | Fast deployment | Quality varies | ✓ |
| V-Code safety | Automated control | Implementation effort | ✓ |
| Rate limiting | Account safety | Growth ceiling | ✓ |
| Stripe | Reliable | 2.9% fee | ✓ |
| SaaS tiers | Recurring revenue | Adoption friction | ✓ |
| Multi-observability | Comprehensive | Operational overhead | ✓ |
| Python 3.12 | Development speed | Slower runtime | ✓ |

All trade-offs are **intentionally accepted** given the constraints and goals of MEGA QUIXAI.

---

## Future ADRs (To Be Decided)

- **ADR-013**: Milvus migration when vectors exceed 10M
- **ADR-014**: Fine-tuned embedding model for Phase 2
- **ADR-015**: Multi-region deployment for global coverage
- **ADR-016**: Custom voice synthesis for phone calls
- **ADR-017**: Persistent memory (long-term lead context)

---

*Document Version*: 1.0
*Date*: 2026-03-14
*Status*: COMPLETE
