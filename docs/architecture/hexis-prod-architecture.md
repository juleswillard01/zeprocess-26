# Hexis Production Architecture — QUIXAI SaaS

**Status**: READY FOR IMPLEMENTATION
**Date**: 2026-03-14
**Scale**: 10-100 users initial, OVH VPS

## Decisions actees

- 1 instance Hexis, multi-chatbot routing (Seduction, Closing, Acquisition)
- Per-subscriber memory (`metadata->>'subscriber_id'`) + shared training knowledge (subscriber_id IS NULL)
- Claude Max 174 EUR/mois (3K-10K calls). Budget: 70% chat, 15% heartbeat, 10% ingestion, 5% maintenance
- No Ollama en prod — Claude pour tout (embeddings inclus)
- RabbitMQ actif (heartbeat agents X fois/jour)
- OVH dedie 8c/32GB/500GB SSD (~100 EUR/mois)
- Outils actifs: memory:recall, memory:create, rag:search, log:event. TOUT LE RESTE DESACTIVE.
- RGPD: donnees sur OVH, droit a l'effacement, audit trail

## Architecture systeme

```
Internet
    |
Nginx (SSL, rate limit, IP whitelist)
    |
FastAPI x3 (8000-8002, round-robin)
    |
    +-- PostgreSQL 16 (pgvector + AGE + pgsql-http)
    |     25 tables Hexis + users/subscriptions
    |
    +-- RabbitMQ 4 (outbox, inbox, heartbeat tasks, DLQ)
    |
    +-- Redis 7 (sessions, rate limits, embedding cache)
    |
    +-- Workers stateless:
    |     - Heartbeat worker (1-2 instances)
    |     - Maintenance worker (daily 2AM)
    |     - Channel worker (Telegram, WhatsApp, Discord)
    |
    +-- Claude Max API (174 EUR/mois)
          Haiku (classif), Sonnet (reponses), Opus (complexe)
```

## Data flows

### Formation upload -> chatbot

```
Video upload -> /var/storage/formations/{id}/
  -> faster-whisper (transcription FR)
  -> Hexis ingestion (fast/slow/hybrid, appraisal emotionnel)
  -> Claude embeddings
  -> memories table (type=training_material, formation_id, subscriber_id=NULL)
  -> Disponible pour RAG
```

Temps: ~30 min/heure video. Cout: ~1.50 EUR/formation.

### Subscriber question -> reponse

```
Message (web/Telegram/WhatsApp/Discord)
  -> Nginx -> FastAPI
  -> JWT validation + subscription check (Redis cache 5min)
  -> Rate limit (tier-based)
  -> Prompt injection check
  -> fast_recall(): vector search + neighborhood
     WHERE subscriber_id = :user_id OR (type=training_material AND subscriber_id IS NULL)
  -> System prompt + RAG context + historique (5 derniers msgs)
  -> Claude Sonnet (stream SSE)
  -> Sauvegarde conversation + tokens
  -> Reponse (latence < 5s)
```

Cout: ~0.21 EUR/message (7K tokens).

## Multi-tenant isolation

```sql
-- Memoire privee du subscriber
INSERT INTO memories (type, content, metadata)
VALUES ('episodic', '...', '{"subscriber_id": "uuid_a"}');

-- Requete filtree
SELECT * FROM memories
WHERE metadata->>'subscriber_id' = :user_id  -- prive
   OR (type = 'training_material' AND metadata->>'subscriber_id' IS NULL)  -- partage
ORDER BY embedding <-> query_embedding
LIMIT 10;
```

Defense en profondeur: filtrage applicatif (JWT) + RLS PostgreSQL + audit log.

## OVH sizing (100 users)

| Composant | Spec |
|-----------|------|
| CPU | 8 cores @ 2.5+ GHz |
| RAM | 32 GB (PG 8GB shared_buffers + cache 8GB + app 4.5GB) |
| SSD | 500 GB (100 formations x 5GB) |
| Bandwidth | 10 Mbps+ |
| Cout | ~100 EUR/mois |

## Migration zeprocess -> Hexis

| Source zeprocess | Destination Hexis |
|------------------|-------------------|
| rag_videos (video_embeddings) | memories (type=training_material) |
| scripts/transcribe.py | Hexis ingestion pipeline |
| scripts/embed_ingest.py | Hexis ingestion (slow/hybrid mode) |
| src/agents/ | System prompts + character cards |
| config/settings.py | Hexis config table |
| Docker infra | Hexis docker-compose (modifie) |

Ce qui est supprime: tout le pipeline zeprocess RAG (remplace par Hexis natif).

## Services Docker prod

```yaml
db:         PostgreSQL 16 + extensions     :5432 (interne)
rabbitmq:   RabbitMQ 4 management          :5672 (interne)
redis:      Redis 7 Alpine                 :6379 (interne)
api_1-3:    FastAPI Python 3.12            :8000-8002 (interne)
heartbeat:  Hexis worker                   depends: db, rabbitmq
maintenance: Hexis worker                  depends: db
channels:   Telegram/WhatsApp/Discord      depends: db, rabbitmq
nginx:      Reverse proxy SSL              :80, :443 (public)
```
