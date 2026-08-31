import { useState, useRef, useEffect } from 'react'
import { Button, Upload, message } from 'antd'
import { SendOutlined, AudioOutlined, PaperClipOutlined, LoadingOutlined } from '@ant-design/icons'
import ModelSelector from './ModelSelector'

interface InputAreaProps {
  onSend: (content: string, files?: File[]) => void
  disabled?: boolean
  loading?: boolean
  modelConfig?: {
    providerId?: string
    modelId?: string
  }
  onModelChange?: (config: { providerId?: string; modelId?: string }) => void
}

const InputArea: React.FC<InputAreaProps> = ({
  onSend,
  disabled = false,
  loading = false,
  modelConfig,
  onModelChange,
}) => {
  const [inputValue, setInputValue] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 150)}px`
    }
  }, [inputValue])

  const handleSend = () => {
    if (!inputValue.trim() && files.length === 0) {
      message.warning('请输入内容')
      return
    }
    
    if (disabled || loading) return

    onSend(inputValue.trim(), files)
    setInputValue('')
    setFiles([])
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleBeforeUpload = (file: File) => {
    const isImage = file.type.startsWith('image/')
    if (!isImage) {
      message.error('只能上传图片文件')
      return false
    }
    const isLt5M = file.size / 1024 / 1024 < 5
    if (!isLt5M) {
      message.error('图片大小不能超过 5MB')
      return false
    }
    setFiles(prev => [...prev, file])
    return false
  }

  return (
    <div style={{
      borderTop: '1px solid #303030',
      background: '#1a1a1a',
      padding: '12px 16px',
    }}>
      <div style={{ marginBottom: '12px' }}>
        <ModelSelector
          value={modelConfig}
          onChange={onModelChange}
          disabled={disabled}
        />
      </div>

      <div style={{
        display: 'flex',
        alignItems: 'flex-end',
        gap: '8px',
        background: '#262626',
        borderRadius: '8px',
        border: '1px solid #404040',
        padding: '8px 12px',
      }}>
        <Upload
          beforeUpload={handleBeforeUpload}
          fileList={[]}
          showUploadList={false}
          multiple
          accept="image/*"
          disabled={disabled}
        >
          <Button
            type="text"
            icon={<PaperClipOutlined />}
            disabled={disabled}
            style={{ color: '#8b8b8b' }}
          />
        </Upload>

        <textarea
          ref={textareaRef}
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入消息... (Shift+Enter 换行)"
          disabled={disabled}
          rows={1}
          style={{
            flex: 1,
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: '#e0e0e0',
            fontSize: '14px',
            lineHeight: '1.5',
            resize: 'none',
            minHeight: '24px',
            maxHeight: '150px',
          }}
        />

        <Button
          type="text"
          icon={<AudioOutlined />}
          disabled={disabled}
          style={{ color: '#8b8b8b' }}
          title="语音输入（暂不支持）"
        />

        <Button
          type="primary"
          icon={loading ? <LoadingOutlined /> : <SendOutlined />}
          onClick={handleSend}
          disabled={disabled || (!inputValue.trim() && files.length === 0)}
          style={{
            background: inputValue.trim() || files.length > 0 
              ? 'linear-gradient(135deg, #3B82F6 0%, #2563EB 100%)' 
              : '#404040',
            border: 'none',
          }}
        />
      </div>

      {files.length > 0 && (
        <div style={{ marginTop: '8px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {files.map((file, index) => (
            <div
              key={index}
              style={{
                position: 'relative',
                width: '60px',
                height: '60px',
                borderRadius: '4px',
                overflow: 'hidden',
              }}
            >
              <img
                src={URL.createObjectURL(file)}
                alt={file.name}
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
              <Button
                type="text"
                size="small"
                danger
                onClick={() => setFiles(prev => prev.filter((_, i) => i !== index))}
                style={{
                  position: 'absolute',
                  top: 0,
                  right: 0,
                  padding: '2px 4px',
                  background: 'rgba(0,0,0,0.5)',
                }}
              >
                ×
              </Button>
            </div>
          ))}
        </div>
      )}

      <div style={{ 
        textAlign: 'center', 
        color: '#666', 
        fontSize: '12px',
        marginTop: '8px' 
      }}>
        模型输出可能包含错误信息，请核实重要内容
      </div>
    </div>
  )
}

export default InputArea
