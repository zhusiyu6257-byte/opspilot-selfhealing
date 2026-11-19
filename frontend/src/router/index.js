import { createRouter, createWebHashHistory, createWebHistory } from 'vue-router'
import PlaceholderView from '@/views/PlaceholderView.vue'
import StaticPreviewView from '@/views/StaticPreviewView.vue'
import ReadonlyOverviewView from '@/views/ReadonlyOverviewView.vue'
import { allNavItems } from '@/config/nav.js'
import { READONLY_LIVE, STATIC_READONLY } from '@/config/runtime.js'

const plannedRoutes = allNavItems
  .filter((item) => item.availability === 'planned')
  .filter((item) => !(READONLY_LIVE && item.id === 'overview'))
  .map((item) => ({
    path: item.path,
    name: item.id,
    component: PlaceholderView,
    meta: { title: item.name, note: item.note },
  }))

const staticRoutes = [
  {
    path: '/preview',
    name: 'static-preview',
    component: StaticPreviewView,
    meta: { title: '静态只读展示' },
  },
  ...allNavItems
    .filter((item) => item.availability === 'planned')
    .map((item) => ({
      path: item.path,
      name: item.id,
      component: PlaceholderView,
      meta: { title: item.name, note: item.note },
    })),
]

const readonlyLiveRoutes = [
  {
    path: '/overview',
    name: 'readonly-overview',
    component: ReadonlyOverviewView,
    meta: { title: '只读实时概览', readonlyLive: true },
  },
  ...plannedRoutes,
]

const fullRoutes = [
  {
    path: '/legacy',
    name: 'legacy',
    component: () => import('@/views/LegacyView.vue'),
    meta: { title: '旧版控制台' },
  },
  ...plannedRoutes,
]

const routes = [
  {
    path: '/',
    redirect: STATIC_READONLY ? '/preview' : READONLY_LIVE ? '/overview' : '/legacy',
  },
  ...(STATIC_READONLY ? staticRoutes : READONLY_LIVE ? readonlyLiveRoutes : fullRoutes),
]

const router = createRouter({
  history: STATIC_READONLY || READONLY_LIVE ? createWebHashHistory() : createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  },
})

export default router
