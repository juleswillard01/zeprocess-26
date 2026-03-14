#!/bin/bash
set -euo pipefail

BACKUP_DIR="/var/backups/mega-quixai"
RETENTION_DAYS=30
LOG_FILE="/var/log/mega-quixai/backup.log"

mkdir -p "$BACKUP_DIR"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# Full backup
log "Starting PostgreSQL full backup..."
BACKUP_FILE="$BACKUP_DIR/mega-quixai-full-$(date +%Y%m%d-%H%M%S).sql.gz"

docker exec mega-quixai-postgres \
    pg_dump -U quixai_user mega_quixai \
    | gzip > "$BACKUP_FILE" || {
    log "ERROR: Backup failed"
    exit 1
}

log "Backup completed: $BACKUP_FILE"
log "Size: $(du -h "$BACKUP_FILE" | cut -f1)"

# Cleanup old backups
log "Cleaning up backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete

log "Backup process completed"
