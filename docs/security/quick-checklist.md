# Hexis Security Hardening - Quick Checklist

**Last Updated**: 2026-03-14
**Status**: CRITICAL LAUNCH BLOCKER

## Pre-Deployment (Execute in Order)

### Phase 1: Secrets & Infrastructure (Day 1-2)

- [ ] Generate JWT_SECRET (64+ random chars): `python -c "import secrets; print(secrets.token_urlsafe(64))"`
- [ ] Generate POSTGRES_PASSWORD (32+ random chars)
- [ ] Obtain STRIPE_API_KEY from Stripe dashboard (test, then live)
- [ ] Obtain STRIPE_WEBHOOK_SECRET from Stripe webhooks config
- [ ] Get TLS certificates (Let's Encrypt via certbot)
- [ ] Set up Redis instance for rate limiting (or use in-memory for <1000 users)
- [ ] Create Docker secrets: `docker secret create jwt_secret -`, `docker secret create postgres_password -`, etc.
- [ ] **NEVER COMMIT .env file to git** (add to .gitignore)

### Phase 2: Database Schema (Day 3)

- [ ] Run migration: Add `users` table (Section 5.1)
- [ ] Run migration: Add `refresh_tokens` table (Section 5.1)
- [ ] Run migration: Add `user_sessions` table (Section 5.1)
- [ ] Run migration: Add `auth_audit_log` table (Section 5.1)
- [ ] Run migration: Add `user_consent` table (Section 5.1)
- [ ] Run migration: Add `data_deletion_requests` table (Section 5.1)
- [ ] Run migration: Add `stripe_events` table (Section 6.2)
- [ ] Run migration: Add `payment_log` table (Section 6.2)
- [ ] Create indices on all audit tables
- [ ] Verify `tool_executions` table exists (should already be in 23_tables_tool_audit.sql)

### Phase 3: Code Changes (Day 4-7)

#### Auth System (Day 4)

- [ ] Implement `/api/auth/signup` endpoint (Section 3.3)
- [ ] Implement `/api/auth/login` endpoint (Section 3.3)
- [ ] Implement `/api/auth/refresh` endpoint (Section 3.3)
- [ ] Implement `/api/auth/logout` endpoint (Section 3.3)
- [ ] Add `_AuthMiddleware` to protect `/api/chat` and other endpoints
- [ ] Test JWT token generation and validation
- [ ] Test refresh token single-use enforcement
- [ ] Implement password hashing with bcrypt
- [ ] Add rate limiting (2s delay on failed auth to prevent brute force)

#### Tool Lockdown (Day 5)

- [ ] Create `create_paying_subscriber_registry()` function (Section 1.3)
- [ ] Update registry startup to use locked-down registry in PRODUCTION (Section 1.4)
- [ ] Update `core/tools/config.py` with production tool whitelist (Section 1.2)
- [ ] Test that only `recall`, `remember`, `web_search`, `fetch_web` tools are available
- [ ] Test that `run_command`, `read_file`, `python_repl` return DISABLED error
- [ ] Create `tests/security/test_tool_lockdown.py` (Section 1.5)

#### Prompt Injection Mitigation (Day 5)

- [ ] Implement hardened system prompt (Section 2.2)
- [ ] Implement `OutputFilter` class (Section 2.3)
- [ ] Implement memory result filtering (Section 2.3)
- [ ] Add 500-char max per memory result (Section 2.4)
- [ ] Create `core/security_audit.py` injection logging (Section 2.5)
- [ ] Test 5 jailbreak prompts → verify safe tool calls only

#### Rate Limiting (Day 6)

- [ ] Implement `RateLimitMiddleware` (Section 4.2)
- [ ] Create tier configuration (Section 4.1)
- [ ] Test FREE tier limits: 100/day, 5/min
- [ ] Test PRO tier limits: 10000/day, 100/min
- [ ] Configure Redis connection string (or in-memory for testing)
- [ ] Verify rate limit headers in responses

#### Stripe Webhooks (Day 6)

- [ ] Implement `/api/webhooks/stripe` endpoint (Section 6.1)
- [ ] Implement HMAC-SHA256 signature verification (Section 6.1)
- [ ] Implement timestamp tolerance check (±5 min)
- [ ] Implement idempotent event processing (check stripe_events table)
- [ ] Implement `_handle_subscription_updated()` (Section 6.1)
- [ ] Implement `_handle_subscription_deleted()` (Section 6.1)
- [ ] Test with Stripe webhook testing tool (`stripe trigger` CLI)

#### GDPR/Consent (Day 7)

- [ ] Implement `/api/user/export` endpoint (Section 5.3)
- [ ] Implement `/api/user/request-deletion` endpoint (Section 5.4)
- [ ] Collect consent at signup (marketing_emails, analytics, third_party_tools)
- [ ] Create daily deletion job `delete_expired_accounts()` (Section 5.4)
- [ ] Create daily audit log pruning job `prune_audit_logs()` (Section 10.3)
- [ ] Test data export produces valid JSON
- [ ] Test deletion request schedules deletion 30 days out

### Phase 4: Testing (Day 8-9)

#### Security Tests

- [ ] Prompt injection tests: 50 jailbreak attempts (Section 11)
- [ ] SQL injection tests: fuzz tool params with `' OR 1=1--`
- [ ] Unauthenticated access: call `/api/chat` without JWT, expect 401
- [ ] Token replay: use expired JWT, expect rejection
- [ ] Rate limit bypass: exceed per-minute limit, expect 429
- [ ] Stripe signature forgery: webhook with wrong HMAC, expect 403
- [ ] Tool access: try `run_command`, expect DISABLED error
- [ ] File access: try `read_file`, expect DISABLED error

#### Integration Tests

- [ ] Signup → login → chat → logout flow
- [ ] Login with wrong password → 2s delay + 401
- [ ] Refresh token → new access token
- [ ] Access /api/chat with valid JWT → allowed
- [ ] Pro tier → can use web_search; free tier → denied
- [ ] Tier rate limits enforced (5/min for free, 100/min for pro)
- [ ] Tool execution logged to audit table
- [ ] Auth events logged to auth_audit_log

#### Load Tests

- [ ] 100 concurrent users → response time <2s
- [ ] Rate limiter handles 10k requests/min distributed across 100 users
- [ ] JWT validation <5ms per request
- [ ] Memory + recall tools respond <500ms median

### Phase 5: Infrastructure & Deployment (Day 10)

#### Docker & Networking

- [ ] Update docker-compose.yml (Section 7.1)
  - [ ] Remove postgres port from external exposure (or bind to 127.0.0.1 only)
  - [ ] Set networks: api → public + private, db → private, workers → private
  - [ ] Verify RabbitMQ network is private only
- [ ] Verify no container exposes dangerous ports
- [ ] Test inter-container communication (api → db, api → rabbitmq)
- [ ] Test external API calls work (OpenAI, Anthropic)
- [ ] Verify containers cannot access host filesystem

#### Secrets & Environment

- [ ] Create Docker secrets (postgresql_password, jwt_secret, stripe_api_key)
- [ ] Remove hardcoded secrets from docker-compose.yml
- [ ] Update app code to read from `/run/secrets/` (Section 9.2)
- [ ] Verify no secrets in logs
- [ ] Verify no secrets in error responses

#### TLS/HTTPS

- [ ] Set up Nginx reverse proxy (Section 7.2)
- [ ] Configure SSL certificate (Let's Encrypt)
- [ ] Set up HSTS header (max-age=31536000)
- [ ] Set up CSP header (default-src 'self')
- [ ] Set up X-Frame-Options: DENY
- [ ] Test HTTPS works: `curl https://api.hexis.example.com/health`
- [ ] Verify only HTTPS allowed, HTTP redirects to HTTPS

#### Firewall

- [ ] Allow 443 (HTTPS) from anywhere
- [ ] Allow 22 (SSH) from admin IPs only
- [ ] Deny all other inbound
- [ ] Test: `nmap api.hexis.example.com` shows only 443 and 22 open

### Phase 6: Monitoring & Alerts (Day 11)

- [ ] Set up logging to centralized system (e.g., ELK, Datadog, CloudWatch)
- [ ] Log to stdout (Docker logs) for easy viewing
- [ ] Set up alerts:
  - [ ] Injection attempts >5/hour → Slack alert
  - [ ] Auth failures >20/min → Slack alert
  - [ ] Tool errors >1% → email
  - [ ] Stripe webhook failures → email
  - [ ] DB disk >80% → email
  - [ ] API latency p99 >5s → email
- [ ] Set up metrics dashboard (CPU, memory, request count, error rate)
- [ ] Configure log retention: 30 days for auth, 90 days for tools, 365 days for payments

### Phase 7: Go-Live (Day 12)

- [ ] Final security review with team
- [ ] Staging deployment with prod secrets
- [ ] Final load test in staging
- [ ] Pen-test report reviewed (if external pentesting done)
- [ ] Legal review of GDPR compliance complete
- [ ] Insurance/liability review complete
- [ ] Database backup strategy confirmed
- [ ] Incident response playbook reviewed
- [ ] Runbook for common issues documented
- [ ] **PRODUCTION DEPLOYMENT**

---

## Post-Deployment (Ongoing)

### Daily (First Week)

- [ ] Check security_audit_log for injection attempts (should be ~0)
- [ ] Review auth_audit_log for failed logins (should be <5)
- [ ] Monitor stripe_events for failed webhooks (should be 0)
- [ ] Check tool_executions for high error rate (should be <1%)

### Weekly

- [ ] Rotate JWT_SECRET (optional, or monthly)
- [ ] Review and prune old audit logs (30-90 days)
- [ ] Check dependency vulnerabilities: `pip audit`, `npm audit`
- [ ] Review logs for anomalies

### Monthly

- [ ] External penetration test (or quarterly)
- [ ] Security review meeting
- [ ] Rotate API secrets (Stripe, LLM providers)
- [ ] Backup restoration test
- [ ] Disaster recovery test

### Quarterly

- [ ] Full security audit (OWASP Top 10)
- [ ] Architecture review
- [ ] Compliance audit (GDPR, SOC 2 if applicable)
- [ ] Update hardening guide with learnings

---

## Critical Failure Points (If Any Below Missing = DO NOT LAUNCH)

- [ ] **Tool Lockdown**: Only memory + web tools enabled
  - Verify: `SELECT spec.name FROM tool_specs WHERE enabled = true` shows max 10 tools
- [ ] **Auth Middleware**: All /api/chat requests require valid JWT
  - Verify: Call without JWT → 401, call with invalid JWT → 401
- [ ] **Rate Limiting**: Free tier enforces 5 calls/min, Pro tier 100 calls/min
  - Verify: Exceed limit → 429 response
- [ ] **Stripe Webhooks**: Signature verification enabled
  - Verify: Webhook with wrong HMAC → 403
- [ ] **GDPR Deletion**: Auto-deletion 30 days after user requests
  - Verify: Query data_deletion_requests table for pending rows
- [ ] **Secrets**: No hardcoded keys in code or .env in git
  - Verify: `git log --all -S 'sk_' | grep -i key` returns nothing
- [ ] **Audit Logging**: Tool calls logged to tool_executions
  - Verify: Call recall() → entry in tool_executions table within 1s
- [ ] **TLS/HTTPS**: API only accessible via HTTPS
  - Verify: `curl http://api.hexis.example.com/health` → redirect or refused

---

## Rollback Plan (If Critical Issue Found Post-Launch)

1. **Immediate**: Set `ENVIRONMENT=development` (disables auth, enables all tools for debugging)
2. **Within 1 hour**: Identify root cause from logs
3. **Within 2 hours**: Deploy fix to staging, test thoroughly
4. **Within 4 hours**: Deploy fix to production
5. **Notify**: Email users if any data concern (GDPR notification within 72h if breach)
6. **Post-Mortem**: Review after incident resolved

---

## File Locations (Summary)

| File | Purpose |
|------|---------|
| `/home/jules/Documents/3-git/zeprocess/main/docs/security/hexis-prod-hardening.md` | Full hardening guide (THIS FILE'S COMPANION) |
| `core/tools/registry.py` | Tool registry + lockdown builder |
| `core/prompts.py` | System prompt definition (Section 2.2) |
| `core/output_filter.py` | Output sanitization (Section 2.3) |
| `core/config.py` | Secret loading from /run/secrets/ (Section 9) |
| `apps/hexis_api.py` | Auth endpoints, Stripe webhooks, rate limiting middleware |
| `db/00_tables.sql` (amended) | Add users, refresh_tokens, sessions, audit tables |
| `docker-compose.yml` | Network isolation + secret references (Section 7) |
| `ops/Dockerfile.api` | API server (ensure ENVIRONMENT env var) |
| `.gitignore` | Add `.env.local`, `.env`, `secrets/` |

---

## Sign-Off

**LAUNCH CANNOT PROCEED UNTIL:**

1. All Phase 1-5 checkboxes ✓
2. All critical failure points verified ✓
3. Security review completed by CTO ✓
4. Legal GDPR review completed ✓
5. This checklist signed off by Ops lead ✓

**Ready for Production**: [ ] YES [ ] NO (Reason: ___________________)

---

**Document Owner**: Hexis Security Lead
**Last Updated**: 2026-03-14
**Review Frequency**: Post-deployment (weekly), then quarterly
