import { useAuthStore } from '../store/auth'

// Minimal localStorage-backed persistence for the chat page's
// model selection. Kept dependency-free so it can be unit-tested
// in plain Node with a localStorage stub.

export interface ModelConfig {
  modelId?: string
}

const STORAGE_KEY_PREFIX = 'chat.modelConfig.v1'

// Build the localStorage key for a given user. Pure helper so tests and
// debug tooling can introspect it without depending on the auth store.
// Passing `undefined` (logged-out or pre-checkAuth state) falls back to
// the unsuffixed key, which is harmless because Chat only mounts once a
// user is loaded (App.tsx gates rendering on `authChecked`).
export const buildModelConfigKey = (userId: string | undefined): string =>
  userId ? `${STORAGE_KEY_PREFIX}.${userId}` : STORAGE_KEY_PREFIX

const currentStorageKey = (): string =>
  buildModelConfigKey(useAuthStore.getState().user?.user_id)

const sanitize = (raw: unknown): ModelConfig => {
  if (!raw || typeof raw !== 'object') return {}
  const obj = raw as Record<string, unknown>
  return {
    modelId: typeof obj.modelId === 'string' ? obj.modelId : undefined,
  }
}

export const loadModelConfig = (): ModelConfig => {
  try {
    const raw = localStorage.getItem(currentStorageKey())
    if (!raw) return {}
    return sanitize(JSON.parse(raw))
  } catch {
    return {}
  }
}

export const saveModelConfig = (cfg: ModelConfig): void => {
  try {
    localStorage.setItem(
      currentStorageKey(),
      JSON.stringify({
        modelId: cfg.modelId,
      }),
    )
  } catch {
    // localStorage may be unavailable (private mode, quota); silently ignore.
  }
}

// Pick the model ID we should actually show on mount.
// Returns the persisted value if it's still available to the current user;
// otherwise falls back to the first available model. Keeps the model selector
// honest when localStorage carries a stale value (e.g. admin→regular user on
// the same browser, or an admin revoking access to a previously saved model).
export const pickInitialModelId = (
  stored: string | undefined,
  availableIds: readonly string[],
): string | undefined => {
  if (stored && availableIds.includes(stored)) return stored
  return availableIds[0]
}

// Remove the persisted chat model config for a given user. Called from the
// auth store's `logout` so the per-user bucket doesn't outlive the session.
// Pure: takes the userId explicitly so callers stay in control of timing.
export const clearModelConfigStorage = (userId: string | undefined): void => {
  if (!userId) return
  try {
    localStorage.removeItem(buildModelConfigKey(userId))
  } catch {
    // localStorage may be unavailable; silently ignore.
  }
}

export const __storageKeyPrefix = STORAGE_KEY_PREFIX
