# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Token中转平台** — an internal API gateway that fronts multiple LLM providers (OpenAI, Anthropic, Moonshot, 火山方舟). Users register, get API keys, and call `/api/v1/proxy/chat/completions` (OpenAI-compatible); the backend selects a provider, forwards via httpx, records usage, and deducts quota. Admins manage providers, models, model groups, users, and view logs/stats.

## Stack

- **Backend**: FastAPI (Python 3.10+), SQLAlchemy 2, Alembic, MySQL 8, Redis, APScheduler, loguru, httpx, python-jose (JWT)
- **Frontend**: React 18 + TypeScript + Vite, Antd 5, Zustand, React Router 6, ECharts, axios
- **Infra**: Docker Compose (`mysql`, `redis`, `backend`, `nginx`, `prometheus`, `grafana`), Nginx reverse proxy

## Common commands

### Stack-wide
```bash
docker-compose up -d            # start everything
docker-compose ps
docker-compose logs -f backend
docker-compose exec backend bash
```

### Backend (local dev without Docker)
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload   # http://localhost:8000, docs at /docs
```

### Backend tests
Tests run against MySQL (see [Backend testing](#backend-testing)).

```bash
cd backend
pytest                                       # all
pytest tests/test_proxy_service_admin_override.py   # one file
pytest tests/test_proxy_service_admin_override.py::test_x   # one test
pytest -k "admin"                            # name pattern
```

### Database migrations (Alembic)
```bash
cd backend
alembic upgrade head                          # apply
alembic downgrade -1                          # revert one
alembic revision --autogenerate -m "msg"      # new migration (autogen)
```
Schema files: `backend/alembic/versions/`. Production schema bootstrap also runs `Base.metadata.create_all` in `app/main.py`, but new tables/changes must go through migrations.

### Frontend
```bash
cd frontend
npm install
npm run dev       # vite dev server
npm run build     # tsc + vite build → dist/
npm run lint      # eslint, --max-warnings 0 (treat warnings as errors)
npm run preview
```

## Architecture

### Backend layout (`backend/app/`)

- `main.py` — FastAPI app, CORS, `ProxyAuthMiddleware`, lifespan (creates default `admin`/`testuser` if missing, warns if no active default model group, starts APScheduler jobs).
- `core/config.py` — Pydantic `Settings`, reads `.env` (DB/Redis/JWT/SMTP). DB & Redis URLs are derived properties.
- `core/database.py` — SQLAlchemy `engine`, `SessionLocal`, `Base`, `get_db()` FastAPI dependency.
- `core/security.py` — JWT helpers, ID generators, **password convention** (see below).
- `middleware/ProxyAuthMiddleware.py` — Validates incoming API keys for `/proxy/*` routes, attaches `request.state.user` and `request.state.api_key`.
- `dependencies/__init__.py` — `get_current_user`, `require_admin` (HTTPBearer).
- `models/` — SQLAlchemy ORM: `user`, `api_key`, `provider`, `model_mapping`, `model_group` (many-to-many with model_mappings), `usage_log`, `operation_log`, `login_log`, `refresh_token`, `notification`, `chat`, `provider_quota`, `quota_record`, `system_config`.
- `schemas/` — Pydantic v2 request/response models.
- `services/proxy_service.py` — **Core gateway logic.** `verify_api_key`, `get_effective_model_group_ids` (GC-1/GC-2 admin short-circuit), `check_model_group_access` (single permission gate), `forward_request`/`forward_stream_request`, `record_usage`, `deduct_quota`, `check_quota`.
- `services/model_groups_service.py` — Transactional `set_default_group` / `unset_default_group` (clears all `is_default`, then sets one).
- `services/sync_service.py` — Provider quota sync (5h / weekly) — runs in scheduler.
- `services/scheduler_service.py`, `services/model_sync_service.py`, `services/notification_service.py`, `services/email_service.py`, `services/operation_log_service.py`, `services/ws_manager.py`, `services/quota_guard.py`.
- `tasks/daily_report.py` — APScheduler daily report job.
- `api/v1/` — One router per resource (see `api/v1/__init__.py`); all mounted under `/api/v1`. WebSocket router (`ws.py`) is registered at root (no `/api/v1` prefix) so clients connect at `/ws/...`.

### Frontend layout (`frontend/src/`)

- `main.tsx`, `App.tsx` — Router setup. Role-based default landing: admin → `/admin/dashboard`, user → `/stats`. `useNotificationWebSocket` runs whenever there's a token.
- `api/` — One module per resource; all call shared `request.ts` (axios instance with `/api/v1` baseURL).
  - `request.ts` — Single-flight 401 refresh (shared `refreshInFlight` promise), automatic `Authorization: Bearer` header, global `$message.error` on response `detail`.
  - `auth.ts` — `login`, `register`, `refresh`, `logout`.
- `store/auth.ts` — Zustand auth store: `token`, `refreshToken`, `user`, `checkAuth`.
- `utils/crypto.ts` — SHA256 hashing (must match backend `FRONTEND_SALT`).
- `pages/` — Login, Register, ApiKeys, Stats, Notifications, Settings, Chat, AdminDashboard.
- `pages/admin/` — `AdminLayout` + Users / Providers / Models / ModelGroups / OperationLogs / LoginLogs (admin-only routes).
- `components/Layout/MainLayout.tsx`, `components/Chat/{ConversationList,InputArea,MessageList,ModelSelector}.tsx`, `components/MessageProvider.tsx`, `components/NotificationDropdown.tsx`.

### Data flow — proxy request
`POST /api/v1/proxy/chat/completions` →
1. `ProxyAuthMiddleware` verifies `tmk_*` API key, sets `request.state.user`/`api_key`.
2. `proxy_service.get_model_mapping` → `get_provider`.
3. `check_model_group_access` (single source of truth; GC-1) — admin role bypasses entirely.
4. `check_quota` pre-flight estimate.
5. `forward_request` (or `forward_stream_request`) via httpx to the provider.
6. `calculate_tokens` → `record_usage` (writes `usage_log`) → `deduct_quota` on success.

Stream responses wrap the generator to capture latency and deduct after the stream ends (`sync_generator` in `api/v1/proxy.py`).

### Auth & password convention

- **No backend rehashing.** Passwords are SHA256-hashed on the frontend with `FRONTEND_SALT = "token_manager_frontend_salt"` (see `frontend/src/utils/crypto.ts` and `backend/app/core/security.py`). The backend stores the hex verbatim and compares with `==`. `bcrypt`/`passlib` are intentionally absent.
- Login returns `access_token` (JWT, HS256) + `refresh_token` (random URL-safe, only its SHA256 is stored in `refresh_tokens`). `ACCESS_TOKEN_EXPIRE_MINUTES` and `REFRESH_TOKEN_EXPIRE_DAYS` are in `Settings`.
- Refresh: `POST /api/v1/auth/refresh` with `{"refresh_token": "..."}`. Frontend uses a single in-flight promise to dedupe concurrent 401s.

### Admin / model-group invariants (the `GC-*` rules)

- **GC-1** — Model group access has a single source of truth: `ProxyService.get_effective_model_group_ids` and `check_model_group_access`. Both the `/proxy/models` listing and the chat endpoint go through it.
- **GC-2** — Admin role short-circuits: returns *all* `active` model groups; the `user.model_group_ids` JSON column is ignored for admins. So adding/removing a group requires no admin user updates.
- **GC-3** — Admin quota is the unlimited sentinel `-1` (do **not** treat as a real number; the recent migration `20260908_1800_admin_quota_unlimited.py` rewrote 100000000 → -1). All `deduct_quota` paths must guard against `-1`.
- **Default group invariant** — At least one `ModelGroup` with `is_default=1 AND status='active'` must exist. Otherwise startup logs a warning, `AdminLayout` shows a yellow banner, and `/proxy/models` returns `{"data": []}`. `set_default_group` is the only sanctioned writer and is transactional.
- When a group is deleted, `model_groups._cleanup_users_with_group` strips the `group_id` out of every user's `model_group_ids` JSON.

### Quota & cost

- `User.quota` is in **USD cents** (post the `20260908_1600_convert_price_cny_to_usd.py` migration). `User.quota_used` tracks cumulative spend. `ApiKey` has separate `daily_limit`/`daily_used` and `monthly_limit`/`monthly_used`.
- Provider costs live on `ProviderQuota` and are synced by `services/sync_service.py` (5-hour and weekly windows per provider).

### WebSocket notifications

`app/api/v1/ws.py` is registered without the `/api/v1` prefix (see `main.py`), so the frontend connects at `/ws/...`. `services/ws_manager.py` keeps a per-user connection set; `useNotificationWebSocket` on the frontend wires notifications into the Antd message/Dropdown.

## Backend testing

Tests use a real MySQL test DB (`token_db_test` by default), not SQLite. `tests/conftest.py` truncates all tables before each test. Set `TEST_DATABASE_URL` to override.

```bash
# one-off setup (matches docker-compose service name)
docker-compose exec mysql mysql -uroot -proot_password \
  -e "CREATE DATABASE IF NOT EXISTS token_db_test CHARACTER SET utf8mb4;"
cd backend
TEST_DATABASE_URL='mysql+pymysql://token_user:token_password@localhost:3306/token_db_test?charset=utf8mb4' pytest
```

Or run tests inside the backend container where `mysql` resolves to the DB host:
```bash
docker-compose exec backend pytest
```

Existing test areas: admin role overrides, admin unlimited quota, model-group & model-binding ORM, proxy service access checks, quota notifications, refresh-token auth, login/operation logs, WS manager.

## Conventions

- **Commit messages**: Conventional Commits (`feat(scope):`, `fix:`, `merge: …`). Recent: `feat(proxy): admin 角色自动拥有所有 active 模型分组 + 无限制额度`, `feat(migration): admin quota 100000000 → -1 (unlimited sentinel)`, `feat(frontend): admin 用户展示 + 表单字段隐藏`.
- **IDs**: `usr_*`, `key_*`, `tmk_*` (API key), shortuuid-based (see `core/security.py:generate_*`).
- **Pydantic v2**: use `model_dump()` not `dict()`; `model_validate` not `parse_obj`.
- **Logs**: loguru writes to `backend/logs/app.log` (500 MB rotation, 10-day retention). Don't add `print` — use `logger`.
- **Env vars**: defaults live in `Settings` (`backend/app/core/config.py`); `.env` at repo root is loaded automatically.
- **Frontend paths**: references to files use the [relative path](path) markdown form. Backend `file_path:line` is fine.

## CodeGraph

This repo is indexed under `.codegraph/`. Before grepping across the backend, try `codegraph explore "<symbol or question>"` (shell) for call-path-aware answers that follow dynamic dispatch across routers/services. The MCP form (`codegraph_explore`) is preferred when available.
# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
