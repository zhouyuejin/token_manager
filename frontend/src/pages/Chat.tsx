import { useState, useEffect, useCallback } from 'react'
import { Layout, Button, message } from 'antd'
import ConversationList from '../components/Chat/ConversationList'
import MessageList from '../components/Chat/MessageList'
import InputArea from '../components/Chat/InputArea'
import {
  createConversation,
  getMessages,
  sendMessageStream,
  ChatConversation,
  ChatMessage,
} from '../api/chat'

const { Sider } = Layout

const SIDEBAR_WIDTH = 260

const Chat: React.FC = () => {
  const [_conversations, setConversations] = useState<ChatConversation[]>([])
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [sending, setSending] = useState(false)
  const [streaming, setStreaming] = useState(false)
  
  // 模型配置
  const [modelConfig, setModelConfig] = useState<{
    providerId?: string
    modelId?: string
  }>({})

  // 加载对话消息
  const loadMessages = useCallback(async (conversationId: string) => {
    setLoading(true)
    try {
      const res = await getMessages(conversationId, 1, 100)
      setMessages(res.items)
    } catch (error) {
      console.error('获取消息失败:', error)
      message.error('加载消息失败')
    } finally {
      setLoading(false)
    }
  }, [])

  // 选择对话
  const handleSelectConversation = async (conversationId: string) => {
    setCurrentConversationId(conversationId)
    await loadMessages(conversationId)
  }

  // 新建对话,返回新创建的会话 ID(避免在调用方依赖尚未更新的 state)
  const handleNewChat = async (): Promise<string | null> => {
    try {
      const res = await createConversation({
        model: modelConfig.modelId,
        provider_id: modelConfig.providerId,
      })
      setCurrentConversationId(res.conversation_id)
      setMessages([])
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

    // 添加用户消息到列表
    const tempUserMessage: ChatMessage = {
      message_id: `temp-${Date.now()}`,
      conversation_id: conversationId,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    }
    setMessages(prev => [...prev, tempUserMessage])

    // 添加一个空的 AI 消息占位
    const tempAssistantMessage: ChatMessage = {
      message_id: `temp-ai-${Date.now()}`,
      conversation_id: conversationId,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
    }
    setMessages(prev => [...prev, tempAssistantMessage])

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
        provider_id: modelConfig.providerId,
        stream: true,
      })

      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(errorText || '请求失败')
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

                  setMessages((prev: ChatMessage[]) => {
                    const newMessages = [...prev]
                    const lastMsg = newMessages[newMessages.length - 1]
                    if (lastMsg?.role === 'assistant') {
                      lastMsg.content = fullContent
                    }
                    return newMessages
                  })
                }
              } catch {
                // 忽略解析错误
              }
            }
          }
        }
      }

      // 流式结束，重新获取完整消息
      await loadMessages(conversationId)
      setStreaming(false)
      setSending(false)
    } catch (error) {
      console.error('发送消息失败:', error)
      message.error('发送消息失败')
      setMessages(prev => prev.slice(0, -2))
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

    setMessages(prev => prev.slice(0, messageIndex))

    const lastUserMessage = userMessages[userMessages.length - 1]
    await handleSendMessage(lastUserMessage.content)
  }

  // 监听对话变化
  useEffect(() => {
    if (currentConversationId) {
      loadMessages(currentConversationId)
    }
  }, [currentConversationId, loadMessages])

  return (
    <Layout style={{ height: 'calc(100% + 40px)', margin: '-20px', background: '#1a1a1a' }}>
      <Sider
        width={SIDEBAR_WIDTH}
        collapsedWidth={0}
        style={{
          background: '#1a1a1a',
          borderRight: '1px solid #303030',
        }}
      >
        <ConversationList
          selectedId={currentConversationId || undefined}
          onSelect={handleSelectConversation}
          onNewChat={handleNewChat}
        />
      </Sider>

      <Layout style={{ background: '#1a1a1a' }}>
        {/* 顶部标题区域 - 简洁优化 */}
        <div
          style={{
            height: '56px',
            borderBottom: '1px solid #303030',
            display: 'flex',
            alignItems: 'center',
            padding: '0 20px',
            background: '#1a1a1a',
          }}
        >
          <span style={{ color: '#e8e8e8', fontSize: '16px', fontWeight: 500 }}>
            AI 对话
          </span>
        </div>

        <Layout.Content style={{ overflow: 'hidden' }}>
          <MessageList
            messages={messages}
            loading={loading}
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
