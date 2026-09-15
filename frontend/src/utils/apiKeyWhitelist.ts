export const parseApiKeyWhitelist = (value?: string): string[] =>
  (value || '')
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean)

export const formatApiKeyWhitelist = (value?: string[] | null): string =>
  (value || []).join('\n')
