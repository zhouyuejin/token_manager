import { useState, useEffect } from 'react'
import { Select, Spin, Empty } from 'antd'
import { getAvailableModels, ModelGroup } from '../../api/chat'

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

  const fetchModels = async () => {
    setLoading(true)
    try {
      const res = await getAvailableModels()
      setModelGroups(res.groups)

      // 默认选中第一个可用模型,免得用户每次都要点
      if (res.groups.length > 0 && !value?.modelId) {
        for (const group of res.groups) {
          if (group.models && group.models.length > 0) {
            const firstModel = group.models[0]
            setSelectedModelId(firstModel.model_id)
            onChange?.({ modelId: firstModel.model_id })
            break
          }
        }
      }
    } catch (error) {
      console.error('获取模型列表失败:', error)
    } finally {
      setLoading(false)
    }
  }

  // 聚合所有分组下的模型,按 model_id 去重
  const getAllModels = () => {
    const seen = new Set<string>()
    const result: { model_id: string; display_name?: string; provider_model?: string }[] = []
    for (const group of modelGroups) {
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
