#!/usr/bin/env bash
set -u

available=$(free -m | awk '/Mem:/{print $7}')
log_file="/var/log/memory_guard.log"

if [ -z "${available}" ]; then
  exit 0
fi

if [ "${available}" -lt 100 ]; then
  pkill -f chromium 2>/dev/null || true
  pkill -f playwright 2>/dev/null || true
  echo "$(date): killed chromium/playwright, available=${available}MB" >> "${log_file}"
fi

if [ "${available}" -lt 50 ]; then
  systemctl restart guessr || true
  echo "$(date): restarted guessr, available=${available}MB" >> "${log_file}"
fi
