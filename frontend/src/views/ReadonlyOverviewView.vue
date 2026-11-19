<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  getReadonlyAssets,
  getReadonlyExecutionStats,
  getReadonlyExecutions,
  getReadonlyHealth,
} from '@/api/readonly.js'

const loading = ref(true)
const lastUpdated = ref(null)
const health = ref(null)
const assets = ref([])
const stats = ref(null)
const executions = ref([])
const apiError = ref('')
let timer = null

const apiState = computed(() => {
  if (apiError.value) return 'unreachable'
  return health.value?.status === 'healthy' ? 'healthy' : 'degraded'
})

const hostCount = computed(() => assets.value.length)
const statusCounts = computed(() => {
  const result = {}
  for (const asset of assets.value) {
    const key = asset.status || 'UNKNOWN'
    result[key] = (result[key] || 0) + 1
  }
  return result
})

const statusText = (status) => {
  const map = {
    ONLINE: '在线',
    OFFLINE: '离线',
    DEGRADED: '降级',
    UNKNOWN: '未知',
    SUCCESS: '成功',
    FAILED: '失败',
    RUNNING: '运行中',
    PENDING: '等待中',
    REJECTED: '已拦截',
  }
  return map[status] || status || '未知'
}

const formatTime = (value) => {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

async function loadReadonlyData() {
  try {
    const [healthResult, assetsResult, statsResult, executionsResult] =
      await Promise.allSettled([
        getReadonlyHealth(),
        getReadonlyAssets(),
        getReadonlyExecutionStats(),
        getReadonlyExecutions(8),
      ])

    const failed = [healthResult, assetsResult, statsResult, executionsResult].filter(
      (item) => item.status === 'rejected',
    )
    apiError.value = failed.length
      ? `${failed.length}/4 个只读接口请求失败，页面只显示成功返回的数据。`
      : ''

    health.value = healthResult.status === 'fulfilled' ? healthResult.value.data : null
    assets.value = assetsResult.status === 'fulfilled' ? assetsResult.value.data || [] : []
    stats.value = statsResult.status === 'fulfilled' ? statsResult.value.data : null
    executions.value =
      executionsResult.status === 'fulfilled' ? executionsResult.value.data || [] : []
    lastUpdated.value = new Date()
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadReadonlyData()
  timer = window.setInterval(loadReadonlyData, 15000)
})

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<template>
  <div class="readonly-overview">
    <section class="readonly-overview__hero">
      <div class="readonly-overview__eyebrow">D1-LITE · READONLY LIVE</div>
      <div class="readonly-overview__title-row">
        <h1>只读实时概览</h1>
        <el-tag :type="apiState === 'healthy' ? 'success' : apiState === 'degraded' ? 'warning' : 'danger'" effect="dark" round>
          {{ apiState === 'healthy' ? '后端在线' : apiState === 'degraded' ? '部分可用' : '后端不可达' }}
        </el-tag>
      </div>
      <p>
        本页只调用后端 GET 接口，每 15 秒刷新一次。没有执行按钮、没有写操作、没有模拟数据。
      </p>
      <div class="readonly-overview__meta">
        <span>最后刷新：{{ lastUpdated ? formatTime(lastUpdated) : '尚未刷新' }}</span>
        <span>数据口径：执行成功率，不是故障恢复成功率</span>
      </div>
      <el-alert v-if="apiError" :title="apiError" type="warning" show-icon :closable="false" />
    </section>

    <section class="readonly-overview__metrics">
      <el-card shadow="never">
        <div class="metric__label">主机资产</div>
        <div class="metric__value">{{ hostCount }}</div>
        <div class="metric__hint">来自 GET /assets</div>
      </el-card>
      <el-card shadow="never">
        <div class="metric__label">今日执行</div>
        <div class="metric__value">{{ stats?.today_count ?? '—' }}</div>
        <div class="metric__hint">来自 GET /executions/stats</div>
      </el-card>
      <el-card shadow="never">
        <div class="metric__label">执行成功率</div>
        <div class="metric__value">{{ stats ? `${stats.success_rate}%` : '—' }}</div>
        <div class="metric__hint">不是故障恢复成功率</div>
      </el-card>
      <el-card shadow="never">
        <div class="metric__label">执行总数</div>
        <div class="metric__value">{{ stats?.total ?? '—' }}</div>
        <div class="metric__hint">来自真实审计记录</div>
      </el-card>
    </section>

    <section class="readonly-overview__grid">
      <el-card shadow="never">
        <template #header>后端依赖状态</template>
        <div v-if="health" class="kv-list">
          <div><span>服务状态</span><strong>{{ statusText(health.status) }}</strong></div>
          <div><span>数据库</span><strong>{{ statusText(health.postgres) }}</strong></div>
          <div><span>Redis</span><strong>{{ statusText(health.redis) }}</strong></div>
        </div>
        <el-empty v-else description="健康接口未返回数据" />

        <div class="section-divider"></div>
        <div class="sub-title">主机状态分布</div>
        <div v-if="hostCount" class="kv-list">
          <div v-for="(count, status) in statusCounts" :key="status">
            <span>{{ statusText(status) }}</span>
            <strong>{{ count }}</strong>
          </div>
        </div>
        <el-empty v-else description="暂无主机资产数据" />
      </el-card>

      <el-card shadow="never">
        <template #header>最近执行记录</template>
        <el-table :data="executions" size="small" v-loading="loading" empty-text="暂无执行记录">
          <el-table-column prop="task_id" label="任务" min-width="140" show-overflow-tooltip />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">{{ statusText(row.status) }}</template>
          </el-table-column>
          <el-table-column label="来源" width="110">
            <template #default="{ row }">{{ statusText(row.trigger_source) }}</template>
          </el-table-column>
          <el-table-column label="时间" min-width="160">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
        </el-table>
      </el-card>
    </section>

    <section class="readonly-overview__boundary">
      <strong>当前边界</strong>
      <span>
        只读取真实后端数据；不进入旧控制台，不展示 Workload/Incident 假数据，不提供 SSH 命令下发或任何写操作入口。
      </span>
    </section>
  </div>
</template>

<style scoped>
.readonly-overview {
  max-width: 1180px;
  margin: 0 auto;
  padding: 32px 28px 56px;
}

.readonly-overview__hero {
  padding: 28px;
  border: 1px solid var(--op-line);
  border-radius: 4px;
  background: var(--op-panel);
}

.readonly-overview__eyebrow {
  color: var(--op-accent);
  font-family: var(--op-font-mono);
  font-size: 11px;
  letter-spacing: 0.08em;
  margin-bottom: 12px;
}

.readonly-overview__title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.readonly-overview h1 {
  margin: 0;
  color: var(--op-text-strong);
  font-size: 26px;
  font-weight: 600;
}

.readonly-overview__hero p {
  margin: 14px 0 0;
  color: var(--op-text);
  font-size: 14px;
  line-height: 1.7;
}

.readonly-overview__meta {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
  margin-top: 14px;
  color: var(--op-text-muted);
  font-size: 12px;
}

.readonly-overview__hero :deep(.el-alert) {
  margin-top: 16px;
}

.readonly-overview__metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-top: 18px;
}

.readonly-overview__metrics :deep(.el-card__body) {
  padding: 18px;
}

.metric__label,
.metric__hint {
  color: var(--op-text-muted);
  font-size: 12px;
}

.metric__value {
  margin: 10px 0 8px;
  color: var(--op-text-strong);
  font-size: 28px;
  font-family: var(--op-font-mono);
}

.readonly-overview__grid {
  display: grid;
  grid-template-columns: minmax(280px, 0.8fr) minmax(420px, 1.2fr);
  gap: 16px;
  margin-top: 18px;
}

.readonly-overview__grid :deep(.el-card__header) {
  color: var(--op-text-strong);
  font-size: 14px;
}

.kv-list {
  display: grid;
  gap: 10px;
}

.kv-list > div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: var(--op-text-muted);
  font-size: 13px;
}

.kv-list strong {
  color: var(--op-text-strong);
  font-weight: 500;
}

.section-divider {
  height: 1px;
  background: var(--op-line);
  margin: 18px 0;
}

.sub-title {
  color: var(--op-text-strong);
  font-size: 13px;
  margin-bottom: 12px;
}

.readonly-overview__boundary {
  margin-top: 18px;
  padding: 18px 20px;
  border-left: 3px solid var(--op-info);
  background: var(--op-panel);
  color: var(--op-text-muted);
  font-size: 13px;
  line-height: 1.75;
}

.readonly-overview__boundary strong {
  color: var(--op-text-strong);
  margin-right: 8px;
}

@media (max-width: 960px) {
  .readonly-overview {
    padding: 24px 16px 40px;
  }

  .readonly-overview__metrics,
  .readonly-overview__grid {
    grid-template-columns: 1fr;
  }
}
</style>
