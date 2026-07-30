#!/usr/bin/env bash

set -euo pipefail

TEST_DATABASE_NAME="${POSTGRES_TEST_DB:-${POSTGRES_DB}_test}"

echo "Ensuring test database '${TEST_DATABASE_NAME}' exists..."

database_exists="$(
    psql \
        --username "${POSTGRES_USER}" \
        --dbname "${POSTGRES_DB}" \
        --tuples-only \
        --no-align \
        --command "SELECT 1 FROM pg_database WHERE datname = '${TEST_DATABASE_NAME}';"
)"

if [[ "${database_exists}" == "1" ]]; then
    echo "Test database '${TEST_DATABASE_NAME}' already exists."
    exit 0
fi

psql \
    --username "${POSTGRES_USER}" \
    --dbname "${POSTGRES_DB}" \
    --set ON_ERROR_STOP=1 \
    --command "CREATE DATABASE \"${TEST_DATABASE_NAME}\" OWNER \"${POSTGRES_USER}\";"

echo "Created test database '${TEST_DATABASE_NAME}'."