import { useMemo, useState } from 'react'
import useSWR from 'swr'
import dayjs, { Dayjs } from 'dayjs'
import { Alert, Button, Card, Col, DatePicker, Empty, Row, Select, Space, Statistic, Tooltip } from 'antd'
import { ApiOutlined, BarChartOutlined, CheckCircleOutlined, ThunderboltOutlined } from '@ant-design/icons'
import ReactECharts from '../../components/AsyncECharts'
import { Department } from '../../api/projects'
import {
  DepartmentUsageStats,
  DepartmentUsageStatsParams,
  getDepartmentUsageStats,
} from '../../api/departmentStats'
import { useThemeToken } from '../../theme/useThemeToken'
import { formatTokenCount } from '../../utils/formatTokenCount.mjs'
import { useSwrData } from '../../hooks/useSwr'

const { RangePicker } = DatePicker

const DepartmentDashboard = () => {
  const { token } = useThemeToken()
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs]>([
    dayjs().subtract(6, 'day'),
    dayjs(),
  ])
  const [departmentId, setDepartmentId] = useState<string>()
  const [projectMetric, setProjectMetric] = useState<'tokens' | 'requests'>('tokens')
  const { data: departmentsData, error: departmentsError, mutate: reloadDepartments } = useSwrData<{ items: Department[] }>(
    '/projects/admin/departments',
  )
  const params: DepartmentUsageStatsParams = {
    start_date: dateRange[0].format('YYYY-MM-DD'),
    end_date: dateRange[1].format('YYYY-MM-DD'),
    ...(departmentId ? { department_id: departmentId } : {}),
  }
  const { data, error: statsError, isLoading, mutate: reloadStats } = useSWR<DepartmentUsageStats>(
    ['/projects/admin/usage-stats', params],
    () => getDepartmentUsageStats(params),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )

  const dailyOption = useMemo(() => ({
    tooltip: { trigger: 'axis' },
    legend: { data: ['Token', '请求数'], textStyle: { color: token.colorTextSecondary } },
    grid: { left: 60, right: 52, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: data?.by_day.map(row => row.date) || [], axisLabel: { color: token.colorTextSecondary } },
    yAxis: [
      { type: 'value', name: 'Token', axisLabel: { color: token.colorTextSecondary, formatter: formatTokenCount }, splitLine: { lineStyle: { color: token.colorBorderSecondary } } },
      { type: 'value', name: '请求数', axisLabel: { color: token.colorTextSecondary }, splitLine: { show: false } },
    ],
    series: [
      { name: 'Token', type: 'line', smooth: true, yAxisIndex: 0, data: data?.by_day.map(row => row.tokens) || [], itemStyle: { color: '#3B82F6' } },
      { name: '请求数', type: 'line', smooth: true, yAxisIndex: 1, data: data?.by_day.map(row => row.requests) || [], itemStyle: { color: '#10B981' } },
    ],
  }), [data, token])

  const projectOption = useMemo(() => ({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 100, right: 32, top: 16, bottom: 24 },
    xAxis: { type: 'value', axisLabel: { color: token.colorTextSecondary, formatter: formatTokenCount }, splitLine: { lineStyle: { color: token.colorBorderSecondary } } },
    yAxis: { type: 'category', data: (data?.by_project || []).map(row => row.name), axisLabel: { color: token.colorTextSecondary } },
    series: [
      { name: 'Token', type: 'bar', data: data?.by_project.map(row => row.tokens) || [], itemStyle: { color: '#3B82F6' } },
    ],
  }), [data, token])

  const webChatOption = useMemo(() => ({
    tooltip: { trigger: 'item', renderMode: 'richText', valueFormatter: (value: number) => value.toLocaleString() },
    legend: { bottom: 0, itemWidth: 10, itemHeight: 10, icon: 'circle', textStyle: { color: token.colorTextSecondary, fontSize: 11 } },
    title: {
      text: `${data?.total_tokens ? ((data.web_chat.tokens / data.total_tokens) * 100).toFixed(1) : '0'}%`,
      subtext: 'Token 占比',
      left: 'center',
      top: '31%',
      textStyle: { color: token.colorText, fontSize: 24 },
      subtextStyle: { color: token.colorTextSecondary },
    },
    series: [{
      type: 'pie',
      radius: ['62%', '78%'],
      center: ['50%', '45%'],
      label: { show: false },
      data: [
        { name: '网页 AI 对话', value: data?.web_chat?.tokens || 0, itemStyle: { color: '#10B981' } },
        { name: '其他用量', value: Math.max(0, (data?.total_tokens || 0) - (data?.web_chat?.tokens || 0)), itemStyle: { color: token.colorFillSecondary } },
      ],
    }],
  }), [data, token])

  const projectDetailOption = useMemo(() => {
    const rows = [...(data?.by_project || [])].sort((a, b) => b[projectMetric] - a[projectMetric])
    const metricName = projectMetric === 'tokens' ? 'Token' : '请求数'
    return {
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, renderMode: 'richText', valueFormatter: (value: number) => value.toLocaleString() },
      grid: { left: 0, right: 64, top: 8, bottom: 8, containLabel: true },
      xAxis: {
        type: 'value',
        show: false,
        minInterval: 1,
        axisLabel: { color: token.colorTextSecondary, ...(projectMetric === 'tokens' ? { formatter: formatTokenCount } : {}) },
        splitLine: { lineStyle: { color: token.colorBorderSecondary } },
      },
      yAxis: {
        type: 'category',
        inverse: true,
        data: rows.map(row => row.name),
        axisLabel: { color: token.colorTextSecondary, width: 100, overflow: 'truncate' },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      series: [{
        name: metricName,
        type: 'bar',
        barMaxWidth: 14,
        showBackground: true,
        backgroundStyle: { color: token.colorFillSecondary, borderRadius: 7 },
        label: { show: true, position: 'right', color: token.colorText, formatter: (params: { value: number }) => projectMetric === 'tokens' ? formatTokenCount(params.value) : params.value.toLocaleString() },
        data: rows.map(row => row[projectMetric]),
        itemStyle: { color: projectMetric === 'tokens' ? '#3B82F6' : '#10B981', borderRadius: 7 },
      }],
    }
  }, [data, projectMetric, token])

  const retry = () => {
    reloadDepartments()
    reloadStats()
  }

  const noDepartments = !departmentsError && departmentsData && departmentsData.items.length === 0
  const hasUsage = Boolean(data?.total_requests)

  return <div style={{ padding: 24, minHeight: '100%' }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16, marginBottom: 24 }}>
      <h2 style={{ color: token.colorText, margin: 0, fontSize: 24 }}>部门仪表盘</h2>
      <Space wrap>
        <Select
          allowClear
          placeholder="全部负责部门"
          value={departmentId}
          onChange={setDepartmentId}
          style={{ width: 180 }}
          options={(departmentsData?.items || []).map(department => ({ value: department.dept_id, label: department.name }))}
        />
        <RangePicker
          value={dateRange}
          onChange={range => { if (range?.[0] && range[1]) setDateRange([range[0], range[1]]) }}
        />
      </Space>
    </div>

    {(departmentsError || statsError) && <Alert
      type="error"
      showIcon
      message="部门统计加载失败"
      action={<Button onClick={retry}>重试</Button>}
      style={{ marginBottom: 16 }}
    />}

    {noDepartments ? <Card><Empty description="当前没有负责的部门" /></Card> : <>
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={12} xl={6}><Card loading={isLoading}>
          <Tooltip title={`${(data?.total_tokens || 0).toLocaleString()} Token`}>
            <Statistic title="总 Token 数" value={data?.total_tokens || 0} formatter={value => formatTokenCount(Number(value))} prefix={<ApiOutlined />} />
          </Tooltip>
        </Card></Col>
        <Col xs={24} sm={12} xl={6}><Card loading={isLoading}>
          <Statistic title="总请求数" value={data?.total_requests || 0} prefix={<ThunderboltOutlined />} />
        </Card></Col>
        <Col xs={24} sm={12} xl={6}><Card loading={isLoading}>
          <Statistic title="费用（CNY）" value={data?.total_cost || 0} precision={8} prefix="¥" />
        </Card></Col>
        <Col xs={24} sm={12} xl={6}><Card loading={isLoading}>
          <Statistic title="成功率" value={data?.success_rate ?? 100} precision={2} suffix="%" prefix={<CheckCircleOutlined />} />
        </Card></Col>
      </Row>

      {!hasUsage && !isLoading ? <Card><Empty description="所选日期范围内暂无用量" /></Card> : <>
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col xs={24} xl={12}><Card title={<><BarChartOutlined />　每日用量趋势</>} loading={isLoading}>
            <ReactECharts option={dailyOption} style={{ height: 320 }} />
          </Card></Col>
          <Col xs={24} xl={12}><Card title={<><BarChartOutlined />　项目用量分布</>} loading={isLoading}>
            <ReactECharts option={projectOption} style={{ height: 320 }} />
          </Card></Col>
        </Row>
        <Row gutter={[16, 16]} align="stretch">
          <Col xs={24} xl={10}>
            <Card title="网页 AI 对话（日常使用）" loading={isLoading} style={{ height: '100%' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flexWrap: 'wrap', gap: 24 }}>
                <ReactECharts option={webChatOption} style={{ height: 200, width: 200, flexShrink: 0 }} />
                <div style={{ flex: '1 1 160px', display: 'grid', gap: 12 }}>
                  <Statistic title="Token 用量" value={data?.web_chat?.tokens || 0} valueStyle={{ fontSize: 24, fontWeight: 600 }} />
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px 24px' }}>
                    <Statistic title="请求数" value={data?.web_chat?.requests || 0} valueStyle={{ fontSize: 18 }} />
                    <Tooltip title={`¥${(data?.web_chat?.cost || 0).toFixed(8)}`}>
                      <Statistic title="费用（CNY）" prefix="¥" value={data?.web_chat?.cost || 0} precision={4} valueStyle={{ fontSize: 18 }} />
                    </Tooltip>
                  </div>
                </div>
              </div>
            </Card>
          </Col>
          <Col xs={24} xl={14}>
            <Card title="项目用量明细" loading={isLoading} style={{ height: '100%' }} extra={
          <Select
            aria-label="项目用量指标"
            value={projectMetric}
            onChange={setProjectMetric}
            style={{ width: 120 }}
            options={[{ label: 'Token 数', value: 'tokens' }, { label: '请求数', value: 'requests' }]}
          />
        }>
          {data?.by_project.length ? <div style={{ height: 200, overflowY: 'auto' }}>
            <ReactECharts option={projectDetailOption} notMerge style={{ height: Math.max(64, data.by_project.length * 48 + 16) }} />
          </div> : <Empty description="所选日期范围内暂无项目用量" />}
            </Card>
          </Col>
        </Row>
      </>}
    </>}
  </div>
}

export default DepartmentDashboard
