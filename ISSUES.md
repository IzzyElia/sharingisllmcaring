# ISSUES.md

Findings from an audit of the codebase. Ordered **most-definite bugs in existing
code first**, trailing off into issues that stem from the project's
work-in-progress state (missing wiring, config, and hardening).

Severity tags: 🔴 breaks at import/runtime · 🟠 wrong behavior · 🟡 minor/quality
· 🔵 security · ⚪ WIP / not-yet-implemented.

---

## A. Bugs in existing code

> **Audit status.** Most of the originally-catalogued bugs have been fixed and
> removed from this file. What remains below is still open. **#14** is a `main.py`
> scratch-harness issue and is out of scope (that file is stale/unused).

### 7. 🟠 `APISendChatMessage` "not found" check is dead code
`server/api.py:164-173`
```python
handler.send_response(200)                 # status sent before the lookup
...
chat = user.user_data.chats[chat_uid]      # KeyError if missing, never None
if chat is None: ...                        # unreachable
```
A missing `chat_uid` raises `KeyError` (→ 500) instead of the intended 404, and
since `send_response(200)` has already been sent, the `send_response(404)` in the
branch would double the status line anyway. Resolve the chat with `.get(chat_uid)`
*before* sending any status, 404 if `None`, otherwise send 200. (`APIGetChat` was
already fixed this way.)

### 14. 🟠 `main.py` test harness will `IndexError`
`main.py:8`
```python
users = list(storage.load_all_objects_of_category("user", auth.User))
deserialized_user = users[5]    # assumes ≥6 users exist on disk
```
Hardcoded index `[5]` assumes a populated `data/user` directory; on a clean
checkout this raises `IndexError`. (This is a scratch harness, but as written it
fails.)

### 15. 🟡 Duplicate import of `UserData` in `auth.py`
`server/auth.py:8` and `:11` import `UserData` twice (once absolute, once
relative). Harmless but redundant.

### 16. 🟡 `LOGIN_ENDPOINT` doesn't match the registered login path
`server/handler.py:7` sets `LOGIN_ENDPOINT = "/login"`, but the actual login
endpoint is `/api/login` (`server/api.py:20`). A `RedirectToLogin` auth failure
would 302 to an unregistered path.

---

## B. Issues stemming from the WIP nature of the project

### 17. ⚪ `auth_types_allowed` is declared but never enforced
`server/handler.py:16-46` authenticates the access token but never checks the
endpoint's `auth_types_allowed()` against the user's `user.auth_types`. The
`can_chat` permission on the chat endpoints is currently decorative — any
authenticated user can call any endpoint. Authorization still needs to be wired
into `Handler.do`.

### 18. ⚪🔵 In-memory-only state; nothing is persisted at runtime
Users, the username→uid index, access tokens, and created chats live only in
module-level dicts (`auth.py`, `UserData`). `add_user` and `APICreateChat` never
call `storage.save_serializable_object`, and nothing loads users on startup. All
state is lost on restart, and a freshly started server has no users to log in as.
Persistence/loading is not yet hooked up.

### 19. ⚪🔵 Hardcoded fallback `HASHING_SECRET` in source
`server/auth.py:18-20` falls back to a long hardcoded secret (and only prints a
warning) when `HASHING_SECRET` is unset — which is the current state, since `.env`
only defines `MODEL`. With a known secret, the deterministic username HMAC is
predictable. Make the secret required (fail fast) before any real deployment, and
keep it out of source.

### 20. ⚪🔵 No locking around shared mutable state under `ThreadingHTTPServer`
The server is threaded (`ThreadingHTTPServer`), but the global auth dicts and each
`Chat.messages` / `currently_responding` are mutated without synchronization.
Concurrent requests can race (lost writes, partial reads). Needs locks or a
thread-safe store as the app matures.

### 21. ⚪ No real server entry point
There is no `if __name__ == "__main__"` that calls `server.start_server()`, and
`main.py` is an unrelated storage scratch test. The `__main__` blocks in
`auth.py:122` and `api.py` are leftover experiments. A proper launch script is
still needed.

### 22. ⚪🔵 Credentials and tokens passed via custom plaintext headers; no TLS
Login takes `Login-Username` / `Login-Password` headers and returns
`Granted-Access-Token`; the server binds `localhost:8080` with no TLS. Acceptable
for local dev, but the request/response contract (and transport security) isn't
finalized.

### 23. ⚪ No `.gitignore`
`__pycache__/`, `.venv/`, `.idea/`, and `.env` are all present in the working
tree with no `.gitignore`. `.env` (secrets) and the virtualenv should be ignored
to avoid accidentally committing them.

### 24. ⚪ Access token never refreshed/cleaned; `routine_cleanup` is never called
`routine_cleanup` (`server/auth.py:117`) now correctly removes expired tokens, but
nothing ever schedules/calls it, so expired tokens accumulate in memory for the
life of the process.
