FROM alpine:3.21

# postgresql17-client must match the server major (pgvector/pgvector:pg17)
RUN apk add --no-cache postgresql17-client age tzdata tar gzip

COPY backup.sh /usr/local/bin/backup.sh
RUN chmod +x /usr/local/bin/backup.sh

# Unhealthy when the last run is older than 26h — a backup that silently stopped
# is worse than none, because you believe you have one.
HEALTHCHECK --interval=1h --timeout=10s --start-period=2m --retries=1 \
  CMD [ -f /backups/.last-success ] && [ "$(( $(date +%s) - $(date -r /backups/.last-success +%s) ))" -lt 93600 ] || exit 1

ENTRYPOINT ["/usr/local/bin/backup.sh"]
