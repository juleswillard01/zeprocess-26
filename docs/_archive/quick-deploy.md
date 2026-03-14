# MEGA QUIXAI — Infrastructure de Déploiement Complète

**Version**: 1.0  
**Date**: 2026-03-14  
**Scope**: Architecture, Docker Compose, CI/CD, Monitoring, Scaling, Security, Costs

---

## Table des Matières

1. [Architecture Infrastructure](#1-architecture-infrastructure)
2. [Docker Compose](#2-docker-compose)
3. [Service Workers](#3-service-workers)
4. [CI/CD Pipeline](#4-cicd-pipeline)
5. [Secrets Management](#5-secrets-management)
6. [Monitoring & Logs](#6-monitoring--logs)
7. [Scaling Strategy](#7-scaling-strategy)
8. [Backup & Recovery](#8-backup--recovery)
9. [Security](#9-security)
10. [Cost Estimation](#10-cost-estimation)

---

## 1. Architecture Infrastructure

### 1.1 Choix: VPS Unique vs Cloud Distribué

#### VPS Unique (RECOMMANDÉ pour MVP)

**Pourquoi** :
- 3 agents autonomes = charge prévisible et stable (pas de spike traffic)
- Lead Acquisition = quelques API calls/sec = CPU-light
- PostgreSQL+pgvector = nécessite state local = simpler en VPS
- Coût : ~50-100 EUR/mois vs 200-500+ EUR/mois en cloud

**Architecture** :
```
Internet
    ↓
Nginx (port 80/443)
    ↓
API Container (FastAPI) ← LangFuse observabilité
    ↓
    ├─→ Agent 1 Worker (Séduction, LangGraph)
    ├─→ Agent 2 Worker (Closing, LangGraph)
    ├─→ Agent 3 Worker (Lead Acquisition, LangGraph)
    ├─→ Redis (task queue, cache)
    └─→ PostgreSQL + pgvector (vectorstore, state)
```

**Specs VPS recommandées** :
- CPU: 4 cores (Intel Xeon E5 ou ARM)
- RAM: 8-16 GB (4 pour agents, 2 pour PostgreSQL, 2 pour buffer)
- Storage: 100 GB SSD (OS 20GB, PostgreSQL 30GB, logs 10GB, buffer 40GB)
- Bandwidth: 10 Mbps (suffisant pour API calls)
- OS: Ubuntu 22.04 LTS ou 24.04

**Fournisseurs** :
- **Hetzner Cloud** (€/mois): 4core/8GB/40GB → 6.90 EUR (standard-2)
- **Scaleway** : 4core/8GB/50GB → 8.99 EUR (DEV1-M)
- **Linode** : 4core/8GB/160GB → $12 USD
- **DigitalOcean** : 4core/8GB/160GB → $24 USD
- **OVH** : 4core/8GB/50GB → 7.99 EUR (Eco)

**Choix** : **Hetzner** (fiabilité + prix, datacenter EU)

