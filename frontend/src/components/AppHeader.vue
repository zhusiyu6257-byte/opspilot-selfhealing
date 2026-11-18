<script setup>
import { computed } from 'vue'
import { Monitor, Refresh, Plus } from '@element-plus/icons-vue'

const props = defineProps({
  loading: { type: Boolean, default: false },
  backend: { type: String, default: 'checking' },
  assetCount: { type: Number, default: 0 },
  activeTaskCount: { type: Number, default: 0 },
})

const emit = defineEmits(['refresh', 'add'])

const BACKEND_META = {
  online: { label: '服务已连接', hint: 'FastAPI · PostgreSQL · Redis', tone: 'success' },
  degraded: { label: '部分依赖异常', hint: '健康检查未通过，请查看后端日志', tone: 'warn' },
  offline: { label: '后端不可达', hint: '请确认 8000 端口已启动', tone: 'danger' },
  checking: { label: '正在检测…', hint: '正在连接后端服务', tone: 'neutral' },
}

const meta = computed(() => BACKEND_META[props.backend] || BACKEND_META.checking)
</script>

<template>
  <header class="hdr">
    <div class="op-container hdr__inner">
      <div class="hdr__brand">
        <div class="hdr__mark" aria-hidden="true">
          <el-icon :size="21"><Monitor /></el-icon>
        </div>
        <div class="hdr__brand-text">
          <div class="hdr__name">
            OpsPilot <span class="hdr__slash">/</span>
            <span class="hdr__sub">运维控制台</span>
          </div>
          <div class="hdr__tagline">ASSET INVENTORY · ASYNC PROBE · REMOTE RUNBOOK</div>
        </div>
      </div>

      <div class="hdr__right">
        <div class="hdr__health" :title="meta.hint">
          <span
            class="op-status-dot"
            :class="[`op-status-dot--${meta.tone}`, props.backend === 'checking' && 'op-status-dot--pulse']"
          />
          <div class="hdr__health-text">
            <strong>{{ meta.label }}</strong>
            <small>{{ meta.hint }}</small>
          </div>
        </div>

        <span class="hdr__env op-mono">DEV · V1</span>
        <span class="hdr__count op-mono">{{ assetCount }} ASSETS</span>

        <el-button :icon="Refresh" :loading="loading" @click="emit('refresh')">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="emit('add')">录入主机</el-button>
      </div>
    </div>
  </header>
</template>

<style scoped>
.hdr {
  position: sticky;
  top: 0;
  z-index: 20;
  border-bottom: 1px solid var(--op-border-soft);
  background: rgba(2, 6, 23, 0.76);
  backdrop-filter: blur(16px) saturate(160%);
}

.hdr__inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  min-height: 72px;
  padding: 12px 0;
}

.hdr__brand {
  display: flex;
  align-items: center;
  gap: 13px;
  min-width: 0;
}

.hdr__mark {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  flex: none;
  border: 1px solid rgba(34, 197, 94, 0.28);
  border-radius: 11px;
  background: linear-gradient(145deg, rgba(34, 197, 94, 0.16), rgba(34, 197, 94, 0.03));
  color: var(--op-accent-bright);
  box-shadow: 0 0 22px rgba(34, 197, 94, 0.14);
}

.hdr__name {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: -0.01em;
  white-space: nowrap;
}

.hdr__slash {
  margin: 0 3px;
  color: var(--op-faint);
  font-weight: 400;
}

.hdr__sub {
  color: var(--op-text-2);
  font-size: 13px;
  font-weight: 500;
}

.hdr__tagline {
  margin-top: 4px;
  color: var(--op-faint);
  font: 500 9px/1 var(--op-mono);
  letter-spacing: 0.14em;
  white-space: nowrap;
}

.hdr__right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.hdr__health {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 12px;
  border: 1px solid var(--op-border-soft);
  border-radius: 9px;
  background: rgba(148, 163, 184, 0.04);
  cursor: default;
}

.hdr__health-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.hdr__health-text strong {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--op-text-2);
}

.hdr__health-text small {
  font-size: 9.5px;
  color: var(--op-faint);
}

.hdr__env,
.hdr__count {
  padding: 5px 8px;
  border: 1px solid var(--op-border-soft);
  border-radius: 6px;
  font-size: 9.5px;
  letter-spacing: 0.08em;
  color: var(--op-muted);
  white-space: nowrap;
}

.hdr__env {
  color: var(--op-accent-bright);
  border-color: rgba(34, 197, 94, 0.24);
  background: rgba(34, 197, 94, 0.07);
}

@media (max-width: 900px) {
  .hdr__health-text small,
  .hdr__tagline,
  .hdr__count {
    display: none;
  }
}

@media (max-width: 620px) {
  .hdr__inner {
    min-height: 0;
    flex-direction: column;
    align-items: flex-start;
  }

  .hdr__right {
    width: 100%;
    justify-content: flex-start;
  }
}
</style>
