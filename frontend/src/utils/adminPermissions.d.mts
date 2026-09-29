export type AdminPermission = 'admin:read' | 'admin:write' | 'department:read' | 'department:write'
export function hasPermission(permissions: string[] | undefined, permission: AdminPermission): boolean
export function canReadAdminPath(path: string, permissions?: string[]): boolean
export function defaultAdminPath(permissions?: string[]): string
export function canWriteAdminPath(path: string, permissions?: string[]): boolean
export function canAccessAdminPath(path: string, permissions?: string[]): boolean
