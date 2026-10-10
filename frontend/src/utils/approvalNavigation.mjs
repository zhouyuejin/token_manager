export function approvalNotificationLink(notification) {
  if (!notification.type.startsWith('approval_')) return null
  let metadata = notification.metadata
  if (typeof metadata === 'string') {
    try { metadata = JSON.parse(metadata) } catch { metadata = null }
  }
  const reviewer = metadata?.audience === 'reviewer' || (!metadata?.audience &&
    notification.type !== 'approval_result' && ['pending', 'cancelled'].includes(metadata?.status))
  const path = reviewer ? '/approval-workbench' : '/applications'
  return {
    href: typeof metadata?.request_id === 'string' ? `${path}?request_id=${encodeURIComponent(metadata.request_id)}` : path,
    label: reviewer ? '查看审批任务' : '查看我的申请',
  }
}

export function legacyApprovalPath(search, hash = '') {
  const params = new URLSearchParams(search)
  const review = params.get('tab') === 'review' || hash === '#review'
  return `${review ? '/approval-workbench' : '/applications'}${search}${hash}`
}
