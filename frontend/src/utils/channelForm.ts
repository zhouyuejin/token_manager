import { $message } from './message'

const validateKey = (key: unknown): string => {
  if (typeof key !== 'string' || !key.trim() || key.trim() === 'null' || key.includes('...') || key.includes('*')) {
    $message.warning('请输入真实 Key，不能提交空值、null 或掩码')
    throw new Error('invalid key')
  }
  return key.trim()
}

// extra_keys 在表单上是 JSON 字符串，后端 ChannelCreate 要求 List[str]。
// 空串 → 删字段；否则解析 JSON 数组，解析失败给出明确提示。
export const parseExtraKeys = (values: any) => {
  const payload = { ...values }
  if (payload.extra_keys == null) {
    delete payload.extra_keys
    return payload
  }
  if (Array.isArray(payload.extra_keys)) {
    payload.extra_keys = payload.extra_keys.map(validateKey)
    return payload
  }
  if (typeof payload.extra_keys !== 'string') throw new Error('invalid extra_keys')
  const trimmed = payload.extra_keys.trim()
  if (!trimmed) {
    delete payload.extra_keys
    return payload
  }
  let parsed: unknown
  try {
    parsed = JSON.parse(trimmed)
  } catch {
    $message.warning('额外 Keys 格式错误，需为 JSON 数组，例如 ["sk-1","sk-2"]')
    throw new Error('invalid extra_keys')
  }
  if (!Array.isArray(parsed) || !parsed.every((k) => typeof k === 'string')) {
    $message.warning('额外 Keys 需为字符串数组')
    throw new Error('invalid extra_keys')
  }
  payload.extra_keys = parsed.map(validateKey)
  return payload
}

// auth_headers 在表单上是 JSON 字符串，后端 ChannelCreate 要求 Dict[str, str]。
// 空串 → undefined（让后端使用默认空字典）；非空则解析 JSON 对象，失败给提示。
export const parseAuthHeaders = (values: any) => {
  const payload = { ...values }
  if (typeof payload.auth_headers !== 'string') return payload
  const trimmed = payload.auth_headers.trim()
  if (!trimmed) {
    payload.auth_headers = undefined
    return payload
  }
  try {
    payload.auth_headers = JSON.parse(trimmed)
  } catch {
    $message.error('额外请求头不是合法 JSON')
    throw new Error('invalid auth_headers')
  }
  return payload
}

export const prepareChannelPayload = (values: any, isEdit: boolean) => {
  const input = { ...values }
  if (isEdit && input.main_key_action === 'keep') delete input.api_key
  if (isEdit && input.main_key_action === 'replace') input.api_key = validateKey(input.api_key)
  if (isEdit && ['keep', 'edit', 'clear'].includes(input.extra_keys_action)) delete input.extra_keys
  if (isEdit && input.extra_keys_action === 'clear') input.extra_keys = []
  if (input.extra_keys_action && input.extra_keys_action !== 'edit') delete input.extra_key_edits
  if (input.extra_keys_action === 'replace' && !input.extra_keys?.trim()) {
    $message.warning('请输入额外 Key 数组；清空请使用清空全部选项')
    throw new Error('invalid extra_keys')
  }
  delete input.main_key_action
  delete input.extra_keys_action
  const payload = parseAuthHeaders(parseExtraKeys(input))
  const edits = payload.extra_key_edits
  delete payload.extra_key_edits
  if (isEdit && edits) {
    const updates: Record<number, string | null> = {}
    edits.forEach((edit: any, index: number) => {
      if (edit.action === 'replace') updates[index] = validateKey(edit.value)
      if (edit.action === 'remove') updates[index] = null
    })
    if (Object.keys(updates).length) payload.extra_key_updates = updates
  }
  if (!payload.extra_key_updates) delete payload.extra_keys_revision
  if (isEdit && !payload.api_key?.trim()) delete payload.api_key
  else if (payload.api_key !== undefined) payload.api_key = validateKey(payload.api_key)
  return payload
}
