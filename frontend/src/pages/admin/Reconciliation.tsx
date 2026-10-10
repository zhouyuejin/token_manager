import { useState } from 'react'
import dayjs from 'dayjs'
import { Alert, Button, Card, Descriptions, Drawer, Select, Space, Table, Tag, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'
import { ReconcileItem, ReconcileReport, ReconcileReportList, runReconcile } from '../../api/billing'
import { useSwrDataWithParams } from '../../hooks/useSwr'
import { useMessage } from '../../utils/message'
import { WriteOnly } from '../../components/WriteOnly'

const Reconciliation = () => {
  const navigate = useNavigate()
  const message = useMessage()
  const [reportPage, setReportPage] = useState(1)
  const [selectedReport, setSelectedReport] = useState<ReconcileReport | null>(null)
  const [itemPage, setItemPage] = useState(1)
  const [anomalyType, setAnomalyType] = useState<string>()
  const [rerunning, setRerunning] = useState<string>()
  const { data: reportData, error: reportError, isLoading: reportsLoading, mutate: mutateReports } =
    useSwrDataWithParams<ReconcileReportList>('/admin/billing/reconcile/reports', { page: reportPage, page_size: 10 })
  const { data: itemData, error: itemError, isLoading: itemsLoading } = useSwrDataWithParams<{ total: number; items: ReconcileItem[] }>(
    selectedReport ? `/admin/billing/reconcile/reports/${selectedReport.report_id}/items` : null,
    selectedReport ? { page: itemPage, page_size: 20, ...(anomalyType ? { anomaly_type: anomalyType } : {}) } : null,
  )
  const rerun = async (report: ReconcileReport) => {
    setRerunning(report.report_id)
    try {
      await runReconcile(report.business_date)
      message.success(`${report.business_date} 对账已完成`)
      mutateReports()
    } catch { /* 请求拦截器显示错误 */ }
    finally { setRerunning(undefined) }
  }

  const statusMeta = {
    running: { color: 'blue', label: '待处理' }, normal: { color: 'green', label: '正常' },
    abnormal: { color: 'red', label: '异常' }, failed: { color: 'default', label: '失败' },
  }
  const anomalyLabels: Record<string, string> = {
    committed_missing_usage: '已结算缺少用量', committed_usage_mismatch: '结算与用量不一致',
    usage_missing_reservation: '用量缺少预扣', usage_missing_cost: '用量缺少费用',
    expired_lease_still_reserved: '过期租约未释放', terminal_reservation_invalid: '终态预扣无效',
    quota_record_chain_broken: '额度流水断链',
  }
  const reportColumns = [
    { title: '业务日', dataIndex: 'business_date', width: 120 },
    { title: '状态', dataIndex: 'status', width: 100, render: (value: ReconcileReport['status']) => <Tag color={statusMeta[value].color}>{statusMeta[value].label}</Tag> },
    { title: '预扣', dataIndex: 'reservation_count', width: 90 },
    { title: '用量', dataIndex: 'usage_count', width: 90 },
    { title: '额度流水', dataIndex: 'quota_record_count', width: 110 },
    { title: '异常', dataIndex: 'anomaly_count', width: 90 },
    { title: '失败原因', dataIndex: 'error_message', ellipsis: true, render: (value: string | null) => value || '—' },
    { title: '操作', key: 'actions', width: 190, fixed: 'right' as const, render: (_: unknown, row: ReconcileReport) => <Space>
      <Button disabled={!row.anomaly_count} onClick={() => { setSelectedReport(row); setItemPage(1); setAnomalyType(undefined) }}>查看异常</Button>
      <WriteOnly><Button loading={rerunning === row.report_id} disabled={!!rerunning || row.status === 'running'} onClick={() => rerun(row)}>重跑</Button></WriteOnly>
    </Space> },
  ]
  const itemColumns = [
    { title: '异常类型', dataIndex: 'anomaly_type', width: 170, render: (value: string) => anomalyLabels[value] || value },
    { title: '说明', dataIndex: 'detail', width: 220 },
    { title: '用户', dataIndex: 'user_id', width: 150, render: (value: string | null) => value || '—' },
    { title: '预扣 ID', dataIndex: 'reservation_id', width: 210, render: (value: string | null) => value || '—' },
    { title: '用量 ID', dataIndex: 'usage_log_id', width: 110, render: (value: number | null) => value ?? '—' },
    { title: '额度流水 ID', dataIndex: 'quota_record_id', width: 210, render: (value: string | null) => value || '—' },
    { title: '期望值', dataIndex: 'expected_value', width: 260, ellipsis: true, render: (value: string | null) => value || '—' },
    { title: '实际值', dataIndex: 'actual_value', width: 260, ellipsis: true, render: (value: string | null) => value || '—' },
  ]
  const sourceLabels: Record<string, string> = {
    reservation_id: '预扣 ID', user_id: '用户 ID', key_id: 'Key ID', project_id: '项目 ID', department_id: '部门 ID',
    model: '模型', status: '状态', estimated_tokens: '预估 Token', actual_tokens: '实际 Token',
    estimated_cost_cny: '预估金额（CNY）', actual_cost_cny: '实际金额（CNY）', id: '用量序号', log_id: '用量 ID',
    price_currency: '原币种', exchange_rate: '换算汇率', exchange_rate_date: '汇率日期', conversion_kind: '换算方式',
    channel_id: '渠道 ID', api_type: '接口类型', cost_cny: '费用（CNY）', prompt_tokens: '输入 Token',
    completion_tokens: '输出 Token', total_tokens: '总 Token', status_code: 'HTTP 状态码', record_id: '流水 ID',
    type: '变动类型', amount: '变动额度', balance_before: '变动前余额', balance_after: '变动后余额',
    source: '来源', reason: '原因',
  }
  const sourceDetails = (source: Record<string, string | number | null> | null | undefined, title: string) => source
    ? <Descriptions title={title} size="small" column={3} items={Object.entries(source).map(([key, value]) => ({
      key, label: sourceLabels[key] || key, children: value ?? '—',
    }))} />
    : <Descriptions title={title} size="small" items={[{ key: 'missing', label: '定位结果', children: '未找到关联源记录' }]} />
  return <div style={{ padding: 24 }}>
    <Card title="对账管理" extra={<Space>
      <Button onClick={() => mutateReports()}>刷新</Button>
      <Button onClick={() => navigate('/admin/dashboard')}>前往用量报表</Button>
    </Space>}>
      {reportData && <Alert type="info" showIcon style={{ marginBottom: 16 }} message={
        `按 ${reportData.timezone} 自然日对账，租约宽限 ${reportData.grace_minutes} 分钟，覆盖起点 ${dayjs(reportData.coverage_started_at).format('YYYY-MM-DD HH:mm:ss')}。${reportData.history_rule}。`
      } />}
      {reportError && <Alert type="error" message="对账报告加载失败" action={<Button onClick={() => mutateReports()}>重试</Button>} />}
      <Table rowKey="report_id" loading={reportsLoading} dataSource={reportData?.items || []} columns={reportColumns} scroll={{ x: 1050 }}
        pagination={{ current: reportPage, pageSize: 10, total: reportData?.total || 0, showSizeChanger: false, onChange: setReportPage }} />
      <Typography.Text type="secondary">用量报表导出会沿用管理驾驶舱的日期、部门、项目、用户、Key、模型和渠道筛选，导出期间不阻塞本页操作。</Typography.Text>
    </Card>
    <Drawer title={`${selectedReport?.business_date || ''} 对账异常`} width="min(1100px, 92vw)" open={!!selectedReport} onClose={() => setSelectedReport(null)}
      extra={<Select allowClear placeholder="全部异常类型" style={{ width: 220 }} value={anomalyType} onChange={value => { setAnomalyType(value); setItemPage(1) }}
        options={Object.entries(anomalyLabels).map(([value, label]) => ({ value, label }))} />}>
      {itemError && <Alert type="error" message="异常明细加载失败" />}
      <Typography.Text type="secondary">展开异常行可查看关联的预扣、用量和额度流水源记录。</Typography.Text>
      <Table rowKey="item_id" loading={itemsLoading} dataSource={itemData?.items || []} columns={itemColumns} scroll={{ x: 1600 }}
        expandable={{ expandedRowRender: row => <Space direction="vertical" style={{ width: '100%' }}>
          {sourceDetails(row.sources?.reservation, '预扣源记录')}
          {sourceDetails(row.sources?.usage, '用量源记录')}
          {sourceDetails(row.sources?.quota_record, '额度流水源记录')}
        </Space> }}
        pagination={{ current: itemPage, pageSize: 20, total: itemData?.total || 0, showSizeChanger: false, onChange: setItemPage }} />
    </Drawer>
  </div>
}

export default Reconciliation
