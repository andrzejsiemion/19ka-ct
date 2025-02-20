FROM alpine:latest

WORKDIR /app

# Install required packages
RUN apk add --no-cache git openssh openrc busybox-extras

# Copy sync and push scripts
COPY sync.sh /app/sync.sh
COPY git-push.sh /app/git-push.sh
RUN chmod +x /app/sync.sh /app/git-push.sh

# Set default cron schedule
ENV CRON_SCHEDULE="*/10 * * * *"

# Ensure `sync.sh` starts on container boot
ENTRYPOINT ["/bin/sh", "-c"]
CMD ["/app/sync.sh"]