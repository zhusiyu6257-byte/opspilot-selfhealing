import { defineStore } from 'pinia'
import { ref } from 'vue'

// 只管理确实需要跨组件共享的状态：Sidebar 折叠态。
// AppShell 需要它算主区宽度、Sidebar 需要它渲染折叠样式、
// Topbar 的折叠按钮也要改它——一处状态、三处读取，所以用 Pinia。
// 其它业务状态仍留在各自组件内，不往这里堆。
const STORAGE_KEY = 'opspilot:sidebar-collapsed'

function readInitial() {
  try {
    return localStorage.getItem(STORAGE_KEY) === '1'
  } catch {
    return false // 隐私模式等读不到存储时默认展开
  }
}

export const useLayoutStore = defineStore('layout', () => {
  // 默认展开；刷新后沿用上次选择，初始化时同步读取避免首帧抖动
  const collapsed = ref(readInitial())

  function toggle() {
    collapsed.value = !collapsed.value
    try {
      localStorage.setItem(STORAGE_KEY, collapsed.value ? '1' : '0')
    } catch {
      // 存储不可用时只影响持久化，不影响本次会话
    }
  }

  return { collapsed, toggle }
})
