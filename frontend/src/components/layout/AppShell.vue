<script setup>
// 布局骨架：持有折叠状态，驱动 Sidebar 与主区宽度。
// 职责边界：只管布局，不管业务数据、不管路由内容。
import { computed } from 'vue'
import AppSidebar from './AppSidebar.vue'
import AppTopbar from './AppTopbar.vue'
import { useLayoutStore } from '@/stores/layout.js'

const layout = useLayoutStore()
const mainClass = computed(() => ({
  'op-main': true,
  'op-main--collapsed': layout.collapsed,
}))
</script>

<template>
  <div class="op-shell">
    <AppSidebar />
    <div :class="mainClass">
      <AppTopbar />
      <main class="op-content">
        <slot />
      </main>
    </div>
  </div>
</template>

<style scoped>
.op-shell {
  min-height: 100vh;
  background: var(--op-bg);
  color: var(--op-text);
}
</style>
