import { useState, useEffect, useMemo } from 'react'
import { useThemeToken } from '@/theme/useThemeToken'
import { Row, Col, Card, Statistic, DatePicker, Typography, Empty, Tooltip } from 'antd'
import { 
  UserOutlined, 
  CloudServerOutlined, 
  ApiOutlined,
  ThunderboltOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  BarChartOutlined,
  DollarOutlined,
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import dayjs from 'dayjs'
import { getAdminStats, AdminStats } from '../api/admin'

const { RangePicker } = DatePicker
const { Text } = Typography

interface SystemStats {
  total_users?: number
  active_users?: number
  total_api_keys?: number
  active_api_keys?: number
  total_providers?: number
  active_providers?: number
}

// 颜色配置
const CHART_COLORS = [
  '#3B82F6', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899',
  '#06B6D4', '#84CC16', '#F97316', '#6366F1', '#14B8A6'
]

// 用户分布只取前 N 名，剩余折叠为"其他"——避免用户多了之后图例/切片不可读
const TOP_USERS_DISPLAY = 10

const AdminDashboard: React.FC = () => {
  const { token, isDark } = useThemeToken()
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [systemStats, setSystemStats] = useState<SystemStats>({})
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs]>([
    dayjs().subtract(7, 'day'),
    dayjs()
  ])

  useEffect(() => {
    fetchData()
  }, [dateRange])

  const fetchData = async () => {
    setLoading(true)
    try {
      const statsParams = {
        start_date: dateRange[0].format('YYYY-MM-DD'),
        end_date: dateRange[1].format('YYYY-MM-DD'),
      }
      
      const statsData = await getAdminStats(statsParams)
      setStats(statsData)
      
      setSystemStats({
        total_users: statsData.by_user?.length || 0,
        total_api_keys: 0,
        total_providers: statsData.by_provider?.length || 0,
      })
    } catch (error) {
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  // 计算总费用
  const totalCost = useMemo(() => {
    if (!stats?.by_model) return 0
    return stats.by_model.reduce((sum, item) => sum + (item.cost || 0), 0)
  }, [stats, isDark, token])
  const hasUsage = (stats?.by_model?.length || 0) > 0
  // 当前查询覆盖的天数（>=1，避免除 0）；用于把周期内成本折合成月预估
  const dayCount = Math.max(1, dateRange[1].diff(dateRange[0], 'day') + 1)
  const monthlyCost = totalCost * (30 / dayCount)

  // 获取模型显示名称
  const getModelDisplayName = (model: string, displayName?: string) => {
    return displayName || model
  }

  // ========== 用户分布横向条形图配置（Top N + 其他折叠） ==========
  const userBarOption = useMemo(() => {
    if (!stats?.by_user?.length) return null

    const totalTokens = stats.by_user.reduce((sum, u) => sum + u.tokens, 0)
    const sorted = [...stats.by_user].sort((a, b) => b.tokens - a.tokens)
    const head = sorted.slice(0, TOP_USERS_DISPLAY)
    const rest = sorted.slice(TOP_USERS_DISPLAY)
    const restTokens = rest.reduce((sum, u) => sum + u.tokens, 0)

    const labels: string[] = head.map(u => u.username || u.user_id)
    const tokens: number[] = head.map(u => u.tokens)
    if (rest.length > 0) {
      labels.push(`其他（${rest.length} 人）`)
      tokens.push(restTokens)
    }

    return {
     tooltip: {
        trigger: 'axis',
       backgroundColor: isDark ? 'rgba(17, 24, 39, 0.9)' : 'rgba(255, 255, 255, 0.95)',
       borderColor: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
       textStyle: { color: token.colorText },
        axisPointer: { type: 'shadow' },
       formatter: (params: any) => {
          const item = params[0]
          const isOthers = rest.length > 0 && item.dataIndex === labels.length - 1 && item.name.startsWith('其他')
          const percent = totalTokens > 0 ? ((item.value / totalTokens) * 100).toFixed(1) : '0.0'
          const detail = isOthers
            ? `<div>聚合用户数: ${rest.length}</div>`
            : ''
          return `<div style="font-family: 'Space Grotesk', sans-serif;">
            <div style="font-weight: 600; margin-bottom: 4px;">${item.name}</div>
            <div>Token: ${item.value.toLocaleString()}</div>
            <div>占比: ${percent}%</div>
            ${detail}
          </div>`
        }
      },
      grid: {
        left: '3%',
        right: '8%',
        top: '4%',
        bottom: '3%',
        containLabel: true
      },
      xAxis: {
        type: 'value',
        axisLine: { show: false },
        axisLabel: {
          color: token.colorTextSecondary,
          fontFamily: "'Space Grotesk', sans-serif",
          formatter: (value: number) => value.toLocaleString()
        },
        splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } }
      },
      yAxis: {
        type: 'category',
        data: labels.slice().reverse(),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: token.colorTextSecondary,
          fontFamily: "'Space Grotesk', sans-serif",
          fontSize: 12
        }
      },
      series: [
        {
          type: 'bar',
          barWidth: '55%',
          data: tokens.slice().reverse().map((t, i) => {
            // 反转后数组里，"其他"会落在索引 0（视觉上在最下方）
            const originalIndex = tokens.length - 1 - i
            const isOthers = rest.length > 0 && originalIndex === tokens.length - 1
            return {
              value: t,
              itemStyle: isOthers
                ? { color: 'rgba(148, 163, 184, 0.45)', borderRadius: [0, 4, 4, 0] }
                : {
                    color: {
                      type: 'linear',
                      x: 0, y: 0, x2: 1, y2: 0,
                      colorStops: [
                        { offset: 0, color: '#60A5FA' },
                        { offset: 1, color: '#3B82F6' }
                      ]
                    },
                    borderRadius: [0, 4, 4, 0]
                  }
            }
          })
        }
      ]
    }
  }, [stats, isDark, token])

  // ========== 供应商分布饼图配置 ==========
  const providerPieOption = useMemo(() => {
    if (!stats?.by_provider?.length) return null
    
    const totalTokens = stats.by_provider.reduce((sum, p) => sum + p.tokens, 0)
    const data = stats.by_provider.map((provider, idx) => ({
      name: provider.provider,
      value: provider.tokens,
      percent: totalTokens > 0 ? ((provider.tokens / totalTokens) * 100).toFixed(1) : 0
    }))

    return {
      tooltip: {
        trigger: 'item',
        backgroundColor: isDark ? 'rgba(17, 24, 39, 0.9)' : 'rgba(255, 255, 255, 0.95)',
        borderColor: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
        textStyle: { color: token.colorText },
        formatter: (params: any) => {
          return `<div style="font-family: 'Space Grotesk', sans-serif;">
            <div style="font-weight: 600; margin-bottom: 4px;">${params.name}</div>
            <div>Token: ${params.value.toLocaleString()}</div>
            <div>占比: ${params.percent}%</div>
          </div>`
        }
      },
      legend: {
        orient: 'vertical',
        right: 10,
        top: 'center',
        textStyle: { color: token.colorTextSecondary, fontFamily: "'Space Grotesk', sans-serif" },
        itemWidth: 12,
        itemHeight: 12,
        itemGap: 8,
      },
      series: [
        {
          type: 'pie',
          radius: ['45%', '70%'],
          center: ['35%', '50%'],
          avoidLabelOverlap: true,
          itemStyle: {
            borderRadius: 6,
            borderColor: isDark ? 'rgba(17, 24, 39, 0.8)' : 'rgba(255, 255, 255, 0.8)',
            borderWidth: 2
          },
          label: {
            show: false
          },
          emphasis: {
            label: {
              show: false
            },
            itemStyle: {
              shadowBlur: 10,
              shadowColor: 'rgba(0, 0, 0, 0.3)'
            }
          },
          data: data.map((d, i) => ({
            ...d,
            itemStyle: { color: CHART_COLORS[i % CHART_COLORS.length] }
          }))
        }
      ]
    }
  }, [stats, isDark, token])

  // ========== 7日趋势折线图配置 ==========
  const trendLineOption = useMemo(() => {
    if (!stats?.by_day?.length) return null
    
    // 取最近7天的数据
    const recentDays = stats.by_day.slice(-7)
    const dates = recentDays.map(d => dayjs(d.date).format('MM-DD'))
    const tokens = recentDays.map(d => d.tokens)
    const requests = recentDays.map(d => d.requests)

    return {
      tooltip: {
        trigger: 'axis',
        backgroundColor: isDark ? 'rgba(17, 24, 39, 0.9)' : 'rgba(255, 255, 255, 0.95)',
        borderColor: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
        textStyle: { color: token.colorText, fontFamily: "'Space Grotesk', sans-serif" },
        axisPointer: {
          type: 'cross',
          crossStyle: { color: '#999' }
        }
      },
      legend: {
        data: ['Token数', '请求数'],
        textStyle: { color: token.colorTextSecondary, fontFamily: "'Space Grotesk', sans-serif" },
        top: 0,
        right: 0,
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        top: '15%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: dates,
        axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.1)' } },
        axisLabel: { color: token.colorTextSecondary, fontFamily: "'Space Grotesk', sans-serif" },
        axisTick: { show: false }
      },
      yAxis: [
        {
          type: 'value',
          name: 'Token数',
          nameTextStyle: { color: token.colorTextSecondary, fontFamily: "'Space Grotesk', sans-serif" },
          axisLine: { show: false },
          axisLabel: { color: token.colorTextSecondary, fontFamily: "'Space Grotesk', sans-serif" },
          splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } }
        },
        {
          type: 'value',
          name: '请求数',
          nameTextStyle: { color: token.colorTextSecondary, fontFamily: "'Space Grotesk', sans-serif" },
          axisLine: { show: false },
          axisLabel: { color: token.colorTextSecondary, fontFamily: "'Space Grotesk', sans-serif" },
          splitLine: { show: false }
        }
      ],
      series: [
        {
          name: 'Token数',
          type: 'line',
          smooth: true,
          symbol: 'circle',
          symbolSize: 8,
          lineStyle: { width: 3, color: '#3B82F6' },
          itemStyle: { color: '#3B82F6' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(59, 130, 246, 0.4)' },
                { offset: 1, color: 'rgba(59, 130, 246, 0.05)' }
              ]
            }
          },
          data: tokens
        },
        {
          name: '请求数',
          type: 'line',
          yAxisIndex: 1,
          smooth: true,
          symbol: 'circle',
          symbolSize: 8,
          lineStyle: { width: 3, color: '#10B981' },
          itemStyle: { color: '#10B981' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(16, 185, 129, 0.4)' },
                { offset: 1, color: 'rgba(16, 185, 129, 0.05)' }
              ]
            }
          },
          data: requests
        }
      ]
    }
  }, [stats, isDark, token])

  // ========== 模型使用分布配置（柱状图） ==========
  const modelBarOption = useMemo(() => {
    if (!stats?.by_model?.length) return null

    // 按 token 数降序排列，便于一眼看出主力模型
    const sortedModels = [...stats.by_model].sort((a, b) => b.tokens - a.tokens)
    const names = sortedModels.map(m => getModelDisplayName(m.model, m.display_name))
    const tokens = sortedModels.map(m => m.tokens || 0)

    return {
      tooltip: {
        trigger: 'axis',
        backgroundColor: isDark ? 'rgba(17, 24, 39, 0.9)' : 'rgba(255, 255, 255, 0.95)',
        borderColor: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
        textStyle: { color: token.colorText, fontFamily: "'Space Grotesk', sans-serif" },
        axisPointer: { type: 'shadow' },
        formatter: (params: any) => {
          const item = params[0]
          return `<div style="font-family: 'Space Grotesk', sans-serif;">
            <div style="font-weight: 600; margin-bottom: 4px;">${item.name}</div>
            <div>Token: ${item.value.toLocaleString()}</div>
          </div>`
        }
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        top: '8%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: names,
        axisLine: { show: false },
        axisLabel: {
          color: token.colorTextSecondary,
          fontFamily: "'Space Grotesk', sans-serif",
          fontSize: 11,
          rotate: names.length > 4 ? 20 : 0,
          interval: 0
        },
        axisTick: { show: false }
      },
      yAxis: {
        type: 'value',
        axisLine: { show: false },
        axisLabel: {
          color: token.colorTextSecondary,
          fontFamily: "'Space Grotesk', sans-serif",
          formatter: (value: number) => value.toLocaleString()
        },
        splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } }
      },
      series: [
        {
          type: 'bar',
          barWidth: '40%',
          data: tokens.map((t, i) => ({
            value: t,
            itemStyle: {
              // 沿用原有渐变色板，与卡片标题的 BarChartOutlined（紫）保持品牌一致
              color: {
                type: 'linear',
                x: 0, y: 0, x2: 0, y2: 1,
                colorStops: [
                  { offset: 0, color: ['#A78BFA', '#60A5FA', '#34D399', '#FBBF24', '#F472B6'][i % 5] },
                  { offset: 1, color: ['#8B5CF6', '#3B82F6', '#10B981', '#F59E0B', '#EC4899'][i % 5] }
                ]
              },
              borderRadius: [4, 4, 0, 0]
            }
          }))
        }
      ]
    }
  }, [stats, isDark, token])

  // ========== 成本统计配置 ==========
  const maxCost = stats?.by_model?.reduce((max, item) => 
    Math.max(max, item.cost || 0), 0) || 0

  // ========== 成本分布折线图配置 ==========
  const costChartOption = useMemo(() => {
    if (!stats?.by_model?.length) return null
    
    const sortedModels = [...stats.by_model].sort((a, b) => b.cost - a.cost)
    const names = sortedModels.map(m => getModelDisplayName(m.model, m.display_name))
    const costs = sortedModels.map(m => m.cost || 0)

    return {
      tooltip: {
        trigger: 'axis',
        backgroundColor: isDark ? 'rgba(17, 24, 39, 0.9)' : 'rgba(255, 255, 255, 0.95)',
        borderColor: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
        textStyle: { color: token.colorText, fontFamily: "'Space Grotesk', sans-serif" },
        formatter: (params: any) => {
          const item = params[0]
          return `<div style="font-family: 'Space Grotesk', sans-serif;">
            <div style="font-weight: 600; margin-bottom: 4px;">${item.name}</div>
            <div>成本: $${item.value.toFixed(4)}</div>
          </div>`
        }
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '15%',
        top: '10%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: names,
        axisLine: { show: false },
        axisLabel: { 
          color: token.colorText, 
          fontFamily: "'Space Grotesk', sans-serif",
          fontSize: 11,
          rotate: names.length > 4 ? 20 : 0
        },
        axisTick: { show: false }
      },
      yAxis: {
        type: 'value',
        name: '成本 ($)',
        nameTextStyle: { color: token.colorTextSecondary, fontFamily: "'Space Grotesk', sans-serif" },
        axisLine: { show: false },
        axisLabel: { 
          color: token.colorTextSecondary, 
          fontFamily: "'Space Grotesk', sans-serif",
          formatter: (value: number) => `$${value.toFixed(3)}`
        },
        splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } }
      },
      series: [
        {
          type: 'line',
          data: costs.map((c, i) => ({
            value: c,
            itemStyle: { color: CHART_COLORS[i % CHART_COLORS.length] }
          })),
          smooth: true,
          symbol: 'circle',
          symbolSize: 10,
          lineStyle: { width: 3 },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(245, 158, 11, 0.5)' },
                { offset: 1, color: 'rgba(245, 158, 11, 0.05)' }
              ]
            }
          }
        }
      ]
    }
  }, [stats, isDark, token])

  return (
    <div style={{ padding: 24, background: token.colorBgLayout, minHeight: '100vh' }}>
      {/* 页面标题 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h2 style={{ 
          color: token.colorText,
          margin: 0,
          fontFamily: "'Space Grotesk', sans-serif",
          fontWeight: 600,
          fontSize: 24,
        }}>
          仪表盘
        </h2>
        <RangePicker
          value={dateRange as any}
          onChange={(dates: any) => {
            if (dates && dates[0] && dates[1]) {
              setDateRange([dates[0], dates[1]])
            }
          }}
          style={{
            background: token.colorBgContainer,
            border: `1px solid ${token.colorBorder}`,
            borderRadius: 10,
          }}
        />
      </div>

      {/* 统计卡片 */}
      <Row gutter={[20, 20]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card 
            style={{ 
              background: isDark ? 'linear-gradient(135deg, #1E3A5F 0%, #0F172A 100%)' : 'linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%)',
              border: '1px solid rgba(59, 130, 246, 0.3)',
              borderRadius: 16,
            }}
          >
            <Statistic
              title={<span style={{ color: 'rgba(148, 163, 184, 0.8)' }}>总Token数</span>}
              value={stats?.total_tokens || 0}
              valueStyle={{ color: '#3B82F6', fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}
              prefix={<ApiOutlined style={{ color: '#3B82F6' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card 
            style={{ 
              background: isDark ? 'linear-gradient(135deg, #1E3A5F 0%, #0F172A 100%)' : 'linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              borderRadius: 16,
            }}
          >
            <Statistic
              title={<span style={{ color: 'rgba(148, 163, 184, 0.8)' }}>总请求数</span>}
              value={stats?.total_requests || 0}
              valueStyle={{ color: '#10B981', fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}
              prefix={<ThunderboltOutlined style={{ color: '#10B981' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card
            style={{
              background: isDark ? 'linear-gradient(135deg, #1E3A5F 0%, #0F172A 100%)' : 'linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%)',
              border: '1px solid rgba(245, 158, 11, 0.3)',
              borderRadius: 16,
            }}
          >
            <Statistic
              title={
                <Tooltip title="费用 = 输入token × 输入价 + 输出token × 输出价（由模型映射的 price_per_1k_input/output 计算，单位 USD）。下方为按当前速率折合的月度预估。">
                  <span style={{
                    color: 'rgba(148, 163, 184, 0.8)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 8,
                  }}>
                    <span>预估费用</span>
                    {hasUsage && (
                      <span style={{
                        fontSize: 12,
                        fontWeight: 400,
                        color: 'rgba(148, 163, 184, 0.7)',
                        fontFamily: "'JetBrains Mono', monospace",
                      }}>
                        ≈ <span style={{ color: '#F59E0B', fontWeight: 600 }}>${monthlyCost.toFixed(2)}</span>/月
                      </span>
                    )}
                  </span>
                </Tooltip>
              }
              value={hasUsage ? totalCost : 0}
              precision={4}
              valueStyle={{ color: '#F59E0B', fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}
              prefix={<DollarOutlined style={{ color: '#F59E0B' }} />}
              formatter={hasUsage ? undefined : () => '—'}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card 
            style={{ 
              background: isDark ? 'linear-gradient(135deg, #1E3A5F 0%, #0F172A 100%)' : 'linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%)',
              border: '1px solid rgba(34, 197, 94, 0.3)',
              borderRadius: 16,
            }}
          >
            <Statistic
              title={<span style={{ color: 'rgba(148, 163, 184, 0.8)' }}>成功率</span>}
              value={stats?.success_rate || 100}
              suffix="%"
              valueStyle={{ color: '#22C55E', fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}
              prefix={<CheckCircleOutlined style={{ color: '#22C55E' }} />}
            />
          </Card>
        </Col>
      </Row>

      {/* 模型使用分布 + 用户占比 */}
      <Row gutter={[20, 20]} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={12}>
          <Card 
            title={
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <BarChartOutlined style={{ color: '#8B5CF6' }} />
                <span style={{ color: token.colorText, fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600 }}>
                  模型使用分布
                </span>
              </div>
            }
            loading={loading}
            style={{ 
              background: token.colorBgContainer,
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: 16,
            }}
            styles={{
              body: { padding: '20px', height: 400 },
              header: { borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }
            }}
          >
            {modelBarOption ? (
              <ReactECharts
                option={modelBarOption}
                style={{ height: 350 }}
                opts={{ renderer: 'svg' }}
              />
            ) : (
              <Empty description="暂无数据" />
            )}
          </Card>
        </Col>
        
        <Col xs={24} lg={12}>
          <Card 
            title={
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <UserOutlined style={{ color: '#3B82F6' }} />
                <span style={{ color: token.colorText, fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600 }}>
                  用户用量分布
                </span>
              </div>
            }
            loading={loading}
            style={{ 
              background: token.colorBgContainer,
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: 16,
            }}
            styles={{ 
              body: { padding: '20px', height: 400 },
              header: { borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }
            }}
          >
            {userBarOption ? (
              <ReactECharts
                option={userBarOption}
                style={{ height: 350 }}
                opts={{ renderer: 'svg' }}
              />
            ) : (
              <Empty description="暂无数据" />
            )}
          </Card>
        </Col>
      </Row>

      {/* 供应商分布 + 成本分析 */}
      <Row gutter={[20, 20]} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={12}>
          <Card 
            title={
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <CloudServerOutlined style={{ color: '#10B981' }} />
                <span style={{ color: token.colorText, fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600 }}>
                  供应商用量分布
                </span>
              </div>
            }
            loading={loading}
            style={{ 
              background: token.colorBgContainer,
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: 16,
            }}
            styles={{ 
              body: { padding: '20px', height: 400 },
              header: { borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }
            }}
          >
            {providerPieOption ? (
              <ReactECharts 
                option={providerPieOption} 
                style={{ height: 350 }}
                opts={{ renderer: 'svg' }}
              />
            ) : (
              <Empty description="暂无数据" />
            )}
          </Card>
        </Col>
        
        <Col xs={24} lg={12}>
          <Card 
            title={
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <DollarOutlined style={{ color: '#F59E0B' }} />
                <span style={{ color: token.colorText, fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600 }}>
                  成本分布
                </span>
              </div>
            }
            loading={loading}
            style={{ 
              background: token.colorBgContainer,
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: 16,
            }}
            styles={{ 
              body: { padding: '20px', height: 400 },
              header: { borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }
            }}
          >
            {costChartOption ? (
              <ReactECharts 
                option={costChartOption} 
                style={{ height: 350 }}
                opts={{ renderer: 'svg' }}
              />
            ) : (
              <div style={{ textAlign: 'center', padding: '40px 0', color: 'rgba(100, 116, 139, 0.6)' }}>
                暂无数据
              </div>
            )}
          </Card>
        </Col>
      </Row>

      {/* 七日趋势 */}
      <Row gutter={[20, 20]}>
        <Col xs={24}>
          <Card 
            title={
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <BarChartOutlined style={{ color: '#F59E0B' }} />
                <span style={{ color: token.colorText, fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600 }}>
                  七日趋势
                </span>
              </div>
            }
            loading={loading}
            style={{ 
              background: token.colorBgContainer,
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: 16,
            }}
            styles={{ 
              body: { padding: '20px' },
              header: { borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }
            }}
          >
            {trendLineOption ? (
              <ReactECharts 
                option={trendLineOption} 
                style={{ height: 350 }}
                opts={{ renderer: 'svg' }}
              />
            ) : (
              <Empty description="暂无数据" />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default AdminDashboard
