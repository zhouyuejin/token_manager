const timestamp = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?$/

export function normalizeApiDates(value) {
  if (Array.isArray(value)) return value.map(normalizeApiDates)
  if (value === null || typeof value !== 'object' || value instanceof Blob) return value
  return Object.fromEntries(Object.entries(value).map(([key, item]) => [
    key,
    /(?:_at|_until)$/.test(key) && typeof item === 'string' && timestamp.test(item)
      ? `${item.replace(' ', 'T')}Z`
      : normalizeApiDates(item),
  ]))
}
