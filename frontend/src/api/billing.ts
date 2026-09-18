import { put } from './request'

export interface BudgetSave {
  amount_usd: string
  thresholds: number[]
  policy: 'block' | 'alert'
  enabled: boolean
}

export interface Budget extends BudgetSave {
  budget_id: string
  scope_type: 'project' | 'department'
  scope_id: string
  scope_name: string
  month: string
  used_usd: number
  reserved_usd: number
  remaining_usd: number
  usage_percent: number | null
}

export const saveBudget = (kind: Budget['scope_type'], scopeId: string, month: string, data: BudgetSave) =>
  put<Budget>(`/admin/billing/budgets/${kind}/${encodeURIComponent(scopeId)}/${month}`, data)
