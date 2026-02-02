#!/bin/sh
# Start dnsmasq with robust file logging.

# 1. Setup Log File
# Create and ensure writable by everyone (dnsmasq drops privileges)
touch /var/log/dnsmasq.log
chmod 666 /var/log/dnsmasq.log

# 2. Start DNSMASQ (Foreground)
# The config file at /etc/dnsmasq.conf is mounted via docker-compose
# and already contains the necessary logging configuration.
exec dnsmasq -k --conf-file=/etc/dnsmasq.conf