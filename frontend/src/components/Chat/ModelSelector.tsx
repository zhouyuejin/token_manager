import { useState, useEffect } from 'react'
import { Select, Spin, Empty } from 'antd'
import { getAvailableModels, ModelGroup } from '../../api/chat'
import { pickInitialModelId } from '../../utils/chatStorage'

interface ModelSelectorProps {
  value?: {
    modelId?: string
  }
  onChange?: (value: { modelId?: string }) => void
  disabled?: boolean
}

const ModelSelector: React.FC<ModelSelectorProps> = ({
  value,
  onChange,
  disabled = false,
}) => {
  const [loading, setLoading] = useState(false)
  const [modelGroups, setModelGroups] = useState<ModelGroup[]>([])
  const [selectedModelId, setSelectedModelId] = useState<string | undefined>(value?.modelId)

  useEffect(() => {
    fetchModels()
  }, [])

  // 父级纠正（如 logout/login 触发 modelConfig 重置）能回流到 Select
  useEffect(() => {
    setSelectedModelId(value?.modelId)
  }, [value?.modelId])

  const fetchModels = async () => {
    setLoading(true)
    try {
      const res = await getAvailableModels()
      setModelGroups(res.groups)

      // 校验持久化的 modelId 是否对当前用户仍可用。
      // localStorage 是全局 key,跨用户/跨权限变更后会留下陈旧值,
      // 不在可用集就回退到第一个,并通过 onChange 覆盖存储。
      if (res.groups.length > 0) {
        const availableIds = getAllModels(res.groups).map((m) => m.model_id)
        const initial = pickInitialModelId(value?.modelId, availableIds)
        if (initial !== value?.modelId) {
          setSelectedModelId(initial)
          onChange?.({ modelId: initial })
        }
      }
    } catch (error) {
      console.error('获取模型列表失败:', error)
    } finally {
      setLoading(false)
    }
  }

  // 聚合所有分组下的模型,按 model_id 去重
  const getAllModels = (groups: ModelGroup[] = modelGroups) => {
    const seen = new Set<string>()
    const result: { model_id: string; display_name?: string; provider_model?: string }[] = []
    for (const group of groups) {
      if (!group.models) continue
      for (const m of group.models) {
        if (seen.has(m.model_id)) continue
        seen.add(m.model_id)
        result.push(m)
      }
    }
    return result
  }

  const handleModelChange = (modelId: string | null) => {
    setSelectedModelId(modelId || undefined)
    onChange?.({ modelId: modelId || undefined })
  }

  const modelOptions = getAllModels().map(model => ({
    label: model.display_name || model.provider_model,
    value: model.model_id,
  }))

  if (loading) {
    return <Spin size="small" />
  }

  if (modelGroups.length === 0) {
    return <Empty description="暂无可用模型" />
  }

  return (
    <Select
      style={{ width: 240 }}
      placeholder="选择模型"
      value={selectedModelId}
      onChange={handleModelChange}
      options={modelOptions}
      disabled={disabled}
      showSearch
      optionFilterProp="label"
    />
  )
}

export default ModelSelector
