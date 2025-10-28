#!/usr/bin/env bash
set -euo pipefail

# Seed ClickHouse with demo data using the HTTP interface

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env.clickhouse"

if [[ -f "${ENV_FILE}" ]]; then
  echo "Loading environment from ${ENV_FILE}"
  # shellcheck disable=SC1090
  set -a && source "${ENV_FILE}" && set +a
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required to load seed data" >&2
  exit 1
fi

CLICKHOUSE_USER="${CLICKHOUSE_USER:-ai_db_advisor}"
CLICKHOUSE_PASSWORD="${CLICKHOUSE_PASSWORD:-ChangeMe123!}"
CLICKHOUSE_DB="${CLICKHOUSE_DB:-ai_db_advisor}"
CLICKHOUSE_HOST="${CLICKHOUSE_HOST:-localhost}"
CLICKHOUSE_HTTP_PORT="${CLICKHOUSE_HTTP_PORT:-8123}"
CLICKHOUSE_CONTAINER="${CLICKHOUSE_CONTAINER:-clickhouse}"
CLICKHOUSE_ADMIN_USER="${CLICKHOUSE_ADMIN_USER:-default}"
CLICKHOUSE_ADMIN_PASSWORD="${CLICKHOUSE_ADMIN_PASSWORD:-}"

BASE_URL="http://${CLICKHOUSE_HOST}:${CLICKHOUSE_HTTP_PORT}"
AUTH_ARGS=(-u "${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}")

echo "Checking ClickHouse availability at ${BASE_URL}..."
if ! curl -sfS "${AUTH_ARGS[@]}" "${BASE_URL}/ping" >/dev/null; then
  echo "ClickHouse is not reachable. Start docker-compose.clickhouse.yml first." >&2
  exit 1
fi

RENDERED_SCHEMA="$(mktemp)"
trap 'rm -f "${RENDERED_SCHEMA}"' EXIT
sed "s/{{CLICKHOUSE_DB}}/${CLICKHOUSE_DB}/g" "${SCRIPT_DIR}/schema.sql" > "${RENDERED_SCHEMA}"

echo "Applying schema for database '${CLICKHOUSE_DB}'..."

if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' | grep -qx "${CLICKHOUSE_CONTAINER}"; then
  docker exec -i "${CLICKHOUSE_CONTAINER}" \
    clickhouse-client \
    --user "${CLICKHOUSE_USER}" \
    --password "${CLICKHOUSE_PASSWORD}" \
    --multiquery < "${RENDERED_SCHEMA}"
else
  echo "Docker container '${CLICKHOUSE_CONTAINER}' not found. Falling back to HTTP apply."
  curl -sfS "${AUTH_ARGS[@]}" \
    --data-binary @"${RENDERED_SCHEMA}" \
    "${BASE_URL}/?allow_multiquery=1" >/dev/null
fi

if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' | grep -qx "${CLICKHOUSE_CONTAINER}"; then
  echo "Ensuring read-only toolbox user exists..."
  client_args=(clickhouse-client)
  if [[ "${CLICKHOUSE_ADMIN_USER}" != "default" || -n "${CLICKHOUSE_ADMIN_PASSWORD}" ]]; then
    client_args+=(--user "${CLICKHOUSE_ADMIN_USER}")
  fi
  if [[ -n "${CLICKHOUSE_ADMIN_PASSWORD}" ]]; then
    client_args+=(--password "${CLICKHOUSE_ADMIN_PASSWORD}")
  fi
  docker exec -i "${CLICKHOUSE_CONTAINER}" \
    "${client_args[@]}" \
    --multiquery <<SQL
CREATE USER IF NOT EXISTS ${TOOLBOX_CLICKHOUSE_USER:-toolbox_reader} IDENTIFIED BY '${TOOLBOX_CLICKHOUSE_PASSWORD:-REDACTED}';
GRANT SELECT ON ${CLICKHOUSE_DB}.* TO ${TOOLBOX_CLICKHOUSE_USER:-toolbox_reader};
SQL
fi

count_rows() {
  local table="$1"
  local result
  if ! result="$(curl -sfS "${AUTH_ARGS[@]}" \
      -G "${BASE_URL}/" \
      --data-urlencode "query=SELECT count() FROM ${CLICKHOUSE_DB}.${table}" \
      --data-urlencode "default_format=TabSeparatedRaw" \
      2>/dev/null)"; then
    echo "0"
    return 0
  fi
  # shellcheck disable=SC2001
  echo "${result}" | sed 's/\r//g'
}

EVENT_COUNT="$(count_rows "events")"
if [[ "${EVENT_COUNT}" == "0" ]]; then
  echo "Loading events from seed.csv..."
  curl -sfS "${AUTH_ARGS[@]}" \
    --data-binary @"${SCRIPT_DIR}/seed.csv" \
    "${BASE_URL}/?query=INSERT%20INTO%20${CLICKHOUSE_DB}.events%20FORMAT%20CSVWithNames" >/dev/null
else
  echo "Events table already has ${EVENT_COUNT} rows — skipping CSV import."
fi

USERS_COUNT="$(count_rows "users")"
if [[ "${USERS_COUNT}" == "0" ]]; then
  echo "Seeding users table..."
  curl -sfS "${AUTH_ARGS[@]}" \
    --data-binary @- \
    "${BASE_URL}/?query=INSERT%20INTO%20${CLICKHOUSE_DB}.users%20FORMAT%20Values" <<SQL
(101,'alex.johnson@example.com','Alex Johnson','2023-08-11','San Francisco',4380.40,'2024-07-05 09:42:00'),
(103,'maria.lopez@example.com','Maria Lopez','2023-12-20','New York',2910.75,'2024-07-04 08:18:34'),
(104,'samir.ahmed@example.com','Samir Ahmed','2024-02-03','Chicago',742.90,'2024-07-02 07:43:21'),
(106,'lucy.chen@example.com','Lucy Chen','2024-03-17','Seattle',12895.10,'2024-07-05 11:02:55'),
(109,'darius.noble@example.com','Darius Noble','2024-05-01','Austin',310.00,'2024-07-05 15:12:47')
SQL
else
  echo "Users table already has ${USERS_COUNT} rows — skipping."
fi

ORDERS_COUNT="$(count_rows "orders")"
if [[ "${ORDERS_COUNT}" == "0" ]]; then
  echo "Seeding orders table..."
  curl -sfS "${AUTH_ARGS[@]}" \
    --data-binary @- \
    "${BASE_URL}/?query=INSERT%20INTO%20${CLICKHOUSE_DB}.orders%20FORMAT%20Values" <<SQL
(5001,101,95.00,'created','2024-07-01 10:15:00','2024-07-01 18:45:00'),
(5005,103,59.50,'refunded','2024-07-03 13:27:33','2024-07-04 09:18:07'),
(5007,104,149.99,'fulfilled','2024-07-02 08:02:45','2024-07-02 18:00:00'),
(5011,106,215.00,'shipped','2024-07-04 11:23:18','2024-07-05 07:01:55'),
(5018,109,32.00,'created','2024-07-05 15:10:02','1970-01-01 00:00:00')
SQL
else
  echo "Orders table already has ${ORDERS_COUNT} rows — skipping."
fi

echo "Verification query (event counts by type):"
curl -sfS "${AUTH_ARGS[@]}" \
  -G "${BASE_URL}/" \
  --data-urlencode "query=SELECT event_type, count() AS total FROM ${CLICKHOUSE_DB}.events GROUP BY event_type ORDER BY total DESC" \
  --data-urlencode "default_format=PrettyCompact"

echo
echo "Seed data load complete."
