<script setup>
import { computed, ref } from 'vue'
import { Search, Refresh, Connection, CaretRight, Loading } from '@element-plus/icons-vue'
import {
  assetStatusMeta,
  formatDateTime,
  formatLatency,
  taskStateMeta,
} from '../utils/format'

const props = defineProps({
  assets: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  pingJobs: { type: Object, default: () => ({}) },
  selectedAssetId: { type: Number, default: null },
})

const emit = defineEmits(['refresh', 'add', 'ping', 'select-terminal'])

const keyword = ref('')

const filtered = computed(() => {
  const key = keyword.value.trim().toLowerCase()
  if (!key) return props.assets
  return props.assets.filter((asset) =>
    [asset.name, asset.ip_address, asset.os_type, asset.ssh_user].some((field) =>
      String(field || '').toLowerCase().includes(key),
    ),
  )
})

const jobOf = (id) => props.pingJobs?.[id]
const isPinging = (id) => jobOf(id)?.state === 'running'
const rowClassName = ({ row }) => (row.id === props.selectedAssetId ? 'op-row--selected' : '')

const lastUpdated = computed(() => {
  const times = props.assets.map((a) => a.updated_at).filter(Boolean).sort()
  return times.length ? formatDateTime(times[times.length - 1]) : '—'
})
</script>

<template>
  <section class="op-card">
    <div class="op-card__header">
      <div>
        <div class="op-card__title">
          <el-icon><Connection /></el-icon>
          纳管资产
          <span class="tbl-count op-mono">{{ assets.length }}</span>
        </div>
        <div class="op-card__subtitle">GET /api/v1/assets · POST /api/v1/tasks/ping</div>
      </div>
      <div class="op-card__tools">
        <el-input
          v-model="keyword"
          :prefix-icon="Search"
          placeholder="搜索名称 / IP"
          clearable
          class="tbl-search"
        />
        <el-button :icon="Refresh" :loading="loading" @click="emit('refresh')">刷新</el-button>
        <el-button type="primary" :icon="CaretRight" @click="emit('add')">新增</el-button>
      </div>
    </div>

    <div class="op-card__body">
      <el-alert v-if="error" type="error" show-icon :closable="false" class="tbl-alert">
        <template #title>资产列表加载失败</template>
        <div class="tbl-alert__body">
          <span>{{ error }}</span>
          <el-button link type="primary" @click="emit('refresh')">重新加载</el-button>
        </div>
      </el-alert>

      <el-table
        :data="filtered"
        v-loading="loading"
        element-loading-text="正在拉取资产列表…"
        :row-class-name="rowClassName"
        row-key="id"
        style="width: 100%"
      >
        <el-table-column label="主机 / HOST" min-width="195">
          <template #default="{ row }">
            <div class="cell-host">
              <div class="cell-host__name">
                {{ row.name }}
                <span class="cell-host__id op-mono">#{{ row.id }}</span>
              </div>
              <div class="cell-host__meta op-mono">
                {{ row.ip_address }}
                <span class="cell-host__os">{{ row.os_type }}</span>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="状态" width="106">
          <template #default="{ row }">
            <div class="cell-status">
              <span
                class="op-status-dot"
                :class="`op-status-dot--${assetStatusMeta(row.status).tone}`"
              />
              <span>{{ assetStatusMeta(row.status).label }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="SSH 连接" min-width="180">
          <template #default="{ row }">
            <div
              class="cell-ssh op-mono"
              :title="`${row.ssh_user}@${row.ip_address}:${row.ssh_port}`"
            >
              <span class="cell-ssh__user">{{ row.ssh_user }}@</span>{{ row.ip_address
              }}<span class="cell-ssh__port">:{{ row.ssh_port }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="探活结果" width="142">
          <template #default="{ row }">
            <div v-if="isPinging(row.id)" class="cell-probing">
              <el-icon class="is-loading"><Loading /></el-icon>
              <span>{{ taskStateMeta(jobOf(row.id).status).label }} · {{ jobOf(row.id).attempts }}次</span>
            </div>
            <span
              v-else-if="jobOf(row.id)?.state === 'error'"
              class="cell-error"
              :title="jobOf(row.id).message"
            >
              探测失败
            </span>
            <span
              v-else
              :class="jobOf(row.id)?.latency != null ? 'cell-latency' : 'op-faint'"
            >
              {{ formatLatency(jobOf(row.id)?.latency) }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="运维操作" width="205">
          <template #default="{ row }">
            <div class="cell-actions">
              <el-button
                size="small"
                :icon="Connection"
                :loading="isPinging(row.id)"
                @click="emit('ping', row)"
              >
                {{ isPinging(row.id) ? '探测中' : '异步探活' }}
              </el-button>
              <el-button size="small" :icon="CaretRight" @click="emit('select-terminal', row)">
                终端
              </el-button>
            </div>
          </template>
        </el-table-column>

        <template #empty>
          <el-empty description="暂无纳管主机" :image-size="72">
            <el-button type="primary" size="small" @click="emit('add')">录入第一台主机</el-button>
          </el-empty>
        </template>
      </el-table>

      <div class="tbl-foot">
        <span>共 <b>{{ assets.length }}</b> 台资产，当前显示 {{ filtered.length }} 台</span>
        <span class="op-faint">最近更新 {{ lastUpdated }}</span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.tbl-count {
  padding: 2px 7px;
  border-radius: 5px;
  background: rgba(34, 197, 94, 0.1);
  border: 1px solid rgba(34, 197, 94, 0.2);
  color: var(--op-accent-bright);
  font-size: 10px;
  font-weight: 600;
}

.tbl-search {
  width: 178px;
}

.tbl-alert {
  margin-bottom: 14px;
}

.tbl-alert__body {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--op-text-2);
}

.cell-host__name {
  font-weight: 600;
  color: var(--op-text);
  font-size: 12.5px;
}

.cell-host__id {
  margin-left: 4px;
  color: var(--op-faint);
  font-size: 10px;
  font-weight: 400;
}

.cell-host__meta {
  margin-top: 4px;
  color: var(--op-muted);
  font-size: 10.5px;
}

.cell-host__os {
  margin-left: 6px;
  padding: 1px 5px;
  border: 1px solid var(--op-border-soft);
  border-radius: 4px;
  color: var(--op-faint);
  font-size: 9px;
}

.cell-status {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--op-text-2);
}

.cell-ssh {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 10.5px;
  color: var(--op-text-2);
}

.cell-ssh__user {
  color: var(--op-accent-bright);
}

.cell-ssh__port {
  color: var(--op-info);
}

.cell-probing {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--op-info);
  font-size: 10.5px;
}

.cell-error {
  color: var(--op-danger);
  font-size: 11px;
  cursor: help;
}

.cell-latency {
  color: #86efac;
  font: 600 11.5px var(--op-mono);
}

.cell-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.tbl-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 14px;
  padding-top: 13px;
  border-top: 1px solid var(--op-border-soft);
  font-size: 11px;
  color: var(--op-muted);
}

.tbl-foot b {
  color: var(--op-text);
  font-family: var(--op-mono);
}

@media (max-width: 760px) {
  .tbl-search {
    width: 100%;
  }

  .op-card__tools {
    width: 100%;
  }
}
</style>
