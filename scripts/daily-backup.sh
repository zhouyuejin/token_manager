#!/usr/bin/env bash
set -euo pipefail

umask 077
chmod 700 /backups

while true; do
  now=$(date +%s)
  next=$((now / 86400 * 86400 + 18 * 3600))
  if (( next <= now )); then
    next=$((next + 86400))
  fi
  echo "next database backup: $(date -u -d "@$next" '+%F %T UTC')"
  sleep $((next - now))

  stamp=$(date -u +%F-%H%M%S)
  backup="/backups/${MYSQL_DATABASE}-${stamp}.sql.gz"
  if mysqldump --single-transaction --routines --triggers --no-tablespaces \
      -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u"$MYSQL_USER" "$MYSQL_DATABASE" \
      | gzip > "${backup}.tmp"; then
    mv "${backup}.tmp" "$backup"
    echo "database backup completed: $backup"
  else
    rm -f "${backup}.tmp"
    echo "database backup failed: $backup" >&2
  fi
done
