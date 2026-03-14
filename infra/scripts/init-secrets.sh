#!/bin/bash
set -euo pipefail

SECRETS_DIR="/opt/mega-quixai/.secrets"
mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"

echo "Initializing secrets..."

# Generate PostgreSQL password
if [ ! -f "$SECRETS_DIR/pg_password.txt" ]; then
    echo "Generating PostgreSQL password..."
    openssl rand -base64 32 | tr -d '\n' > "$SECRETS_DIR/pg_password.txt"
    chmod 600 "$SECRETS_DIR/pg_password.txt"
    echo "✓ PostgreSQL password generated"
fi

# Prompt for Anthropic API key
if [ ! -f "$SECRETS_DIR/anthropic_key.txt" ]; then
    echo "Enter your Anthropic API key:"
    read -rs ANTHROPIC_KEY
    echo "$ANTHROPIC_KEY" > "$SECRETS_DIR/anthropic_key.txt"
    chmod 600 "$SECRETS_DIR/anthropic_key.txt"
    echo "✓ Anthropic API key saved"
fi

# Prompt for LangFuse secret
if [ ! -f "$SECRETS_DIR/langfuse_secret.txt" ]; then
    echo "Enter your LangFuse secret key:"
    read -rs LANGFUSE_SECRET
    echo "$LANGFUSE_SECRET" > "$SECRETS_DIR/langfuse_secret.txt"
    chmod 600 "$SECRETS_DIR/langfuse_secret.txt"
    echo "✓ LangFuse secret saved"
fi

echo ""
echo "Secrets initialized successfully!"
echo "⚠️  IMPORTANT: .secrets/ is in .gitignore and will never be committed"
