FROM alpine:latest
RUN apk add --no-cache dnsmasq netcat-openbsd

# Create the log file so tail doesn't complain before dnsmasq starts
RUN touch /var/log/dnsmasq.log

# Copy a wrapper script
COPY start.sh /start.sh
RUN chmod +x /start.sh

ENTRYPOINT ["/start.sh"]
