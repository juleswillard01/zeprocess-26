-- Hexis Production Security Schema Migrations
--
-- These migrations add multi-user auth, audit logging, and compliance tables
-- to the existing Hexis database.
--
-- Apply in order. Idempotent (safe to re-run).

-- ============================================================================
-- 1. Users Table (Multi-User Support)
-- ============================================================================

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT,
    subscription_tier TEXT DEFAULT 'free',
    stripe_customer_id TEXT UNIQUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ,

    CONSTRAINT email_lowercase CHECK (email = LOWER(email)),
    CONSTRAINT valid_tier CHECK (subscription_tier IN ('free', 'pro', 'enterprise'))
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(LOWER(email)) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_users_stripe_id ON users(stripe_customer_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_users_deleted ON users(deleted_at) WHERE deleted_at IS NOT NULL;

-- ============================================================================
-- 2. Refresh Tokens (JWT Rotation)
-- ============================================================================

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    ip_address TEXT,
    user_agent TEXT
);

CREATE INDEX IF NOT EXISTS idx_refresh_token_user ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_token_expires ON refresh_tokens(expires_at) WHERE used_at IS NULL;

-- ============================================================================
-- 3. User Sessions (Long-lived Sessions)
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_token TEXT UNIQUE NOT NULL,
    ip_address TEXT NOT NULL,
    user_agent TEXT NOT NULL,
    last_activity_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ NOT NULL,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_session_user ON user_sessions(user_id) WHERE active = true;
CREATE INDEX IF NOT EXISTS idx_session_expires ON user_sessions(expires_at) WHERE active = true;

-- ============================================================================
-- 4. Authentication Audit Log
-- ============================================================================

CREATE TABLE IF NOT EXISTS auth_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    success BOOLEAN NOT NULL,
    failure_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_auth_audit_user ON auth_audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_audit_event ON auth_audit_log(event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_auth_audit_created ON auth_audit_log(created_at DESC);

-- ============================================================================
-- 5. User Consent (GDPR)
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_consent (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    marketing_emails BOOLEAN DEFAULT false,
    analytics BOOLEAN DEFAULT false,
    third_party_tools BOOLEAN DEFAULT false,
    consented_at TIMESTAMPTZ NOT NULL,
    consent_version TEXT NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_consent_user ON user_consent(user_id);

-- ============================================================================
-- 6. Data Deletion Requests (GDPR Right to Be Forgotten)
-- ============================================================================

CREATE TABLE IF NOT EXISTS data_deletion_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'pending',
    requested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deletion_scheduled_for TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    reason TEXT,
    contacted_support BOOLEAN DEFAULT false
);

CREATE INDEX IF NOT EXISTS idx_deletion_status ON data_deletion_requests(status);
CREATE INDEX IF NOT EXISTS idx_deletion_user ON data_deletion_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_deletion_scheduled ON data_deletion_requests(deletion_scheduled_for) WHERE status = 'pending';

-- ============================================================================
-- 7. Stripe Events (Webhook Processing)
-- ============================================================================

CREATE TABLE IF NOT EXISTS stripe_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id TEXT UNIQUE NOT NULL,
    event_type TEXT NOT NULL,
    data JSONB NOT NULL,
    error TEXT,
    processed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_stripe_event_id ON stripe_events(event_id);
CREATE INDEX IF NOT EXISTS idx_stripe_event_type ON stripe_events(event_type, processed_at DESC);

-- ============================================================================
-- 8. Payment Log (For Financial Records & Audit)
-- ============================================================================

CREATE TABLE IF NOT EXISTS payment_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_id TEXT UNIQUE,
    amount_cents INTEGER,
    status TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_payment_user ON payment_log(user_id);
CREATE INDEX IF NOT EXISTS idx_payment_created ON payment_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_payment_status ON payment_log(status);

-- ============================================================================
-- 9. Security Audit Log (Injection Attempts & Anomalies)
-- ============================================================================

CREATE TABLE IF NOT EXISTS security_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    session_id TEXT,
    event_type TEXT NOT NULL,
    details TEXT,
    severity TEXT DEFAULT 'low',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_security_event ON security_audit_log(event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_security_user ON security_audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_security_created ON security_audit_log(created_at DESC);

-- ============================================================================
-- 10. Configuration Table Validation
-- ============================================================================

-- Ensure config table exists with 'tools' entry for tool lockdown
CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Insert production tool config if not present
INSERT INTO config (key, value)
VALUES (
    'tools',
    '{"enabled": ["recall", "remember", "forget", "list_memories", "semantic_search", "recall_concept", "web_search", "fetch_web"], "disabled": ["run_command", "execute_shell", "python_repl", "javascript_repl", "read_file", "write_file", "glob_files", "grep", "screenshot", "click_element", "type_text", "scroll", "send_email", "send_slack", "send_discord", "send_telegram"], "disabled_categories": ["filesystem", "shell", "code", "browser", "calendar", "email", "messaging", "ingest", "external"], "context_overrides": {"chat": {"disabled": ["run_command", "execute_shell", "read_file", "write_file"], "allow_shell": false, "allow_file_write": false, "allow_file_read": false, "max_energy_per_tool": 5}}}'::jsonb
)
ON CONFLICT (key) DO NOTHING;

-- ============================================================================
-- 11. Migrate Existing tool_executions (Rename if Needed)
-- ============================================================================

-- Ensure tool_executions table includes user_id for audit trails
-- If it doesn't exist, it will be created by 23_tables_tool_audit.sql
-- If it does exist, add user_id if missing:

-- ALTER TABLE tool_executions ADD COLUMN IF NOT EXISTS user_id UUID;
-- ALTER TABLE tool_executions ADD COLUMN IF NOT EXISTS session_id TEXT;

CREATE INDEX IF NOT EXISTS idx_tool_exec_user ON tool_executions(user_id) WHERE user_id IS NOT NULL;

-- ============================================================================
-- 12. Grant Permissions (If Using Role-Based Access)
-- ============================================================================

-- Create application role (optional, for security isolation)
-- CREATE ROLE hexis_app WITH PASSWORD 'strong_password' LOGIN;
-- GRANT CONNECT ON DATABASE hexis_memory TO hexis_app;
-- GRANT USAGE ON SCHEMA public TO hexis_app;
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO hexis_app;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO hexis_app;

-- Create read-only role for backups
-- CREATE ROLE hexis_backup WITH PASSWORD 'strong_password' LOGIN;
-- GRANT CONNECT ON DATABASE hexis_memory TO hexis_backup;
-- GRANT USAGE ON SCHEMA public TO hexis_backup;
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO hexis_backup;

-- ============================================================================
-- 13. Data Retention Policies (For Cleanup Jobs)
-- ============================================================================

-- NOTE: These are informational. Actual cleanup happens in application.
--
-- Auth Audit Log: Keep 30 days
--   DELETE FROM auth_audit_log WHERE created_at < NOW() - INTERVAL '30 days'
--
-- Tool Executions: Keep 90 days
--   DELETE FROM tool_executions WHERE created_at < NOW() - INTERVAL '90 days'
--
-- Payment Log: Keep 365 days (PCI DSS requirement)
--   DELETE FROM payment_log WHERE created_at < NOW() - INTERVAL '365 days'
--
-- Security Audit Log: Keep 90 days (or 365 for investigation)
--   DELETE FROM security_audit_log WHERE created_at < NOW() - INTERVAL '90 days'

-- ============================================================================
-- 14. Validation Queries (Run to Verify Setup)
-- ============================================================================

-- Verify all tables exist:
-- SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;

-- Verify no duplicate emails:
-- SELECT email, COUNT(*) FROM users GROUP BY email HAVING COUNT(*) > 1;

-- Verify tool config is set:
-- SELECT value FROM config WHERE key = 'tools';

-- Verify indexes created:
-- SELECT indexname FROM pg_indexes WHERE schemaname = 'public' AND tablename IN ('users', 'auth_audit_log', 'tool_executions');

-- ============================================================================
-- END OF MIGRATIONS
-- ============================================================================

-- Apply this script with:
--   psql -h localhost -U hexis_user -d hexis_memory -f migrations.sql
--
-- Or from within psql:
--   \i migrations.sql
