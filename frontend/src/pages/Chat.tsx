import { useState, useEffect } from 'react'
import { loadModelConfig, saveModelConfig } from '../utils/chatStorage'
import { useThemeToken } from '@/theme/useThemeToken'
import { Layout, Button, App } from 'antd'
import ConversationList from '../components/Chat/ConversationList'
import MessageList from '../components/Chat/MessageList'
import InputArea from '../components/Chat/InputArea'
import {
  createConversation,
  sendMessageStream,
  ChatConversation,
  ChatMessage,
} from '../api/chat'
import { useSwrDataWithParams } from '../hooks/useSwr'

const { Sider } = Layout

const SIDEBAR_WIDTH = 260

const Chat: React.FC = () => {
  const { token, isDark } = useThemeToken()
  const { message } = App.useApp()
  const [_conversations, setConversations] = useState<ChatConversation[]>([])
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null)
  const [sending, setSending] = useState(false)
  const [streaming, setStreaming] = useState(false)

  // 模型配置
  const [modelConfig, setModelConfig] = useState<{
    modelId?: string
  }>(() => loadModelConfig())

  // 使用 SWR 获取当前会话消息:同一 URL 在 dedupingInterval 内共享请求,
  // 避免 select + useEffect 触发两次,以及 StrictMode 双调用
  const messagesUrl = currentConversationId
    ? `/chats/${currentConversationId}/messages`
    : null
  const messagesParams = currentConversationId ? { page: 1, page_size: 100 } : null
  const {
    data: messagesData,
    mutate: mutateMessages,
    isLoading: messagesLoading,
  } = useSwrDataWithParams<{ total: number; items: ChatMessage[] }>(
    messagesUrl,
    messagesParams,
  )
  const messages = messagesData?.items ?? []

  // 选择对话
  const handleSelectConversation = (conversationId: string) => {
    setCurrentConversationId(conversationId)
  }

  // 新建对话,返回新创建的会话 ID(避免在调用方依赖尚未更新的 state)
  const handleNewChat = async (): Promise<string | null> => {
    try {
      const res = await createConversation({
        model: modelConfig.modelId,
      })
      setCurrentConversationId(res.conversation_id)
      setConversations(prev => [res, ...prev])
      return res.conversation_id
    } catch (error) {
      console.error('创建对话失败:', error)
      message.error('创建对话失败')
      return null
    }
  }

  // 发送消息
  const handleSendMessage = async (content: string, _files?: File[]) => {
    // 先校验模型,提示信息才名副其实
    if (!modelConfig.modelId) {
      message.warning('请先选择模型')
      return
    }

    // 用局部变量获取会话 ID,避免闭包陈旧
    let conversationId = currentConversationId
    if (!conversationId) {
      conversationId = await handleNewChat()
      if (!conversationId) return
    }

    setSending(true)
    setStreaming(true)

    // 乐观更新:添加用户消息 + AI 占位消息
    const tempUserMessage: ChatMessage = {
      message_id: `temp-${Date.now()}`,
      conversation_id: conversationId,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    }
    const tempAssistantMessage: ChatMessage = {
      message_id: `temp-ai-${Date.now()}`,
      conversation_id: conversationId,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
    }
    mutateMessages(
      (prev) => {
        const items = prev?.items ?? []
        return {
          total: items.length + 2,
          items: [...items, tempUserMessage, tempAssistantMessage],
        }
      },
      { revalidate: false },
    )

    try {
      // 构造消息历史
      const messageHistory = [
        ...messages.slice(-10).map(m => ({ role: m.role, content: m.content })),
        { role: 'user', content },
      ]

      // 使用流式 API
      const response = await sendMessageStream(conversationId, {
        messages: messageHistory,
        model: modelConfig.modelId,
        stream: true,
      })

      if (!response.ok) {
        const errorText = await response.text()
        // 尝试解析后端返回的 JSON 错误格式 {"detail":"..."}
        let errorMessage = '请求失败'
        try {
          const parsed = JSON.parse(errorText)
          if (parsed.detail) {
            errorMessage = parsed.detail
          } else if (parsed.message) {
            errorMessage = parsed.message
          } else {
            errorMessage = errorText || '请求失败'
          }
        } catch {
          errorMessage = errorText || '请求失败'
        }
        throw new Error(errorMessage)
      }

      // 处理流式响应
      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      let fullContent = ''

      if (reader) {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          const chunk = decoder.decode(value)
          const lines = chunk.split('\n')

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6)
              if (data === '[DONE]') {
                setStreaming(false)
                continue
              }

              try {
                const parsed = JSON.parse(data)
                if (parsed.choices?.[0]?.delta?.content) {
                  const contentChunk = parsed.choices[0].delta.content
                  fullContent += contentChunk

                  mutateMessages(
                    (prev) => {
                      if (!prev) return prev
                      const items = [...prev.items]
                      const lastMsg = items[items.length - 1]
                      if (lastMsg?.role === 'assistant') {
                        items[items.length - 1] = {
                          ...lastMsg,
                          content: fullContent,
                        }
                      }
                      return { ...prev, items }
                    },
                    { revalidate: false },
                  )
                }
              } catch {
                // 忽略解析错误
              }
            }
          }
        }
      }

      // 流式结束,重新拉取完整消息以保证与服务端一致
      await mutateMessages()
      setStreaming(false)
      setSending(false)
    } catch (error: any) {
      console.error('发送消息失败:', error)
      // 优先显示后端返回的具体错误信息(如额度不足)
      const detail = error?.message || '发送消息失败'
      message.error(detail)
      // 回滚乐观更新
      mutateMessages(
        (prev) => {
          if (!prev) return prev
          return { ...prev, items: prev.items.slice(0, -2) }
        },
        { revalidate: false },
      )
      setStreaming(false)
      setSending(false)
    }
  }

  // 重新生成
  const handleRegenerate = async (messageIndex: number) => {
    const msg = messages[messageIndex]
    if (msg?.role !== 'assistant') return

    const userMessages = messages.filter((m, i) => m.role === 'user' && i < messageIndex)
    if (userMessages.length === 0) return

    mutateMessages(
      (prev) => (prev ? { ...prev, items: prev.items.slice(0, messageIndex) } : prev),
      { revalidate: false },
    )

    const lastUserMessage = userMessages[userMessages.length - 1]
    await handleSendMessage(lastUserMessage.content)
  }

  // 持久化模型选择,刷新后仍然保留
  useEffect(() => {
    saveModelConfig(modelConfig)
  }, [modelConfig])

  return (
    <Layout style={{ height: 'calc(100vh - 56px)', margin: '-20px', background: token.colorBgLayout }}>
      <Sider
        width={SIDEBAR_WIDTH}
        collapsedWidth={0}
        style={{
          background: token.colorBgLayout,
          borderRight: `1px solid ${token.colorBorder}`,
        }}
      >
        <ConversationList
          selectedId={currentConversationId || undefined}
          onSelect={handleSelectConversation}
          onNewChat={handleNewChat}
        />
      </Sider>

      <Layout style={{ background: token.colorBgLayout, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        {/* 顶部标题区域 - 简洁优化 */}
        <div
          style={{
            height: '56px',
            borderBottom: `1px solid ${token.colorBorder}`,
            display: 'flex',
            alignItems: 'center',
            padding: '0 20px',
            background: token.colorBgLayout,
          }}
        >
          <span style={{ color: token.colorText, fontSize: '16px', fontWeight: 500 }}>
            AI 对话
          </span>
        </div>

        <Layout.Content style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
          <MessageList
            messages={messages}
            loading={messagesLoading}
            streaming={streaming}
            onRegenerate={handleRegenerate}
          />
        </Layout.Content>

        <InputArea
          onSend={handleSendMessage}
          disabled={sending && !streaming}
          loading={sending}
          modelConfig={modelConfig}
          onModelChange={setModelConfig}
        />
      </Layout>
    </Layout>
  )
}

export default Chat
