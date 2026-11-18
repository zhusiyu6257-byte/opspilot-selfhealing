<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Monitor,
  CaretRight,
  Delete,
  DocumentCopy,
  Lock,
  Close,
  MagicStick,
} from '@element-plus/icons-vue'
import { executeRunbook } from '../api'
import { pollTask, TERMINAL_STATES } from '../utils/taskPoller'
import { formatClock, shortId, taskStateMeta } from '../utils/format'

const props = defineProps({
  assets: { type: Array, default: () => [] },
  selectedAssetId: { type: Number, default: null },
})

const emit = defineEmits(['update:selectedAssetId', 'running-change'])

const QUICK_COMMANDS = [
  { label: '磁盘与负载', command: 'df -h && uptime' },
  { label: '内存占用', command: 'free -h' },
  { label: '系统信息', command: 'uname -a && hostname' },
  { label: '进程快照', command: 'ps aux --sort=-%cpu | head -n 10' },
]

const selectedId = computed({
  get: () => props.selectedAssetId ?? props.assets[0]?.id ?? null,
  set: (value) => emit('update:selectedAssetId', value),
})

const currentAsset = computed(
  () => props.assets.find((asset) => asset.id === selectedId.value) || null,
)

const targetLabel = computed(() =>
  currentAsset.value
    ? `${currentAsset.value.ssh_user}@${currentAsset.value.ip_address}:${currentAsset.value.ssh_port}`
    : '未选择主机',
)

const command = ref('df -h && uptime')
const commandRef = ref()
const sshPassword = ref('')
const isRunning = ref(false)
const controller = ref(null)
const status = ref('IDLE')
const currentTaskId = ref('')
const sessions = ref([])
const activeSessionId = ref(null)
const outputRef = ref(null)
const now = ref(Date.now())
let ticker = null

const activeSession = computed(
  () => sessions.value.find((item) => item.id === activeSessionId.value) || null,
)
const lines = computed(() => activeSession.value?.lines || [])

const statusMeta = computed(() => {
  if (status.value === 'IDLE') return { label: '待命', tone: 'neutral' }
  if (status.value === 'ERROR') return { label: '执行异常', tone: 'danger' }
  return taskStateMeta(status.value)
})

const elapsedLabel = computed(() => {
  const session = activeSession.value
  if (!session) return '—'
  const ms = session.durationMs || (isRunning.value ? now.value - session.startedAt : 0)
  return ms > 0 ? `${(ms / 1000).toFixed(1)}s` : '—'
})

const toneClass = (state) => {
  if (!state || state === 'IDLE' || state === 'ERROR') {
    return state === 'ERROR' ? 'op-status-dot--danger' : 'op-status-dot--neutral'
  }
  return `op-status-dot--${taskStateMeta(state).tone}`
}

const scrollToBottom = () =>
  nextTick(() => {
    const el = outputRef.value
    if (el) el.scrollTop = el.scrollHeight
  })

const addLine = (session, kind, text) => {
  if (text === undefined || text === null || text === '') return
  session.lines.push({ time: formatClock(), kind, text: String(text) })
  scrollToBottom()
}

const useQuickCommand = (item) => {
  command.value = item.command
  commandRef.value?.focus()
}

const handleCopy = async () => {
  const text = lines.value.map((line) => line.text).join('\n')
  if (!text.trim()) {
    ElMessage.warning('暂无输出可复制')
    return
  }
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('终端输出已复制')
  } catch {
    ElMessage.warning('浏览器拒绝了剪贴板访问，请手动选中复制')
  }
}

const handleClear = () => {
  if (isRunning.value) controller.value?.abort()
  sessions.value = []
  activeSessionId.value = null
  currentTaskId.value = ''
  status.value = 'IDLE'
}

const handleAbort = () => {
  controller.value?.abort()
  ElMessage.info('已停止前端轮询（后端任务仍会继续执行）')
}

const handleExecute = async () => {
  const asset = currentAsset.value
  if (!asset) {
    ElMessage.warning('请先选择目标主机')
    return
  }
  const cmd = command.value.trim()
  if (!cmd) {
    ElMessage.warning('请输入要执行的命令')
    return
  }
  if (isRunning.value) return

  const session = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    assetName: asset.name,
    target: targetLabel.value,
    command: cmd,
    startedAt: Date.now(),
    durationMs: 0,
    exitCode: null,
    taskId: '',
    state: 'PENDING',
    lines: [],
  }
  sessions.value.push(session)
  if (sessions.value.length > 8) sessions.value.shift()
  activeSessionId.value = session.id

  isRunning.value = true
  status.value = 'PENDING'
  currentTaskId.value = ''
  const ctrl = new AbortController()
  controller.value = ctrl

  addLine(session, 'cmd', `$ ${cmd}`)
  addLine(session, 'info', `目标 ${session.target} · 正在下发远程剧本任务…`)

  try {
    const dispatched = await executeRunbook({
      asset_id: asset.id,
      command: cmd,
      ...(sshPassword.value ? { ssh_password: sshPassword.value } : {}),
    })

    session.taskId = dispatched.task_id
    currentTaskId.value = dispatched.task_id
    addLine(session, 'info', `202 Accepted · task_id=${dispatched.task_id}`)
    if (dispatched.message) addLine(session, 'info', dispatched.message)

    let lastState = ''
    const outcome = await pollTask(dispatched.task_id, {
      signal: ctrl.signal,
      onUpdate: ({ status: state, attempts, message }) => {
        status.value = state
        session.state = state
        const meta = taskStateMeta(state)
        if (state === 'RETRYING') {
          addLine(session, 'state', `[轮询 #${attempts}] ${message || '状态查询重试'}`)
        } else if (!TERMINAL_STATES.includes(state) && state !== lastState) {
          addLine(session, 'state', `[轮询 #${attempts}] ${meta.label} · 等待 Worker 写入结果`)
        } else if (!TERMINAL_STATES.includes(state) && attempts <= 2) {
          addLine(session, 'state', `[轮询 #${attempts}] ${meta.label} · 结果尚未就绪`)
        }
        lastState = state
      },
    })

    status.value = outcome.status
    session.state = outcome.status
    session.durationMs = Date.now() - session.startedAt

    if (outcome.status === 'SUCCESS') {
      const result = outcome.result || {}
      const exitCode = result.exit_code ?? null
      const succeeded = result.success !== false && (exitCode === 0 || exitCode === null)
      session.exitCode = exitCode

      addLine(
        session,
        'state',
        `任务完成 · exit_code=${exitCode ?? 'N/A'} · 耗时 ${(session.durationMs / 1000).toFixed(1)}s`,
      )
      if (result.stdout) addLine(session, 'stdout', result.stdout)
      if (result.stderr) addLine(session, 'stderr', result.stderr)
      if (!result.stdout && !result.stderr) addLine(session, 'info', '（命令无标准输出）')

      if (succeeded) {
        addLine(session, 'success', `[OK] ${asset.name} 执行成功`)
        ElMessage.success(`${asset.name} 命令执行成功`)
      } else {
        addLine(session, 'error', `命令未成功：exit_code=${exitCode}，请检查上方 stderr`)
        ElMessage.error(`${asset.name} 命令返回非零退出码或 SSH 连接失败`)
      }
    } else if (outcome.status === 'FAILURE') {
      const detail =
        typeof outcome.result === 'string'
          ? outcome.result
          : JSON.stringify(outcome.result ?? {})
      addLine(session, 'error', `后台任务失败：${detail}`)
      ElMessage.error('后台任务执行失败，请查看终端输出')
    } else {
      addLine(session, 'error', `任务被撤销：${outcome.result ?? ''}`)
      ElMessage.warning('任务已被撤销')
    }
  } catch (err) {
    status.value = 'ERROR'
    session.state = 'ERROR'
    session.durationMs = Date.now() - session.startedAt
    if (err.code === 'ABORTED') {
      addLine(session, 'error', '已停止前端轮询，后端任务仍会继续执行（可用 task_id 在后端查询结果）')
    } else {
      addLine(session, 'error', `执行中断：${err.message}`)
      ElMessage.error(`命令下发失败：${err.message}`)
    }
  } finally {
    isRunning.value = false
    controller.value = null
    scrollToBottom()
  }
}

watch(isRunning, (value) => emit('running-change', value))

onMounted(() => {
  ticker = setInterval(() => {
    now.value = Date.now()
  }, 500)
})

onBeforeUnmount(() => {
  clearInterval(ticker)
  controller.value?.abort()
})
</script>

<template>
  <section class="op-card term-card">
    <div class="op-card__header">
      <div>
        <div class="op-card__title">
          <el-icon><Monitor /></el-icon>
          远程剧本终端
        </div>
        <div class="op-card__subtitle">POST /api/v1/runbooks/execute → GET /api/v1/tasks/{task_id}</div>
      </div>
      <div class="op-card__tools">
        <span class="op-tag" :class="`op-tag--${statusMeta.tone}`">
          <span
            class="op-status-dot"
            :class="[toneClass(status), isRunning && 'op-status-dot--pulse']"
          />
          {{ statusMeta.label }}
        </span>
      </div>
    </div>

    <div class="op-card__body term-body">
      <div class="term-config">
        <label class="term-label">目标主机</label>
        <el-select
          v-model="selectedId"
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
            <div class="term-option">
              <span>{{ asset.name }}</span>
              <span class="op-mono">{{ asset.ip_address }}</span>
            </div>
          </el-option>
        </el-select>
      </div>

      <div class="term-config">
        <label class="term-label">SSH 密码 <span class="op-faint">（可选）</span></label>
        <el-input
          v-model="sshPassword"
          type="password"
          show-password
          :prefix-icon="Lock"
          clearable
          placeholder="留空则使用免密密钥"
        />
      </div>
      <p class="term-hint">密码仅随本次请求发送，不写入资产库、不保存在浏览器。</p>

      <div class="term-quick">
        <span class="term-label">快捷剧本</span>
        <div class="term-quick__list">
          <button
            v-for="item in QUICK_COMMANDS"
            :key="item.command"
            type="button"
            class="term-chip"
            :title="item.command"
            @click="useQuickCommand(item)"
          >
            <el-icon><MagicStick /></el-icon>
            {{ item.label }}
          </button>
        </div>
      </div>

      <div class="term-config">
        <label class="term-label">Shell 命令</label>
        <el-input
          ref="commandRef"
          v-model="command"
          type="textarea"
          :rows="3"
          resize="none"
          spellcheck="false"
          class="term-command op-mono"
          placeholder="df -h && uptime"
          @keydown.ctrl.enter.prevent="handleExecute"
          @keydown.meta.enter.prevent="handleExecute"
        />
      </div>

      <div class="term-actions">
        <el-button
          type="primary"
          :icon="CaretRight"
          :loading="isRunning"
          :disabled="!currentAsset"
          @click="handleExecute"
        >
          {{ isRunning ? '执行中…' : '下发并执行' }}
        </el-button>
        <el-button v-if="isRunning" :icon="Close" @click="handleAbort">停止轮询</el-button>
        <el-button :icon="Delete" :disabled="!sessions.length" @click="handleClear">清空</el-button>
        <el-button :icon="DocumentCopy" :disabled="!lines.length" @click="handleCopy">
          复制输出
        </el-button>
        <span class="term-shortcut">
          <span class="op-kbd">Ctrl</span> + <span class="op-kbd">Enter</span> 执行
        </span>
      </div>

      <div v-if="sessions.length > 1" class="term-sessions">
        <button
          v-for="(session, index) in sessions"
          :key="session.id"
          type="button"
          class="term-session"
          :class="{ 'term-session--active': session.id === activeSessionId }"
          :title="session.command"
          @click="activeSessionId = session.id"
        >
          <span class="op-status-dot" :class="toneClass(session.state)" />
          <span class="op-mono">#{{ index + 1 }} {{ session.command }}</span>
        </button>
      </div>

      <div class="term-window">
        <div class="term-window__bar">
          <span class="term-dots" aria-hidden="true"><i /><i /><i /></span>
          <span class="term-window__title op-mono">
            opspilot@{{ currentAsset?.name || 'console' }}:~$
          </span>
          <span class="term-window__meta op-mono">
            {{ currentTaskId ? `task ${shortId(currentTaskId)}` : 'idle' }}
          </span>
        </div>

        <div ref="outputRef" class="term-output">
          <div v-if="!activeSession" class="term-empty">
            <div class="term-empty__prompt op-mono">$ <span class="term-caret">_</span></div>
            <p>选择目标主机并输入命令，执行过程与结果会实时回显在这里。</p>
            <p class="op-faint">异步链路：下发 → task_id → 短轮询查询任务状态</p>
          </div>
          <template v-else>
            <div
              v-for="(line, index) in lines"
              :key="index"
              class="term-line"
              :class="`term-line--${line.kind}`"
            >
              <span class="term-line__time op-mono">{{ line.time }}</span>
              <pre
                v-if="line.kind === 'stdout' || line.kind === 'stderr'"
                class="term-line__text"
              >{{ line.text }}</pre>
              <span v-else class="term-line__text">{{ line.text }}</span>
            </div>
            <div v-if="isRunning" class="term-waiting">
              <span class="op-status-dot op-status-dot--info op-status-dot--pulse" />
              <span class="op-mono">正在等待 Celery Worker 写入结果（{{ elapsedLabel }}）…</span>
            </div>
          </template>
        </div>

        <div class="term-foot">
          <span><b>TASK</b> <span class="op-mono">{{ currentTaskId ? shortId(currentTaskId) : '—' }}</span></span>
          <span><b>EXIT</b> <span class="op-mono">{{ activeSession?.exitCode ?? '—' }}</span></span>
          <span><b>ELAPSED</b> <span class="op-mono">{{ elapsedLabel }}</span></span>
          <span class="term-foot__state op-mono" :class="`term-foot__state--${statusMeta.tone}`">
            {{ statusMeta.label }}
          </span>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.term-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.term-config {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.term-label {
  font: 600 10px/1 var(--op-mono);
  letter-spacing: 0.11em;
  text-transform: uppercase;
  color: var(--op-faint);
}

.term-hint {
  margin-top: -6px;
  font-size: 10.5px;
  color: var(--op-faint);
}

.term-option {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  font-size: 12px;
}

.term-option .op-mono {
  color: var(--op-muted);
  font-size: 10.5px;
}

.term-quick {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.term-quick__list {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.term-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 9px;
  border: 1px solid var(--op-border);
  border-radius: 7px;
  background: rgba(148, 163, 184, 0.05);
  color: var(--op-text-2);
  font-size: 11px;
  cursor: pointer;
  transition: border-color 0.18s ease, color 0.18s ease, background-color 0.18s ease;
}

.term-chip:hover {
  border-color: rgba(34, 197, 94, 0.4);
  background: rgba(34, 197, 94, 0.08);
  color: var(--op-accent-bright);
}

.term-command :deep(.el-textarea__inner) {
  background-color: #05090f !important;
  box-shadow: 0 0 0 1px #1b2b42 inset !important;
  color: #86efac;
  font-family: var(--op-mono);
  font-size: 12px;
  line-height: 1.7;
  padding: 10px 12px;
}

.term-command :deep(.el-textarea__inner:focus) {
  box-shadow: 0 0 0 1px var(--op-accent) inset, 0 0 0 3px rgba(34, 197, 94, 0.1) !important;
}

.term-actions {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
}

.term-shortcut {
  margin-left: auto;
  font-size: 10px;
  color: var(--op-faint);
  white-space: nowrap;
}

.term-sessions {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  padding-bottom: 4px;
}

.term-session {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 190px;
  padding: 5px 9px;
  border: 1px solid var(--op-border);
  border-radius: 6px;
  background: rgba(148, 163, 184, 0.04);
  color: var(--op-muted);
  font-size: 10px;
  cursor: pointer;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: border-color 0.18s ease, color 0.18s ease;
}

.term-session:hover,
.term-session--active {
  border-color: rgba(34, 197, 94, 0.38);
  color: var(--op-text);
}

.term-session .op-mono {
  overflow: hidden;
  text-overflow: ellipsis;
}

.term-window {
  border: 1px solid #1b2b42;
  border-radius: 10px;
  overflow: hidden;
  background: #05090f;
  box-shadow: inset 0 0 40px rgba(0, 0, 0, 0.45);
}

.term-window__bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  background: linear-gradient(180deg, #0d1728, #0a1220);
  border-bottom: 1px solid #16243a;
}

.term-dots {
  display: flex;
  gap: 5px;
  flex: none;
}

.term-dots i {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #ef4444;
}

.term-dots i:nth-child(2) {
  background: #fbbf24;
}

.term-dots i:nth-child(3) {
  background: #22c55e;
}

.term-window__title {
  font-size: 10.5px;
  color: #7c93b3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.term-window__meta {
  margin-left: auto;
  font-size: 10px;
  color: #4b617f;
  white-space: nowrap;
}

.term-output {
  height: 318px;
  overflow-y: auto;
  padding: 13px 12px;
  font-family: var(--op-mono);
  font-size: 11.5px;
  line-height: 1.65;
}

.term-empty {
  display: flex;
  flex-direction: column;
  gap: 9px;
  padding: 12px 4px;
  color: var(--op-faint);
  font-size: 11.5px;
}

.term-empty__prompt {
  color: var(--op-accent-bright);
  font-size: 13px;
}

.term-caret {
  animation: termBlink 1.1s steps(2, start) infinite;
}

@keyframes termBlink {
  to {
    visibility: hidden;
  }
}

.term-line {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr);
  gap: 10px;
  padding: 1px 0;
}

.term-line__time {
  color: #3f536e;
  font-size: 10px;
  user-select: none;
  padding-top: 2px;
}

.term-line__text {
  margin: 0;
  color: #cbd5e1;
  font-family: var(--op-mono);
  font-size: 11.5px;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
}

.term-line--cmd .term-line__text {
  color: #4ade80;
  font-weight: 600;
}

.term-line--info .term-line__text {
  color: #7c93b3;
}

.term-line--state .term-line__text {
  color: #7dd3fc;
}

.term-line--stdout .term-line__text {
  color: #e2e8f0;
}

.term-line--stderr .term-line__text,
.term-line--error .term-line__text {
  color: #fca5a5;
}

.term-line--success .term-line__text {
  color: #4ade80;
}

.term-waiting {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  color: #7dd3fc;
  font-size: 10.5px;
}

.term-foot {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  padding: 9px 12px;
  border-top: 1px solid #16243a;
  background: #080f1c;
  font-size: 10px;
  color: var(--op-muted);
}

.term-foot b {
  color: #4b617f;
  font: 600 9px var(--op-mono);
  letter-spacing: 0.09em;
  margin-right: 4px;
}

.term-foot__state {
  margin-left: auto;
  font-size: 10px;
}

.term-foot__state--success {
  color: #4ade80;
}

.term-foot__state--danger {
  color: #fca5a5;
}

.term-foot__state--warn {
  color: #fcd34d;
}

.term-foot__state--info {
  color: #7dd3fc;
}

@media (max-width: 480px) {
  .term-output {
    height: 280px;
  }

  .term-shortcut {
    display: none;
  }

  .term-foot {
    gap: 10px;
  }
}
</style>
