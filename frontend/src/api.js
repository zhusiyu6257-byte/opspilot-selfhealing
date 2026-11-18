import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 资产相关
export const getAssets = () => api.get('/assets')
export const createAsset = (data) => api.post('/assets', data)
export const updateAsset = (id, data) => api.put(`/assets/${id}`, data)
export const deleteAsset = (id) => api.delete(`/assets/${id}`)

// 异步探活
export const dispatchPing = (ip_address) => api.post('/tasks/ping', { ip_address })
export const getTaskStatus = (taskId) => api.get(`/tasks/${taskId}`)

// 远程命令与剧本
export const executeCommand = (payload) => api.post('/runbooks/execute', payload)

// 任务执行审计历史
export const getExecutions = (params) => api.get('/executions', { params })
export const getExecutionStats = () => api.get('/executions/stats')
export const getExecutionDetail = (taskId) => api.get(`/executions/by-task/${taskId}`)

// 后端与依赖组件健康状态
export const getHealth = () => api.get('/healthz')

export default api
