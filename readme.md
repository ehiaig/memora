# Memora

Memora is a memory middleware server for AI applications. It gives agents and LLM-powered systems a persistent memory layer for storing facts, retrieving relevant context, inspecting stored records, and assembling prompt-ready memory payloads.

This repository contains the backend API service for Memora. It runs on FastAPI, stores data in PostgreSQL with `pgvector`, and uses OpenAI embeddings for semantic retrieval.

## What It Does

Memora provides a focused memory API for applications that need long-term context:

- store user, project, and task memory records
- retrieve relevant memories for a query
- rank results beyond raw vector similarity
- build prompt-ready context for model calls
- inspect and delete stored memories

Memora sits between your application and your model stack. Your application writes memory events into Memora and queries Memora before an LLM call to retrieve the most useful context.

## Current Scope

The current project includes:

- FastAPI API service
- API key authentication for memory endpoints
- PostgreSQL + `pgvector` persistence
- OpenAI embedding generation
- memory write, search, context, inspect, and delete endpoints
- database migrations with Alembic
- local development with `uv`
- Docker Compose for local infrastructure

This repository does not include a dashboard UI, SDKs, background workers, or a hosted control plane.

## Architecture

```text
Your App / Agent
       |
       v
    Memora API
       |
       v
Postgres + pgvector
```

Typical request flow:

1. Your application writes notable events, preferences, tasks, and facts into Memora.
2. Your application requests relevant context before an LLM call.
3. Memora retrieves, ranks, and formats the best matching memories.
4. Your application injects the returned context into the prompt sent to the model.

## API Overview

The API is exposed under `/api/v1`.

Endpoints:

- `GET /health`
- `POST /memory/write`
- `POST /memory/search`
- `POST /memory/context`
- `POST /memory/inspect`
- `DELETE /memory/{memory_id}`

All `/memory/*` endpoints require the `X-API-Key` header.

### Health Check

`GET /health` returns service status, service name, and version.

### Write Memory

`POST /memory/write`

Stores a memory record and returns the created object.

Example request:

```json
{
  "user_id": "user-123",
  "project_id": "project-alpha",
  "text": "User prefers FastAPI for backend work.",
  "source": "chat",
  "tags": ["preference", "backend"],
  "metadata": {
    "channel": "support"
  },
  "importance_score": 0.8,
  "ttl_days": 90
}
```

### Search Memory

`POST /memory/search`

Returns ranked memory results for a query.

Example request:

```json
{
  "user_id": "user-123",
  "project_id": "project-alpha",
  "query": "backend preferences",
  "limit": 5,
  "include_expired": false
}
```

Ranking combines:

- semantic similarity
- importance score
- freshness
- prior access patterns

### Build Context

`POST /memory/context`

Returns a prompt-ready context block plus the underlying ranked results.

Example request:

```json
{
  "user_id": "user-123",
  "project_id": "project-alpha",
  "query": "backend architecture preferences",
  "limit": 8,
  "max_chars": 2000,
  "include_expired": false
}
```

### Inspect Memories

`POST /memory/inspect`

Lists stored memories for a user or project so developers can review stored state and remove bad entries.

Example request:

```json
{
  "user_id": "user-123",
  "project_id": "project-alpha",
  "limit": 25,
  "include_expired": true
}
```

### Delete Memory

`DELETE /memory/{memory_id}`

Deletes a memory record for the specified `user_id`.

Example request body:

```json
{
  "user_id": "user-123"
}
```

## Stored Memory Shape

Stored records include these core fields:

- `id`
- `user_id`
- `project_id`
- `raw_text`
- `embedding`
- `metadata`
- `source`
- `tags`
- `importance_score`
- `access_count`
- `created_at`
- `last_accessed_at`
- `expires_at`

## Local Development

### Requirements

- Python 3.12+
- `uv`
- Docker
- an OpenAI API key

### Environment

Copy `.env.example` to `.env` and set the required values:

```env
DATABASE_URL=postgresql+asyncpg://memora:memora@localhost:5432/memora
OPENAI_API_KEY=your_openai_api_key
MEMORA_API_KEY=your_memora_api_key
EMBEDDING_MODEL_NAME=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
```

Use `localhost` when you run the API with `make dev`. Use `db` as the database host when the API runs inside Docker Compose.

### Install

```bash
cp .env.example .env
make install
```

### Start PostgreSQL

```bash
make docker-up
```

The API service is also included in `docker-compose.yml`. If you want to run the full stack in containers, use Docker Compose for both the API and PostgreSQL. If you want to run the API on your host with `make dev`, keep PostgreSQL running and use `localhost` in `DATABASE_URL`.

### Apply Migrations

```bash
make migrate
```

### Run the API

```bash
make dev
```

By default, the development server runs at [http://localhost:8000](http://localhost:8000).

### Run Tests

```bash
make test
```

### Run a Compile Check

```bash
make compile
```

## Example Usage

Write a memory:

```bash
curl -X POST http://localhost:8000/api/v1/memory/write \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_memora_api_key" \
  -d '{
    "user_id": "user-123",
    "project_id": "project-alpha",
    "text": "User prefers FastAPI for backend work.",
    "source": "chat",
    "tags": ["preference", "backend"],
    "metadata": {"channel": "support"}
  }'
```

Build prompt-ready context:

```bash
curl -X POST http://localhost:8000/api/v1/memory/context \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_memora_api_key" \
  -d '{
    "user_id": "user-123",
    "project_id": "project-alpha",
    "query": "backend architecture preferences",
    "limit": 5,
    "max_chars": 1200
  }'
```

## Version

Current application version: `0.1.0`
