#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/opt/guessr}"
BACKEND_DIR="${APP_ROOT}/backend"
ENV_FILE="${BACKEND_DIR}/.env"
UNIT_SOURCE="${APP_ROOT}/deploy/systemd"

on_exit() {
  status=$?
  trap - EXIT
  if [[ "${status}" -ne 0 ]]; then
    echo "Crawl timer installation failed; attempting to keep the Web service online." >&2
    sudo systemctl start guessr || true
  fi
  exit "${status}"
}
trap on_exit EXIT

if [[ ! -x "${BACKEND_DIR}/venv/bin/python" ]]; then
  echo "Missing Python virtual environment: ${BACKEND_DIR}/venv/bin/python" >&2
  exit 1
fi
if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing environment file: ${ENV_FILE}" >&2
  exit 1
fi
if [[ ! -d "${UNIT_SOURCE}" ]]; then
  echo "Missing systemd unit source: ${UNIT_SOURCE}" >&2
  exit 1
fi

sudo systemctl disable --now \
  guessr-crawl-t0.timer \
  guessr-crawl-t1.timer \
  guessr-crawl-t2.timer 2>/dev/null || true
sudo systemctl stop \
  guessr-crawl@t0.service \
  guessr-crawl@t1.service \
  guessr-crawl@t2.service 2>/dev/null || true
sudo systemctl stop guessr

set_env() {
  local key="$1"
  local value="$2"
  if sudo grep -q "^${key}=" "${ENV_FILE}"; then
    sudo sed -i "s/^${key}=.*/${key}=${value}/" "${ENV_FILE}"
  else
    printf '%s=%s\n' "${key}" "${value}" | sudo tee -a "${ENV_FILE}" >/dev/null
  fi
}

# The Web process must never launch Playwright in production.
set_env CRAWL_ENABLED true
set_env CRAWL_SCHEDULER_MODE external
set_env CRAWL_CANARY_ENABLED true
set_env CRAWL_STOP_ON_RISK true
set_env CRAWL_CONCURRENCY 1
set_env CRAWL_CONCURRENCY_MAX 1

# A killed embedded scheduler cannot release its Redis lock. At this point both
# the Web service and all external workers are stopped, so these keys are stale.
(
  cd "${BACKEND_DIR}"
  sudo -u ubuntu ./venv/bin/python - <<'PY'
import asyncio

from app.models.redis_client import LOCK_CRAWL_KEY, close_redis, get_redis


async def main():
    client = await get_redis()
    if client is None:
        raise RuntimeError("Redis is unavailable; refusing to clear crawl locks")
    keys = [f"{LOCK_CRAWL_KEY}:crawl-{tier}" for tier in ("t0", "t1", "t2")]
    deleted = await client.delete(*keys)
    print(f"Cleared {deleted} stale crawl lock(s)")
    await close_redis()


asyncio.run(main())
PY
)

sudo install -m 0644 "${UNIT_SOURCE}/guessr-crawl@.service" /etc/systemd/system/
sudo install -m 0644 "${UNIT_SOURCE}/guessr-crawl-t0.timer" /etc/systemd/system/
sudo install -m 0644 "${UNIT_SOURCE}/guessr-crawl-t1.timer" /etc/systemd/system/
sudo install -m 0644 "${UNIT_SOURCE}/guessr-crawl-t2.timer" /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl start guessr

for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/ready >/dev/null; then
    break
  fi
  sleep 2
done
curl -fsS http://127.0.0.1:8000/ready

echo "Running one-keyword external worker canary..."
(
  cd "${BACKEND_DIR}"
  sudo -u ubuntu ./venv/bin/python -m app.crawl_runner \
    --tier t0 \
    --keyword-limit 1
)

sudo systemctl enable --now guessr-crawl-t0.timer

echo "External worker canary passed; installed independent T0 crawl timer."
echo "Enable slower tiers when required:"
echo "  sudo systemctl enable --now guessr-crawl-t1.timer guessr-crawl-t2.timer"
