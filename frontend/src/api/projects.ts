import { get, post, put } from './request'

export interface Department {
  dept_id: string
  name: string
  owner_user_id?: string | null
  status: 'active' | 'disabled'
}

export interface Project {
  project_id: string
  dept_id: string
  name: string
  department_name: string
  owner_user_id?: string | null
  status: 'active' | 'disabled'
}

export type DepartmentSave = Omit<Department, 'dept_id'>
export type ProjectSave = Omit<Project, 'project_id' | 'department_name'>

export const saveDepartment = (data: DepartmentSave, deptId?: string) =>
  deptId ? put<Department>(`/projects/admin/departments/${deptId}`, data) : post<Department>('/projects/admin/departments', data)

export const saveProject = (data: ProjectSave, projectId?: string) =>
  projectId ? put<Project>(`/projects/admin/${projectId}`, data) : post<Project>('/projects/admin', data)

export const getProjectUsers = (projectId: string) =>
  get<{ user_ids: string[]; items: { user_id: string; username: string }[] }>(`/projects/admin/${projectId}/users`)

export const setProjectUsers = (projectId: string, userIds: string[]) =>
  put(`/projects/admin/${projectId}/users`, { user_ids: userIds })
