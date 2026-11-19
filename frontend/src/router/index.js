import { createRouter, createWebHashHistory, createWebHistory } from 'vue-router'
import PlaceholderView from '@/views/PlaceholderView.vue'
import StaticPreviewView from '@/views/StaticPreviewView.vue'
import { allNavItems } from '@/config/nav.js'
import { STATIC_READONLY } from '@/config/runtime.js'

const plannedRoutes = allNavItems
  .filter((item) => item.availability === 'planned')
  .map((item) => ({
    path: item.path,
    name: item.id,
    component: PlaceholderView,
    meta: { title: item.name, note: item.note },
  }))

const routes = [
  {
    path: '/',
    redirect: STATIC_READONLY ? '/preview' : '/legacy',
  },
  {
    path: '/preview',
    name: 'static-preview',
    component: StaticPreviewView,
    meta: { title: '静态只读展示' },
  },
  {
    path: '/legacy',
    name: 'legacy',
    component: () => import('@/views/LegacyView.vue'),
    meta: { title: '旧版控制台' },
  },
  ...plannedRoutes,
]

const router = createRouter({
  history: STATIC_READONLY ? createWebHashHistory() : createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  },
})

export default router
