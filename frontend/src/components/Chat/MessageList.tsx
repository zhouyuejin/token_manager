import { useEffect, useRef } from 'react'
import { useThemeToken } from '@/theme/useThemeToken'
import { Spin, Empty, Avatar } from 'antd'
import { UserOutlined, RobotOutlined, CopyOutlined, ReloadOutlined } from '@ant-design/icons'
import { XMarkdown } from '@ant-design/x-markdown'
import { ChatMessage } from '../../api/chat'
import { stripThinkTags } from '../../utils/thinkTag'
import dayjs from 'dayjs'

interface MessageListProps {
  messages: ChatMessage[]
  loading?: boolean
  streaming?: boolean
  onRegenerate?: (messageIndex: number) => void
}

const MessageList: React.FC<MessageListProps> = ({
  messages,
  loading = false,
  streaming = false,
  onRegenerate,
}) => {
  const { token, isDark } = useThemeToken()
  const containerRef = useRef<HTMLDivElement>(null)

  // 自动滚动到底部
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [messages, loading, streaming])

  // 复制消息内容
  const handleCopy = async (content: string) => {
    try {
      await navigator.clipboard.writeText(content)
    } catch (error) {
      console.error('复制失败:', error)
    }
  }

  if (loading && messages.length === 0) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
        <Spin size="large">加载中...</Spin>
      </div>
    )
  }

  if (messages.length === 0) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="开始一段新对话吧"
        />
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      style={{
        height: '100%',
        overflow: 'auto',
        padding: '20px',
      }}
    >
      {messages.map((msg, index) => {
        const isUser = msg.role === 'user'
        const isLast = index === messages.length - 1
        // 只对"当前正在流式输出的最后一条 assistant 消息"启用 XMarkdown 的增量渲染
        // 否则传 streaming 会触发未完成块的额外处理,反而抖动
        const isStreamingMsg = streaming && isLast && !isUser
        const displayContent = stripThinkTags(msg.content)
        return (
          <div
            key={msg.message_id || index}
            style={{
              display: 'flex',
              flexDirection: isUser ? 'row-reverse' : 'row',
              alignItems: 'flex-start',
              gap: '12px',
              marginBottom: '16px',
            }}
          >
            {/* 头像 */}
            <Avatar
              icon={isUser ? <UserOutlined /> : <RobotOutlined />}
              style={{
                background: isUser ? '#3B82F6' : '#10B981',
                flexShrink: 0,
              }}
            />

            {/* 消息内容 */}
            <div
              style={{
                maxWidth: '70%',
                padding: '12px 16px',
                borderRadius: '12px',
                background: isUser ? token.colorPrimary : (isDark ? '#2a2a2a' : '#F1F5F9'),
                color: isDark ? '#e0e0e0' : '#1E293B',
                wordBreak: 'break-word',
                // 不再设置 whiteSpace: pre-wrap —— XMarkdown 自己处理空白与换行
              }}
            >
              <XMarkdown
                content={displayContent}
                className="chat-md"
                style={{ color: 'inherit' }}
                streaming={
                  isStreamingMsg
                    ? { hasNextChunk: true, tail: { content: '▋' } }
                    : undefined
                }
              />

              {/* 底部操作栏和时间 */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginTop: '8px',
                  fontSize: '12px',
                  color: 'rgba(255,255,255,0.5)',
                }}
              >
                <span>{dayjs.utc(msg.created_at).local().format('HH:mm')}</span>

                {!isUser && (
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <CopyOutlined
                      style={{ cursor: 'pointer', opacity: 0.6 }}
                      onClick={() => handleCopy(msg.content)}
                      title="复制"
                    />
                    {onRegenerate && (
                      <ReloadOutlined
                        style={{ cursor: 'pointer', opacity: 0.6 }}
                        onClick={() => onRegenerate(index)}
                        title="重新生成"
                      />
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )
      })}

      {streaming && (
        <div style={{ padding: '12px', opacity: 0.6, display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Spin size="small" />
          <span>AI 正在思考...</span>
        </div>
      )}
    </div>
  )
}

export default MessageList
