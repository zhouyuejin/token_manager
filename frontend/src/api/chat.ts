import { get, post, del, put } from './request'
import { useAuthStore } from '../store/auth'

// ========== 类型定义 ==========

export interface ChatMessage {
  message_id: string
  conversation_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  model?: string
  tokens?: number
  created_at: string
}

export interface ChatConversation {
  conversation_id: string
  user_id: string
  title?: string
  provider_id?: string
  model_id?: string
  system_prompt?: string
  created_at: string
  updated_at: string
  message_count?: number
}

export interface Provider {
  provider_id: string
  name: string
  type: string
  models: {
    model_id: string
    display_name: string
    provider_model: string
  }[]
}

export interface ModelGroup {
  group_id: string
  name: string
  providers: Provider[]
  models: {
    model_id: string
    display_name: string
    provider_model: string
  }[]
}

export interface SendMessageRequest {
  messages: {
    role: string
    content: string
  }[]
  model?: string
  provider_id?: string
  temperature?: number
  max_tokens?: number
  stream?: boolean
}

export interface SendMessageResponse {
  conversation_id: string
  message_id: string
  role: string
  content: string
  model: string
  tokens?: number
}

// ========== API 接口 ==========

/**
 * 获取用户可用模型列表
 */
export const getAvailableModels = () => get<{ groups: ModelGroup[] }>('/chats/models')

/**
 * 获取对话列表
 */
export const getConversations = (page: number = 1, pageSize: number = 20) =>
  get<{ total: number; items: ChatConversation[] }>('/chats', { params: { page, page_size: pageSize } })

/**
 * 获取单个对话详情
 */
export const getConversation = (conversationId: string) =>
  get<ChatConversation>(`/chats/${conversationId}`)

/**
 * 创建新对话
 */
export const createConversation = (data: {
  title?: string
  model?: string
  provider_id?: string
  system_prompt?: string
}) => post<ChatConversation>('/chats', data)

/**
 * 更新对话
 */
export const updateConversation = (conversationId: string, data: {
  title?: string
  model?: string
  provider_id?: string
  system_prompt?: string
}) => put<ChatConversation>(`/chats/${conversationId}`, data)

/**
 * 删除对话
 */
export const deleteConversation = (conversationId: string) =>
  del<void>(`/chats/${conversationId}`)

/**
 * 获取对话消息列表
 */
export const getMessages = (conversationId: string, page: number = 1, pageSize: number = 50) =>
  get<{ total: number; items: ChatMessage[] }>(`/chats/${conversationId}/messages`, {
    params: { page, page_size: pageSize }
  })

/**
 * 发送消息（非流式）
 */
export const sendMessage = (conversationId: string, data: SendMessageRequest) =>
  post<SendMessageResponse>(`/chats/${conversationId}/messages`, data)

/**
 * 发送消息（流式）- 返回 fetch response 用于处理流
 */
export const sendMessageStream = (conversationId: string, data: SendMessageRequest) => {
  const params = new URLSearchParams()
  params.append('stream', 'true')

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  const token = useAuthStore.getState().token
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  return fetch(`/api/v1/chats/${conversationId}/messages?${params}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(data),
  })
}
