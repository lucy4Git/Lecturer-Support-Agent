#!/bin/sh
set -eu

if [ -z "${LSA_APP_DB_PASSWORD:-}" ] || [ -z "${LSA_AUTH_DB_PASSWORD:-}" ] || [ -z "${LSA_WORKER_DB_PASSWORD:-}" ]; then
  echo "LSA_APP_DB_PASSWORD, LSA_AUTH_DB_PASSWORD and LSA_WORKER_DB_PASSWORD are required" >&2
  exit 1
fi

psql --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=app_password="$LSA_APP_DB_PASSWORD" \
  --set=auth_password="$LSA_AUTH_DB_PASSWORD" \
  --set=worker_password="$LSA_WORKER_DB_PASSWORD" \
  --set=db_name="$POSTGRES_DB" <<'SQL'
SELECT format('CREATE ROLE lsa_app LOGIN PASSWORD %L', :'app_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lsa_app') \gexec
SELECT format('ALTER ROLE lsa_app LOGIN PASSWORD %L', :'app_password') \gexec
SELECT format('CREATE ROLE lsa_auth LOGIN PASSWORD %L', :'auth_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lsa_auth') \gexec
SELECT format('ALTER ROLE lsa_auth LOGIN PASSWORD %L', :'auth_password') \gexec
SELECT format('CREATE ROLE lsa_worker LOGIN PASSWORD %L', :'worker_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lsa_worker') \gexec
SELECT format('ALTER ROLE lsa_worker LOGIN PASSWORD %L', :'worker_password') \gexec
GRANT CONNECT ON DATABASE :"db_name" TO lsa_app, lsa_auth, lsa_worker;
ALTER ROLE lsa_app NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
ALTER ROLE lsa_auth NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
ALTER ROLE lsa_worker NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
SQL
