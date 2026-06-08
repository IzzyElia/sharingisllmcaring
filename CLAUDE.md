# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A self-hosted, multi-user chat backend that streams responses from a local
[Ollama](https://ollama.com) model over a plain HTTP API. Everything is built on
Python's standard library `http.server` — there is no web framework. Persistence
is flat JSON files on disk.

## Running

- Install deps: `pip install -r requirements.txt` (`ollama`, `bcrypt`, `python-dotenv`).
- A local Ollama server must be running, and the model named by `MODEL` must be
  pulled (`ollama pull <model>`). `.env` sets `MODEL=cogito:3b`.
- The HTTP server binds `localhost:8080` via `restapi.server.start_server()`.
  Note: nothing currently calls `start_server()` — `main.py` is a scratch harness
  that exercises `auth` + `storage` directly, not the server entry point.
- Environment variables (loaded from `.env` via `python-dotenv`):
  - `MODEL` (required by `api.py`) — Ollama model name.
  - `HASHING_SECRET` — HMAC key for hashing usernames; falls back to a hardcoded
    default with a warning if unset.
  - `DATA_DIR` — root for JSON storage, defaults to `./data`.

There is no test suite, linter, or build step configured.

## Architecture

The `restapi/` package is the whole application. Request flow:

`server.py` → `handler.Handler` (routes `do_GET/POST/PUT/DELETE` → `do()`) →
looks up the path in the global `endpoints` dict → calls the matching
`APIFunction.execute(...)`.

### Endpoint registration (the key indirection)

Endpoints are not wired up manually. `start_server()` discovers every
`APIFunction` subclass via `APIFunction.__subclasses__()` and registers each of
its declared endpoint paths into the module-level `handler.endpoints` dict. So to
add an endpoint you only define a new `APIFunction` subclass in `api.py` (or any
module imported before `start_server` runs) — no central route table to edit.

Each `APIFunction` (see `api.py`) implements:
- `endpoints` — the URL path(s) it serves.
- `auth_types_allowed` — required auth-type strings (e.g. `'can_chat'`).
- `on_auth_failure` — one of `AuthFailureResponse.{AlwaysAllowed, RedirectToLogin, Unauthorized}`.
- `execute(handler, body, method, user)` — does the work, writing directly to
  `handler.wfile`. Auth is enforced in `Handler.do()` before `execute` is called,
  using the `Access-Token` request header resolved through `auth.get_access_token_user`.

Streaming chat (`APISendChatMessage`) writes a manual HTTP **chunked** transfer:
each Ollama token is wrapped as a JSON object and framed with hex length prefixes,
terminated by `0\r\n\r\n`.

### Auth (`auth.py`)

In-memory user/session store — `_users_by_uid`, `_user_uid_by_hashed_username`,
`_access_tokens` are module globals (not persisted between process restarts on
their own). Usernames are HMAC-SHA256 hashed (lookup keys, deterministic);
passwords are bcrypt hashed. Access tokens are random UIDs with an `expires_at`
epoch check.

### Persistence (`storage.py`)

`Serializable` (serialize/deserialize) and its subclass `Savable` (adds
`category()` + `id()`) are the core abstractions. `save_serializable_object`
writes each object to `DATA_DIR/<category>/<id>.<category>` as pretty JSON;
`load_all_objects_of_category` reads them back. All filenames pass through
`sanitize()` (Unicode-normalizes, strips path separators and Windows-illegal
chars/reserved names, truncates to 255). A `User` is `Savable`; its nested
`UserData`/`Chat` are `Serializable` and serialized inline as part of the user.

### Data model (`user_data.py`)

`User` owns one `UserData`, which owns a `dict[str, Chat]` keyed by chat UID. A
`Chat` holds the running `messages` list (seeded with a system prompt) that is
sent to Ollama and appended to in place as tokens stream in.

`uids.py` generates collision-checked, URL-safe base64 UIDs from 32 secure random
bytes.

## Conventions

- Module-level mutable globals are the intended state store for the request
  lifetime; pass `auth.User` objects through `execute` rather than re-fetching.
- Endpoints write responses by hand (`send_response` / `send_header` /
  `end_headers` / `wfile.write`); there are no response helpers yet.
- New persistable types subclass `Savable` and implement `category`/`id`/
  `serialize`/`deserialize`; storage paths derive from `category`/`id`.
