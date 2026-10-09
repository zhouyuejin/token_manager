import type { ChannelHealth } from '../api/channels'
import type { AdminProviderUsage } from '../api/admin'
export type ChannelState = { key: string; label: string; color: string }
export type QuotaSummary = { text: string; low: boolean; unavailable: boolean; updatedAt?: string }
export const channelStates: Record<string, ChannelState>
export function channelState(health?: ChannelHealth, quota?: Partial<QuotaSummary>): ChannelState
export function quotaSummary(quota?: any, threshold?: number): QuotaSummary
export function topChannelUsage(rows?: AdminProviderUsage[], metric?: string): AdminProviderUsage[]
