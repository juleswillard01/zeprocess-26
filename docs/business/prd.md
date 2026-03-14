# Product Requirements Document - MEGA QUIXAI

## Executive Summary

MEGA QUIXAI est un système multi-agents autonome conçu pour automatiser entièrement le pipeline de vente dans la niche coaching séduction/développement personnel masculin. Trois agents IA collaborent via LangGraph pour qualifier, engager et convertir des prospects à grande échelle.

**Vision**: Transformer un entrepreneur solo en une machine de vente 24/7 capable de traiter 100-1000 leads/mois avec taux de conversion humain.

---

## Product Overview

### Three-Agent Autonomous System

#### Agent 1: SÉDUCTION (Content & Engagement)
- **Rôle**: Attraction, qualification, nurture
- **Responsabilités**:
  - Générer 5-10 posts Instagram/jour (storytelling, hooks, CTA)
  - Répondre aux DMs avec personnalisation RAG (histoire du prospect)
  - Qualifier les leads entrants (intérêt, budget, timeline)
  - Segmenter les prospects par profil ICP
  - Construire rapport émotionnel et crédibilité
- **Critères de succès**:
  - Engagement rate > 5% sur posts
  - Réponse <2h aux DMs
  - Qualification rate > 70% (lead qualifié)
  - Handoff à CLOSING avec score ≥ 7/10

#### Agent 2: CLOSING (Sales & Conversion)
- **Rôle**: Conversion, objection handling, deal closing
- **Responsabilités**:
  - Conversations de closing via DM (follow-ups)
  - Appels téléphoniques simulés (transcription → handling)
  - Gérer 10+ objections courantes (prix, timing, doute, alternatives)
  - Créer urgence et scarcité appropriée
  - Négocier et customiser offres
  - Finaliser contrats et paiements
- **Critères de succès**:
  - Close rate > 20% des leads qualifiés
  - Deal value moyen > 500€
  - Cycle de vente < 7 jours
  - CLTV > 2000€ (multi-produits)

#### Agent 3: LEAD ACQUISITION (Sourcing & Scoring)
- **Rôle**: Prospection, qualification ICP, premier contact
- **Responsabilités**:
  - Scraper leads depuis Instagram, TikTok, forums (ICP matching)
  - Scorer profils via heuristiques (intérêt, pouvoir d'achat, urgence)
  - Envoyer premiers DMs de sensibilisation (cold outreach)
  - Trier faux positifs (bots, concurrents, wrong audience)
  - Maintenir database de leads prospectés
  - A/B tester premiers messages
- **Critères de succès**:
  - 100-300 leads qualifiés/mois
  - Reply rate > 15% aux premiers DMs
  - ICP accuracy > 80%
  - Cost per lead qualified < 5€

---

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    MEGA QUIXAI SYSTEM FLOW                      │
└─────────────────────────────────────────────────────────────────┘

  LEAD ACQUISITION AGENT
        │
        ├─ Scrape leads (Instagram, TikTok, etc.)
        ├─ Score ICP match
        ├─ First contact (cold DM)
        └─ Handoff → SÉDUCTION with score
                      │
                      ↓
         SÉDUCTION AGENT (RAG-powered)
        │
        ├─ Respond to DMs (personalized)
        ├─ Share valuable content
        ├─ Build relationship
        ├─ Qualify objections
        └─ Handoff → CLOSING with score ≥7/10
                      │
                      ↓
           CLOSING AGENT (High-touch)
        │
        ├─ Follow-up conversations
        ├─ Handle objections
        ├─ Negotiate
        ├─ Close deal
        └─ Handoff → Post-sale (upsell tracking)
```

---

## Technical Specifications

### Stack & Infrastructure

| Component | Technology | Version | Justification |
|-----------|-----------|---------|---------------|
| LLM Orchestration | LangGraph | 0.2+ | State management, multi-agent coordination |
| LLM Chain | LangChain | 0.3+ | Memory, RAG, tool integration |
| Code Execution | Claude Code SDK | Latest | Native code execution, tool definition |
| Primary LLM | Claude 3.5 Opus/Sonnet | Latest | High reasoning (Opus), fast execution (Sonnet) |
| Memory/Context | LangFuse | Latest | Production observability, token tracking |
| Database | PostgreSQL 16 | 16+ | Transactional, pgvector for embeddings |
| Embeddings | sentence-transformers | 3.0+ | French language support, local or cloud |
| VCS/Deployment | Docker + Systemd | Latest | Containerized, auto-restart on VPS |
| Language | Python | 3.12+ | Type safety, performance |
| Package Manager | uv | Latest | Fast, deterministic builds |

### Infrastructure Requirements

- **Compute**: VPS Linux (8GB RAM, 4 CPU minimum)
  - Dev: Single container, single agent
  - Prod: Multi-container, 3 agents + orchestrator
- **Storage**: PostgreSQL (10GB initial, +1GB/month for leads)
- **Network**: Residential proxies for scraping (optional, high volume)
- **Monitoring**: LangFuse (observability), Sentry (errors), custom logging

### Scale Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Leads processed/month | 100-1000 | Depends on scraping + cold outreach velocity |
| Concurrent conversations | 10-50 | Per-agent load balancing |
| API calls/day | 10k-50k | Model routing optimization critical |
| Tokens/month | 50M-500M | Budget-dependent routing |
| Latency (DM response) | <2 hours | Async processing, batch inference |
| Uptime SLA | 99% | Critical for revenue generation |

---

## Business Model & Monetization

### Revenue Streams

1. **Core Coaching**: 2000€ per client (90-day program)
2. **Upsells**: 500-1000€ per client (group coaching, tools, accountability)
3. **Affiliate**: 10-15% commission on partner products
4. **Automation/Licensing**: 200€/month per agent deployment

### Cost Structure

| Cost Category | Estimate | Notes |
|---|---|---|
| **API Costs (Claude)** | 3000-10000€/month | Primary driver; 3000 for MVP, 10k at scale |
| **Infrastructure** | 50-100€/month | VPS, DB, monitoring |
| **Third-party APIs** | 100-500€/month | Instagram/TikTok scraping, proxy services |
| **Labor** | Automation removes manual work | MEGA QUIXAI goal |
| **Total** | 3150-10600€/month | ROI target: 50k+€/month revenue |

### Licensing Fees

- **Base licensing**: 200€/month for agent access
- **Volume-based**: +50€/month per additional concurrent agent instance
- **Support**: Included in licensing

---

## Key Features & Use Cases

### Feature Set by Agent

#### SÉDUCTION Agent
- **Content Generation**
  - Instagram carousel posts (storytelling arcs)
  - Reels scripts (hook, value, CTA)
  - Stories (behind-the-scenes, social proof)
  - RAG-powered personalization (tailored to prospect's pain points)

- **DM Engagement**
  - Prospect history + previous interactions (context window)
  - Objection anticipation (common reasons they say no)
  - Follow-up sequences (drip campaigns, automated persistence)
  - Lead qualification (BANT: Budget, Authority, Need, Timeline)

- **Lead Scoring**
  - Engagement score (replies, time-to-reply, message length)
  - Intent score (keywords, audience segment)
  - Funnel position (awareness → consideration → decision)

#### CLOSING Agent
- **Conversation Management**
  - Multi-turn objection handling (price, timing, social proof, alternatives)
  - Dynamic offer customization (payment plans, bonuses, guarantees)
  - Urgency creation (limited spots, deadline)
  - Social proof injection (testimonials, results, case studies)

- **Sales Tactics**
  - Trial closes (assumptive language)
  - Yes-ladder (small agreements → big commitment)
  - Takeaway close (remove the offer)
  - Alternative choice close (multiple wins, no way to lose)

- **Post-Close**
  - Upsell identification (what else might they need)
  - Payment processing integration (Stripe API)
  - Welcome sequence automation
  - Success tracking (onboarding, results)

#### LEAD ACQUISITION Agent
- **Sourcing**
  - Instagram scraping (hashtags, locations, follower profiles)
  - TikTok audience identification (trending sounds, creator audiences)
  - Reddit/Forum monitoring (relevant discussions)
  - LinkedIn prospect discovery

- **ICP Matching**
  - Age/location filters (demographic)
  - Interest inference (bio keywords, follow patterns)
  - Socioeconomic signals (profile indicators of spending power)
  - Pain point identification (posts, comments, engagement)

- **Lead Management**
  - Deduplication (same person across platforms)
  - Status tracking (new, contacted, unresponsive, qualified, closed)
  - Recycle lists (retry after 30 days)
  - Blacklisting (competitors, bots, spam)

---

## Data Architecture

### Core Data Entities

#### Lead
```
id: UUID
source: enum (instagram, tiktok, reddit, linkedin, email)
username: str
profile_url: str
name: str (inferred)
age: int (estimated)
location: str
bio: str
interest_score: float [0-1]
icp_match: float [0-1]
status: enum (new, contacted, unresponsive, qualified, closed, lost)
created_at: timestamp
last_contact: timestamp
attempts: int
next_retry: timestamp
metadata: json (interests, pain points, engagement patterns)
```

#### Conversation
```
id: UUID
lead_id: FK
agent_id: enum (SEDUCTION, CLOSING, LEAD_ACQUISITION)
channel: enum (dm, whatsapp, phone, sms)
messages: array of {
  timestamp: timestamp
  sender: enum (agent, prospect)
  content: str
  sentiment: str
  intent: str
  agent_reasoning: str
}
status: enum (active, paused, closed_won, closed_lost)
created_at: timestamp
updated_at: timestamp
```

#### Content
```
id: UUID
type: enum (post, reel, story, dm, email)
agent_id: FK (SEDUCTION)
created_by: Claude model
content: text
media_urls: array
posted_at: timestamp
metrics: {
  likes: int
  comments: int
  shares: int
  saves: int
  engagement_rate: float
  reach: int
  impressions: int
}
a_b_test_variant: str (optional)
```

#### Interaction
```
id: UUID
lead_id: FK
agent_id: enum
event_type: enum (post_view, dm_sent, dm_replied, link_click, call_join, purchase, objection)
timestamp: timestamp
context: json
metadata: json
```

---

## Integration Points

### External APIs & Services

| Service | Integration | Purpose | Frequency |
|---------|-----------|---------|-----------|
| **Instagram Graph API** | DM reading/sending, story/post upload | Content distribution, DM engagement | Real-time |
| **TikTok API** | User search, video upload (optional) | Lead sourcing, content distribution | Daily |
| **Stripe API** | Payment processing | Close deals, collect payment | On demand |
| **Twilio** | SMS/WhatsApp messaging | Backup communication channel | Real-time |
| **Agora/Twilio Video** | Phone/video calls | CLOSING agent calls | On demand |
| **LangFuse** | Observability | Cost tracking, performance monitoring | Real-time |
| **Sentry** | Error tracking | Production errors, incidents | On demand |

---

## Success Criteria

### Phase 1: MVP (Weeks 1-4)
- [ ] LEAD ACQUISITION: Scrape 100 leads, manual scoring test
- [ ] SÉDUCTION: Respond to 10 inbound DMs with RAG
- [ ] CLOSING: 2-3 manual conversations + objection script templates
- [ ] Database schema complete, pgvector working
- [ ] Claude Code SDK integration working
- [ ] LangGraph coordination tested

### Phase 2: Automation (Weeks 5-8)
- [ ] LEAD ACQUISITION: Automated first contact (cold DMs) at scale
- [ ] SÉDUCTION: End-to-end automation (DM response → qualification)
- [ ] CLOSING: Conversation handoff + objection handling
- [ ] Cost tracking via LangFuse
- [ ] Model routing optimized (Haiku for filters, Sonnet for agents, Opus for strategy)
- [ ] 3 simultaneous prospects closing

### Phase 3: Scale (Weeks 9-12)
- [ ] Process 100-300 leads/month
- [ ] 20+ concurrent conversations
- [ ] Close rate > 15%
- [ ] Cost per lead < 5€
- [ ] Revenue > 20k€/month (100+ customers)

---

## Risks & Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|-----------|
| API rate limits (Instagram) | Blocked lead sourcing | Medium | Rotate credentials, add delays, use proxies |
| Low-quality leads spam | Wasted tokens, bad reputation | High | Strong ICP scoring, qualification gates |
| Poor objection handling | Lost deals, refunds | Medium | Test scripts, Opus for complex cases, human fallback |
| Instagram account ban | Complete lead source loss | Low | Respect API limits, human-like behavior patterns |
| Budget overrun (API costs) | Margin collapse | High | Aggressive token counting, Haiku for filters, cost-per-lead limits |
| Regulatory/legal (EU compliance) | Fines, operational shutdown | Medium | GDPR consent, privacy-by-design, data retention policies |
| Cold outreach deliverability | Lead sourcing fails | Medium | Warmup sequences, reputation monitoring, multi-channel approach |

---

## Non-Functional Requirements

### Performance
- DM response latency: <2 hours (async acceptable)
- Content generation time: <5 minutes per post
- Lead scoring: <1 second per lead
- Conversation inference: <10 seconds per turn

### Reliability
- System uptime: 99% (9 hours downtime/month acceptable)
- Data durability: Daily backups, 30-day retention
- Graceful degradation: Fallback to human review on agent errors

### Security
- API keys: Encrypted in .env, never logged
- User data: GDPR-compliant, encrypted at rest
- Conversation data: Audit logs, no deletion without approval
- Code execution: Sandboxed via Claude Code SDK, no shell access

### Observability
- All agent decisions logged (LangFuse)
- Token usage tracked per agent
- Conversion funnel metrics tracked
- Errors escalated to human (Slack notification)

---

## Go-to-Market Strategy

### Phase 1: Proof of Concept
- Build MEGA QUIXAI for internal use (coaching business)
- Generate case studies (client results)
- Document ROI (cost per lead, close rate, revenue impact)

### Phase 2: Beta Program
- Offer to 5-10 coaches in niche (invite-only)
- Collect feedback, measure results
- Price testing (validate 200€/month licensing)

### Phase 3: Public Launch
- Create landing page, product demo video
- Sell to 50+ coaches/entrepreneurs
- Build marketplace for custom agents (tools, templates)

---

## Success Definition

MEGA QUIXAI is successful when:
1. **Autonomous**: 0 manual work per lead (fully automated pipeline)
2. **Profitable**: Cost per lead < 5€, close rate > 20%, LTV > 2000€
3. **Scalable**: Can handle 1000+ leads/month without human intervention
4. **Repeatable**: Works across different coaches, niches, markets
5. **Measured**: Complete observability via LangFuse, dashboards, reporting

---

*Document Version*: 1.0
*Date*: 2026-03-14
*Status*: APPROVED FOR ARCHITECTURE DESIGN
