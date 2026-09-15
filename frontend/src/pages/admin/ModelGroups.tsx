import { useState, useEffect } from 'react'
import { useThemeToken } from '@/theme/useThemeToken'
import { useNavigate } from 'react-router-dom'
import { useMessage } from '../../utils/message'
import {
  Table, Button, Tag, Space, Input,
  Popconfirm, Card, Alert, Typography, Popover,
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, SearchOutlined } from '@ant-design/icons'
import { 
  getModelGroups, 
  deleteModelGroup, setModelGroupDefault, unsetModelGroupDefault,
  ModelGroup 
} from '../../api/modelGroups'
import { getModels, ModelMapping } from '../../api/models'
import {
  useDefaultModelGroupWarning,
} from '../../hooks/useDefaultModelGroupWarning'

const { Text } = Typography

interface ModelIdsCellProps {
  modelIds: string[]
  models: ModelMapping[]
  onManage: () => void
}

/**
 * 关联模型单元格：
 * - 0 个：Tag "未关联"
 * - 1-2 个：全部内联 Tag（紧凑，不需要交互）
 * - 3+ 个：首 Tag + 悬浮可搜索 Popover（包含全部模型列表、搜索、复制ID入口）
 */
const ModelIdsCell: React.FC<ModelIdsCellProps> = ({ modelIds, models, onManage }) => {
  const [popoverOpen, setPopoverOpen] = useState(false)
  const [search, setSearch] = useState('')
  const { token } = useThemeToken()

  if (!modelIds.length) {
    return <Tag>未关联</Tag>
  }

  const modelMap = new Map(models.map(m => [m.model_id, m]))
  const items = modelIds
    .map(id => modelMap.get(id))
    .filter(Boolean) as ModelMapping[]

  const filtered = search
    ? items.filter(m =>
        (m.display_name || m.model_id || '').toLowerCase().includes(search.toLowerCase()) ||
        m.model_id.toLowerCase().includes(search.toLowerCase())
      )
    : items

  const firstName = items[0]?.display_name || items[0]?.model_id || ''

  const popoverContent = (
    <div style={{ width: 340 }}>
      <Input
        prefix={<SearchOutlined style={{ color: token.colorTextDescription }} />}
        placeholder="搜索模型名称或 ID"
        value={search}
        onChange={e => setSearch(e.target.value)}
        allowClear
        style={{ marginBottom: 8 }}
        autoFocus
        onClick={e => e.stopPropagation()}
      />
      <div style={{ maxHeight: 280, overflow: 'auto' }}>
        {filtered.length === 0 ? (
          <div style={{ color: token.colorTextDescription, textAlign: 'center', padding: '16px 0' }}>
            无匹配结果
          </div>
        ) : (
          filtered.map(m => (
            <div
              key={m.model_id}
              style={{
                padding: '6px 4px',
                borderBottom: `1px solid ${token.colorBorderSecondary}`,
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}
            >
              <Text style={{ flex: 1 }}>{m.display_name || m.model_id}</Text>
              <Text type="secondary" style={{ fontSize: 12 }} copyable={{ text: m.model_id }}>
                {m.model_id.length > 16 ? m.model_id.slice(0, 16) + '…' : m.model_id}
              </Text>
            </div>
          ))
        )}
      </div>
      <Button
        type="link"
        onClick={() => { setPopoverOpen(false); setSearch(''); onManage() }}
        style={{ padding: '4px 0', marginTop: 4 }}
      >
        管理模型 →
      </Button>
    </div>
  )

  // 3+ 个模型时：首 Tag + 可点击的 "共 N 个" chip
  if (items.length >= 3) {
    return (
      <Popover
        content={popoverContent}
        trigger="hover"
        open={popoverOpen}
        onOpenChange={setPopoverOpen}
        destroyTooltipOnHide={{ keepParent: false }}
        placement="bottomLeft"
        overlayStyle={{ width: 360 }}
      >
        <Tag color="blue">{firstName}</Tag>
        <a
          style={{ color: token.colorPrimary, fontSize: 12, cursor: 'pointer', userSelect: 'none' }}
          onClick={e => e.stopPropagation()}
        >
          共 {items.length} 个
        </a>
      </Popover>
    )
  }

  // 1-2 个模型：全部内联
  return (
    <>
      {items.map((m, i) => (
        <Tag key={i} color="blue">{m.display_name || m.model_id}</Tag>
      ))}
    </>
  )
}

const ModelGroups: React.FC = () => {
  const [loading, setLoading] = useState(false)
  const [groups, setGroups] = useState<ModelGroup[]>([])
  const [models, setModels] = useState<ModelMapping[]>([])
  const message = useMessage()
  const { token, isDark } = useThemeToken()
  const navigate = useNavigate()
  const { needsAttention, refresh } = useDefaultModelGroupWarning()

  useEffect(() => {
    fetchGroups()
    fetchModels()
  }, [])

  const fetchGroups = async () => {
    setLoading(true)
    try {
      const res = await getModelGroups()
      setGroups(res.items || [])
    } catch (error) {
      message.error('获取分组失败')
    } finally {
      setLoading(false)
    }
  }

  const fetchModels = async () => {
    try {
      const res = await getModels()
      setModels(res.items || [])
    } catch (error) {
      console.error('获取模型失败', error)
    }
  }


  const handleDelete = async (groupId: string) => {
    try {
      await deleteModelGroup(groupId)
      message.success('删除成功')
      fetchGroups()
      refresh()
    } catch (error: any) {
      const detail = error?.response?.data?.detail
      if (typeof detail === 'string' && detail.includes('该分组已绑定')) {
        message.error('该分组已绑定模型，请先解除绑定后再删除')
      } else {
        message.error('删除失败')
      }
    }
  }

  const handleSetDefault = async (groupId: string) => {
    try {
      await setModelGroupDefault(groupId)
      message.success('已设为默认分组')
      fetchGroups()
      refresh()
    } catch (error) {
      message.error('设置失败')
    }
  }

  const handleUnsetDefault = async (groupId: string) => {
    try {
      await unsetModelGroupDefault(groupId)
      message.success('已取消默认分组')
      fetchGroups()
      refresh()
    } catch (error) {
      message.error('取消失败')
    }
  }

  const noActiveDefault = needsAttention

  const columns = [
    {
      title: '分组ID',
      dataIndex: 'group_id',
      key: 'group_id',
      width: 180
    },
    {
      title: '分组名称',
      dataIndex: 'name',
      key: 'name',
      width: 150
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      width: 200
    },
    {
      title: '关联模型',
      dataIndex: 'model_ids',
      key: 'model_ids',
      width: 250,
      render: (_: string[], record: ModelGroup) => (
        <ModelIdsCell
          modelIds={record.model_ids}
          models={models}
          onManage={() => navigate(`/admin/model-groups/${record.group_id}/edit`)}
        />
      )
    },
    {
      title: '默认分组',
      dataIndex: 'is_default',
      key: 'is_default',
      width: 100,
      render: (isDefault: number) => (
        isDefault === 1 ? <Tag color="green">是</Tag> : <Tag>否</Tag>
      )
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (status: string) => (
        <Tag color={status === 'active' ? 'green' : 'red'}>
          {status === 'active' ? '启用' : '禁用'}
        </Tag>
      )
    },
    {
      title: '操作',
      key: 'action',
      width: 220,
      fixed: 'right' as const,
      render: (_: any, record: ModelGroup) => {
        const isDefault = record.is_default === 1
        const isActive = record.status === 'active'
        const useDanger = noActiveDefault && !isDefault && isActive

        return (
          <Space>
            {isActive && (
              isDefault ? (
                <Popconfirm
                  title="确认取消默认分组？"
                  onConfirm={() => handleUnsetDefault(record.group_id)}
                >
                  <Button type="text" danger>
                    取消默认
                  </Button>
                </Popconfirm>
              ) : (
                <Button
                  type="text"
                  danger={useDanger}
                  onClick={() => handleSetDefault(record.group_id)}
                >
                  设为默认
                </Button>
              )
            )}
            <Button
              type="text"
              icon={<EditOutlined />}
              onClick={() => navigate(`/admin/model-groups/${record.group_id}/edit`)}
              style={{ color: '#3B82F6' }}
            >
              编辑
            </Button>
            <Popconfirm
              title="确认删除此分组？"
              onConfirm={() => handleDelete(record.group_id)}
            >
              <Button type="text" danger icon={<DeleteOutlined />}>
                删除
              </Button>
            </Popconfirm>
          </Space>
        )
      }
    }
  ]

  return (
    <div style={{ padding: '24px' }}>
      {noActiveDefault && (
        <Alert
          banner
          type="warning"
          showIcon
          message={
            <span>
              缺少已启用的默认模型分组，新用户将无法正常使用 API Key。
              {groups.length === 0 ? (
                <Button type="link" size="small" onClick={() => navigate('/admin/model-groups/new')}>
                  立即创建分组
                </Button>
              ) : (
                <span style={{ marginLeft: 8, color: 'rgba(0,0,0,0.45)' }}>
                  请在下方将一个分组设为默认。
                </span>
              )}
            </span>
          }
          style={{ marginBottom: 12, borderRadius: 8 }}
        />
      )}

      <Card 
        title="模型分组管理" 
        extra={
          <Button 
            type="primary" 
            icon={<PlusOutlined />} 
            onClick={() => navigate('/admin/model-groups/new')}
          >
            新建分组
          </Button>
        }
      >
        <Table
          columns={columns}
          dataSource={groups}
          rowKey="group_id"
          loading={loading}
          pagination={false}
          scroll={{ x: 'max-content', y: 'calc(100vh - 440px)' }}
        />
      </Card>

    </div>
  )
}

export default ModelGroups
