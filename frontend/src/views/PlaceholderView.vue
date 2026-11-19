<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Box } from '@element-plus/icons-vue'
import { READONLY_LIVE, STATIC_READONLY } from '@/config/runtime.js'

const route = useRoute()
const backPath = computed(() => {
  if (STATIC_READONLY) return '/preview'
  if (READONLY_LIVE) return '/overview'
  return '/legacy'
})
const backLabel = computed(() => {
  if (STATIC_READONLY) return '返回静态展示'
  if (READONLY_LIVE) return '返回只读概览'
  return '返回旧版控制台'
})
</script>

<template>
  <div class="placeholder">
    <div class="placeholder__box">
      <div class="placeholder__icon"><el-icon :size="40"><Box /></el-icon></div>
      <h1 class="placeholder__title">{{ route.meta.title }}</h1>
      <p class="placeholder__note">{{ route.meta.note || '该模块规划中，尚未接入真实数据。' }}</p>
      <div class="placeholder__tag">尚未实现 · 无模拟数据</div>
      <el-button type="primary" plain @click="$router.push(backPath)">
        {{ backLabel }}
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.placeholder {
  display: grid;
  place-items: center;
  min-height: 60vh;
  padding: 24px;
}
.placeholder__box {
  max-width: 520px;
  text-align: center;
}
.placeholder__icon {
  color: var(--op-accent, #63e6a6);
  margin-bottom: 16px;
}
.placeholder__title {
  font-size: 22px;
  margin: 0 0 12px;
  color: var(--op-text-strong, #e8f4ee);
}
.placeholder__note {
  font-size: 14px;
  line-height: 1.7;
  color: var(--op-text-muted, #8fa3a0);
  margin: 0 0 20px;
}
.placeholder__tag {
  display: inline-block;
  font-size: 12px;
  padding: 4px 12px;
  border: 1px solid var(--op-line, #1c2b2b);
  border-radius: 3px;
  color: var(--op-text-muted, #8fa3a0);
  margin-bottom: 24px;
}
</style>
