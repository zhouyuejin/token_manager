import { useState, useEffect } from 'react'
import { Select, Spin, Empty } from 'antd'
import { getAvailableModels, ModelGroup } from '../../api/chat'

interface ModelSelectorProps {
  value?: {
    providerId?: string
    modelId?: string
  }
  onChange?: (value: { providerId?: string; modelId?: string }) => void
  disabled?: boolean
}

const ModelSelector: React.FC<ModelSelectorProps> = ({
  value,
  onChange,
  disabled = false,
}) => {
  const [loading, setLoading] = useState(false)
  const [modelGroups, setModelGroups] = useState<ModelGroup[]>([])
  const [selectedProviderId, setSelectedProviderId] = useState<string | undefined>(value?.providerId)
  const [selectedModelId, setSelectedModelId] = useState<string | undefined>(value?.modelId)

  useEffect(() => {
    fetchModels()
  }, [])

  const fetchModels = async () => {
    setLoading(true)
    try {
      const res = await getAvailableModels()
      setModelGroups(res.groups)
      
      // 如果有分组，根据后端数据结构处理：
      // 后端返回: providers = [{provider_id, name, type}], models = [{model_id, display_name, provider_model}]
      // 前端期望: providers = [{provider_id, name, type, models: [...]}]
      if (res.groups.length > 0) {
        const firstGroup = res.groups[0]
        
        // 优先使用 providers 字段（如果存在且有 models）
        if (firstGroup.providers && firstGroup.providers.length > 0) {
          const firstProvider = firstGroup.providers[0]
          // 尝试从 provider 获取 models（前端期望的结构）
          const providerModels = (firstProvider as any).models
          if (providerModels && providerModels.length > 0) {
            const firstModel = providerModels[0]
            if (firstModel && !value?.providerId && !value?.modelId) {
              setSelectedProviderId(firstProvider.provider_id)
              setSelectedModelId(firstModel.model_id)
              onChange?.({
                providerId: firstProvider.provider_id,
                modelId: firstModel.model_id,
              })
            }
          }
        } else if (firstGroup.models && firstGroup.models.length > 0) {
          // 使用 group 级别的 models（后端返回的结构）
          const firstModel = firstGroup.models[0]
          if (firstModel && !value?.providerId && !value?.modelId) {
            // 从 providers 中获取第一个作为默认值
            const firstProvider = firstGroup.providers?.[0]
            setSelectedProviderId(firstProvider?.provider_id)
            setSelectedModelId(firstModel.model_id)
            onChange?.({
              providerId: firstProvider?.provider_id,
              modelId: firstModel.model_id,
            })
          }
        }
      }
    } catch (error) {
      console.error('获取模型列表失败:', error)
    } finally {
      setLoading(false)
    }
  }

  // 获取当前供应商的模型列表
  const getCurrentProviderModels = () => {
    // 优先从 provider 级别获取
    for (const group of modelGroups) {
      if (group.providers) {
        const provider = group.providers.find(p => p.provider_id === selectedProviderId)
        if (provider) {
          const providerModels = (provider as any).models
          if (providerModels) return providerModels
        }
      }
    }
    // 降级：从 group 级别获取
    for (const group of modelGroups) {
      if (group.models) return group.models
    }
    return []
  }

  // 处理供应商变化
  const handleProviderChange = (providerId: string | null) => {
    setSelectedProviderId(providerId || undefined)
    
    // 优先从 provider 级别获取模型
    let providerModels: any[] = []
    for (const group of modelGroups) {
      if (group.providers) {
        const provider = group.providers.find(p => p.provider_id === providerId)
        if (provider) {
          providerModels = (provider as any).models || []
          break
        }
      }
    }
    // 降级：从 group 级别过滤
    if (providerModels.length === 0) {
      for (const group of modelGroups) {
        if (group.models) {
          providerModels = group.models
          break
        }
      }
    }
    
    if (providerModels.length > 0) {
      setSelectedModelId(providerModels[0].model_id)
      onChange?.({
        providerId: providerId || undefined,
        modelId: providerModels[0].model_id,
      })
    } else {
      setSelectedModelId(undefined)
      onChange?.({
        providerId: providerId || undefined,
        modelId: undefined,
      })
    }
  }

  // 处理模型变化
  const handleModelChange = (modelId: string | null) => {
    setSelectedModelId(modelId || undefined)
    onChange?.({
      providerId: selectedProviderId,
      modelId: modelId || undefined,
    })
  }

  // 构建供应商选项 - 兼容两种结构
  const getProviderOptions = () => {
    const options: { label: string; value: string; group: string }[] = []
    for (const group of modelGroups) {
      if (group.providers) {
        for (const provider of group.providers) {
          options.push({
            label: `${provider.name} (${group.name})`,
            value: provider.provider_id,
            group: group.name,
          })
        }
      }
    }
    return options
  }

  const providerOptions = getProviderOptions()
  const modelOptions = getCurrentProviderModels().map(model => ({
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
    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
      <Select
        style={{ width: 160 }}
        placeholder="选择供应商"
        value={selectedProviderId}
        onChange={handleProviderChange}
        options={providerOptions}
        disabled={disabled}
        showSearch
        optionFilterProp="label"
      />
      <Select
        style={{ width: 180 }}
        placeholder="选择模型"
        value={selectedModelId}
        onChange={handleModelChange}
        options={modelOptions}
        disabled={disabled || !selectedProviderId}
        showSearch
        optionFilterProp="label"
      />
    </div>
  )
}

export default ModelSelector
