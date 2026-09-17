import { useState } from 'react'
import { Alert, Button, Card, Form, Input, Modal, Select, Space, Table, Tag } from 'antd'
import { Department, Project, saveDepartment, saveProject, getProjectUsers, setProjectUsers } from '../../api/projects'
import { User } from '../../api/users'
import { useSwrData, useSwrDataWithParams } from '../../hooks/useSwr'
import { useMessage } from '../../utils/message'

const ProjectsPage = ({ departmentsOnly = false }: { departmentsOnly?: boolean }) => {
  const title = departmentsOnly ? '部门' : '项目'
  const { data, error, isLoading, mutate } = useSwrData<{ items: (Department | Project)[] }>(
    departmentsOnly ? '/projects/admin/departments' : '/projects/admin'
  )
  const { data: departments } = useSwrData<{ items: Department[] }>(departmentsOnly ? null : '/projects/admin/departments')
  const [visible, setVisible] = useState(false)
  const [editing, setEditing] = useState<Department | Project | null>(null)
  const [saving, setSaving] = useState(false)
  const [search, setSearch] = useState('')
  const { data: users, error: usersError, isLoading: usersLoading } = useSwrDataWithParams<{ items: User[] }>(
    visible ? '/admin/users' : null, { page: 1, page_size: 100, keyword: search }
  )
  const [form] = Form.useForm()
  const message = useMessage()
  const [membersProject, setMembersProject] = useState<Project | null>(null)
  const [members, setMembers] = useState<string[]>([])
  const [memberOptions, setMemberOptions] = useState<{ value: string; label: string }[]>([])
  const [membersLoading, setMembersLoading] = useState(false)
  const [membersError, setMembersError] = useState(false)
  const [memberSearch, setMemberSearch] = useState('')
  const { data: memberUsers, error: memberUsersError } = useSwrDataWithParams<{ items: User[] }>(
    membersProject ? '/admin/users' : null, { page: 1, page_size: 100, keyword: memberSearch }
  )
  const userOptions = (users?.items || []).map(user => ({ value: user.user_id, label: `${user.username} (${user.user_id})` }))
  if (editing?.owner_user_id && !userOptions.some(option => option.value === editing.owner_user_id)) {
    userOptions.push({ value: editing.owner_user_id, label: editing.owner_user_id })
  }
  const allMemberOptions = [...memberOptions]
  for (const user of memberUsers?.items || []) {
    if (!allMemberOptions.some(option => option.value === user.user_id)) {
      allMemberOptions.push({ value: user.user_id, label: `${user.username} (${user.user_id})` })
    }
  }

  const openForm = (row: Department | Project | null) => {
    setEditing(row)
    setSearch('')
    form.resetFields()
    form.setFieldsValue(row || { status: 'active' })
    setVisible(true)
  }

  const save = async (values: any) => {
    setSaving(true)
    try {
      const payload = { ...values, owner_user_id: values.owner_user_id || null }
      if (departmentsOnly) await saveDepartment(payload, editing?.dept_id)
      else await saveProject(payload, (editing as Project | null)?.project_id)
      message.success(`${title}保存成功`)
      setVisible(false)
      mutate()
    } catch { /* 请求拦截器显示错误 */ }
    finally { setSaving(false) }
  }

  const openMembers = async (project: Project) => {
    setMembersProject(project)
    setMembers([])
    setMemberOptions([])
    setMemberSearch('')
    setMembersError(false)
    setMembersLoading(true)
    try {
      const response = await getProjectUsers(project.project_id)
      setMembers(response.user_ids)
      setMemberOptions(response.items.map(user => ({ value: user.user_id, label: `${user.username} (${user.user_id})` })))
    } catch { setMembersError(true) }
    finally { setMembersLoading(false) }
  }

  const saveMembers = async () => {
    if (!membersProject) return
    setSaving(true)
    try {
      await setProjectUsers(membersProject.project_id, members)
      message.success('项目分配成功')
      setMembersProject(null)
    } catch { /* 请求拦截器显示错误 */ }
    finally { setSaving(false) }
  }

  const columns = [
    { title: `${title}名称`, dataIndex: 'name' },
    ...(!departmentsOnly ? [{ title: '所属部门', dataIndex: 'department_name' }] : []),
    { title: '负责人', dataIndex: 'owner_user_id', render: (value: string) => value || '未设置' },
    { title: '状态', dataIndex: 'status', render: (value: string) => <Tag color={value === 'active' ? 'green' : 'default'}>{value === 'active' ? '启用' : '停用'}</Tag> },
    { title: '操作', key: 'actions', render: (_: unknown, row: Department | Project) => <Space>
      <Button onClick={() => openForm(row)}>编辑</Button>
      {!departmentsOnly && <Button onClick={() => openMembers(row as Project)}>分配用户</Button>}
    </Space> }
  ]

  return <div style={{ padding: 24 }}>
    <Card title={`${title}管理`} extra={<Button type="primary" onClick={() => openForm(null)}>新增{title}</Button>}>
      {error && <Alert type="error" showIcon message={`${title}加载失败`} action={<Button onClick={() => mutate()}>重试</Button>} style={{ marginBottom: 16 }} />}
      <Table rowKey={departmentsOnly ? 'dept_id' : 'project_id'} columns={columns} dataSource={data?.items || []} loading={isLoading} />
    </Card>
    <Modal title={`${editing ? '编辑' : '新增'}${title}`} open={visible} onCancel={() => setVisible(false)} onOk={() => form.submit()} confirmLoading={saving}>
      <Form form={form} layout="vertical" onFinish={save}>
        <Form.Item name="name" label={`${title}名称`} rules={[{ required: true, whitespace: true, message: `请输入${title}名称` }]}><Input maxLength={100} /></Form.Item>
        {!departmentsOnly && <Form.Item name="dept_id" label="所属部门" rules={[{ required: true, message: '请选择部门' }]}>
          <Select showSearch optionFilterProp="label" options={(departments?.items || []).map(dept => ({ value: dept.dept_id, label: `${dept.name}${dept.status === 'disabled' ? '（停用）' : ''}` }))} />
        </Form.Item>}
        {usersError && <Alert type="error" message="用户搜索失败，请重新搜索" />}
        <Form.Item name="owner_user_id" label="负责人">
          <Select showSearch allowClear filterOption={false} onSearch={setSearch} loading={usersLoading} options={userOptions} placeholder="搜索用户名或邮箱" />
        </Form.Item>
        <Form.Item name="status" label="状态" rules={[{ required: true }]}><Select options={[{ value: 'active', label: '启用' }, { value: 'disabled', label: '停用' }]} /></Form.Item>
        <Alert type="info" message="停用后，该部门或项目将不再出现在新建和编辑 Key 的可用项目中。历史用量归因保持不变。" />
      </Form>
    </Modal>
    <Modal title={`分配用户：${membersProject?.name || ''}`} open={!!membersProject} closable={!membersLoading} maskClosable={!membersLoading} keyboard={!membersLoading} cancelButtonProps={{ disabled: membersLoading }} onCancel={() => setMembersProject(null)} onOk={saveMembers} confirmLoading={saving} okButtonProps={{ disabled: membersLoading || membersError }}>
      {(membersError || memberUsersError) && <Alert type="error" message="用户加载失败" action={membersError && membersProject ? <Button onClick={() => openMembers(membersProject)}>重试</Button> : undefined} style={{ marginBottom: 16 }} />}
      <Select mode="multiple" showSearch filterOption={false} loading={membersLoading} disabled={membersLoading || membersError} value={members} onChange={values => {
        setMembers(values)
        setMemberOptions(allMemberOptions.filter(option => values.includes(option.value)))
      }} onSearch={setMemberSearch} options={allMemberOptions} style={{ width: '100%' }} placeholder="搜索并选择可使用该项目的用户" />
      <p>所选用户可在创建或编辑 API Key 时选择该项目。清空后保存会撤销全部用户的项目分配；已有 Key 保留归属。</p>
    </Modal>
  </div>
}

export default ProjectsPage
