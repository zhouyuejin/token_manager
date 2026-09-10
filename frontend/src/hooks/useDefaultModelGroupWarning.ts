import { useEffect, useReducer } from 'react'
import { getModelGroups, ModelGroup } from '../api/modelGroups'

type WarningState = {
  loading: boolean
  hasActiveDefault: boolean
}

// Module-level shared cache so the sidebar dot and the ModelGroups page
// don't each fire their own request. Re-fetches only when refresh() is called.
let state: WarningState = { loading: true, hasActiveDefault: true }
let inflight: Promise<void> | null = null
const listeners = new Set<() => void>()

function publish(next: WarningState) {
  state = next
  listeners.forEach((l) => l())
}

export async function refreshDefaultModelGroupWarning(): Promise<void> {
  if (inflight) return inflight
  inflight = (async () => {
    publish({ ...state, loading: true })
    try {
      const res = await getModelGroups()
      const items: ModelGroup[] = res.items || []
      const hasActiveDefault = items.some(
        (g) => g.is_default === 1 && g.status === 'active',
      )
      publish({ loading: false, hasActiveDefault })
    } catch {
      // On network failure assume default exists so we don't false-alarm.
      publish({ loading: false, hasActiveDefault: true })
    } finally {
      inflight = null
    }
  })()
  return inflight
}

export function useDefaultModelGroupWarning(enabled = true) {
  const [, forceRender] = useReducer((c: number) => c + 1, 0)

  useEffect(() => {
    listeners.add(forceRender)
    if (enabled) refreshDefaultModelGroupWarning()
    return () => {
      listeners.delete(forceRender)
    }
  }, [enabled])

  return {
    loading: state.loading,
    hasActiveDefault: state.hasActiveDefault,
    needsAttention: !state.loading && !state.hasActiveDefault,
    refresh: refreshDefaultModelGroupWarning,
  }
}
