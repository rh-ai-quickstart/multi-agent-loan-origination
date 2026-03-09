#!/bin/bash
# This project was developed with assistance from AI tools.
# Creates additional databases and roles needed by services sharing the postgres container.
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Enable pgvector extension (required by KB and embedding features)
    CREATE EXTENSION IF NOT EXISTS vector;

    -- Create langfuse database for observability stack
    CREATE DATABASE langfuse;

    -- HMDA isolation: dual PostgreSQL roles
    CREATE ROLE lending_app WITH LOGIN PASSWORD 'lending_pass';
    CREATE ROLE compliance_app WITH LOGIN PASSWORD 'compliance_pass';
    GRANT CONNECT ON DATABASE "mortgage-ai" TO lending_app;
    GRANT CONNECT ON DATABASE "mortgage-ai" TO compliance_app;
EOSQL
