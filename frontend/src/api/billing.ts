import { get, put } from './request'

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

export interface Reservation {
  reservation_id: string
  user_id?: string
  key_id: string
  project_id?: string | null
  department_id?: string | null
  model: string
  estimated_tokens: number
  actual_tokens?: number | null
  estimated_cost_usd: number
  actual_cost_usd?: number | null
  status: 'reserved' | 'committed' | 'released' | 'expired'
  created_at: string
  updated_at?: string
  expires_at: string
}

export interface MyBilling {
  month: string
  budgets: Pick<Budget, 'budget_id' | 'scope_type' | 'scope_id' | 'scope_name' | 'amount_usd' | 'policy' | 'used_usd' | 'reserved_usd' | 'remaining_usd' | 'usage_percent'>[]
  reservations: Reservation[]
}

export const getMyBilling = () => get<MyBilling>('/stats/billing')
