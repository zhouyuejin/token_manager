import { useMemo, useState } from 'react'
import useSWR from 'swr'
import dayjs, { Dayjs } from 'dayjs'
import { Alert, Button, Card, Col, DatePicker, Empty, Row, Select, Space, Statistic, Table, Tooltip } from 'antd'
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
        <Card title="网页 AI 对话（日常使用）" style={{ marginBottom: 16 }}>
          <Row gutter={16}>
            <Col span={8}><Statistic title="请求数" value={data?.web_chat?.requests || 0} /></Col>
            <Col span={8}><Statistic title="Token" value={data?.web_chat?.tokens || 0} /></Col>
            <Col span={8}><Statistic title="费用（CNY）" value={data?.web_chat?.cost || 0} precision={8} /></Col>
          </Row>
        </Card>
        <Card title="项目用量明细" loading={isLoading}>
          <Table
            rowKey="project_id"
            size="small"
            pagination={{ pageSize: 10 }}
            dataSource={data?.by_project || []}
            columns={[
              { title: '项目', dataIndex: 'name' },
              { title: 'Token 数', dataIndex: 'tokens', align: 'right', render: (value: number) => <Tooltip title={value.toLocaleString()}>{formatTokenCount(value)}</Tooltip> },
              { title: '请求数', dataIndex: 'requests', align: 'right' },
            ]}
          />
        </Card>
      </>}
    </>}
  </div>
}

export default DepartmentDashboard
