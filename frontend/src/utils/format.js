/** 后端旧版本可能不返回 ssh_port / ssh_user，这里统一补齐，避免 UI 出现 undefined */
export function normalizeAsset(raw = {}) {
  return {
    id: raw.id,
    name: raw.name || '未命名主机',
    ip_address: raw.ip_address || '—',
    os_type: raw.os_type || 'Linux',
    status: raw.status || 'unknown',
    ssh_port: Number(raw.ssh_port) || 22,
    ssh_user: raw.ssh_user || 'root',
    created_at: raw.created_at || null,
    updated_at: raw.updated_at || null,
  }
}

const pad = (n) => String(n).padStart(2, '0')

export function formatDateTime(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

export function formatClock(value = new Date()) {
  const d = value instanceof Date ? value : new Date(value)
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

export function formatLatency(value) {
  if (value === null || value === undefined || value === '') return '—'
  const n = Number(value)
  return Number.isNaN(n) ? '—' : `${n.toFixed(1)} ms`
}

export function shortId(id) {
  return id ? String(id).slice(0, 8) : '—'
}

const ASSET_STATUS = {
  online: { label: '在线', tone: 'success' },
  offline: { label: '离线', tone: 'danger' },
  unknown: { label: '待探测', tone: 'neutral' },
  error: { label: '异常', tone: 'warn' },
}

export function assetStatusMeta(status) {
  return (
    ASSET_STATUS[String(status || '').toLowerCase()] || {
      label: String(status || '未知').toUpperCase(),
      tone: 'neutral',
    }
  )
}

const TASK_STATE = {
  PENDING: { label: '排队中', tone: 'neutral' },
  RECEIVED: { label: '已接收', tone: 'info' },
  STARTED: { label: '执行中', tone: 'info' },
  RETRY: { label: '重试中', tone: 'warn' },
  RETRYING: { label: '重试查询', tone: 'warn' },
  SUCCESS: { label: '执行成功', tone: 'success' },
  FAILURE: { label: '执行失败', tone: 'danger' },
  REVOKED: { label: '已撤销', tone: 'warn' },
}

export function taskStateMeta(state) {
  return TASK_STATE[String(state || '').toUpperCase()] || { label: state || '未知', tone: 'neutral' }
}
