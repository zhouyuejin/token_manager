import { useState, useEffect, useCallback, memo } from 'react'
import { List, Button, Empty, Spin, Avatar, Dropdown, App, message } from 'antd'
import { PlusOutlined, DeleteOutlined, MoreOutlined, MessageOutlined } from '@ant-design/icons'
import type { MenuProps } from 'antd'
import { getConversations, deleteConversation, ChatConversation } from '../../api/chat'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import 'dayjs/locale/zh-cn'

dayjs.extend(relativeTime)
dayjs.locale('zh-cn')

interface ConversationListProps {
  selectedId?: string
  onSelect: (id: string) => void
  onNewChat: () => void
}

interface ConversationItemProps {
  conv: ChatConversation
  selected: boolean
  deleting: boolean
  onSelect: (id: string) => void
  onDelete: (e: React.MouseEvent | React.KeyboardEvent, id: string) => void
}

// 抽出单个会话项并 memo
const ConversationItem = memo(function ConversationItem({
  conv,
  selected,
  deleting,
  onSelect,
  onDelete,
}: ConversationItemProps) {
  const menuItems: MenuProps['items'] = [
    {
      key: 'delete',
      icon: <DeleteOutlined />,
      label: '删除对话',
      danger: true,
      onClick: ({ domEvent }) => onDelete(domEvent, conv.conversation_id),
    },
  ]

  const title = conv.title || '新对话'

  return (
    <List.Item
      onClick={() => onSelect(conv.conversation_id)}
      style={{
        padding: '12px 12px',
        cursor: 'pointer',
        background: selected ? 'rgba(59, 130, 246, 0.15)' : 'transparent',
        borderLeft: selected ? '3px solid #3B82F6' : '3px solid transparent',
        transition: 'all 0.2s',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', width: '100%', minWidth: 0 }}>
        {/* 头像 */}
        <Avatar
          size={38}
          style={{
            background: selected ? '#3B82F6' : '#424242',
            flexShrink: 0,
          }}
          icon={<MessageOutlined />}
        />
        
        {/* 标题和时间 - 增加宽度 */}
        <div style={{ marginLeft: '12px', flex: 1, minWidth: 0 }}>
          <div 
            style={{
              color: selected ? '#e0e0e0' : '#a0a0a0',
              fontWeight: selected ? 500 : 400,
              fontSize: '14px',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {title}
          </div>
          <div style={{ color: '#666', fontSize: '12px', marginTop: '2px' }}>
            {dayjs(conv.updated_at).fromNow()}
          </div>
        </div>

        {/* 更多按钮 */}
        <Dropdown
          menu={{ items: menuItems }}
          trigger={['click']}
          placement="bottomRight"
        >
          <Button
            type="text"
            size="small"
            icon={<MoreOutlined />}
            onClick={(e) => e.stopPropagation()}
            loading={deleting}
            style={{ color: '#8b8b8b', flexShrink: 0, marginLeft: '8px' }}
          />
        </Dropdown>
      </div>
    </List.Item>
  )
})

const ConversationList: React.FC<ConversationListProps> = ({
  selectedId,
  onSelect,
  onNewChat,
}) => {
  const [conversations, setConversations] = useState<ChatConversation[]>([])
  const [loading, setLoading] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)
  const { modal } = App.useApp()

  const fetchConversations = async () => {
    setLoading(true)
    try {
      const res = await getConversations(1, 50)
      setConversations(res.items)
    } catch (error) {
      console.error('获取对话列表失败:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchConversations()
  }, [])

  const handleDelete = useCallback(
    async (e: React.MouseEvent | React.KeyboardEvent, conversationId: string) => {
      e.stopPropagation()
      modal.confirm({
        title: '确认删除',
        content: '确定要删除这个对话吗？删除后无法恢复。',
        okText: '删除',
        cancelText: '取消',
        onOk: async () => {
          setDeleting(conversationId)
          try {
            await deleteConversation(conversationId)
            message.success('删除成功')
            setConversations(prev => prev.filter(c => c.conversation_id !== conversationId))
            if (selectedId === conversationId) {
              onNewChat()
            }
          } catch (error) {
            message.error('删除失败')
          } finally {
            setDeleting(null)
          }
        },
      })
    },
    [modal, selectedId, onNewChat]
  )

  return (
    <div className="conversation-list" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* 标题区域 */}
      <div 
        style={{ 
          padding: '20px 16px 16px', 
          borderBottom: '1px solid #303030',
          background: 'linear-gradient(180deg, #222 0%, #1a1a1a 100%)',
        }}
      >
        <span style={{ 
          color: '#f0f0f0', 
          fontSize: '16px', 
          fontWeight: 600,
        }}>
          历史对话
        </span>
      </div>

      {/* 新建对话按钮 */}
      <div style={{ padding: '12px 16px', borderBottom: '1px solid #303030' }}>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          block
          onClick={onNewChat}
          style={{
            background: 'linear-gradient(135deg, #3B82F6 0%, #2563EB 100%)',
            border: 'none',
          }}
        >
          新建对话
        </Button>
      </div>

      {/* 对话列表 */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '20px' }}>
            <Spin />
          </div>
        ) : conversations.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="暂无对话"
            style={{ marginTop: '40px' }}
          />
        ) : (
          <List
            dataSource={conversations}
            renderItem={(conv) => (
              <ConversationItem
                key={conv.conversation_id}
                conv={conv}
                selected={selectedId === conv.conversation_id}
                deleting={deleting === conv.conversation_id}
                onSelect={onSelect}
                onDelete={handleDelete}
              />
            )}
          />
        )}
      </div>
    </div>
  )
}

export default ConversationList
