import { $message } from './message'

// extra_keys 在表单上是 JSON 字符串，后端 ChannelCreate 要求 List[str]。
// 空串 → 删字段；否则解析 JSON 数组，解析失败给出明确提示。
export const parseExtraKeys = (values: any) => {
  const payload = { ...values }
  if (typeof payload.extra_keys !== 'string') return payload
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
  payload.extra_keys = parsed
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
