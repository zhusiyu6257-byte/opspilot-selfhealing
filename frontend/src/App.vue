<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus,
  Refresh,
  Monitor,
  Connection,
  Search,
  CaretRight,
  Timer,
  Loading,
  CircleCheck,
  Warning,
  Delete,
  DocumentCopy,
  Lock,
  Close,
  MagicStick,
  Edit,
  DataAnalysis,
} from '@element-plus/icons-vue'
import {
  getAssets,
  createAsset,
  updateAsset,
  deleteAsset,
  dispatchPing,
  getTaskStatus,
  executeCommand,
  getExecutions,
  getExecutionStats,
  getExecutionDetail,
  getHealth,
} from '@/api.js'

/* ==========================================================================
   常量
   ========================================================================== */
const PRESET_COMMANDS = [
  { label: 'uptime', command: 'uptime' },
  { label: 'df -h', command: 'df -h' },
  { label: 'docker ps', command: 'docker ps' },
  { label: 'free -m', command: 'free -m' },
]

const TERMINAL_STATES = ['SUCCESS', 'FAILURE', 'REVOKED']
const POLL_INTERVAL_MS = 1200
const POLL_TIMEOUT_MS = 60000

const ASSET_STATUS = {
  online: { label: 'ONLINE', tone: 'success' },
  offline: { label: 'OFFLINE', tone: 'danger' },
  unknown: { label: 'UNKNOWN', tone: 'neutral' },
}

const EXEC_STATUS = {
  SUCCESS: { label: 'SUCCESS', tone: 'success' },
  FAILED: { label: 'FAILED', tone: 'danger' },
  FAILURE: { label: 'FAILED', tone: 'danger' },
  RUNNING: { label: 'RUNNING', tone: 'warn' },
  PENDING: { label: 'PENDING', tone: 'info' },
  REJECTED: { label: 'REJECTED', tone: 'blocked' },
}

const TRIGGER_SOURCE = {
  MANUAL: { label: 'MANUAL', tone: 'info' },
  ALERT_WEBHOOK: { label: 'ALERT_WEBHOOK', tone: 'purple' },
  CRON: { label: 'CRON', tone: 'neutral' },
}

/* ==========================================================================
   通用工具
   ========================================================================== */
const pad = (n) => String(n).padStart(2, '0')

// 当前 api.js 直接返回 axios response；若以后加了响应拦截器也能兼容
const unwrap = (res) =>
  res && typeof res === 'object' && 'data' in res ? res.data : res

function errorText(err) {
  if (!err) return '未知错误'
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((item) => {
        const field = Array.isArray(item?.loc) ? item.loc.slice(1).join('.') : '参数'
        return `${field}: ${item?.msg || '不合法'}`
      })
      .join('；')
  }
  if (err.code === 'ECONNABORTED') return '请求超时，请检查后端服务是否响应'
  if (!err.response) return '无法连接后端服务，请确认 FastAPI 已启动（127.0.0.1:8000）'
  return err.message || `请求失败（HTTP ${err.response.status}）`
}

function notifyError(prefix, err) {
  ElMessage({
    type: 'error',
    message: `${prefix}：${errorText(err)}`,
    showClose: true,
    duration: 5000,
  })
}

function formatDateTime(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function formatClock(value = new Date()) {
  const d = value instanceof Date ? value : new Date(value)
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function formatDuration(ms) {
  if (ms === null || ms === undefined || ms === '') return '—'
  const n = Number(ms)
  if (Number.isNaN(n)) return '—'
  return n >= 1000 ? `${(n / 1000).toFixed(2)} s（${Math.round(n)} ms）` : `${n.toFixed(0)} ms`
}

const shortId = (id) => (id ? String(id).slice(0, 8) : '—')

function todayKey() {
  const d = new Date()
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

const isToday = (value) => String(value || '').slice(0, 10) === todayKey()
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

const assetStatusMeta = (status) =>
  ASSET_STATUS[String(status || '').toLowerCase()] || {
    label: String(status || 'UNKNOWN').toUpperCase(),
    tone: 'neutral',
  }

const statusMeta = (status) =>
  EXEC_STATUS[String(status || '').toUpperCase()] || {
    label: String(status || 'UNKNOWN').toUpperCase(),
    tone: 'neutral',
  }

const triggerMeta = (source) =>
  TRIGGER_SOURCE[String(source || '').toUpperCase()] || {
    label: String(source || 'UNKNOWN').toUpperCase(),
    tone: 'neutral',
  }

function normalizeAsset(raw = {}) {
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

function normalizeExecution(raw = {}) {
  return {
    id: raw.id,
    task_id: raw.task_id || '',
    asset_id: raw.asset_id ?? null,
    task_type: raw.task_type || 'COMMAND',
    command: raw.command || '—',
    trigger_source: raw.trigger_source || 'MANUAL',
    status: raw.status || 'PENDING',
    exit_code: raw.exit_code ?? null,
    stdout: raw.stdout || '',
    stderr: raw.stderr || '',
    duration_ms: raw.duration_ms ?? null,
    created_at: raw.created_at || null,
    finished_at: raw.finished_at || null,
  }
}

/* ==========================================================================
   通用短轮询：串行等待、终态判定、超时控制、可取消、网络抖动容错
   ========================================================================== */
function createPoller() {
  let cancelled = false
  const abortedError = () =>
    Object.assign(new Error('轮询已取消'), { code: 'ABORTED' })

  async function run(taskId, onTick) {
    const startedAt = Date.now()
    let attempts = 0
    let failures = 0

    while (true) {
      if (cancelled) throw abortedError()
      if (Date.now() - startedAt >= POLL_TIMEOUT_MS) {
        throw Object.assign(
          new Error(`任务等待超时（${POLL_TIMEOUT_MS / 1000} 秒），已停止前端轮询`),
          { code: 'TIMEOUT' },
        )
      }

      attempts += 1
      let snapshot
      try {
        snapshot = unwrap(await getTaskStatus(taskId))
        failures = 0
      } catch (err) {
        if (cancelled) throw abortedError()
        failures += 1
        onTick?.({
          status: 'RETRYING',
          attempts,
          message: `状态查询失败：${errorText(err)}（第 ${failures} 次）`,
          elapsedMs: Date.now() - startedAt,
        })
        if (failures >= 3) {
          throw Object.assign(
            new Error(`连续 3 次无法查询任务状态：${errorText(err)}`),
            { code: 'NETWORK' },
          )
        }
        await sleep(POLL_INTERVAL_MS)
        continue
      }

      if (cancelled) throw abortedError()
      const state = snapshot?.status || 'PENDING'
      onTick?.({
        status: state,
        attempts,
        result: snapshot?.result ?? null,
        elapsedMs: Date.now() - startedAt,
      })
      if (TERMINAL_STATES.includes(state)) return snapshot
      await sleep(POLL_INTERVAL_MS)
    }
  }

  return {
    run,
    cancel: () => {
      cancelled = true
    },
  }
}

/* ==========================================================================
   状态
   ========================================================================== */
const activeTab = ref('console')
const assets = ref([])
const executions = ref([])
const assetsLoading = ref(false)
const executionsLoading = ref(false)
const refreshing = ref(false)
const assetsError = ref('')
const executionsError = ref('')

// 指标：优先用后端聚合接口（口径统一、不受列表 limit 截断影响），
// 后端没返回时回退到前端从列表计算，保证老后端也能用。
const execStats = ref(null)
const onlineCount = computed(() => assets.value.filter((a) => a.status === 'online').length)
const offlineCount = computed(() => assets.value.filter((a) => a.status === 'unreachable' || a.status === 'offline').length)
// 指标口径：REJECTED 是「被拦在门口、从未执行」的请求，不算执行任务，
// 也不进成功率分母 —— 否则故意刷一批危险命令就能把成功率打下来。
const dispatchedExecs = computed(() => executions.value.filter((e) => e.status !== 'REJECTED'))
const todayCount = computed(() => execStats.value?.today_count ?? dispatchedExecs.value.filter((e) => isToday(e.created_at)).length)
const successCount = computed(
  () => execStats.value?.success_count ?? dispatchedExecs.value.filter((e) => String(e.status).toUpperCase() === 'SUCCESS').length,
)
const successRate = computed(() => {
  if (execStats.value) return execStats.value.success_rate
  if (!dispatchedExecs.value.length) return null
  return Math.round((successCount.value / dispatchedExecs.value.length) * 100)
})

// 资产台账
const assetKeyword = ref('')
const filteredAssets = computed(() => {
  const key = assetKeyword.value.trim().toLowerCase()
  if (!key) return assets.value
  return assets.value.filter((a) =>
    [a.name, a.ip_address, a.os_type, a.ssh_user].some((field) =>
      String(field || '').toLowerCase().includes(key),
    ),
  )
})
const assetMap = computed(() => new Map(assets.value.map((a) => [a.id, a])))
const pingJobs = reactive({})
const pingPollers = new Map()

// 录入/编辑表单（同一个对话框复用：有 editingAssetId 就是编辑）
const createDialogVisible = ref(false)
const editingAssetId = ref(null)
const editingAsset = computed(() => assets.value.find((a) => a.id === editingAssetId.value) || null)
const submitting = ref(false)
const formError = ref('')
const formRef = ref()
const INITIAL_FORM = {
  name: '',
  ip_address: '',
  os_type: 'Linux',
  ssh_port: 22,
  ssh_user: 'root',
  ssh_password: '',
}
const form = reactive({ ...INITIAL_FORM })

const validateIp = (rule, value, callback) => {
  const ipv4 = /^(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)){3}$/
  if (!value) return callback(new Error('请输入 IP 地址'))
  if (!ipv4.test(value) && !/^[\da-fA-F:.]+$/.test(value)) {
    return callback(new Error('请输入合法的 IPv4 或 IPv6 地址'))
  }
  return callback()
}

const formRules = {
  name: [
    { required: true, message: '请输入主机名称', trigger: 'blur' },
    {
      pattern: /^[A-Za-z0-9._-]{2,64}$/,
      message: '仅支持字母、数字、点、下划线、连字符（2-64 位）',
      trigger: 'blur',
    },
  ],
  ip_address: [{ validator: validateIp, trigger: 'blur' }],
  os_type: [{ required: true, message: '请选择操作系统', trigger: 'change' }],
  ssh_port: [
    {
      validator: (rule, value, callback) => {
        if (!Number.isInteger(value) || value < 1 || value > 65535) {
          return callback(new Error('端口范围 1-65535'))
        }
        return callback()
      },
      trigger: 'change',
    },
  ],
  ssh_user: [{ required: true, message: '请输入 SSH 用户名', trigger: 'blur' }],
}

// 远程终端
const selectedAssetId = ref(null)
const selectedAsset = computed(
  () => assets.value.find((a) => a.id === selectedAssetId.value) || null,
)
const terminalCommand = ref('uptime')
const terminalPassword = ref('')
const terminalLines = ref([])
const isExecuting = ref(false)
const outputRef = ref()
const commandRef = ref()
const terminalStartedAt = ref(null)
const terminalMeta = reactive({
  taskId: '-',
  exitCode: null,
  durationMs: null,
  status: 'IDLE',
  elapsedMs: 0,
})
let commandPoller = null

const now = ref(Date.now())
let ticker = null

const terminalElapsedLabel = computed(() => {
  if (isExecuting.value && terminalStartedAt.value) {
    return `${((now.value - terminalStartedAt.value) / 1000).toFixed(1)}s`
  }
  return terminalMeta.durationMs == null ? '—' : formatDuration(terminalMeta.durationMs)
})

const terminalStatusMeta = computed(() => {
  if (terminalMeta.status === 'IDLE') return { label: '待命', tone: 'neutral' }
  if (terminalMeta.status === 'ERROR') return { label: '执行异常', tone: 'danger' }
  return statusMeta(terminalMeta.status)
})

// 审计日志
const execStatusFilter = ref('')
const execLimit = ref(50)
const drawerVisible = ref(false)
const currentExecution = ref(null)

const executionRows = computed(() =>
  executions.value
    .filter((e) => !execStatusFilter.value || e.status === execStatusFilter.value)
    .slice(0, execLimit.value)
    .map((e) => {
    const asset = assetMap.value.get(e.asset_id)
    return {
      ...e,
      taskShort: shortId(e.task_id),
      assetLabel: asset?.name || (e.asset_id ? `资产 #${e.asset_id}` : '—'),
      assetIp: asset?.ip_address || '—',
      durationLabel:
        e.duration_ms == null ? '—' : `${Math.round(Number(e.duration_ms))} ms`,
      createdLabel: formatDateTime(e.created_at),
      finishedLabel: formatDateTime(e.finished_at),
    }
  }),
)

/* ==========================================================================
   数据加载
   ========================================================================== */
// 真实健康状态：200 = 在线；503 = 接口活着但数据库/缓存有依赖异常；连不上 = 离线
const backendHealth = ref('checking')
let healthTimer = null

const healthMeta = computed(() => ({
  online: { label: 'API ONLINE', tone: 'success' },
  degraded: { label: 'API DEGRADED', tone: 'warn' },
  offline: { label: 'API OFFLINE', tone: 'danger' },
  checking: { label: 'API CHECKING', tone: 'neutral' },
}[backendHealth.value]))

async function refreshHealth() {
  try {
    await getHealth()
    backendHealth.value = 'online'
  } catch (err) {
    backendHealth.value = err?.response?.status === 503 ? 'degraded' : 'offline'
  }
}

async function refreshAssets({ silent = false } = {}) {
  assetsLoading.value = true
  try {
    const data = unwrap(await getAssets())
    assets.value = (Array.isArray(data) ? data : []).map((raw) => {
      const asset = normalizeAsset(raw)
      // 探活任务不写库，刷新时把本会话结论补回去
      const job = pingJobs[asset.id]
      if (job?.state === 'done' && job.reachable !== undefined) {
        asset.status = job.reachable ? 'online' : 'offline'
      }
      return asset
    })
    assetsError.value = ''
    if (
      selectedAssetId.value === null ||
      !assets.value.some((a) => a.id === selectedAssetId.value)
    ) {
      selectedAssetId.value = assets.value[0]?.id ?? null
    }
  } catch (err) {
    assetsError.value = errorText(err)
    if (!silent) notifyError('资产列表加载失败', err)
  } finally {
    assetsLoading.value = false
  }
}

async function refreshExecutions({ silent = false } = {}) {
  executionsLoading.value = true
  try {
    // 始终拉全量快照：指标大盘必须基于完整数据，表格的状态/条数筛选放在前端做
    const data = unwrap(await getExecutions({ limit: 100 }))
    executions.value = (Array.isArray(data) ? data : []).map(normalizeExecution)
    executionsError.value = ''
    // 统计口径由后端统一，独立于列表 limit
    try {
      execStats.value = unwrap(await getExecutionStats())
    } catch {
      execStats.value = null // 后端没有该接口时回退前端计算
    }
  } catch (err) {
    executionsError.value = errorText(err)
    if (!silent) notifyError('审计日志加载失败', err)
  } finally {
    executionsLoading.value = false
  }
}

async function refreshAll() {
  refreshing.value = true
  try {
    await Promise.all([refreshAssets(), refreshExecutions(), refreshHealth()])
  } finally {
    refreshing.value = false
  }
}

/* ==========================================================================
   录入主机
   ========================================================================== */
watch(createDialogVisible, (open) => {
  if (open) {
    formError.value = ''
    nextTick(() => formRef.value?.clearValidate())
  } else {
    // 取消/关闭时清掉编辑态，避免下次点"新增"误带入编辑 ID
    editingAssetId.value = null
  }
})

function resetForm() {
  Object.assign(form, INITIAL_FORM)
  editingAssetId.value = null
  nextTick(() => formRef.value?.clearValidate())
}

// 打开新增对话框
function openCreate() {
  resetForm()
  createDialogVisible.value = true
}

// 打开编辑对话框：把已有资产的值灌进表单。
// 密码框留空 = 保持原密码（后端按三态语义处理），不回填密文。
function openEdit(asset) {
  editingAssetId.value = asset.id
  Object.assign(form, {
    name: asset.name,
    ip_address: asset.ip_address,
    os_type: asset.os_type,
    ssh_port: asset.ssh_port,
    ssh_user: asset.ssh_user,
    ssh_password: '',
  })
  formError.value = ''
  createDialogVisible.value = true
  nextTick(() => formRef.value?.clearValidate())
}

async function handleCreate() {
  formError.value = ''
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  submitting.value = true
  const payload = {
    name: form.name.trim(),
    ip_address: form.ip_address.trim(),
    os_type: form.os_type,
    ssh_port: Number(form.ssh_port),
    ssh_user: form.ssh_user.trim(),
    ssh_password: form.ssh_password.trim() || undefined,
  }
  try {
    if (editingAssetId.value) {
      await updateAsset(editingAssetId.value, payload)
      ElMessage.success(`主机 ${form.name} 已更新`)
    } else {
      await createAsset(payload)
      ElMessage.success(`主机 ${form.name} 已纳入资产台账`)
    }
    createDialogVisible.value = false
    resetForm()
    await refreshAssets({ silent: true })
  } catch (err) {
    formError.value = errorText(err)
    notifyError(editingAssetId.value ? '更新失败' : '录入失败', err)
  } finally {
    submitting.value = false
  }
}

async function handleDelete(asset) {
  try {
    await ElMessageBox.confirm(
      `确定删除主机「${asset.name}」？关联的审计记录会保留，只是不再关联该主机。`,
      '删除资产',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await deleteAsset(asset.id)
    ElMessage.success(`主机 ${asset.name} 已删除`)
    if (selectedAssetId.value === asset.id) selectedAssetId.value = null
    await refreshAssets({ silent: true })
  } catch (err) {
    notifyError('删除失败', err)
  }
}

/* ==========================================================================
   异步探活
   ========================================================================== */
async function handlePing(asset) {
  if (pingJobs[asset.id]?.state === 'running') return
  const poller = createPoller()
  pingPollers.set(asset.id, poller)
  pingJobs[asset.id] = {
    state: 'running',
    status: 'PENDING',
    attempts: 0,
    latency: null,
    message: '正在下发探测任务…',
  }

  try {
    const dispatched = unwrap(await dispatchPing(asset.ip_address))
    const taskId = dispatched?.task_id
    if (!taskId) throw new Error('后端未返回 task_id')

    const outcome = await poller.run(taskId, ({ status, attempts, message }) => {
      const job = pingJobs[asset.id]
      if (!job) return
      job.status = status
      job.attempts = attempts
      job.message = message || `第 ${attempts} 次状态查询`
    })

    const job = pingJobs[asset.id]
    const row = assets.value.find((a) => a.id === asset.id)
    if (outcome?.status === 'SUCCESS') {
      const result = outcome.result || {}
      const reachable = result.reachable !== false
      Object.assign(job, {
        state: 'done',
        status: 'SUCCESS',
        reachable,
        latency: result.latency_ms ?? null,
      })
      if (row) row.status = reachable ? 'online' : 'offline'
      if (reachable) ElMessage.success(`${asset.name} 探活成功 · ${result.latency_ms ?? '—'} ms`)
      else ElMessage.warning(`${asset.name} 不可达`)
    } else {
      Object.assign(job, {
        state: 'error',
        status: outcome?.status || 'FAILURE',
        message: '后台探测任务未返回成功结果',
      })
      if (row) row.status = 'offline'
      ElMessage.error(`${asset.name} 探测失败`)
    }
  } catch (err) {
    const job = pingJobs[asset.id]
    if (job) Object.assign(job, { state: 'error', status: 'ERROR', message: errorText(err) })
    if (err.code === 'TIMEOUT') {
      ElMessage({ type: 'error', message: err.message, showClose: true, duration: 5000 })
    } else if (err.code !== 'ABORTED') {
      notifyError('探活中断', err)
    }
  } finally {
    pingPollers.delete(asset.id)
  }
}

/* ==========================================================================
   远程剧本终端
   ========================================================================== */
function pushLine(kind, text) {
  if (text === undefined || text === null || text === '') return
  terminalLines.value.push({ time: formatClock(), kind, text: String(text) })
  nextTick(() => {
    const el = outputRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

function usePreset(item) {
  terminalCommand.value = item.command
  commandRef.value?.focus()
}

function handleQuickCommand(asset) {
  selectedAssetId.value = asset.id
  terminalCommand.value = 'uptime'
  activeTab.value = 'console'
  nextTick(() => {
    commandRef.value?.focus()
    document.getElementById('cy-terminal')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  })
  ElMessage.info(`已选中 ${asset.name}，终端预填 uptime，确认后点击执行`)
}

function handleAbort() {
  commandPoller?.cancel()
  ElMessage.info('已停止前端轮询（后端任务仍会继续执行）')
}

function clearTerminal() {
  if (isExecuting.value) commandPoller?.cancel()
  terminalLines.value = []
  Object.assign(terminalMeta, {
    taskId: '-',
    exitCode: null,
    durationMs: null,
    status: 'IDLE',
    elapsedMs: 0,
  })
}

async function copyText(text, label = '内容') {
  if (!text) {
    ElMessage.warning(`暂无${label}可复制`)
    return
  }
  try {
    await navigator.clipboard.writeText(String(text))
    ElMessage.success(`${label}已复制`)
  } catch {
    ElMessage.warning('浏览器拒绝了剪贴板访问，请手动选中复制')
  }
}

const copyTerminalOutput = () =>
  copyText(terminalLines.value.map((line) => line.text).join('\n'), '终端输出')

async function handleExecute() {
  if (isExecuting.value) return
  const asset = selectedAsset.value
  if (!asset) {
    ElMessage.warning('请先选择目标主机')
    return
  }
  const cmd = terminalCommand.value.trim()
  if (!cmd) {
    ElMessage.warning('请输入要执行的命令')
    return
  }

  isExecuting.value = true
  terminalStartedAt.value = Date.now()
  terminalLines.value = []
  Object.assign(terminalMeta, {
    taskId: '-',
    exitCode: null,
    durationMs: null,
    status: 'PENDING',
    elapsedMs: 0,
  })
  commandPoller = createPoller()

  pushLine('cmd', `$ ${cmd}`)
  pushLine('info', `目标 ${asset.ssh_user}@${asset.ip_address}:${asset.ssh_port} · 正在下发剧本任务…`)

  try {
    const dispatched = unwrap(
      await executeCommand({
        asset_id: asset.id,
        command: cmd,
        trigger_source: 'MANUAL',
        ...(terminalPassword.value ? { ssh_password: terminalPassword.value } : {}),
      }),
    )
    const taskId = dispatched?.task_id
    if (!taskId) throw new Error('后端未返回 task_id')
    terminalMeta.taskId = taskId
    pushLine('info', `202 Accepted · task_id=${taskId}`)
    if (dispatched.message) pushLine('info', dispatched.message)

    let lastState = ''
    const outcome = await commandPoller.run(
      taskId,
      ({ status, attempts, message, elapsedMs }) => {
        terminalMeta.status = status
        terminalMeta.elapsedMs = elapsedMs
        if (status === 'RETRYING') {
          pushLine('state', `[轮询 #${attempts}] ${message}`)
        } else if (!TERMINAL_STATES.includes(status) && status !== lastState) {
          pushLine('state', `[轮询 #${attempts}] ${statusMeta(status).label} · 等待 Worker 写入结果`)
        } else if (!TERMINAL_STATES.includes(status) && attempts <= 2) {
          pushLine('state', `[轮询 #${attempts}] 结果尚未就绪…`)
        }
        lastState = status
      },
    )

    const state = outcome?.status
    terminalMeta.status = state
    const result = outcome?.result || {}

    if (state === 'SUCCESS') {
      terminalMeta.exitCode = result.exit_code ?? null
      terminalMeta.durationMs = result.duration_ms ?? terminalMeta.elapsedMs
      pushLine(
        'meta',
        `exit_code=${result.exit_code ?? 'N/A'} · 耗时 ${formatDuration(terminalMeta.durationMs)}`,
      )
      const quiet = !result.stdout && !result.stderr
      if (result.stdout) pushLine('stdout', result.stdout)
      if (result.stderr) pushLine('stderr', result.stderr)
      if (quiet) pushLine('info', '（stdout / stderr 均为空）')

      const failed =
        result.success === false ||
        (result.exit_code !== undefined && result.exit_code !== null && result.exit_code !== 0)
      if (failed) {
        pushLine('error', '命令执行失败，请检查上方 stderr（审计记录已标记为 FAILED）')
        ElMessage({ type: 'error', message: '命令执行失败，详见终端 stderr', showClose: true, duration: 5000 })
      } else if (quiet) {
        // 任务成功 != 命令做了事：rm -rf 缺目标时 shell 会静默返回 0、不输出任何内容
        pushLine('success', '[OK] 任务完成 · exit_code=0，但命令没有任何输出（可能未产生实际效果）')
        ElMessage.success('任务完成（命令无输出），审计日志已更新')
      } else {
        pushLine('success', '[OK] 任务完成 · exit_code=0')
        ElMessage.success('命令执行成功，审计日志已更新')
      }
    } else if (state === 'FAILURE') {
      pushLine(
        'error',
        `后台任务失败：${typeof outcome.result === 'string' ? outcome.result : JSON.stringify(outcome.result ?? {})}`,
      )
      ElMessage.error('后台任务执行失败')
    } else {
      pushLine('error', `任务被撤销：${outcome?.result ?? ''}`)
      ElMessage.warning('任务已被撤销')
    }

    // 核心交互：终端执行结束后自动刷新审计列表（Worker 已 commit，稍等再拉）
    await sleep(300)
    await refreshExecutions({ silent: true })
  } catch (err) {
    terminalMeta.status = 'ERROR'
    if (err.code === 'ABORTED') {
      pushLine('error', '已停止前端轮询，后端任务仍会继续执行')
    } else if (err.code === 'TIMEOUT') {
      pushLine('error', err.message)
      ElMessage({ type: 'error', message: err.message, showClose: true, duration: 5000 })
    } else {
      pushLine('error', `执行中断：${errorText(err)}`)
      notifyError('命令下发失败', err)
    }
  } finally {
    isExecuting.value = false
    commandPoller = null
    terminalStartedAt.value = null
  }
}

/* ==========================================================================
   审计日志抽屉
   ========================================================================== */
async function handleViewLog(row) {
  // 先用列表行秒开抽屉，再异步拉详情补全最新全文（长输出在列表里可能被截断）。
  currentExecution.value = row
  drawerVisible.value = true
  try {
    const detail = unwrap(await getExecutionDetail(row.task_id))
    currentExecution.value = normalizeExecution(detail)
  } catch {
    // 详情接口不可用时保留列表行，抽屉照样能看，不打断操作。
  }
}

// 状态与条数为前端本地筛选，不触发额外请求；指标大盘始终基于全量快照

/* ==========================================================================
   生命周期
   ========================================================================== */
onMounted(() => {
  refreshAll()
  healthTimer = setInterval(refreshHealth, 30000)
  ticker = setInterval(() => {
    now.value = Date.now()
  }, 500)
})

onBeforeUnmount(() => {
  clearInterval(ticker)
  clearInterval(healthTimer)
  pingPollers.forEach((poller) => poller.cancel())
  commandPoller?.cancel()
})
</script>

<template>
  <div class="cy-shell">
    <!-- ===================== 顶部栏 ===================== -->
    <header class="cy-header">
      <div class="cy-container cy-header__inner">
        <div class="cy-brand">
          <div class="cy-brand__mark"><el-icon :size="20"><Monitor /></el-icon></div>
          <div>
            <div class="cy-brand__name">OpsPilot <span>/</span> <em>自愈控制台</em></div>
            <div class="cy-brand__tag">ASSET · PROBE · RUNBOOK · AUDIT</div>
          </div>
        </div>
        <div class="cy-header__actions">
          <span class="cy-live">
            <span
              class="cy-dot"
              :class="[`cy-dot--${healthMeta.tone}`, backendHealth === 'checking' && 'cy-dot--pulse']"
            />
            {{ healthMeta.label }}
          </span>
          <el-button :icon="Refresh" :loading="refreshing" @click="refreshAll">刷新全盘</el-button>
          <el-button type="primary" :icon="Plus" @click="openCreate()">
            + 录入主机
          </el-button>
        </div>
      </div>
    </header>

    <main class="cy-container cy-main">
      <!-- ===================== 指标大盘 ===================== -->
      <section class="cy-metrics">
        <div class="cy-metric">
          <div class="cy-metric__icon"><el-icon><Monitor /></el-icon></div>
          <div class="cy-metric__body">
            <div class="cy-metric__label">纳管主机总数</div>
            <div class="cy-metric__value">{{ assets.length }}</div>
            <div class="cy-metric__hint">ONLINE {{ onlineCount }} / OFFLINE {{ offlineCount }}</div>
          </div>
          <div class="cy-metric__glow" />
        </div>
        <div class="cy-metric">
          <div class="cy-metric__icon cy-metric__icon--blue"><el-icon><Timer /></el-icon></div>
          <div class="cy-metric__body">
            <div class="cy-metric__label">今日执行任务数</div>
            <div class="cy-metric__value">{{ todayCount }}</div>
            <div class="cy-metric__hint">共 {{ executions.length }} 条审计记录</div>
          </div>
          <div class="cy-metric__glow" />
        </div>
        <div class="cy-metric">
          <div class="cy-metric__icon cy-metric__icon--green"><el-icon><CircleCheck /></el-icon></div>
          <div class="cy-metric__body">
            <div class="cy-metric__label">任务成功率</div>
            <div class="cy-metric__value">
              {{ successRate === null ? '—' : `${successRate}%` }}
            </div>
            <div class="cy-metric__hint">SUCCESS {{ successCount }} / 全部 {{ dispatchedExecs.length }}</div>
          </div>
          <div class="cy-metric__glow" />
        </div>
      </section>

      <!-- ===================== 主功能区 ===================== -->
      <el-tabs v-model="activeTab" class="cy-tabs">
        <!-- ---------- Tab 1 ---------- -->
        <el-tab-pane name="console">
          <template #label>
            <span class="cy-tab-label"><el-icon><Monitor /></el-icon> 主机台账与控制台</span>
          </template>

          <div class="cy-grid">
            <!-- 主机台账 -->
            <section class="cy-card">
              <div class="cy-card__head">
                <div>
                  <div class="cy-card__title">主机台账</div>
                  <div class="cy-card__sub">GET /api/v1/assets · POST /api/v1/tasks/ping</div>
                </div>
                <el-input
                  v-model="assetKeyword"
                  :prefix-icon="Search"
                  placeholder="搜索名称 / IP"
                  clearable
                  class="cy-search"
                />
              </div>
              <div class="cy-card__body">
                <el-alert v-if="assetsError" type="error" show-icon :closable="false" class="cy-alert">
                  <template #title>资产列表加载失败</template>
                  <div class="cy-alert__body">
                    <span>{{ assetsError }}</span>
                    <el-button link type="primary" @click="refreshAssets()">重新加载</el-button>
                  </div>
                </el-alert>

                <el-table
                  :data="filteredAssets"
                  v-loading="assetsLoading"
                  element-loading-text="正在拉取资产台账…"
                  row-key="id"
                  style="width: 100%"
                >
                  <el-table-column label="主机名" min-width="150">
                    <template #default="{ row }">
                      <div class="cy-host-name">
                        {{ row.name }}
                        <el-tooltip v-if="row.has_stored_password" content="已加密保存 SSH 密码" placement="top">
                          <el-icon class="cy-host-lock"><Lock /></el-icon>
                        </el-tooltip>
                      </div>
                      <div class="cy-host-id">#{{ row.id }} · {{ row.os_type }}</div>
                    </template>
                  </el-table-column>
                  <el-table-column label="IP 地址" min-width="140">
                    <template #default="{ row }">
                      <span class="cy-mono cy-ip">{{ row.ip_address }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="SSH 用户 / 端口" min-width="140">
                    <template #default="{ row }">
                      <div class="cy-ssh">
                        <span class="cy-ssh__user">{{ row.ssh_user }}</span>
                        <span class="cy-ssh__sep">:</span>
                        <span>{{ row.ssh_port }}</span>
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column label="状态 / 探活" width="140">
                    <template #default="{ row }">
                      <div class="cy-status">
                        <span class="cy-dot" :class="`cy-dot--${assetStatusMeta(row.status).tone}`" />
                        <span>{{ assetStatusMeta(row.status).label }}</span>
                      </div>
                      <div v-if="pingJobs[row.id]?.state === 'running'" class="cy-probing">
                        <el-icon class="is-loading"><Loading /></el-icon>
                        {{ statusMeta(pingJobs[row.id].status).label }} · {{ pingJobs[row.id].attempts }}次
                      </div>
                      <div v-else-if="pingJobs[row.id]?.state === 'error'" class="cy-probe-fail">
                        探测失败
                      </div>
                      <div v-else-if="pingJobs[row.id]?.latency != null" class="cy-latency">
                        {{ Number(pingJobs[row.id].latency).toFixed(1) }} ms
                      </div>
                      <div v-else class="cy-hint">未探测</div>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="290">
                    <template #default="{ row }">
                      <div class="cy-actions">
                        <el-button
                          size="small"
                          :icon="Connection"
                          :loading="pingJobs[row.id]?.state === 'running'"
                          @click="handlePing(row)"
                        >
                          {{ pingJobs[row.id]?.state === 'running' ? '探测中' : '异步探活' }}
                        </el-button>
                        <el-button size="small" :icon="CaretRight" @click="handleQuickCommand(row)">
                          下发命令
                        </el-button>
                        <el-button size="small" :icon="Edit" @click="openEdit(row)">编辑</el-button>
                        <el-button
                          size="small"
                          type="danger"
                          plain
                          :icon="Delete"
                          @click="handleDelete(row)"
                        >
                          删除
                        </el-button>
                      </div>
                    </template>
                  </el-table-column>
                  <template #empty>
                    <el-empty description="暂无纳管主机" :image-size="70">
                      <el-button type="primary" size="small" @click="openCreate()">
                        录入第一台主机
                      </el-button>
                    </el-empty>
                  </template>
                </el-table>

                <div class="cy-table-foot">
                  <span>共 <b>{{ assets.length }}</b> 台，显示 {{ filteredAssets.length }} 台</span>
                  <span class="cy-hint">探活结果仅保留在当前会话（后端不写库）</span>
                </div>
              </div>
            </section>

            <!-- 远程剧本终端 -->
            <section id="cy-terminal" class="cy-card">
              <div class="cy-card__head">
                <div>
                  <div class="cy-card__title">远程剧本终端</div>
                  <div class="cy-card__sub">POST /api/v1/runbooks/execute → GET /api/v1/tasks/{task_id}</div>
                </div>
                <span class="cy-tag" :class="`cy-tag--${terminalStatusMeta.tone}`">
                  <span
                    class="cy-dot"
                    :class="[`cy-dot--${terminalStatusMeta.tone}`, isExecuting && 'cy-dot--pulse']"
                  />
                  {{ terminalStatusMeta.label }}
                </span>
              </div>

              <div class="cy-card__body cy-term-body">
                <div class="cy-field">
                  <label class="cy-label">目标主机</label>
                  <el-select
                    v-model="selectedAssetId"
                    placeholder="请选择已纳管主机"
                    :disabled="!assets.length"
                    style="width: 100%"
                  >
                    <el-option
                      v-for="asset in assets"
                      :key="asset.id"
                      :label="`${asset.name} · ${asset.ip_address}`"
                      :value="asset.id"
                    >
                      <div class="cy-option">
                        <span>{{ asset.name }}</span>
                        <span class="cy-mono">{{ asset.ip_address }}</span>
                      </div>
                    </el-option>
                  </el-select>
                </div>

                <div class="cy-field">
                  <label class="cy-label">SSH 密码 <span class="cy-hint">（可选）</span></label>
                  <el-input
                    v-model="terminalPassword"
                    type="password"
                    show-password
                    :prefix-icon="Lock"
                    clearable
                    placeholder="留空则使用免密密钥"
                  />
                </div>
                <p class="cy-hint cy-note">密码仅随本次请求发送，不写入资产库、不保存在浏览器。</p>

                <div class="cy-field">
                  <label class="cy-label">预设命令</label>
                  <div class="cy-presets">
                    <button
                      v-for="item in PRESET_COMMANDS"
                      :key="item.command"
                      type="button"
                      class="cy-chip"
                      :title="item.command"
                      @click="usePreset(item)"
                    >
                      <el-icon><MagicStick /></el-icon>{{ item.label }}
                    </button>
                  </div>
                </div>

                <div class="cy-field">
                  <label class="cy-label">Shell 命令</label>
                  <el-input
                    ref="commandRef"
                    v-model="terminalCommand"
                    type="textarea"
                    :rows="3"
                    resize="none"
                    spellcheck="false"
                    class="cy-command cy-mono"
                    placeholder="uptime"
                    @keydown.ctrl.enter.prevent="handleExecute"
                    @keydown.meta.enter.prevent="handleExecute"
                  />
                </div>

                <div class="cy-actions cy-term-actions">
                  <el-button
                    type="primary"
                    :icon="CaretRight"
                    :loading="isExecuting"
                    :disabled="!selectedAsset"
                    @click="handleExecute"
                  >
                    {{ isExecuting ? '执行中…' : '下发并执行' }}
                  </el-button>
                  <el-button v-if="isExecuting" :icon="Close" @click="handleAbort">停止轮询</el-button>
                  <el-button :icon="Delete" :disabled="!terminalLines.length" @click="clearTerminal">
                    清空
                  </el-button>
                  <el-button
                    :icon="DocumentCopy"
                    :disabled="!terminalLines.length"
                    @click="copyTerminalOutput"
                  >
                    复制
                  </el-button>
                  <span class="cy-shortcut"><span class="cy-kbd">Ctrl</span> + <span class="cy-kbd">Enter</span></span>
                </div>

                <div class="cy-window">
                  <div class="cy-window__bar">
                    <span class="cy-dots" aria-hidden="true"><i /><i /><i /></span>
                    <span class="cy-mono cy-window__title">
                      opspilot@{{ selectedAsset?.name || 'console' }}:~$
                    </span>
                    <span class="cy-mono cy-window__meta">
                      {{ terminalMeta.taskId !== '-' ? `task ${shortId(terminalMeta.taskId)}` : 'idle' }}
                    </span>
                  </div>

                  <div ref="outputRef" class="cy-output">
                    <div v-if="!terminalLines.length" class="cy-output-empty">
                      <div class="cy-mono cy-prompt">$ <span class="cy-caret">_</span></div>
                      <p>选择目标主机并输入命令，执行过程与结果会实时回显在这里。</p>
                      <p class="cy-hint">异步链路：下发 → task_id → 短轮询查询任务状态</p>
                    </div>
                    <template v-else>
                      <div
                        v-for="(line, index) in terminalLines"
                        :key="index"
                        class="cy-line"
                        :class="`cy-line--${line.kind}`"
                      >
                        <span class="cy-line__time cy-mono">{{ line.time }}</span>
                        <pre
                          v-if="line.kind === 'stdout' || line.kind === 'stderr'"
                          class="cy-line__text"
                        >{{ line.text }}</pre>
                        <span v-else class="cy-line__text">{{ line.text }}</span>
                      </div>
                      <div v-if="isExecuting" class="cy-waiting">
                        <span class="cy-dot cy-dot--info cy-dot--pulse" />
                        <span class="cy-mono">等待 Celery Worker 写入结果（{{ terminalElapsedLabel }}）…</span>
                      </div>
                    </template>
                  </div>

                  <div class="cy-term-foot">
                    <span><b>TASK</b> <span class="cy-mono">{{ shortId(terminalMeta.taskId) }}</span></span>
                    <span><b>EXIT</b> <span class="cy-mono">{{ terminalMeta.exitCode ?? '—' }}</span></span>
                    <span><b>耗时</b> <span class="cy-mono">{{ terminalElapsedLabel }}</span></span>
                    <span class="cy-mono" :class="`cy-foot-state--${terminalStatusMeta.tone}`">
                      {{ terminalStatusMeta.label }}
                    </span>
                  </div>
                </div>
              </div>
            </section>
          </div>
        </el-tab-pane>

        <!-- ---------- Tab 2 ---------- -->
        <el-tab-pane name="audit">
          <template #label>
            <span class="cy-tab-label"><el-icon><DocumentCopy /></el-icon> 执行历史与审计日志</span>
          </template>

          <section class="cy-card">
            <div class="cy-card__head">
              <div>
                <div class="cy-card__title">执行历史与审计日志</div>
                <div class="cy-card__sub">GET /api/v1/executions · 全生命周期留痕</div>
              </div>
              <div class="cy-card__tools">
                <el-select v-model="execStatusFilter" placeholder="全部状态" clearable class="cy-filter">
                  <el-option label="SUCCESS" value="SUCCESS" />
                  <el-option label="FAILED" value="FAILED" />
                  <el-option label="RUNNING" value="RUNNING" />
                  <el-option label="PENDING" value="PENDING" />
                  <el-option label="REJECTED" value="REJECTED" />
                </el-select>
                <el-select v-model="execLimit" class="cy-filter cy-filter--small">
                  <el-option :label="'最近 20 条'" :value="20" />
                  <el-option :label="'最近 50 条'" :value="50" />
                  <el-option :label="'最近 100 条'" :value="100" />
                </el-select>
                <el-button :icon="Refresh" :loading="executionsLoading" @click="refreshExecutions()">
                  刷新
                </el-button>
              </div>
            </div>

            <div class="cy-card__body">
              <el-alert v-if="executionsError" type="error" show-icon :closable="false" class="cy-alert">
                <template #title>审计日志加载失败</template>
                <div class="cy-alert__body">
                  <span>{{ executionsError }}</span>
                  <el-button link type="primary" @click="refreshExecutions()">重新加载</el-button>
                </div>
              </el-alert>

              <el-table
                :data="executionRows"
                v-loading="executionsLoading"
                element-loading-text="正在拉取审计记录…"
                row-key="task_id"
                style="width: 100%"
              >
                <el-table-column label="任务 ID" width="116">
                  <template #default="{ row }">
                    <span class="cy-mono cy-task-id" :title="row.task_id">{{ row.taskShort }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="目标资产" min-width="160">
                  <template #default="{ row }">
                    <div class="cy-host-name">{{ row.assetLabel }}</div>
                    <div class="cy-host-id cy-mono">{{ row.assetIp }}</div>
                  </template>
                </el-table-column>
                <el-table-column label="执行命令" min-width="190" show-overflow-tooltip>
                  <template #default="{ row }">
                    <span class="cy-mono cy-command-cell">{{ row.command }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="触发源" width="150">
                  <template #default="{ row }">
                    <span class="cy-tag" :class="`cy-tag--${triggerMeta(row.trigger_source).tone}`">
                      {{ triggerMeta(row.trigger_source).label }}
                    </span>
                  </template>
                </el-table-column>
                <el-table-column label="状态" width="118">
                  <template #default="{ row }">
                    <span class="cy-tag" :class="`cy-tag--${statusMeta(row.status).tone}`">
                      <span class="cy-dot" :class="`cy-dot--${statusMeta(row.status).tone}`" />
                      {{ statusMeta(row.status).label }}
                    </span>
                  </template>
                </el-table-column>
                <el-table-column label="耗时" width="110">
                  <template #default="{ row }">
                    <span class="cy-mono cy-duration">{{ row.durationLabel }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="执行时间" width="160">
                  <template #default="{ row }">
                    <span class="cy-mono cy-time">{{ row.createdLabel }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="118" fixed="right">
                  <template #default="{ row }">
                    <el-button size="small" :icon="Search" @click="handleViewLog(row)">
                      查看日志
                    </el-button>
                  </template>
                </el-table-column>
                <template #empty>
                  <el-empty description="暂无执行审计记录" :image-size="70" />
                </template>
              </el-table>

              <div class="cy-table-foot">
                <span>共 <b>{{ executionRows.length }}</b> 条记录</span>
                <span class="cy-hint">终端执行完成后会自动刷新此列表</span>
              </div>
            </div>
          </section>
        </el-tab-pane>
      </el-tabs>

      <footer class="cy-foot">
        <span class="cy-mono">OpsPilot · FastAPI / Celery / Redis / PostgreSQL</span>
        <span class="cy-hint">远程命令请谨慎执行 · 所有操作均写入审计日志</span>
      </footer>
    </main>

    <!-- ===================== 录入主机 ===================== -->
    <el-dialog
      v-model="createDialogVisible"
      width="540px"
      align-center
      :close-on-click-modal="false"
      destroy-on-close
      class="cy-dialog"
    >
      <template #header>
        <div class="cy-dialog__head">
          <div class="cy-dialog__icon"><el-icon :size="18"><Monitor /></el-icon></div>
          <div>
            <div class="cy-dialog__title">{{ editingAssetId ? '编辑主机资产' : '录入新主机资产' }}</div>
            <div class="cy-mono cy-dialog__sub">
              {{ editingAssetId ? `PUT /api/v1/assets/${editingAssetId}` : 'POST /api/v1/assets' }}
            </div>
          </div>
        </div>
      </template>

      <el-form ref="formRef" :model="form" :rules="formRules" label-position="top">
        <div class="cy-form-grid">
          <el-form-item label="主机名称" prop="name">
            <el-input v-model="form.name" placeholder="node-prod-02" clearable />
          </el-form-item>
          <el-form-item label="IP 地址" prop="ip_address">
            <el-input v-model="form.ip_address" placeholder="192.168.1.101" clearable />
          </el-form-item>
          <el-form-item label="操作系统" prop="os_type">
            <el-select v-model="form.os_type" style="width: 100%">
              <el-option label="Linux" value="Linux" />
              <el-option label="Windows" value="Windows" />
              <el-option label="Darwin / macOS" value="Darwin" />
              <el-option label="其他" value="Other" />
            </el-select>
          </el-form-item>
          <el-form-item label="SSH 端口" prop="ssh_port">
            <el-input-number
              v-model="form.ssh_port"
              :min="1"
              :max="65535"
              controls-position="right"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="SSH 用户" prop="ssh_user">
            <el-input v-model="form.ssh_user" placeholder="root" clearable />
          </el-form-item>
          <el-form-item :label="editingAssetId ? 'SSH 密码（留空=不改动）' : 'SSH 密码（可选）'">
            <el-input
              v-model="form.ssh_password"
              type="password"
              show-password
              clearable
              :placeholder="editingAssetId
                ? (editingAsset?.has_stored_password ? '已存密码；留空保持不变，清空请点右侧×' : '留空则使用免密密钥')
                : '留空则使用已配置的免密密钥'"
            />
          </el-form-item>
          <el-form-item :label="editingAssetId ? '当前状态' : '初始状态'">
            <el-input
              :model-value="editingAssetId ? (editingAsset?.status || 'unknown') : '待探测 (unknown)'"
              disabled
            />
          </el-form-item>
        </div>

        <el-alert type="info" :closable="false" show-icon class="cy-form-note">
          <template #title>密码会被加密保存</template>
          填写的密码用服务端主钥匙加密后入库，接口不回显；任务队列只传密文，真正连接时才解开。留空则沿用免密密钥。
        </el-alert>
        <el-alert
          v-if="formError"
          type="error"
          :closable="false"
          show-icon
          class="cy-form-error"
          :title="formError"
        />
      </el-form>

      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleCreate">
          {{ submitting ? (editingAssetId ? '正在更新…' : '正在录入…') : (editingAssetId ? '保存修改' : '确认录入') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- ===================== 审计日志抽屉 ===================== -->
    <el-drawer v-model="drawerVisible" size="52%" direction="rtl" class="cy-drawer">
      <template #header>
        <div class="cy-drawer__head">
          <div class="cy-drawer__title">执行日志详情</div>
          <div class="cy-mono cy-drawer__sub">task_id: {{ currentExecution?.task_id || '—' }}</div>
        </div>
      </template>

      <div v-if="currentExecution" class="cy-drawer__body">
        <div class="cy-kv">
          <div class="cy-kv__item"><span>目标资产</span><b>{{ currentExecution.assetLabel }}</b></div>
          <div class="cy-kv__item"><span>资产 IP</span><b class="cy-mono">{{ currentExecution.assetIp }}</b></div>
          <div class="cy-kv__item"><span>任务类型</span><b class="cy-mono">{{ currentExecution.task_type }}</b></div>
          <div class="cy-kv__item">
            <span>状态</span>
            <span class="cy-tag" :class="`cy-tag--${statusMeta(currentExecution.status).tone}`">
              {{ statusMeta(currentExecution.status).label }}
            </span>
          </div>
          <div class="cy-kv__item">
            <span>触发源</span>
            <span class="cy-tag" :class="`cy-tag--${triggerMeta(currentExecution.trigger_source).tone}`">
              {{ triggerMeta(currentExecution.trigger_source).label }}
            </span>
          </div>
          <div class="cy-kv__item"><span>退出码</span><b class="cy-mono">{{ currentExecution.exit_code ?? '—' }}</b></div>
          <div class="cy-kv__item"><span>耗时</span><b class="cy-mono">{{ currentExecution.durationLabel }}</b></div>
          <div class="cy-kv__item"><span>执行时间</span><b class="cy-mono">{{ currentExecution.createdLabel }}</b></div>
          <div class="cy-kv__item cy-kv__item--wide">
            <span>执行命令</span><b class="cy-mono cy-kv__command">{{ currentExecution.command }}</b>
          </div>
        </div>

        <div class="cy-log">
          <div class="cy-log__head">
            <span>STDOUT · 标准输出</span>
            <el-button link type="primary" :icon="DocumentCopy" @click="copyText(currentExecution.stdout, 'stdout')">
              复制
            </el-button>
          </div>
          <pre class="cy-log__pre">{{ currentExecution.stdout || '（无标准输出）' }}</pre>
        </div>

        <div class="cy-log">
          <div class="cy-log__head cy-log__head--err">
            <span>STDERR · 错误输出</span>
            <el-button link type="primary" :icon="DocumentCopy" @click="copyText(currentExecution.stderr, 'stderr')">
              复制
            </el-button>
          </div>
          <pre class="cy-log__pre cy-log__pre--err">{{ currentExecution.stderr || '（无错误输出）' }}</pre>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<style>
/* ==========================================================================
   OpsPilot 单文件主题：Dark Cyber / Terminal · 荧光绿 #00e676
   全局块（非 scoped）：确保 teleport 到 body 的 dialog / drawer 同样生效
   ========================================================================== */
html.dark:root {
  --cy-accent: #00e676;
  --cy-accent-bright: #4dffa6;
  --cy-bg: #05080d;
  --cy-surface: #0a1018;
  --cy-surface-2: #0e1722;
  --cy-line: #1b2a38;
  --cy-text: #e8f4ee;
  --cy-text-2: #b8c9c2;
  --cy-muted: #7d918a;
  --cy-faint: #556a63;
  --cy-blue: #38bdf8;
  --cy-purple: #a78bfa;
  --cy-yellow: #ffc107;
  --cy-red: #ff5c5c;
  --cy-mono: 'Fira Code', 'JetBrains Mono', 'IBM Plex Mono', ui-monospace,
    SFMono-Regular, Menlo, Consolas, monospace;
  --cy-sans: 'Fira Sans', 'IBM Plex Sans', 'Segoe UI', 'PingFang SC',
    'Microsoft YaHei', sans-serif;

  --el-color-primary: #00e676;
  --el-color-primary-light-3: #33eb91;
  --el-color-primary-light-5: #66f0ac;
  --el-color-primary-light-7: #99f6c7;
  --el-color-primary-light-9: rgba(0, 230, 118, 0.12);
  --el-color-primary-dark-2: #00b85e;
  --el-color-success: #00e676;
  --el-color-info: #38bdf8;
  --el-color-warning: #ffc107;
  --el-color-danger: #ff5c5c;
  --el-bg-color: #0a1018;
  --el-bg-color-page: #05080d;
  --el-bg-color-overlay: #0e1722;
  --el-fill-color-blank: #060c12;
  --el-fill-color-light: #101d29;
  --el-fill-color: #142432;
  --el-border-color: #1b2a38;
  --el-border-color-light: #1b2a38;
  --el-border-color-lighter: #172532;
  --el-text-color-primary: #e8f4ee;
  --el-text-color-regular: #b8c9c2;
  --el-text-color-secondary: #7d918a;
  --el-text-color-placeholder: #556a63;
  --el-mask-color: rgba(2, 6, 10, 0.76);
}

html.dark body {
  background-color: #05080d;
  color: #e8f4ee;
  font-family: var(--cy-sans);
}

html.dark body::before {
  background-image:
    linear-gradient(rgba(0, 230, 118, 0.022) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 230, 118, 0.022) 1px, transparent 1px),
    radial-gradient(900px 520px at 8% -12%, rgba(0, 230, 118, 0.11), transparent 60%),
    radial-gradient(760px 460px at 98% 0%, rgba(56, 189, 248, 0.06), transparent 55%);
}

html.dark .el-button--primary {
  --el-button-text-color: #00190c;
  --el-button-hover-text-color: #00190c;
  --el-button-active-text-color: #00190c;
  font-weight: 650;
}

html.dark .el-button {
  transition: background-color 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
  cursor: pointer;
}

html.dark .el-button:not(.is-disabled):hover {
  box-shadow: 0 0 0 3px rgba(0, 230, 118, 0.1);
}

html.dark .el-input__wrapper,
html.dark .el-textarea__inner,
html.dark .el-select__wrapper {
  background-color: rgba(3, 8, 13, 0.7);
  box-shadow: 0 0 0 1px #1b2a38 inset;
  transition: box-shadow 0.2s ease;
}

html.dark .el-input__wrapper:hover,
html.dark .el-textarea__inner:hover,
html.dark .el-select__wrapper:hover {
  box-shadow: 0 0 0 1px #2b4152 inset;
}

html.dark .el-input__wrapper.is-focus,
html.dark .el-textarea__inner:focus,
html.dark .el-select__wrapper.is-focused {
  box-shadow: 0 0 0 1px #00e676 inset, 0 0 0 3px rgba(0, 230, 118, 0.1);
}

html.dark .el-table {
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: transparent;
  --el-table-border-color: rgba(125, 145, 138, 0.12);
  --el-table-row-hover-bg-color: rgba(0, 230, 118, 0.05);
  --el-table-text-color: #b8c9c2;
  --el-table-header-text-color: #7d918a;
  background: transparent;
}

html.dark .el-table th.el-table__cell {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.09em;
  text-transform: uppercase;
}

html.dark .el-table .el-table__cell {
  padding: 10px 0;
}

html.dark .el-table__inner-wrapper::before {
  display: none;
}

html.dark .el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell {
  background: rgba(125, 145, 138, 0.02);
}

html.dark .el-loading-mask {
  background-color: rgba(5, 8, 13, 0.74);
  backdrop-filter: blur(2px);
}

html.dark .el-tabs__item {
  color: #7d918a;
  font-size: 13px;
}

html.dark .el-tabs__item.is-active {
  color: #00e676;
  font-weight: 600;
}

html.dark .el-tabs__active-bar {
  background-color: #00e676;
  box-shadow: 0 0 10px rgba(0, 230, 118, 0.7);
}

html.dark .el-tabs__nav-wrap::after {
  background-color: #1b2a38;
}

html.dark .el-dialog,
html.dark .el-drawer {
  --el-dialog-bg-color: #0a1018;
  background: #0a1018;
  border: 1px solid #1b2a38;
}

html.dark .el-dialog {
  border-radius: 14px;
  box-shadow: 0 32px 80px rgba(0, 0, 0, 0.6);
}

html.dark .el-drawer__header {
  margin-bottom: 0;
  padding: 18px 22px;
  border-bottom: 1px solid #1b2a38;
}

html.dark .el-drawer__body {
  padding: 20px 22px 28px;
}

html.dark .el-message {
  border: 1px solid #1b2a38;
  border-radius: 9px;
}

html.dark .el-select-dropdown__item.is-selected {
  color: #00e676;
}

html.dark .el-form-item__label {
  color: #b8c9c2;
}

html.dark .el-overlay {
  backdrop-filter: blur(4px);
}

:focus-visible {
  outline: 2px solid rgba(0, 230, 118, 0.75);
  outline-offset: 2px;
}

::-webkit-scrollbar {
  width: 9px;
  height: 9px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: #1b2a38;
  border: 2px solid transparent;
  border-radius: 999px;
  background-clip: padding-box;
}

::-webkit-scrollbar-thumb:hover {
  background: #2b4152;
  background-clip: padding-box;
}

/* ---------------- 骨架 ---------------- */
.cy-shell {
  min-height: 100vh;
  padding-bottom: 32px;
}

.cy-container {
  width: min(1520px, calc(100% - 48px));
  margin: 0 auto;
}

.cy-header {
  position: sticky;
  top: 0;
  z-index: 20;
  border-bottom: 1px solid rgba(0, 230, 118, 0.13);
  background: rgba(5, 8, 13, 0.82);
  backdrop-filter: blur(16px) saturate(160%);
}

.cy-header__inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  min-height: 70px;
  padding: 12px 0;
}

.cy-brand {
  display: flex;
  align-items: center;
  gap: 13px;
}

.cy-brand__mark {
  display: grid;
  place-items: center;
  width: 39px;
  height: 39px;
  border: 1px solid rgba(0, 230, 118, 0.32);
  border-radius: 10px;
  background: linear-gradient(145deg, rgba(0, 230, 118, 0.17), rgba(0, 230, 118, 0.02));
  color: #00e676;
  box-shadow: 0 0 24px rgba(0, 230, 118, 0.16);
}

.cy-brand__name {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.cy-brand__name span {
  color: #556a63;
  margin: 0 3px;
  font-weight: 400;
}

.cy-brand__name em {
  font-style: normal;
  font-size: 13px;
  font-weight: 500;
  color: #b8c9c2;
}

.cy-brand__tag {
  margin-top: 4px;
  font: 500 9px/1 var(--cy-mono);
  letter-spacing: 0.15em;
  color: #556a63;
}

.cy-header__actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.cy-live {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 6px 10px;
  border: 1px solid rgba(0, 230, 118, 0.22);
  border-radius: 7px;
  background: rgba(0, 230, 118, 0.05);
  color: #4dffa6;
  font: 600 10px/1 var(--cy-mono);
  letter-spacing: 0.07em;
}

.cy-main {
  padding-top: 22px;
}

/* ---------------- 指标大盘 ---------------- */
.cy-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}

.cy-metric {
  position: relative;
  display: flex;
  align-items: center;
  gap: 16px;
  overflow: hidden;
  padding: 20px 22px;
  border: 1px solid rgba(125, 145, 138, 0.14);
  border-radius: 13px;
  background: linear-gradient(145deg, rgba(16, 29, 41, 0.82), rgba(8, 14, 21, 0.94));
  box-shadow: 0 14px 36px rgba(0, 0, 0, 0.3);
  transition: transform 0.24s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.24s ease;
}

.cy-metric:hover {
  transform: translate3d(0, -2px, 0);
  border-color: rgba(0, 230, 118, 0.3);
}

.cy-metric__icon {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  flex: none;
  border-radius: 11px;
  background: rgba(0, 230, 118, 0.09);
  border: 1px solid rgba(0, 230, 118, 0.2);
  color: #00e676;
  font-size: 20px;
}

.cy-metric__icon--blue {
  background: rgba(56, 189, 248, 0.09);
  border-color: rgba(56, 189, 248, 0.2);
  color: #38bdf8;
}

.cy-metric__icon--green {
  background: rgba(0, 230, 118, 0.12);
  border-color: rgba(0, 230, 118, 0.26);
  color: #4dffa6;
}

.cy-metric__label {
  font-size: 11.5px;
  color: #7d918a;
  letter-spacing: 0.03em;
}

.cy-metric__value {
  margin-top: 3px;
  font: 700 30px/1.1 var(--cy-mono);
  letter-spacing: -0.04em;
  color: #e8f4ee;
}

.cy-metric__hint {
  margin-top: 6px;
  font: 400 10px/1.3 var(--cy-mono);
  color: #556a63;
}

.cy-metric__glow {
  position: absolute;
  right: -40px;
  top: -60px;
  width: 150px;
  height: 150px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(0, 230, 118, 0.1), transparent 70%);
  pointer-events: none;
}

/* ---------------- Tabs ---------------- */
.cy-tabs > .el-tabs__header {
  margin-bottom: 18px;
}

.cy-tab-label {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.cy-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.32fr) minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}

/* ---------------- 卡片 ---------------- */
.cy-card {
  border: 1px solid rgba(125, 145, 138, 0.14);
  border-radius: 13px;
  background: linear-gradient(180deg, rgba(16, 29, 41, 0.76), rgba(8, 14, 21, 0.94));
  box-shadow: 0 16px 42px rgba(0, 0, 0, 0.3);
  overflow: hidden;
}

.cy-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 17px 20px;
  border-bottom: 1px solid rgba(125, 145, 138, 0.12);
}

.cy-card__title {
  font-size: 14.5px;
  font-weight: 650;
  color: #e8f4ee;
}

.cy-card__sub {
  margin-top: 5px;
  font: 400 10px/1.4 var(--cy-mono);
  color: #556a63;
}

.cy-card__tools {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.cy-card__body {
  padding: 16px 20px 20px;
}

.cy-search {
  width: 190px;
}

.cy-filter {
  width: 140px;
}

.cy-filter--small {
  width: 128px;
}

.cy-alert {
  margin-bottom: 14px;
}

.cy-alert__body {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #b8c9c2;
}

.cy-table-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 14px;
  padding-top: 13px;
  border-top: 1px solid rgba(125, 145, 138, 0.12);
  font-size: 11px;
  color: #7d918a;
}

.cy-table-foot b {
  color: #e8f4ee;
  font-family: var(--cy-mono);
}

/* ---------------- 通用文字 / 标记 ---------------- */
.cy-mono {
  font-family: var(--cy-mono);
  font-variant-ligatures: none;
}

.cy-hint {
  color: #556a63;
  font-size: 10.5px;
}

.cy-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  flex: none;
  border-radius: 50%;
  background: #556a63;
  box-shadow: 0 0 0 3px rgba(125, 145, 138, 0.12);
}

.cy-dot--success {
  background: #00e676;
  box-shadow: 0 0 0 3px rgba(0, 230, 118, 0.14), 0 0 11px rgba(0, 230, 118, 0.6);
}

.cy-dot--danger {
  background: #ff5c5c;
  box-shadow: 0 0 0 3px rgba(255, 92, 92, 0.14);
}

.cy-dot--warn {
  background: #ffc107;
  box-shadow: 0 0 0 3px rgba(255, 193, 7, 0.14);
}

.cy-dot--info {
  background: #38bdf8;
  box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.14);
}

.cy-dot--purple {
  background: #a78bfa;
  box-shadow: 0 0 0 3px rgba(167, 139, 250, 0.14);
}

.cy-dot--neutral {
  background: #7d918a;
  box-shadow: 0 0 0 3px rgba(125, 145, 138, 0.12);
}

.cy-dot--pulse {
  animation: cyPulse 1.6s ease-in-out infinite;
}

@keyframes cyPulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.42; transform: scale(0.8); }
}

.cy-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 23px;
  padding: 0 9px;
  border: 1px solid transparent;
  border-radius: 6px;
  font: 600 10px/1 var(--cy-mono);
  letter-spacing: 0.03em;
  white-space: nowrap;
}

.cy-tag--success {
  color: #4dffa6;
  background: rgba(0, 230, 118, 0.1);
  border-color: rgba(0, 230, 118, 0.26);
}

.cy-tag--danger {
  color: #ff9b9b;
  background: rgba(255, 92, 92, 0.1);
  border-color: rgba(255, 92, 92, 0.26);
}

.cy-tag--warn {
  color: #ffd75e;
  background: rgba(255, 193, 7, 0.1);
  border-color: rgba(255, 193, 7, 0.26);
}

.cy-tag--info {
  color: #7dd3fc;
  background: rgba(56, 189, 248, 0.1);
  border-color: rgba(56, 189, 248, 0.26);
}

.cy-tag--purple {
  color: #c4b5fd;
  background: rgba(167, 139, 250, 0.12);
  border-color: rgba(167, 139, 250, 0.3);
}

.cy-tag--neutral {
  color: #7d918a;
  background: rgba(125, 145, 138, 0.08);
  border-color: rgba(125, 145, 138, 0.2);
}

/* REJECTED 用橙色：区别于「跑了但失败」（红）和「正常运行」（绿/黄） */
.cy-tag--blocked {
  color: #ffb36b;
  background: rgba(255, 150, 60, 0.12);
  border-color: rgba(255, 150, 60, 0.3);
}

.cy-dot--blocked {
  background: #ffb36b;
  box-shadow: 0 0 0 3px rgba(255, 150, 60, 0.14), 0 0 11px rgba(255, 150, 60, 0.55);
}

.cy-kbd {
  display: inline-block;
  padding: 3px 5px;
  border: 1px solid #1b2a38;
  border-radius: 4px;
  background: #0e1722;
  font: 500 9px/1 var(--cy-mono);
  color: #7d918a;
}

/* ---------------- 表格内容 ---------------- */
.cy-host-name {
  font-size: 12.5px;
  font-weight: 600;
  color: #e8f4ee;
  display: flex;
  align-items: center;
  gap: 6px;
}
.cy-host-lock {
  color: #63e6a6;
  font-size: 12px;
}

.cy-host-id {
  margin-top: 4px;
  font: 400 10px/1.3 var(--cy-mono);
  color: #556a63;
}

.cy-ip,
.cy-task-id,
.cy-command-cell,
.cy-duration,
.cy-time {
  font-size: 10.5px;
  color: #b8c9c2;
}

.cy-task-id {
  color: #00e676;
  cursor: help;
}

.cy-command-cell {
  color: #7dd3fc;
}

.cy-duration {
  color: #4dffa6;
}

.cy-ssh {
  display: flex;
  align-items: center;
  gap: 3px;
  font: 500 11px var(--cy-mono);
  color: #b8c9c2;
}

.cy-ssh__user {
  color: #00e676;
}

.cy-ssh__sep {
  color: #556a63;
}

.cy-status {
  display: flex;
  align-items: center;
  gap: 7px;
  font: 600 10px var(--cy-mono);
  color: #b8c9c2;
}

.cy-probing {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 5px;
  font-size: 10px;
  color: #38bdf8;
}

.cy-probe-fail {
  margin-top: 5px;
  font-size: 10px;
  color: #ff9b9b;
}

.cy-latency {
  margin-top: 5px;
  font: 600 10px var(--cy-mono);
  color: #4dffa6;
}

.cy-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.cy-option {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  font-size: 12px;
}

.cy-option .cy-mono {
  color: #7d918a;
  font-size: 10.5px;
}

/* ---------------- 终端 ---------------- */
.cy-term-body {
  display: flex;
  flex-direction: column;
  gap: 11px;
}

.cy-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.cy-label {
  font: 600 10px/1 var(--cy-mono);
  letter-spacing: 0.11em;
  text-transform: uppercase;
  color: #556a63;
}

.cy-note {
  margin-top: -6px;
}

.cy-presets {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.cy-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 9px;
  border: 1px solid #1b2a38;
  border-radius: 7px;
  background: rgba(125, 145, 138, 0.05);
  color: #b8c9c2;
  font: 500 10.5px var(--cy-mono);
  cursor: pointer;
  transition: border-color 0.18s ease, color 0.18s ease, background-color 0.18s ease;
}

.cy-chip:hover {
  border-color: rgba(0, 230, 118, 0.42);
  background: rgba(0, 230, 118, 0.08);
  color: #00e676;
}

html.dark .cy-command .el-textarea__inner {
  background-color: #03080d !important;
  box-shadow: 0 0 0 1px #1b2a38 inset !important;
  color: #4dffa6;
  font-family: var(--cy-mono);
  font-size: 12px;
  line-height: 1.7;
  padding: 10px 12px;
}

html.dark .cy-command .el-textarea__inner:focus {
  box-shadow: 0 0 0 1px #00e676 inset, 0 0 0 3px rgba(0, 230, 118, 0.1) !important;
}

.cy-term-actions {
  align-items: center;
}

.cy-shortcut {
  margin-left: auto;
  font-size: 10px;
  color: #556a63;
  white-space: nowrap;
}

.cy-window {
  border: 1px solid #1b2a38;
  border-radius: 9px;
  overflow: hidden;
  background: #03080d;
  box-shadow: inset 0 0 40px rgba(0, 0, 0, 0.5);
}

.cy-window__bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  background: linear-gradient(180deg, #0d1924, #09131d);
  border-bottom: 1px solid #162634;
}

.cy-dots {
  display: flex;
  gap: 5px;
  flex: none;
}

.cy-dots i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ff5c5c;
}

.cy-dots i:nth-child(2) { background: #ffc107; }
.cy-dots i:nth-child(3) { background: #00e676; }

.cy-window__title {
  font-size: 10.5px;
  color: #7d918a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cy-window__meta {
  margin-left: auto;
  font-size: 10px;
  color: #4a5f58;
  white-space: nowrap;
}

.cy-output {
  height: 300px;
  overflow-y: auto;
  padding: 12px;
  font-family: var(--cy-mono);
  font-size: 11.5px;
  line-height: 1.65;
}

.cy-output-empty {
  display: flex;
  flex-direction: column;
  gap: 9px;
  padding: 10px 4px;
  color: #556a63;
  font-size: 11px;
}

.cy-prompt {
  color: #00e676;
  font-size: 13px;
}

.cy-caret {
  animation: cyBlink 1.1s steps(2, start) infinite;
}

@keyframes cyBlink {
  to { visibility: hidden; }
}

.cy-line {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr);
  gap: 10px;
  padding: 1px 0;
}

.cy-line__time {
  padding-top: 2px;
  color: #3b5148;
  font-size: 10px;
  user-select: none;
}

.cy-line__text {
  margin: 0;
  color: #c8d8d0;
  font-family: var(--cy-mono);
  font-size: 11.5px;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
}

.cy-line--cmd .cy-line__text { color: #4dffa6; font-weight: 600; }
.cy-line--info .cy-line__text { color: #66847a; }
.cy-line--state .cy-line__text { color: #7dd3fc; }
.cy-line--meta .cy-line__text { color: #ffd75e; }
.cy-line--stdout .cy-line__text { color: #e8f4ee; }
.cy-line--stderr .cy-line__text,
.cy-line--error .cy-line__text { color: #ff9b9b; }
.cy-line--success .cy-line__text { color: #4dffa6; }

.cy-waiting {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  color: #7dd3fc;
  font-size: 10.5px;
}

.cy-term-foot {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  padding: 9px 12px;
  border-top: 1px solid #162634;
  background: #07101a;
  font-size: 10px;
  color: #7d918a;
}

.cy-term-foot b {
  margin-right: 4px;
  font: 600 9px var(--cy-mono);
  letter-spacing: 0.09em;
  color: #4a5f58;
}

.cy-foot-state--success { margin-left: auto; color: #4dffa6; }
.cy-foot-state--danger { margin-left: auto; color: #ff9b9b; }
.cy-foot-state--warn { margin-left: auto; color: #ffd75e; }
.cy-foot-state--info { margin-left: auto; color: #7dd3fc; }
.cy-foot-state--neutral { margin-left: auto; color: #7d918a; }

/* ---------------- 录入对话框 ---------------- */
.cy-dialog__head {
  display: flex;
  align-items: center;
  gap: 12px;
}

.cy-dialog__icon {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: rgba(0, 230, 118, 0.1);
  border: 1px solid rgba(0, 230, 118, 0.24);
  color: #00e676;
}

.cy-dialog__title {
  font-size: 15px;
  font-weight: 650;
}

.cy-dialog__sub {
  margin-top: 4px;
  font-size: 10px;
  color: #556a63;
}

.cy-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 16px;
}

.cy-form-note {
  margin-top: 4px;
  background: rgba(56, 189, 248, 0.06);
  border: 1px solid rgba(56, 189, 248, 0.18);
}

.cy-form-error {
  margin-top: 12px;
}

/* ---------------- 审计抽屉 ---------------- */
.cy-drawer__title {
  font-size: 15px;
  font-weight: 650;
  color: #e8f4ee;
}

.cy-drawer__sub {
  margin-top: 5px;
  font-size: 10px;
  color: #556a63;
  word-break: break-all;
}

.cy-drawer__body {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.cy-kv {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 18px;
  padding: 16px;
  border: 1px solid #1b2a38;
  border-radius: 10px;
  background: rgba(14, 23, 34, 0.6);
}

.cy-kv__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
  font-size: 11.5px;
}

.cy-kv__item > span:first-child {
  color: #7d918a;
  white-space: nowrap;
}

.cy-kv__item b {
  color: #e8f4ee;
  font-weight: 600;
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cy-kv__item--wide {
  grid-column: 1 / -1;
}

.cy-kv__command {
  color: #7dd3fc !important;
  font-size: 11px !important;
}

.cy-log__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font: 600 10px/1 var(--cy-mono);
  letter-spacing: 0.11em;
  color: #00e676;
}

.cy-log__head--err {
  color: #ff9b9b;
}

.cy-log__pre {
  margin: 0;
  min-height: 110px;
  max-height: 320px;
  overflow: auto;
  padding: 13px;
  border: 1px solid #1b2a38;
  border-radius: 9px;
  background: #03080d;
  color: #d6e8de;
  font: 400 11.5px/1.7 var(--cy-mono);
  white-space: pre-wrap;
  word-break: break-word;
}

.cy-log__pre--err {
  color: #ffb3b3;
}

/* ---------------- 页脚 ---------------- */
.cy-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
  margin-top: 24px;
  padding-top: 18px;
  border-top: 1px solid rgba(125, 145, 138, 0.12);
  font-size: 10.5px;
  color: #556a63;
}

/* ---------------- 响应式 ---------------- */
@media (max-width: 1180px) {
  .cy-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 900px) {
  .cy-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .cy-card__head {
    flex-direction: column;
    align-items: flex-start;
  }

  .cy-search {
    width: 100%;
  }
}

@media (max-width: 620px) {
  .cy-container {
    width: calc(100% - 26px);
  }

  .cy-header__inner {
    flex-direction: column;
    align-items: flex-start;
  }

  .cy-header__actions {
    width: 100%;
    justify-content: flex-start;
  }

  .cy-metrics {
    grid-template-columns: minmax(0, 1fr);
  }

  .cy-card__body {
    padding: 14px;
  }

  .cy-form-grid,
  .cy-kv {
    grid-template-columns: minmax(0, 1fr);
  }

  .cy-output {
    height: 260px;
  }

  .cy-shortcut {
    display: none;
  }

  .cy-drawer {
    width: 100% !important;
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
</style>

<!-- 第二套视觉层：只覆盖样式与布局，不触碰上面的业务逻辑 -->
<style src="./styles/console-v2.css"></style>
