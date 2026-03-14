#!/bin/bash
set -euo pipefail

echo "Setting up UFW firewall..."

ufw --force enable

# Default policies
ufw default deny incoming
ufw default allow outgoing

# SSH (restrict to admin IP - change as needed)
ufw allow from 203.0.113.0/24 to any port 22 proto tcp || true

# HTTP/HTTPS
ufw allow in on eth0 to any port 80 proto tcp || true
ufw allow in on eth0 to any port 443 proto tcp || true

# Internal services (blocked from outside)
ufw deny in on eth0 to any port 5432 proto tcp || true  # PostgreSQL
ufw deny in on eth0 to any port 6379 proto tcp || true  # Redis
ufw deny in on eth0 to any port 3000 proto tcp || true  # API

# Allow loopback
ufw allow from 127.0.0.1 || true

# Allow internal Docker network
ufw allow from 172.20.0.0/16 || true

ufw status verbose
