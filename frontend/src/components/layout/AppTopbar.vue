<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Expand, Fold } from '@element-plus/icons-vue'
import { useLayoutStore } from '@/stores/layout.js'
import { allNavItems, navGroups } from '@/config/nav.js'
import { READONLY_LIVE, STATIC_READONLY } from '@/config/runtime.js'

const route = useRoute()
const router = useRouter()
const layout = useLayoutStore()

const pageTitle = computed(() => route.meta.title || 'OpsPilot')
const currentItem = computed(() =>
  allNavItems.find((item) => {
    if (route.path === item.path) return true
    return item.path !== '/' && route.path.startsWith(`${item.path}/`)
  }),
)
const groupTitle = computed(() => {
  if (STATIC_READONLY && route.path === '/preview') return '静态展示'
  if (route.path === '/legacy') return 'V1 兼容控制台'
  const group = navGroups.find((item) =>
    item.items.some(
      (navItem) => route.path === navItem.path || route.path.startsWith(`${navItem.path}/`),
    ),
  )
  return group?.title || ''
})
const isPlanned = computed(
  () => !route.meta.readonlyLive && currentItem.value?.availability === 'planned',
)
const toggleIcon = computed(() => (layout.collapsed ? Expand : Fold))
const toggleLabel = computed(() => (layout.collapsed ? '展开侧边栏' : '收起侧边栏'))
const stageLabel = computed(() => {
  if (STATIC_READONLY) return 'D0 · 静态只读'
  if (READONLY_LIVE) return 'D1 · 只读实时'
  return 'S1 · 布局骨架'
})
const showLegacyButton = computed(
  () => !STATIC_READONLY && !READONLY_LIVE && route.path !== '/legacy',
)
</script>

<template>
  <header class="op-topbar">
    <div class="op-topbar__left">
      <button
        class="op-icon-button"
        type="button"
        :aria-label="toggleLabel"
        :title="toggleLabel"
        @click="layout.toggle"
      >
        <el-icon :size="18"><component :is="toggleIcon" /></el-icon>
      </button>

      <el-breadcrumb separator="/" class="op-breadcrumb">
        <el-breadcrumb-item v-if="groupTitle">{{ groupTitle }}</el-breadcrumb-item>
        <el-breadcrumb-item>{{ pageTitle }}</el-breadcrumb-item>
      </el-breadcrumb>
    </div>

    <div class="op-topbar__right">
      <span class="op-topbar__stage">{{ stageLabel }}</span>
      <el-tag v-if="isPlanned" size="small" type="warning" effect="dark" round>规划中</el-tag>
      <el-tooltip v-if="showLegacyButton" content="返回 V1 完整控制台" placement="bottom">
        <el-button size="small" text bg @click="router.push('/legacy')">
          <el-icon><ArrowLeft /></el-icon>
          <span>旧控制台</span>
        </el-button>
      </el-tooltip>
    </div>
  </header>
</template>

<style scoped>
.op-topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  height: var(--op-topbar-h);
  flex: 0 0 var(--op-topbar-h);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 18px;
  background: color-mix(in srgb, var(--op-panel) 92%, transparent);
  border-bottom: 1px solid var(--op-line);
  backdrop-filter: blur(8px);
}

.op-topbar__left,
.op-topbar__right {
  display: flex;
  align-items: center;
  min-width: 0;
}

.op-topbar__left {
  gap: 12px;
  flex: 1 1 auto;
  overflow: hidden;
}

.op-topbar__right {
  gap: 10px;
  flex: 0 0 auto;
}

.op-icon-button {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  padding: 0;
  color: var(--op-text);
  background: var(--op-panel-2);
  border: 1px solid var(--op-line-strong);
  border-radius: 3px;
  cursor: pointer;
  transition: color var(--op-transition) ease, border-color var(--op-transition) ease;
}

.op-icon-button:hover {
  color: var(--op-accent);
  border-color: var(--op-accent);
}

.op-breadcrumb {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  font-size: 12px;
  line-height: 32px;
  white-space: nowrap;
}

.op-breadcrumb :deep(.el-breadcrumb) {
  flex-wrap: nowrap;
  white-space: nowrap;
}

.op-breadcrumb :deep(.el-breadcrumb__item) {
  flex-shrink: 0;
}

.op-breadcrumb :deep(.el-breadcrumb__inner) {
  display: block;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.op-topbar__stage {
  color: var(--op-text-muted);
  font-family: var(--op-font-mono);
  font-size: 11px;
  white-space: nowrap;
}

@media (max-width: 760px) {
  .op-topbar {
    padding: 0 12px;
  }

  .op-breadcrumb :deep(.el-breadcrumb__item:not(:last-child)),
  .op-topbar__stage {
    display: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .op-icon-button {
    transition: none;
  }
}
</style>
