// Minimal localStorage-backed persistence for the chat page's
// provider/model selection. Kept dependency-free so it can be unit-tested
// in plain Node with a localStorage stub.

export interface ModelConfig {
  providerId?: string
  modelId?: string
}

const STORAGE_KEY = 'chat.modelConfig.v1'

const sanitize = (raw: unknown): ModelConfig => {
  if (!raw || typeof raw !== 'object') return {}
  const obj = raw as Record<string, unknown>
  return {
    providerId: typeof obj.providerId === 'string' ? obj.providerId : undefined,
    modelId: typeof obj.modelId === 'string' ? obj.modelId : undefined,
  }
}

export const loadModelConfig = (): ModelConfig => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    return sanitize(JSON.parse(raw))
  } catch {
    return {}
  }
}

export const saveModelConfig = (cfg: ModelConfig): void => {
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        providerId: cfg.providerId,
        modelId: cfg.modelId,
      }),
    )
  } catch {
    // localStorage may be unavailable (private mode, quota); silently ignore.
  }
}

export const __storageKey = STORAGE_KEY
