# Memora

Memora is a memory middleware server for AI applications.

It gives agents and LLM-powered apps a persistent memory layer they can write to, retrieve from, inspect, and turn into prompt-ready context.

Think:

- a drop-in memory server for AI apps
- an opinionated context engine on top of Postgres + pgvector
- infrastructure for long-term memory, not a chatbot and not a generic RAG wrapper

## What Memora Is

Memora is a service that helps AI applications:

- store memories over time
- retrieve the most relevant memories for a task
- rank memories using more than raw vector similarity
- build LLM-ready context payloads
- inspect what was remembered and why it was returned

The product boundary is important:

- Memora is not an end-user chat interface
- Memora is not a model gateway
- Memora is not a replacement for your app database
- Memora is not just a vector index

Memora sits between your application and your model stack. Your app sends memory events into Memora, and asks Memora for the best context to inject into prompts.

## Positioning

The shortest accurate description is:

> Memora is a drop-in memory server for AI apps and agents.

Useful shorthand:

> Postgres/Redis for AI memory.

That shorthand is directionally helpful, but incomplete. Memora is not trying to be only a low-level storage primitive. It is an opinionated memory layer with retrieval, ranking, context assembly, and inspection.

## What Memora Is Not

Memora is explicitly not:

- a chatbot product
- a browser extension
- a model comparison tool
- a generic "RAG starter kit"
- a full observability suite for all LLM traffic
- a replacement for app-specific business logic

If you need cross-model answer comparison, agent orchestration, or conversational UX, those belong outside Memora.

## Core Use Cases

- Persist user preferences, tasks, constraints, and long-term facts
- Rehydrate relevant context for an agent or LLM call
- Keep memory scoped by user, project, or workspace
- Inspect retrieval quality when prompts go wrong
- Control memory lifecycle with expiration and metadata

## v1 Product Contract

Memora v1 should do a small set of things well:

1. Accept memories from an application
2. Retrieve and rank relevant memories for a query
3. Build prompt-ready context from retrieved memories
4. Let developers inspect and delete stored memories
5. Expose enough metadata to debug memory quality

If Memora cannot reliably improve context injection and make retrieval inspectable, it is not yet succeeding at its core job.

## Current Scope

The current repository is focused on the backend memory gateway:

- FastAPI service
- API-key protected memory APIs
- PostgreSQL + pgvector storage
- OpenAI embeddings
- semantic retrieval
- ranked context assembly
- inspection and deletion APIs

Not in scope yet:

- dashboard UI
- SDKs
- async summarization workers
- hybrid keyword/vector retrieval
- advanced policy engines
- hosted multi-tenant control plane

## Architecture

Memora is designed as infrastructure middleware.

Applications connect to a running Memora server:

```text
Your App / Agent
       |
       v
    Memora API
       |
       v
Postgres + pgvector
```

Typical flow:

1. Your app writes notable events, preferences, facts, and tasks into Memora
2. Your app asks Memora for context before an LLM call
3. Memora retrieves, ranks, and formats the best memories
4. Your app injects that context into the prompt it sends to the model

## Migrations

Memora uses Alembic for schema management. The application no longer creates tables automatically on startup.

Use:

```bash
make migrate
```

This keeps the running schema explicit and versioned.

## API Surface

The backend is exposed under `/api/v1`.

Core endpoints:

- `POST /memory/write`
- `POST /memory/search`
- `POST /memory/context`
- `POST /memory/inspect`
- `DELETE /memory/{memory_id}`
- `GET /health`

All `/memory/*` endpoints require an `X-API-Key` header.

### Memory Write

Store a memory for later retrieval.

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
  "ttl_days": 90
}
```

### Memory Search

Retrieve ranked memories for a query.

Search ranking should consider:

- semantic similarity
- memory importance
- freshness
- prior accesses

### Memory Context

Build LLM-ready context from the best retrieved memories within a budget.

The purpose of this endpoint is not to return raw nearest neighbors only. It should return a context payload your app can place into prompts directly.

### Memory Inspect

List stored memories for a user or project so developers can inspect quality and delete polluted or stale entries.

## Data Model

Each memory should carry:

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

## Ranking Philosophy

Memora should rank memories better than a plain vector store.

Raw similarity alone is not enough. Memora should bias toward memories that are:

- semantically relevant
- still fresh
- likely to matter long-term
- repeatedly useful

That is the beginning of Memora's product value.

## Roadmap

### Credible v1

- FastAPI backend
- Postgres + pgvector
- memory write/search/context/inspect/delete
- OpenAI embeddings
- ranked retrieval
- Docker Compose

### Next

- inspector dashboard
- SDKs for Python and TypeScript
- summarization workers
- richer memory policies
- provider abstraction for summarization and reranking
- hybrid retrieval

### Later

- team/shared memory
- retrieval analytics
- observability dashboards
- hosted cloud version

## Open Source Goal

This project is intended to be open-source infrastructure for developers building AI-native products.

The promise to contributors and users should stay clear:

- Memora helps applications manage long-term memory
- Memora improves retrieval quality and context assembly
- Memora gives developers visibility into remembered state
- Memora does not try to become every AI tool at once

## Local Development

Requirements:

- `uv`
- Docker
- an OpenAI API key

Environment:

```env
DATABASE_URL=postgresql+asyncpg://memora:memora@db:5432/memora
OPENAI_API_KEY=your_key
MEMORA_API_KEY=your_memora_api_key
EMBEDDING_MODEL_NAME=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
```

Install dependencies:

```bash
cp .env.example .env
make install
```

Apply migrations:

```bash
make migrate
```

Run locally:

```bash
make dev
```

Run tests:

```bash
make test
```

Run a quick compile check:

```bash
make compile
```

Refresh the lockfile:

```bash
make lock
```

Run with Docker:

```bash
make docker-up
```

API docs:

- [http://localhost:8000/docs](http://localhost:8000/docs)

## Near-Term Priorities

If you are contributing to Memora, prioritize these in order:

1. retrieval quality
2. context assembly quality
3. inspectability
4. lifecycle controls
5. summarization and policy automation

Those are the foundations of the product. Everything else is secondary until those are solid.
