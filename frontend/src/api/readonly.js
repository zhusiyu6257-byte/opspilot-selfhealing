import axios from 'axios'
import { READONLY_API_BASE } from '@/config/runtime.js'

const api = axios.create({
  baseURL: READONLY_API_BASE,
  timeout: 10000,
  headers: { Accept: 'application/json' },
})

export const getReadonlyHealth = () => api.get('/healthz')
export const getReadonlyAssets = () => api.get('/assets')
export const getReadonlyExecutionStats = () => api.get('/executions/stats')
export const getReadonlyExecutions = (limit = 8) =>
  api.get('/executions', { params: { limit } })
