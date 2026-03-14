# Implementation Roadmap v2 — QUIXAI / Hexis

**Timeline**: 8 semaines vers production MVP
**Equipe**: 2-3 ingenieurs + 1 DevOps (partiel)

## Critical Path

```
Sem 1: Phase 0 Foundation     <- Merge repos, Hexis local, pipeline OK
    |
    | BLOCKER: Claude Max approval
    v
Sem 2-3: Phase 1 Auth+Billing <- JWT, Stripe, user management
    |
Sem 3-4: Phase 2 Pipeline     <- Ingestion auto, Claude embeddings
    |
Sem 4-5: Phase 3 Chatbot      <- Multi-tenant, tool lockdown, securite
    |
Sem 5: Phase 4 Frontend       <- React landing, auth, chat (parallele)
    |
Sem 6: Phase 5 Channels       <- Telegram, WhatsApp, Discord (parallele)
    |
    | BLOCKER: OVH provisioning (48h)
    v
Sem 7: Phase 6 Production     <- OVH deploy, SSL, backups, RGPD
    |
Sem 8+: Phase 7 Launch        <- 10-20 beta users, iterate
```

## Phase 0: Foundation (Sem 1, 40h)

- [ ] Merge zeprocess + Hexis en un repo
- [ ] Hexis tourne en local (docker-compose up, chat fonctionnel)
- [ ] Pipeline valide (transcribe -> embed -> search < 200ms)
- [ ] .env.example complet
- [ ] Architecture diagram a jour

**Risque**: Conflits de merge, versions PostgreSQL

## Phase 1: Auth + Billing (Sem 2-3, 80h)

- [ ] Modeles: User, Subscription, ChatbotAccess (Pydantic v2 + SQLAlchemy)
- [ ] JWT: register, login, refresh, logout
- [ ] Stripe: create_customer, create_subscription, webhooks
- [ ] Access control par tier (20 EUR = 1 agent, 90 EUR = tous 1X, 180 EUR = tous 5X)
- [ ] Rate limiting Redis par tier
- [ ] Emails: verification, subscription, payment failure, deletion
- [ ] Tests 80%+

**Risque**: Stripe webhooks complexes, edge cases paiement

## Phase 2: Content Pipeline (Sem 3-4, 80h)

- [ ] Upload video -> transcription (faster-whisper)
- [ ] Hexis ingestion sophistiquee (fast/slow/hybrid)
- [ ] Claude Max embeddings (pas Ollama)
- [ ] Tagging par formation (metadata.formation_id)
- [ ] Admin API: CRUD formations
- [ ] Usage tracking (tokens, cout)
- [ ] Tests 80%+

**Risque**: Claude Max quota, qualite RAG

## Phase 3: Chatbot Product (Sem 4-5, 80h)

- [ ] Multi-tenant chat (memoire isolee par subscriber_id)
- [ ] Endpoints: POST /chat/send (SSE), GET /conversations, DELETE /conversation
- [ ] Tool lockdown: SEULEMENT memory + RAG (tout le reste OFF)
- [ ] Prompt injection: sanitization, system prompt verrouille, output filtering
- [ ] 3 chatbots: Seduction (M1-3), Closing (M4-6), Acquisition (M7-9)
- [ ] Choix personnalite par l'utilisateur
- [ ] Tests 80%+

**Risque**: Prompt injection, fuite de contenu formation

## Phase 4: Frontend (Sem 5, 40h)

- [ ] Next.js 15 + Tailwind + shadcn/ui
- [ ] Landing page (hero, pricing, FAQ)
- [ ] Auth UI (register, login, forgot password)
- [ ] Dashboard (profil, subscription, usage)
- [ ] Chat interface (streaming SSE, agent selector, historique)
- [ ] Billing (tier selector, Stripe Checkout redirect)
- [ ] Mobile responsive

**Risque**: Streaming SSE frontend, UX chat

## Phase 5: Channels (Sem 6, 40h)

- [ ] Telegram bot (polling, /chat commande)
- [ ] WhatsApp Business API (webhook, Twilio)
- [ ] Discord bot (slash commands, DM)
- [ ] Router: message -> auth subscriber -> chatbot -> reponse
- [ ] Channel linking dans settings utilisateur

**Risque**: Auth cross-canal (Telegram user -> subscriber account)

## Phase 6: Production (Sem 7, 50h)

- [ ] OVH dedie (8c/32GB/500GB, ~100 EUR/mois)
- [ ] Docker Compose prod (sans Ollama)
- [ ] SSL Let's Encrypt + auto-renewal
- [ ] Nginx (reverse proxy, rate limit, HSTS)
- [ ] UFW firewall (22, 80, 443 uniquement)
- [ ] Backups PostgreSQL quotidiens (pg_dump + S3)
- [ ] Monitoring + alertes (health checks, disk, errors)
- [ ] RGPD: privacy policy, deletion endpoint, DPA
- [ ] Post-deploy verification

**Risque**: OVH provisioning delay, PostgreSQL extensions build

## Phase 7: Launch (Sem 8+)

- [ ] 10-20 beta users recrutes
- [ ] NPS survey hebdo
- [ ] Metriques: MRR, churn, engagement, latence
- [ ] Objectif M1: 500-1000 EUR MRR
- [ ] Objectif M6: 50 abonnes, 4000 EUR MRR, 92% marge

## Couts mensuels

| | M1 | M6 |
|---|---|---|
| OVH | 55 EUR | 100 EUR |
| Claude Max | 174 EUR | 174 EUR |
| Stripe/Email/Monitoring | 50 EUR | 100 EUR |
| **Total** | **279 EUR** | **374 EUR** |
| Revenue cible | 500 EUR | 4000 EUR |
| Profit | 221 EUR | 3626 EUR |
