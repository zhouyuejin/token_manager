# Plan: Fix Model Group Default Assignment Bug

## Context

**Bug**: When a normal user creates an API Key, the key inherits only the user's `user.model_group_ids`. If the admin forgets to assign groups to that user, the key has zero model groups and cannot access any model. The `is_default` field on `ModelGroup` exists in the schema/model but is never read anywhere — it is the unused primitive for "system default group."

**Fix philosophy**: Default group (`is_default=1`) is the **primary** access mechanism. `user.model_group_ids` becomes a **secondary** "premium user" grant. The user-facing API and UI never expose group info — only admins do.

## Global Constraints

- **GC-1**: All access logic flows through ONE function: `ProxyService.get_effective_model_group_ids(user) -> set[str]` returning `default_ids ∪ user_ids`. No other code may compute "what groups can this key use" inline.
- **GC-2**: User-facing API responses and schemas MUST NOT contain `model_groups` field. User-facing create/update requests MUST NOT accept `model_group_ids` field. Only admin schemas/routes carry these fields.
- **GC-3**: Error messages returned to end users on model access denial MUST NOT reveal group structure (no group names, no list of available groups). Generic: "当前 Key 未被授权访问该模型".
- **GC-4**: Admin must be visibly warned whenever `is_default=1` count is 0. Three layers: (a) startup warn log, (b) AdminLayout yellow closable banner, (c) `/admin/model-groups` red Card that cannot be dismissed.
- **GC-5**: When computing effective groups, only groups with `status == active` count. A disabled default group automatically stops being a default.
- **GC-6**: No `is_default` uniqueness constraint. Multiple default groups are allowed.
- **GC-7**: `user.model_group_ids` is a JSON string column, already exists. No schema migration for it. `is_default` already exists on `model_groups`; only add `server_default="0"` via Alembic if missing.
- **GC-8**: No new dependencies. No breaking changes to existing routes for admins (admin routes keep all current fields).
- **GC-9**: No new tests in code that lacks tests today. Existing tests must pass; new logic gets focused tests.

## Design Rules

```
R1. System should have at least one is_default=1 group (admin warned via three layers per GC-4)
R2. User creates Key → auto-assigned effective = default_ids ∪ user_authorised_ids
R3. User API surface: no model_group_ids accepted, no model_groups returned
R4. Admin API surface: full control over both user-level and key-level groups
R5. Only admins adjust user.model_group_ids (no UI on user side)
```

## Tasks

### Task 1: Backend — schema split, route split, access convergence

**Files touched**:
- `backend/app/schemas/api_key.py` — split into user-facing vs admin-facing
- `backend/app/api/v1/api_keys.py` — user routes use user-facing schema; admin routes use admin schema; create/update logic uses `ProxyService.get_effective_model_group_ids`
- `backend/app/services/proxy_service.py` — add `get_effective_model_group_ids(user)` and `check_model_group_access(api_key, user, model_id)`; replace any inline model-group checks in `/api/v1/chat/completions` and `/api/v1/proxy/chat/completions` with calls to `check_model_group_access`
- `backend/app/main.py` (or wherever startup lives) — startup hook logs warn when `is_default=1` count is 0

**Acceptance**:
- `ApiKeyResponse` (user) has no `model_groups` field
- `ApiKeyCreate` (user) has no `model_group_ids` field
- `ApiKeyAdminResponse` and `ApiKeyAdminCreate` exist, both contain the removed fields
- User `/api-keys`, `/api-keys/{key_id}`, `POST /api-keys`, `PUT /api-keys/{key_id}` use user-facing schemas
- Admin `/api-keys/admin/all` and any new `/api-keys/admin/*` routes use admin-facing schemas
- `ProxyService.get_effective_model_group_ids(user)` returns the union of `is_default=1 ∩ status=active` and `user.model_group_ids` (parsed JSON)
- `ProxyService.check_model_group_access(api_key, user, model_id)` returns generic error (no group leak)
- Startup logs warn when no active default group exists
- All existing tests still pass
- New focused tests covering: effective computation, default-only user, default+user, disabled default, no default scenario

### Task 2: Frontend — user-side cleanup + admin warnings

**Files touched**:
- `frontend/src/api/apiKeys.ts` — remove `model_groups` from `ApiKey` interface, remove `model_group_ids` from `CreateApiKeyParams`
- `frontend/src/pages/ApiKeys.tsx` — remove model-group multi-select from create form; remove `model_groups` column from list; remove "auto-assigned groups" success message
- `frontend/src/pages/admin/AdminLayout.tsx` (or the actual layout file) — add yellow closable banner when no active default group, with "前往设置" CTA
- `frontend/src/pages/admin/ModelGroups.tsx` — add red non-dismissible Card on top when no active default group; make "设为默认" button prominent when no default exists; add "创建后立即设为默认" checkbox in create modal
- `backend/app/api/v1/model_groups.py` — add `POST /{group_id}/set-default` and `POST /{group_id}/unset-default` (admin only)

**Acceptance**:
- `ApiKey` TS interface has no `model_groups`
- `CreateApiKeyParams` TS interface has no `model_group_ids`
- ApiKeys page create form has no group selector
- ApiKeys page list/column has no group info displayed
- AdminLayout shows yellow banner when no default; clicking CTA navigates to groups page; banner closable (session-only)
- ModelGroups page shows red Card when no default; red Card not closable; offers "立即创建分组" CTA when groups list is empty
- ModelGroups page "设为默认" button uses `primary` (or `danger` if no default anywhere) styling when not yet default
- ModelGroups page create modal has "创建后立即设为默认" checkbox
- Backend `set-default` / `unset-default` endpoints are admin-only and idempotent
- All existing frontend builds pass (typecheck + lint if configured)

### Task 3: Test coverage and final verification

**Files touched**:
- New test files under `backend/tests/` for the access logic and effective-group computation
- Possibly add integration tests under `frontend/` for the page-level behaviors (if test infra exists)

**Acceptance**:
- Table of 8 acceptance scenarios from the original discussion all pass:
  1. Default group set, new user, no model_group_ids passed → key has default group
  2. User authorised + default → key has both
  3. Disabled group excluded
  4. No default + no user auth → key has no groups; error message generic
  5. Old user, default added → effective includes default
  6. Admin `set-default` is idempotent; multiple default groups allowed
  7. Admin warns visible in AdminLayout / ModelGroups / startup log
  8. Error messages do not leak group info
- All previously passing tests still pass
- Lint / typecheck clean

## Out of Scope

- Per-key restriction UI for non-admin users (explicitly removed by R3)
- Unique constraint on `is_default` (multiple defaults allowed per GC-6)
- Hard-blocking key creation when no default exists (soft warning only per GC-4)
- Renaming `is_default` field
- Migration of historical keys (soft path: existing keys gain access automatically once a default is set, because effective is computed at access time, not stored on the key)
