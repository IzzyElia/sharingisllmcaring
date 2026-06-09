# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repository.

## Overview

`sharing-is-llm-caring` is a small, self-hosted multi-user chat server that puts a
locally-run LLM (served by [Ollama](https://ollama.com)) behind a simple
authenticated HTTP API. Users log in, create chat sessions, and stream model
responses. It is an early work-in-progress: there is a working-ish HTTP layer,
auth primitives, and file-based persistence, but the pieces are not yet fully
wired together (see `ISSUES.md`).

- **Language:** Python 3.12 (uses PEP 701 nested f-string quoting and modern
  generics like `list[str]`).
- **HTTP layer:** standard-library `http.server.ThreadingHTTPServer` — no web
  framework.
- **LLM backend:** Ollama via the `ollama` Python client (async streaming).
- **Persistence:** JSON files on disk (one file per object), no database.
- **Auth:** bcrypt password hashes + HMAC-SHA256 username hashing + in-memory
  bearer access tokens.

## Running

```bash
# 1. Install deps (a .venv already exists in the repo)
pip install -r requirements.txt          # ollama, bcrypt, python-dotenv

# 2. Make sure Ollama is running and the model is pulled
ollama pull cogito:3b

# 3. Configure environment (see "Configuration" below) in a .env file

# 4. Start the server
python -c "from server.server import start_server; start_server"   # serves on localhost:8080

# main.py is currently a scratch/test harness, NOT the server entry point.
python main.py
```

> Note: there is currently no single "run the server" entry point script.
> `server.start_server()` is the function that boots the HTTP server.

## Configuration (environment variables, via `.env`)

| Variable          | Used by            | Required | Default                                  |
|-------------------|--------------------|----------|------------------------------------------|
| `MODEL`           | `server/api.py`    | **Yes** — raises on startup if unset | none                  |
| `HASHING_SECRET`  | `server/auth.py`   | Strongly recommended | falls back to a **hardcoded** secret in source (insecure) |
| `DATA_DIR`        | `server/storage.py`| No       | `data`                                   |

The checked-in `.env` only sets `MODEL=cogito:3b`. `.env` is untracked (not in git).

## Project Structure

```
.
├── main.py              # Scratch/test harness (creates a user, round-trips through storage)
├── requirements.txt     # ollama, bcrypt, python-dotenv
├── .env                 # Local config (untracked); currently only MODEL
└── server/              # The application package
    ├── __init__.py      # Empty (marks the package)
    ├── server.py        # Boots ThreadingHTTPServer, auto-registers API endpoints
    ├── handler.py       # BaseHTTPRequestHandler subclass + APIFunction ABC + endpoint registry
    ├── api.py           # Concrete API endpoints (login, chat CRUD, LLM streaming)
    ├── auth.py          # User model, password/username hashing, access tokens, user store
    ├── user_data.py     # Serializable UserData + Chat models
    ├── storage.py       # Serializable/Savable ABCs, filename sanitizer, JSON file persistence
    └── uids.py          # Cryptographically-random unique ID generation
```

## Architecture

### Request lifecycle
1. `server.start_server()` enumerates `APIFunction.__subclasses__()` and registers
   each declared endpoint path into the module-level `handler.endpoints` dict.
2. `ThreadingHTTPServer` dispatches every request to `Handler.do(method)` (via
   `do_GET`/`do_POST`/`do_DELETE`/`do_PUT`).
3. `Handler.do` looks up the path, validates the `Access-Token` header through
   `auth.get_access_token_user`, reads the (size-capped) request body, and calls
   the matched `APIFunction.execute(handler, body, method, user)`.

### Key abstractions
- **`APIFunction` (handler.py):** abstract endpoint. Subclasses declare
  `endpoints()`, `auth_types_allowed()`, `on_auth_failure()` (one of
  `AlwaysAllowed` / `RedirectToLogin` / `Unauthorized`), and `execute()`.
  Adding an endpoint = subclass `APIFunction` in `api.py`; registration is
  automatic via subclass discovery.
- **`Serializable` / `Savable` (storage.py):** `Serializable` defines
  `serialize()`/`deserialize()`; `Savable` adds `category()` (storage subfolder)
  and `id()` (filename). `storage.save_serializable_object` /
  `load_all_objects_of_category` read and write `DATA_DIR/<category>/<id>.<category>`
  JSON files. `storage.sanitize()` makes ids/categories filesystem-safe.
- **Auth (auth.py):** usernames are HMAC-SHA256 hashed (deterministic, for
  lookup); passwords are bcrypt-hashed. State lives in module-level dicts
  (`_users_by_uid`, `_user_uid_by_hashed_username`, `_access_tokens`) — **in
  memory only**, lost on restart.

### Data model
- **`User`** (`Savable`, category `"user"`): `uid`, `auth_types`,
  `hashed_username`, `hashed_password`, and a nested `UserData`.
- **`UserData`**: holds `chats: dict[str, Chat]`.
- **`Chat`**: `uid`, `title`, `currently_responding` flag, and `messages`
  (a list of `{role, content}` dicts in Ollama's chat format, seeded with a
  system prompt).

### Current API endpoints (`api.py`)
| Path                  | Auth type     | Purpose                                   |
|-----------------------|---------------|-------------------------------------------|
| `/api/login`          | always allowed| Exchange username/password headers for an access token |
| `/create_chat`        | `can_chat`    | Create a new chat from a system prompt    |
| `/list_chats`         | `can_chat`    | List the user's chats                      |
| `/get_chat`           | `can_chat`    | Fetch one chat by `chat_uid`               |
| `/send_chat_message`  | `can_chat`    | Stream an LLM response (chunked transfer)  |

## Conventions
- No web framework — work with raw `BaseHTTPRequestHandler` (`send_response`,
  `send_header`, `end_headers`, `wfile.write`).
- New endpoints: subclass `APIFunction` in `api.py`; do not edit the registry
  by hand.
- New persisted types: implement `Savable` and use `storage.*` helpers; never
  build file paths by hand (use `storage.sanitize`).
- Generate all ids via `uids.generate_uid(existing_ids)`.
- Read config through `os.getenv` after `load_dotenv()`.

## Status / Gotchas
This project has known bugs and unfinished wiring. **Read `ISSUES.md` before
making changes** — several modules will not currently import or run as written.
