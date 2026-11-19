<script setup>
// S1 根组件：只负责布局壳 + 路由出口。
// 旧 App.vue 作为 /legacy 的子路由渲染，功能完全保留。
import AppShell from '@/components/layout/AppShell.vue'
</script>

<template>
  <AppShell>
    <router-view />
  </AppShell>
</template>
