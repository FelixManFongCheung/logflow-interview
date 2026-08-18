# Codebase Learner Reference

Teacher-oriented map of **fastapi-langgraph-agent-production-ready-template**.  
Audience: someone who can read Python but is **not** an expert in FastAPI, LangGraph, or LangChain.

---

## 0. What this app is (30 seconds)

This project is a **backend API for an AI chatbot agent**.

- Clients talk to it over **HTTP** (like a website API).
- **FastAPI** is the web framework that receives those HTTP requests.
- **LangGraph** is the “brain workflow”: multi-step chat → maybe call tools → respond.
- **PostgreSQL** stores users, chat sessions, conversation checkpoints, and vector memory.
- Extra production pieces: JWT login, rate limits, metrics, tracing, Docker.

Think of it as:

```text
Phone app / curl  →  FastAPI door  →  Auth check  →  Chat route  →  LangGraph agent  →  LLM + tools + memory
                                                                              ↓
                                                                         PostgreSQL
```

---

## 1. Folder map (what lives where)

| Path | Plain English |
|------|----------------|
| `app/main.py` | App factory: creates the FastAPI app, wires middleware, mounts routes, startup/shutdown |
| `app/api/v1/` | HTTP endpoints (URLs you can call) |
| `app/schemas/` | Request/response **shapes** (validation for JSON) — not DB tables |
| `app/models/` | Database **tables** (SQLModel) |
| `app/services/` | Business logic talking to DB, LLM, memory |
| `app/core/` | Shared infrastructure: config, logging, auth helpers, middleware, LangGraph, prompts |
| `app/utils/` | Small helpers (JWT, message formatting, sanitization) |
| `alembic/` | Database migrations (versioned schema changes) |
| `evals/` | Offline quality checks of LLM answers using Langfuse traces |
| `docs/` | Human documentation |
| `docker-compose.yml` | How to run API + DB (+ monitoring) in containers |

---

## 2. FastAPI basics you need for this repo

### 2.1 App

```python
app = FastAPI(..., lifespan=lifespan)
```

**What:** The central application object. Every route hangs off this.

**Syntax:** `FastAPI(...)` constructs the app. `lifespan=` points to an async context manager that runs **once at startup** and **once at shutdown** (warm up graph, close pools).

### 2.2 Router and URL assembly

```python
# api.py
api_router.include_router(chatbot_router, prefix="/chatbot")

# main.py
app.include_router(api_router, prefix=settings.API_V1_STR)  # usually "/api/v1"
```

**Logic:** Prefixes stack.

- Route declares `@router.post("/chat")`
- Included with `/chatbot`
- Mounted with `/api/v1`
- Final URL: **`POST /api/v1/chatbot/chat`**

### 2.3 Decorators

```python
@router.post("/chat", response_model=ChatResponse)
@limiter.limit("...")
async def chat(...):
```

**What:** A decorator is a function that wraps another function.

**Logic here:**

1. `@limiter.limit` — check rate limit first
2. `@router.post` — register as POST handler; `response_model=` tells FastAPI how to serialize/validate the return JSON

### 2.4 Pydantic schemas (request body)

```python
async def chat(..., chat_request: ChatRequest, ...):
```

**Logic:** Because the parameter is typed as `ChatRequest` (a Pydantic model) and is not a special type like `Request`, FastAPI treats it as **JSON body**. Invalid JSON → **422** before your function runs.

### 2.5 Depends (dependency injection)

```python
session: Session = Depends(get_current_session)
```

**Plain English:** “Before calling `chat`, run `get_current_session`. Pass its return value in as `session`.”

**Logic:** That function reads the `Authorization: Bearer …` header, verifies JWT, loads the session from the DB. Fail → HTTP 401/404; success → handler runs with a real `Session` object.

### 2.6 Middleware

Middleware wraps **every** request (onion layers): CORS, request ID, metrics, logging context.

Order matters. In `main.py`, correlation ID is added last among custom middleware so it sits outermost and every layer sees `request_id`.

### 2.7 `async` / `await`

Handlers are `async def` so the server can handle many waiting LLM/DB calls without one slow request freezing others. `await something()` means “wait for that I/O.”

---

## 3. Startup path (`app/main.py`)

**Role:** Build and configure the running API.

**Logic at startup (`lifespan`):**

1. Log environment / version
2. Initialize cache (Valkey/Redis if configured, else in-memory)
3. Pre-warm LangGraph agent (`agent.create_graph()`)
4. Pre-warm mem0 memory service
5. On shutdown: close cache and DB connection pool

**Also wires:**

| Piece | Why |
|-------|-----|
| Prometheus metrics | Count requests, timings |
| `LoggingContextMiddleware` | Put session_id into logs when Bearer token present |
| `MetricsMiddleware` | Record HTTP metrics |
| `ProfilingMiddleware` | Only if `DEBUG` — profile slow requests |
| `CorrelationIdMiddleware` | Unique `request_id` per request |
| Rate limit exception handler | Friendly response when limited |
| Validation exception handler | Pretty 422 errors |
| CORS | Allow browser frontends |
| `api_router` | All `/api/v1/...` routes |

**Root routes on `app` itself:**

- `GET /` — basic API info
- `GET /health` — health + DB ping (503 if DB down)

---

## 4. API layer (`app/api/v1/`)

### 4.1 `api.py` — the hub

Includes:

- `auth_router` → `/api/v1/auth/...`
- `chatbot_router` → `/api/v1/chatbot/...`
- `GET /api/v1/health` — simple healthy JSON

### 4.2 `auth.py` — identity and sessions

| Endpoint | Purpose |
|----------|---------|
| `POST /register` | Create user, return user JWT |
| `POST /login` | Form email/password → JWT |
| `POST /session` | Needs **user** JWT → create chat session + **session** JWT |
| `GET /sessions` | List user’s sessions |
| `PATCH/DELETE /session/{id}` | Rename / delete session |

**Critical teaching point — two kinds of tokens:**

1. **User token** — JWT `sub` = user id (string of int). Used for register/login/session management.
2. **Session token** — JWT `sub` = session UUID. Used for **chat**. Chat will fail if you send the user token.

**Key functions:**

- `get_current_user` — `Depends` helper: Bearer → verify → load `User`
- `get_current_session` — Bearer → verify → load `Session`

**Syntax note:** `credentials: HTTPAuthorizationCredentials = Depends(security)` where `security = HTTPBearer()` means “require Authorization header.”

### 4.3 `chatbot.py` — talking to the agent

| Endpoint | Purpose |
|----------|---------|
| `POST /chat` | Full reply as JSON |
| `POST /chat/stream` | Server-Sent Events (SSE) stream of chunks |
| `GET /messages` | History for this session |
| `DELETE /messages` | Clear history |

**`chat` logic:**

1. Rate limit
2. Validate `ChatRequest` body (`messages: [{role, content}, ...]`)
3. `Depends(get_current_session)` → authenticated session
4. Optional session auto-naming
5. `await agent.get_response(...)` → LangGraph
6. Return `ChatResponse(messages=...)`

**`chat/stream` logic:** Same auth, but yields `data: {...}\n\n` events until `done: true`.

Module-level: `agent = LangGraphAgent()` — one agent instance shared by routes (graph created at startup).

---

## 5. Schemas vs models (easy to confuse)

### 5.1 Schemas — `app/schemas/` (HTTP)

| File | Contents |
|------|----------|
| `base.py` | `BaseResponse` with auto `request_id` from middleware |
| `auth.py` | `UserCreate`, `Token`, `TokenResponse`, `SessionResponse`, … |
| `chat.py` | `Message`, `ChatRequest`, `ChatResponse`, `StreamResponse` |
| `graph.py` | `GraphState` for LangGraph (messages + long_term_memory) |

**Syntax:** Classes inherit `BaseModel` (Pydantic). Fields use type hints + `Field(...)`. Validators (`@field_validator`) reject bad passwords, script tags in chat, etc.

### 5.2 Models — `app/models/` (database)

| File | Table meaning |
|------|----------------|
| `base.py` | Shared `BaseModel` with `created_at` (no `table=True` alone) |
| `user.py` | `User` — email, hashed password, username |
| `session.py` | `Session` — chat session owned by a user |
| `thread.py` | `Thread` — older/simple thread table shape |
| `database.py` | Re-exports (`__all__`) for convenience |

**Syntax:**

```python
class User(BaseModel, table=True):
```

- Inherits SQLModel features (Pydantic + SQLAlchemy)
- `table=True` = create a real DB table
- `Field(primary_key=True)`, `Relationship(...)` = columns and links between tables

**User helpers:** `hash_password` / `verify_password` use bcrypt.

---

## 6. Services — `app/services/`

### 6.1 `database.py` — `DatabaseService`

**Role:** CRUD for users and sessions via SQLModel + SQLAlchemy engine.

**Logic:** Creates a connection pool to Postgres. Methods like `create_user`, `get_session`, `get_user_by_email` open a short-lived `Session(engine)`, run SQL, commit.

Used by auth routes (not by LangGraph message history — that lives in the checkpointer).

### 6.2 `llm/` — talking to models

- **`registry.py`** — list of available chat models (OpenAI-compatible)
- **`service.py`** — `LLMService`: retries with **tenacity**, circular fallback across models, `bind_tools` for agent tools

**Logic:** Agent calls `llm_service.call(messages)`. On failure, retry / switch model. Tool-bound LLM is used for the main agent path.

### 6.3 `memory.py` — long-term memory

**Role:** mem0 `AsyncMemory` on **pgvector**.

- `search(user_id, query)` — find relevant past facts (cache first)
- `add(user_id, messages)` — store new memories
- Skips if `user_id` is None

Injected into the system prompt as `{long_term_memory}`.

### 6.4 `session_naming.py`

Optionally names a session from the first user messages (LLM structured title) so the UI isn’t stuck with a blank name.

---

## 7. Core infrastructure — `app/core/`

### 7.1 `config.py`

Loads `.env.*` into a settings object (`API_V1_STR`, DB creds, JWT secret, rate limits, Langfuse flags, …). **Never hardcode secrets** — they come from env.

### 7.2 `logging.py`

**structlog**: event names like `"chat_request_received"`, variables as kwargs (not f-strings). Context binding adds `user_id` / `session_id` to later logs.

### 7.3 `limiter.py`

**slowapi** rate limiter keyed by client IP. Optional Valkey/Redis backend for multi-instance.

### 7.4 `middleware.py`

- **MetricsMiddleware** — count/duration of HTTP calls
- **LoggingContextMiddleware** — decode JWT early for log context (auth still enforced by `Depends`)
- **ProfilingMiddleware** — slow-request profiles when DEBUG

### 7.5 `metrics.py` / `observability.py`

Prometheus counters/histograms; Langfuse callback for LLM tracing.

### 7.6 `cache.py`

Cache service for memory search results (Redis/Valkey or in-memory TTL).

### 7.7 `prompts/`

- `system.md` — agent system prompt template
- `session_title.md` — title generation prompt
- `__init__.py` — loads templates once; `load_system_prompt(username=..., long_term_memory=...)`

---

## 8. LangChain vs LangGraph (do not mix them)

| Library | Job in this repo | Main files |
|---------|------------------|------------|
| **LangChain** | LLM client, message types, `@tool`, `bind_tools` | `app/services/llm/`, `app/core/langgraph/tools/` |
| **LangGraph** | Flowchart: nodes, state, `Command`, checkpointer, interrupt | `app/core/langgraph/graph.py`, `app/schemas/graph.py` |

LangGraph **calls** LangChain objects. FastAPI **calls** the compiled graph. Three layers, not one.

## 9. LangGraph agent — `app/core/langgraph/`

### 9.1 Mental model

A **graph** is a flowchart of steps (nodes). State is `GraphState`:

```python
class GraphState(BaseModel):
    messages: Annotated[list, add_messages] = ...
    long_term_memory: str = ...
```

`add_messages` means new messages **append** instead of replacing the whole list.

### 9.2 Nodes

```text
START → chat → (if tool_calls) → tool_call → chat → ... → END
```

| Node | Logic |
|------|--------|
| `_chat` | Build system prompt + history → call LLM → if tool calls, go to `tool_call`, else `END` |
| `_tool_call` | Run requested tools (concurrent if many) → append `ToolMessage`s → back to `chat` |

Routing uses LangGraph `Command(update=..., goto=...)`.

### 9.3 Checkpointer

`AsyncPostgresSaver` saves graph state per `thread_id` (= session id). That gives **multi-turn memory** of the conversation even after the HTTP request ends.

### 9.4 Tools — `tools/`

| Tool | Job |
|------|-----|
| `duckduckgo_search` | Web search |
| `ask_human` | Pause graph (`interrupt`) and ask the user before risky actions |

Tools are bound onto the LLM so the model can request them by name.

### 9.5 Public methods on `LangGraphAgent`

| Method | Job |
|--------|-----|
| `create_graph` / `_get_graph` | Build/compile once |
| `get_response` | Non-streaming invoke (also searches memory, may resume after interrupt) |
| `get_stream_response` | Async generator of text chunks |
| `get_chat_history` / `clear_chat_history` | Read/clear checkpointer state |

---

## 10. Utils — `app/utils/`

| Module | Job |
|--------|-----|
| `auth.py` | `create_access_token`, `verify_token` (python-jose JWT) |
| `sanitization.py` | Clean email/strings, password strength |
| `graph.py` | `dump_messages`, trim history by tokens, extract text from structured LLM content, prepare messages with system prompt |

---

## 11. Alembic — database migrations

| Piece | Job |
|-------|-----|
| `alembic.ini` | Config |
| `alembic/env.py` | Connects models → autogenerate |
| `alembic/versions/*.py` | Upgrade/downgrade scripts |

**Plain English:** When you change SQLModel tables, Alembic creates a script so every environment’s Postgres schema stays in sync. Run via `make migrate`.

---

## 12. Evals — `evals/`

**Role:** After chats are traced in Langfuse, score them (helpfulness, hallucination, toxicity, …) with an eval LLM and write a report.

Not part of the live request path — quality assurance offline/CI-ish.

---

## 13. End-to-end happy path (memorize this)

```text
1. POST /api/v1/auth/register
   → User row in Postgres + USER_JWT

2. POST /api/v1/auth/session
   Authorization: Bearer USER_JWT
   → Session row + SESSION_JWT

3. POST /api/v1/chatbot/chat
   Authorization: Bearer SESSION_JWT
   Body: { "messages": [{ "role": "user", "content": "Hi" }] }

   Middleware → rate limit → validate body → get_current_session
   → LangGraphAgent.get_response
      → memory search (optional)
      → chat node → LLM (maybe tools) → final messages
   → ChatResponse JSON
```

---

## 14. Syntax cheat sheet

| You see | It means |
|---------|----------|
| `@router.get/post/...` | Register HTTP route |
| `response_model=X` | Validate/serialize return as schema X |
| `Depends(fn)` | Run `fn` first; inject result |
| `Request` param | Needed for rate limiter; raw HTTP request |
| `BaseModel` | Pydantic data shape |
| `SQLModel, table=True` | DB table class |
| `Field(...)` | Column/field options |
| `async def` / `await` | Non-blocking I/O |
| `__all__ = [...]` | Public exports for `import *` |
| `@retry(...)` (tenacity) | Auto-retry failed calls |
| `Command(goto=...)` | LangGraph: update state + jump to next node |
| `StreamingResponse` | Stream bytes/events to client |

---

## 15. Suggested learning order

1. `app/api/v1/api.py` + `auth.py` register/login (simplest HTTP)
2. `schemas/auth.py` + `models/user.py` (shape vs table)
3. `utils/auth.py` (JWT)
4. `chatbot.py` chat endpoint
5. `core/langgraph/graph.py` (`_chat` / `_tool_call`)
6. `services/memory.py` + `services/llm/service.py`
7. `main.py` middleware + lifespan
8. `alembic/` + `evals/` when you care about ops/quality

---

## 16. One teaching paragraph for interviews / yourself

> “This is a production FastAPI service. Routes live under `/api/v1`. Auth issues JWTs; chat requires a session JWT. Pydantic schemas validate HTTP JSON; SQLModel models map to Postgres. The chat route delegates to a LangGraph agent with a chat node and a tool-call node, Postgres checkpointing for conversation state, mem0/pgvector for long-term memory, and Langfuse/Prometheus for observability.”
