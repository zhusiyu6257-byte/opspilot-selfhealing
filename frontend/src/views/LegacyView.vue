<script setup>
// 包装视图：把 V1 的完整 App.vue 原样挂到路由上。
// 不改动 App.vue 一行代码，保证主机 CRUD/探活/终端/审计/弹窗/抽屉/Prometheus 全部保留。
import LegacyApp from '@/App.vue'
</script>

<template>
  <LegacyApp />
</template>
