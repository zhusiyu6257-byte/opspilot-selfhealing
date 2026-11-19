import { createRouter, createWebHashHistory, createWebHistory } from 'vue-router'
import AppRoot from '@/AppRoot.vue'
import PlaceholderView from '@/views/PlaceholderView.vue'
import StaticPreviewView from '@/views/StaticPreviewView.vue'
import { allNavItems } from '@/config/nav.js'
import { STATIC_READONLY } from '@/config/runtime.js'

const plannedRoutes = allNavItems
  .filter((item) => item.availability === 'planned')
  .map((item) => ({
    path: item.path.replace(/^\//, ''),
    name: item.id,
    component: PlaceholderView,
    meta: { title: item.name, note: item.note },
  }))

const previewRoute = {
  path: 'preview',
  name: 'static-preview',
  component: StaticPreviewView,
  meta: { title: '静态只读展示' },
}

const legacyRoute = {
  path: 'legacy',
  name: 'legacy',
  component: () => import('@/views/LegacyView.vue'),
  meta: { title: '旧版控制台' },
}

const shellRoutes = STATIC_READONLY
  ? [previewRoute, ...plannedRoutes]
  : [legacyRoute, ...plannedRoutes]

const routes = [
  {
    path: '/',
    redirect: STATIC_READONLY ? '/preview' : '/legacy',
  },
  {
    path: '/',
    component: AppRoot,
    children: shellRoutes,
  },
]

const router = createRouter({
  history: STATIC_READONLY ? createWebHashHistory() : createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  },
})

export default router
